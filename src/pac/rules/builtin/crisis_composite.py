"""Composite crisis rule — N-of-M indicator voting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import IndicatorSpec, IndicatorValues, SignalRule
from pac.rules.builtin._indicators import (
    compute_death_cross,
    compute_divergence,
    compute_drawdown,
    compute_relative_strength,
)

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class CrisisCompositeParams(BaseModel):
    """Parameters for the composite crisis detection rule."""

    # Asset ID references
    equity_asset_id: str = "stocks"
    gold_asset_id: str = "gold"

    # Activation rule
    min_active_indicators: int = Field(default=3, ge=1, le=6)

    # Drawdown depth thresholds
    drawdown_warning_pct: float = Field(default=-12.0, le=0)
    drawdown_critical_pct: float = Field(default=-20.0, le=0)

    # Drawdown velocity thresholds
    velocity_warning: float = Field(default=-0.25, le=0)
    velocity_critical: float = Field(default=-0.50, le=0)

    # Gold-equity divergence thresholds
    divergence_warning_pct: float = Field(default=12.0, ge=0)
    divergence_critical_pct: float = Field(default=20.0, ge=0)

    # Relative strength thresholds
    rs_ma_window: int = Field(default=120, ge=20)
    rs_warning_pct: float = Field(default=8.0, ge=0)
    rs_critical_pct: float = Field(default=15.0, ge=0)

    # Death cross SMA windows
    death_cross_short_window: int = Field(default=50, ge=5)
    death_cross_long_window: int = Field(default=200, ge=20)

    # Lookback windows (calendar days for MarketContext)
    equity_lookback_days: int = Field(default=450, ge=60)
    gold_lookback_days: int = Field(default=250, ge=20)

    # Lookback windows (trading days for indicator calculations)
    drawdown_lookback_bars: int = Field(default=252, ge=30)
    divergence_lookback_bars: int = Field(default=40, ge=10)


def _indicator_severity(
    active: bool,
    value: float,
    warning_threshold: float,
    critical_threshold: float,
    *,
    higher_is_worse: bool = True,
) -> str | None:
    """Return severity string for an indicator, or None if inactive."""
    if not active:
        return None
    if higher_is_worse:
        if value >= critical_threshold:
            return "critical"
        return "warning"
    # Lower is worse (drawdown, velocity — negative values)
    if value <= critical_threshold:
        return "critical"
    return "warning"


class CrisisCompositeRule(SignalRule[CrisisCompositeParams]):
    """Combines 5 crisis indicators with N-of-M voting."""

    @property
    def name(self) -> str:
        return "crisis_composite"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: CrisisCompositeParams,
        market_ctx: MarketContext | None = None,
    ) -> list[Signal]:
        if market_ctx is None:
            return []

        # -----------------------------------------------------------------
        # Fetch price series (any missing asset → abort)
        # -----------------------------------------------------------------
        try:
            equity_series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.equity_lookback_days,
            )
        except KeyError:
            return []

        try:
            gold_series = market_ctx.get_asset_prices(
                params.gold_asset_id,
                params.gold_lookback_days,
            )
        except KeyError:
            gold_series = None

        # -----------------------------------------------------------------
        # Compute all 5 voting indicators
        # -----------------------------------------------------------------
        indicators: dict[str, dict[str, Any]] = {}

        # 1. Drawdown depth
        try:
            dd = compute_drawdown(equity_series, params.drawdown_lookback_bars)
            depth_pct = dd.drawdown_pct * 100
            dd_active = depth_pct <= params.drawdown_warning_pct
            indicators["drawdown_depth"] = {
                "active": dd_active,
                "severity": _indicator_severity(
                    dd_active,
                    depth_pct,
                    params.drawdown_warning_pct,
                    params.drawdown_critical_pct,
                    higher_is_worse=False,
                ),
                "value": depth_pct,
                "threshold": params.drawdown_warning_pct,
            }
        except ValueError:
            indicators["drawdown_depth"] = {
                "active": False,
                "severity": None,
                "value": None,
                "threshold": params.drawdown_warning_pct,
            }
            dd = None

        # 2. Drawdown velocity
        if dd is not None and dd.days_since_peak > 0:
            vel_pct = dd.velocity * 100
            vel_active = vel_pct <= params.velocity_warning
            indicators["drawdown_velocity"] = {
                "active": vel_active,
                "severity": _indicator_severity(
                    vel_active,
                    vel_pct,
                    params.velocity_warning,
                    params.velocity_critical,
                    higher_is_worse=False,
                ),
                "value": vel_pct,
                "threshold": params.velocity_warning,
            }
        else:
            indicators["drawdown_velocity"] = {
                "active": False,
                "severity": None,
                "value": None,
                "threshold": params.velocity_warning,
            }

        # 3. Gold-equity divergence
        if gold_series is not None:
            try:
                div = compute_divergence(
                    gold_series,
                    equity_series,
                    params.divergence_lookback_bars,
                )
                div_pct = div.divergence * 100
                div_active = div_pct >= params.divergence_warning_pct
                indicators["gold_equity_divergence"] = {
                    "active": div_active,
                    "severity": _indicator_severity(
                        div_active,
                        div_pct,
                        params.divergence_warning_pct,
                        params.divergence_critical_pct,
                        higher_is_worse=True,
                    ),
                    "value": div_pct,
                    "threshold": params.divergence_warning_pct,
                }
            except ValueError:
                indicators["gold_equity_divergence"] = {
                    "active": False,
                    "severity": None,
                    "value": None,
                    "threshold": params.divergence_warning_pct,
                }
        else:
            indicators["gold_equity_divergence"] = {
                "active": False,
                "severity": None,
                "value": None,
                "threshold": params.divergence_warning_pct,
            }

        # 4. Death cross (SMA50 < SMA200)
        # Uses inline severity logic instead of _indicator_severity() because
        # death cross is fundamentally boolean (bearish_regime or not). The
        # standard helper compares a continuous value against warning/critical
        # thresholds, which doesn't apply to a crossover signal.
        try:
            dc = compute_death_cross(
                equity_series,
                params.death_cross_short_window,
                params.death_cross_long_window,
            )
            dc_active = dc.bearish_regime
            dc_severity: str | None = None
            if dc_active:
                dc_severity = "critical" if dc.cross_event else "warning"
            indicators["death_cross"] = {
                "active": dc_active,
                "severity": dc_severity,
                "value": dc.sma_short - dc.sma_long,
                "threshold": 0.0,
            }
        except ValueError:
            indicators["death_cross"] = {
                "active": False,
                "severity": None,
                "value": None,
                "threshold": 0.0,
            }

        # 5. Relative strength
        if gold_series is not None:
            try:
                rs = compute_relative_strength(
                    gold_series,
                    equity_series,
                    params.rs_ma_window,
                )
                rs_active = rs.breakout_pct >= params.rs_warning_pct
                indicators["relative_strength"] = {
                    "active": rs_active,
                    "severity": _indicator_severity(
                        rs_active,
                        rs.breakout_pct,
                        params.rs_warning_pct,
                        params.rs_critical_pct,
                        higher_is_worse=True,
                    ),
                    "value": rs.breakout_pct,
                    "threshold": params.rs_warning_pct,
                }
            except ValueError:
                indicators["relative_strength"] = {
                    "active": False,
                    "severity": None,
                    "value": None,
                    "threshold": params.rs_warning_pct,
                }
        else:
            indicators["relative_strength"] = {
                "active": False,
                "severity": None,
                "value": None,
                "threshold": params.rs_warning_pct,
            }

        # -----------------------------------------------------------------
        # Count active voting indicators
        # -----------------------------------------------------------------
        voting_keys = [
            "drawdown_depth",
            "drawdown_velocity",
            "gold_equity_divergence",
            "death_cross",
            "relative_strength",
        ]
        active_count = sum(1 for k in voting_keys if indicators[k]["active"])

        if active_count < params.min_active_indicators:
            return []

        # -----------------------------------------------------------------
        # Determine composite severity
        # -----------------------------------------------------------------
        critical_count = sum(
            1
            for k in voting_keys
            if indicators[k]["active"] and indicators[k]["severity"] == "critical"
        )
        severity = (
            SignalSeverity.CRITICAL if critical_count >= 2 else SignalSeverity.WARNING
        )

        metadata: dict[str, Any] = {
            "composite": True,
            "active_count": active_count,
            "min_required": params.min_active_indicators,
            "indicators": indicators,
        }

        return [
            Signal(
                name=self.name,
                severity=severity,
                message=(
                    f"Crisis composite: {active_count}/{len(voting_keys)} "
                    f"indicators active "
                    f"(min {params.min_active_indicators} required)"
                ),
                triggered_at=report.timestamp,
                metadata=metadata,
            )
        ]

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        return [
            IndicatorSpec(
                key_suffix="active_count",
                display_name="Active Indicators",
                group="Crisis Composite",
                kind=IndicatorKind.CONTINUOUS,
                unit="count",
                thresholds=[
                    IndicatorThreshold(
                        value=3.0,
                        label="Crisis Active",
                        color="red",
                    ),
                ],
            ),
        ]

    def compute_indicators(
        self,
        params: CrisisCompositeParams,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        if market_ctx is None:
            return None

        try:
            equity_series = market_ctx.get_asset_prices(
                params.equity_asset_id,
                params.equity_lookback_days,
            )
        except KeyError:
            return None

        try:
            gold_series = market_ctx.get_asset_prices(
                params.gold_asset_id,
                params.gold_lookback_days,
            )
        except KeyError:
            gold_series = None

        active_count = 0

        # 1. Drawdown depth
        try:
            dd = compute_drawdown(
                equity_series,
                params.drawdown_lookback_bars,
            )
            if dd.drawdown_pct * 100 <= params.drawdown_warning_pct:
                active_count += 1
            # 2. Drawdown velocity
            if dd.days_since_peak > 0 and dd.velocity * 100 <= params.velocity_warning:
                active_count += 1
        except ValueError:
            dd = None

        # 3. Gold-equity divergence
        if gold_series is not None:
            try:
                div = compute_divergence(
                    gold_series,
                    equity_series,
                    params.divergence_lookback_bars,
                )
                if div.divergence * 100 >= params.divergence_warning_pct:
                    active_count += 1
            except ValueError:
                pass

        # 4. Death cross
        try:
            dc = compute_death_cross(
                equity_series,
                params.death_cross_short_window,
                params.death_cross_long_window,
            )
            if dc.bearish_regime:
                active_count += 1
        except ValueError:
            pass

        # 5. Relative strength
        if gold_series is not None:
            try:
                rs = compute_relative_strength(
                    gold_series,
                    equity_series,
                    params.rs_ma_window,
                )
                if rs.breakout_pct >= params.rs_warning_pct:
                    active_count += 1
            except ValueError:
                pass

        return IndicatorValues(
            values={"active_count": float(active_count)},
        )

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        meta = signals[0].metadata
        return {
            "signal": signals[0],
            "indicators": meta["indicators"],
            "active_count": meta["active_count"],
            "min_required": meta["min_required"],
        }
