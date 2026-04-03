from __future__ import annotations

from pac.analysis.deviation import DeviationReport
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity


class ThresholdDeviationRule:
    """Fires a signal for each asset class exceeding deviation thresholds."""

    @property
    def name(self) -> str:
        return "threshold_deviation"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        settings: Settings,
    ) -> list[Signal]:
        signals: list[Signal] = []
        for ac, result in report.deviations.items():
            if result.severity == SignalSeverity.INFO:
                continue  # below thresholds — no alert

            direction = "overweight" if result.deviation_pct > 0 else "underweight"
            signals.append(
                Signal(
                    name=self.name,
                    severity=result.severity,
                    message=(
                        f"{ac.value} is {direction} by "
                        f"{result.abs_deviation_pct:.1f}pp "
                        f"(actual={result.actual_pct:.1f}%, "
                        f"target={result.target_pct:.1f}%)"
                    ),
                    triggered_at=report.timestamp,
                    metadata={
                        "asset_class": ac.value,
                        "deviation_pct": float(result.deviation_pct),
                        "abs_deviation_pct": float(result.abs_deviation_pct),
                        "direction": direction,
                    },
                )
            )
        return signals
