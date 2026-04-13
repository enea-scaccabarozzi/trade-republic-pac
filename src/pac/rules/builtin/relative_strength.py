"""Relative strength rule — gold/equity ratio trend with MA breakout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import compute_relative_strength

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class RelativeStrengthParams(BaseModel):
    """Parameters for the gold/equity relative strength rule."""

    equity_asset_id: str = "stocks"
    gold_asset_id: str = "gold"
    lookback_days: int = Field(default=250, ge=60)
    ma_window: int = Field(default=120, ge=20)

    warning_pct: float = Field(default=5.0, ge=0)
    critical_pct: float = Field(default=10.0, ge=0)


class RelativeStrengthRule(SignalRule[RelativeStrengthParams]):
    """Fires signals when gold/equity RS ratio breaks above MA."""

    @property
    def name(self) -> str:
        return "relative_strength"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: RelativeStrengthParams,
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
            result = compute_relative_strength(
                gold_series,
                equity_series,
                params.ma_window,
            )
        except ValueError:
            return []

        if result.breakout_pct >= params.critical_pct:
            severity = SignalSeverity.CRITICAL
        elif result.breakout_pct >= params.warning_pct:
            severity = SignalSeverity.WARNING
        else:
            return []

        return [
            Signal(
                name=self.name,
                severity=severity,
                message=(
                    f"Gold/equity RS breakout {result.breakout_pct:+.1f}% "
                    f"above {params.ma_window}-day MA "
                    f"(RS={result.rs_current:.4f}, "
                    f"MA={result.rs_ma:.4f})"
                ),
                triggered_at=report.timestamp,
                metadata={
                    "indicator": "relative_strength",
                    "rs_current": result.rs_current,
                    "rs_ma": result.rs_ma,
                    "breakout_pct": result.breakout_pct,
                },
            )
        ]

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="rs_current",
                display_name="RS Ratio",
                group="Relative Strength",
                kind=IndicatorKind.RATIO,
                companion_suffixes=["rs_ma"],
            ),
            IndicatorSpec(
                key_suffix="rs_ma",
                display_name="RS Moving Average",
                group="Relative Strength",
                kind=IndicatorKind.RATIO,
                companion_suffixes=["rs_current"],
            ),
            IndicatorSpec(
                key_suffix="breakout_pct",
                display_name="RS Breakout %",
                group="Relative Strength",
                kind=IndicatorKind.CONTINUOUS,
                unit="%",
                thresholds=[
                    IndicatorThreshold(
                        value=5.0,
                        label="Warning",
                        color="amber",
                    ),
                    IndicatorThreshold(
                        value=10.0,
                        label="Critical",
                        color="red",
                    ),
                ],
            ),
        ]

    def compute_indicators(
        self,
        params: RelativeStrengthParams,
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
            result = compute_relative_strength(
                gold,
                equity,
                params.ma_window,
            )
        except (KeyError, ValueError):
            return None
        return IndicatorValues(
            values={
                "rs_current": result.rs_current,
                "rs_ma": result.rs_ma,
                "breakout_pct": result.breakout_pct,
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
            "relative_strength": signals[0].metadata,
        }
