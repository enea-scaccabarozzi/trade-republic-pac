"""Equity drawdown rule — detects drawdown depth and velocity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import compute_drawdown

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class EquityDrawdownParams(BaseModel):
    """Parameters for the equity drawdown rule."""

    equity_asset_id: str = "stocks"
    lookback_days: int = Field(default=365, ge=60)
    lookback_bars: int = Field(default=252, ge=30)

    depth_warning_pct: float = Field(default=-10.0, le=0)
    depth_critical_pct: float = Field(default=-20.0, le=0)

    velocity_warning: float = Field(default=-0.30, le=0)
    velocity_critical: float = Field(default=-0.60, le=0)


class EquityDrawdownRule(SignalRule[EquityDrawdownParams]):
    """Fires signals for equity drawdown depth and velocity."""

    @property
    def name(self) -> str:
        return "equity_drawdown"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: EquityDrawdownParams,
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
            result = compute_drawdown(series, params.lookback_bars)
        except ValueError:
            return []

        signals: list[Signal] = []
        meta_base = {
            "drawdown_pct": result.drawdown_pct,
            "days_since_peak": result.days_since_peak,
            "velocity": result.velocity,
            "rolling_peak": result.rolling_peak,
        }

        # Drawdown depth check
        depth_pct = result.drawdown_pct * 100
        if depth_pct <= params.depth_critical_pct:
            severity = SignalSeverity.CRITICAL
        elif depth_pct <= params.depth_warning_pct:
            severity = SignalSeverity.WARNING
        else:
            severity = None

        if severity is not None:
            signals.append(
                Signal(
                    name=self.name,
                    severity=severity,
                    message=(
                        f"Equity drawdown {depth_pct:.1f}% from "
                        f"{result.days_since_peak}-day rolling peak"
                    ),
                    triggered_at=report.timestamp,
                    metadata={
                        "indicator": "equity_drawdown",
                        **meta_base,
                    },
                )
            )

        # Drawdown velocity check
        if result.days_since_peak > 0:
            velocity_pct = result.velocity * 100
            if velocity_pct <= params.velocity_critical:
                vel_severity = SignalSeverity.CRITICAL
            elif velocity_pct <= params.velocity_warning:
                vel_severity = SignalSeverity.WARNING
            else:
                vel_severity = None

            if vel_severity is not None:
                signals.append(
                    Signal(
                        name=self.name,
                        severity=vel_severity,
                        message=(
                            f"Drawdown velocity {velocity_pct:.2f}%/day "
                            f"over {result.days_since_peak} days"
                        ),
                        triggered_at=report.timestamp,
                        metadata={
                            "indicator": "drawdown_velocity",
                            **meta_base,
                        },
                    )
                )

        return signals

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="drawdown_pct",
                display_name="Equity Drawdown",
                group="Drawdown",
                kind=IndicatorKind.CONTINUOUS,
                unit="%",
                thresholds=[
                    IndicatorThreshold(
                        value=-10.0,
                        label="Warning",
                        color="amber",
                    ),
                    IndicatorThreshold(
                        value=-20.0,
                        label="Critical",
                        color="red",
                    ),
                ],
            ),
            IndicatorSpec(
                key_suffix="velocity",
                display_name="Drawdown Velocity",
                group="Drawdown",
                kind=IndicatorKind.CONTINUOUS,
                unit="%/day",
                thresholds=[
                    IndicatorThreshold(
                        value=-0.30,
                        label="Warning",
                        color="amber",
                    ),
                    IndicatorThreshold(
                        value=-0.60,
                        label="Critical",
                        color="red",
                    ),
                ],
            ),
        ]

    def compute_indicators(
        self,
        params: EquityDrawdownParams,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        if market_ctx is None:
            return None
        try:
            series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.lookback_days,
            )
            result = compute_drawdown(series, params.lookback_bars)
        except (KeyError, ValueError):
            return None
        return IndicatorValues(
            values={
                "drawdown_pct": result.drawdown_pct * 100,
                "velocity": result.velocity * 100,
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
            "drawdown": signals[0].metadata,
        }
