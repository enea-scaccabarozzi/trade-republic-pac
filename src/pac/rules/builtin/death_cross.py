"""Death cross rule — standalone MA crossover detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import compute_death_cross

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class DeathCrossParams(BaseModel):
    """Parameters for the death cross MA rule."""

    equity_asset_id: str = "stocks"
    lookback_days: int = Field(default=400, ge=200)
    short_window: int = Field(default=50, ge=10)
    long_window: int = Field(default=200, ge=50)


class DeathCrossRule(SignalRule[DeathCrossParams]):
    """Fires signals for SMA death cross events and bearish regimes."""

    @property
    def name(self) -> str:
        return "death_cross"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: DeathCrossParams,
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
            result = compute_death_cross(
                series,
                params.short_window,
                params.long_window,
            )
        except ValueError:
            return []

        meta = {
            "indicator": "death_cross",
            "sma_short": result.sma_short,
            "sma_long": result.sma_long,
            "bearish_regime": result.bearish_regime,
            "cross_event": result.cross_event,
        }

        if result.cross_event:
            return [
                Signal(
                    name=self.name,
                    severity=SignalSeverity.CRITICAL,
                    message=(
                        f"Death cross: {params.short_window}-day SMA "
                        f"({result.sma_short:.2f}) crossed below "
                        f"{params.long_window}-day SMA "
                        f"({result.sma_long:.2f})"
                    ),
                    triggered_at=report.timestamp,
                    metadata=meta,
                )
            ]

        if result.bearish_regime:
            return [
                Signal(
                    name=self.name,
                    severity=SignalSeverity.WARNING,
                    message=(
                        f"Bearish regime: {params.short_window}-day SMA "
                        f"({result.sma_short:.2f}) below "
                        f"{params.long_window}-day SMA "
                        f"({result.sma_long:.2f})"
                    ),
                    triggered_at=report.timestamp,
                    metadata=meta,
                )
            ]

        return []

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="sma_short",
                display_name="SMA Short",
                group="Momentum",
                kind=IndicatorKind.RATIO,
                companion_suffixes=["sma_long"],
            ),
            IndicatorSpec(
                key_suffix="sma_long",
                display_name="SMA Long",
                group="Momentum",
                kind=IndicatorKind.RATIO,
                companion_suffixes=["sma_short"],
            ),
            IndicatorSpec(
                key_suffix="bearish_regime",
                display_name="Bearish Regime",
                group="Momentum",
                kind=IndicatorKind.BOOLEAN,
            ),
            IndicatorSpec(
                key_suffix="cross_event",
                display_name="Death Cross Event",
                group="Momentum",
                kind=IndicatorKind.EVENT,
            ),
        ]

    def compute_indicators(
        self,
        params: DeathCrossParams,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        if market_ctx is None:
            return None
        try:
            series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
            result = compute_death_cross(
                series,
                params.short_window,
                params.long_window,
            )
        except (KeyError, ValueError):
            return None
        return IndicatorValues(
            values={
                "sma_short": result.sma_short,
                "sma_long": result.sma_long,
                "bearish_regime": result.bearish_regime,
                "cross_event": result.cross_event,
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
            "death_cross": signals[0].metadata,
        }
