from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import SignalRule


class ThresholdParams(BaseModel):
    """Parameters for the threshold deviation rule."""

    warning_pct: Decimal = Field(default=Decimal("3.0"), ge=0)
    critical_pct: Decimal = Field(default=Decimal("5.0"), ge=0)


class ThresholdDeviationRule(SignalRule[ThresholdParams]):
    """Fires a signal for each asset exceeding deviation thresholds."""

    @property
    def name(self) -> str:
        return "threshold_deviation"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: ThresholdParams,
    ) -> list[Signal]:
        """Emit a signal for each asset exceeding its deviation threshold.

        Iterates per-asset deviations; assets below ``warning_pct`` are
        skipped. Assets at or above ``critical_pct`` get CRITICAL severity,
        otherwise WARNING.
        """
        signals: list[Signal] = []
        for aid, result in report.deviations.items():
            if result.abs_deviation_pct < params.warning_pct:
                continue

            if result.abs_deviation_pct >= params.critical_pct:
                severity = SignalSeverity.CRITICAL
            else:
                severity = SignalSeverity.WARNING

            direction = "overweight" if result.deviation_pct > 0 else "underweight"
            signals.append(
                Signal(
                    name=self.name,
                    severity=severity,
                    message=(
                        f"{result.name} is {direction} by "
                        f"{result.abs_deviation_pct:.1f}pp "
                        f"(actual={result.actual_pct:.1f}%, "
                        f"target={result.target_pct:.1f}%)"
                    ),
                    triggered_at=report.timestamp,
                    metadata={
                        "asset_id": aid,
                        "deviation_pct": float(result.deviation_pct),
                        "abs_deviation_pct": float(result.abs_deviation_pct),
                        "direction": direction,
                    },
                )
            )
        return signals

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        """Build template context with signal and deviation list."""
        return {
            "signal": signals[0],
            "deviations": list(report.deviations.values()),
        }
