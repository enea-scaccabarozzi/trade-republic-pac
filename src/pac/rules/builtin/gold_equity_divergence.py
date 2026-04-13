"""Gold-equity divergence rule — detects flight-to-safety flows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import compute_divergence

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class GoldEquityDivergenceParams(BaseModel):
    """Parameters for the gold-equity divergence rule."""

    equity_asset_id: str = "stocks"
    gold_asset_id: str = "gold"
    lookback_days: int = Field(default=80, ge=20)
    lookback_bars: int = Field(default=40, ge=10)

    warning_pct: float = Field(default=10.0, ge=0)
    critical_pct: float = Field(default=20.0, ge=0)


class GoldEquityDivergenceRule(SignalRule[GoldEquityDivergenceParams]):
    """Fires signals when gold and equity returns diverge significantly."""

    @property
    def name(self) -> str:
        return "gold_equity_divergence"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: GoldEquityDivergenceParams,
        market_ctx: MarketContext | None = None,
    ) -> list[Signal]:
        if market_ctx is None:
            return []

        try:
            gold_series = market_ctx.get_asset_prices(
                params.gold_asset_id,
                params.lookback_days,
            )
            equity_series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
        except KeyError:
            return []

        try:
            result = compute_divergence(
                gold_series,
                equity_series,
                params.lookback_bars,
            )
        except ValueError:
            return []

        divergence_pct = result.divergence * 100

        if divergence_pct >= params.critical_pct:
            severity = SignalSeverity.CRITICAL
        elif divergence_pct >= params.warning_pct:
            severity = SignalSeverity.WARNING
        else:
            return []

        return [
            Signal(
                name=self.name,
                severity=severity,
                message=(
                    f"Gold-equity divergence {divergence_pct:.1f}%: "
                    f"gold {result.gold_return * 100:+.1f}%, "
                    f"equity {result.equity_return * 100:+.1f}%"
                ),
                triggered_at=report.timestamp,
                metadata={
                    "indicator": "gold_equity_divergence",
                    "gold_return_pct": result.gold_return * 100,
                    "equity_return_pct": result.equity_return * 100,
                    "divergence_pct": divergence_pct,
                },
            )
        ]

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="divergence_pct",
                display_name="Gold-Equity Divergence",
                group="Divergence",
                kind=IndicatorKind.CONTINUOUS,
                unit="%",
                thresholds=[
                    IndicatorThreshold(
                        value=10.0,
                        label="Warning",
                        color="amber",
                    ),
                    IndicatorThreshold(
                        value=20.0,
                        label="Critical",
                        color="red",
                    ),
                ],
            ),
            IndicatorSpec(
                key_suffix="gold_return_pct",
                display_name="Gold Return",
                group="Divergence",
                kind=IndicatorKind.RATIO,
                unit="%",
                companion_suffixes=["equity_return_pct"],
            ),
            IndicatorSpec(
                key_suffix="equity_return_pct",
                display_name="Equity Return",
                group="Divergence",
                kind=IndicatorKind.RATIO,
                unit="%",
                companion_suffixes=["gold_return_pct"],
            ),
        ]

    def compute_indicators(
        self,
        params: GoldEquityDivergenceParams,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        if market_ctx is None:
            return None
        try:
            gold = market_ctx.get_asset_prices(
                params.gold_asset_id,
                params.lookback_days,
            )
            equity = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
            result = compute_divergence(
                gold,
                equity,
                params.lookback_bars,
            )
        except (KeyError, ValueError):
            return None
        return IndicatorValues(
            values={
                "divergence_pct": result.divergence * 100,
                "gold_return_pct": result.gold_return * 100,
                "equity_return_pct": result.equity_return * 100,
            }
        )

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        return {
            "signal": signals[0],
            "divergence": signals[0].metadata,
        }
