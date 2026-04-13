"""Volatility regime rule — detects vol regime transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import compute_volatility_regime

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class VolatilityRegimeParams(BaseModel):
    """Parameters for the volatility regime rule."""

    equity_asset_id: str = "stocks"
    lookback_days: int = Field(default=120, ge=30)
    short_window: int = Field(default=20, ge=5)
    long_window: int = Field(default=60, ge=20)

    warning_ratio: float = Field(default=1.80, ge=1.0)
    critical_ratio: float = Field(default=2.50, ge=1.0)


class VolatilityRegimeRule(SignalRule[VolatilityRegimeParams]):
    """Fires signals when short-term vol exceeds long-term vol."""

    @property
    def name(self) -> str:
        return "volatility_regime"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: VolatilityRegimeParams,
        market_ctx: MarketContext | None = None,
    ) -> list[Signal]:
        if market_ctx is None:
            return []

        try:
            series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
        except KeyError:
            return []

        try:
            result = compute_volatility_regime(
                series,
                params.short_window,
                params.long_window,
            )
        except ValueError:
            return []

        if result.vol_ratio >= params.critical_ratio:
            severity = SignalSeverity.CRITICAL
        elif result.vol_ratio >= params.warning_ratio:
            severity = SignalSeverity.WARNING
        else:
            return []

        return [
            Signal(
                name=self.name,
                severity=severity,
                message=(
                    f"Volatility regime shift: "
                    f"{params.short_window}d/{params.long_window}d "
                    f"ratio {result.vol_ratio:.2f}x "
                    f"(short={result.short_vol:.1f}%, "
                    f"long={result.long_vol:.1f}%)"
                ),
                triggered_at=report.timestamp,
                metadata={
                    "indicator": "volatility_regime",
                    "short_vol_ann": result.short_vol,
                    "long_vol_ann": result.long_vol,
                    "vol_ratio": result.vol_ratio,
                },
            )
        ]

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="vol_ratio",
                display_name="Volatility Ratio",
                group="Volatility",
                kind=IndicatorKind.CONTINUOUS,
                unit="ratio",
                thresholds=[
                    IndicatorThreshold(
                        value=1.80,
                        label="Warning",
                        color="amber",
                    ),
                    IndicatorThreshold(
                        value=2.50,
                        label="Critical",
                        color="red",
                    ),
                ],
            ),
            IndicatorSpec(
                key_suffix="short_vol",
                display_name="Short-term Volatility",
                group="Volatility",
                kind=IndicatorKind.CONTINUOUS,
                unit="%",
            ),
            IndicatorSpec(
                key_suffix="long_vol",
                display_name="Long-term Volatility",
                group="Volatility",
                kind=IndicatorKind.CONTINUOUS,
                unit="%",
            ),
        ]

    def compute_indicators(
        self,
        params: VolatilityRegimeParams,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        if market_ctx is None:
            return None
        try:
            series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
            result = compute_volatility_regime(
                series,
                params.short_window,
                params.long_window,
            )
        except (KeyError, ValueError):
            return None
        return IndicatorValues(
            values={
                "vol_ratio": result.vol_ratio,
                "short_vol": result.short_vol,
                "long_vol": result.long_vol,
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
            "volatility": signals[0].metadata,
        }
