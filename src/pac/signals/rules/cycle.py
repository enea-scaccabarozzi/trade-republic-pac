from __future__ import annotations

from itertools import combinations

from pac.analysis.deviation import DeviationReport
from pac.config import Settings
from pac.models.portfolio import AssetClass, PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity


class CycleInversionRule:
    """Detects diverging asset pairs (one overweight, other underweight).

    Note: Unlike ThresholdDeviationRule (which skips INFO-severity deviations),
    this rule intentionally emits INFO signals for marginal inversions.
    Downstream consumers can filter by severity if they only want
    WARNING/CRITICAL alerts.
    """

    @property
    def name(self) -> str:
        return "cycle_inversion"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        settings: Settings,
    ) -> list[Signal]:
        signals: list[Signal] = []
        min_deviation = settings.cycle_inversion_min_pct

        for ac_a, ac_b in combinations(AssetClass, 2):
            dev_a = report.deviations[ac_a]
            dev_b = report.deviations[ac_b]

            # Both must exceed minimum threshold
            if dev_a.abs_deviation_pct < min_deviation:
                continue
            if dev_b.abs_deviation_pct < min_deviation:
                continue

            # Must be opposite signs (one positive, one negative)
            if (dev_a.deviation_pct > 0) == (dev_b.deviation_pct > 0):
                continue

            # Identify which is over and which is under
            if dev_a.deviation_pct > 0:
                over, under = ac_a, ac_b
                over_dev, under_dev = dev_a, dev_b
            else:
                over, under = ac_b, ac_a
                over_dev, under_dev = dev_b, dev_a

            # Severity based on combined divergence
            combined = over_dev.abs_deviation_pct + under_dev.abs_deviation_pct
            if combined >= settings.deviation_critical_pct * 2:
                severity = SignalSeverity.CRITICAL
            elif combined >= settings.deviation_warning_pct * 2:
                severity = SignalSeverity.WARNING
            else:
                severity = SignalSeverity.INFO

            signals.append(
                Signal(
                    name=self.name,
                    severity=severity,
                    message=(
                        f"Cycle inversion: {over.value} overweight "
                        f"(+{over_dev.abs_deviation_pct:.1f}pp) while "
                        f"{under.value} underweight "
                        f"(-{under_dev.abs_deviation_pct:.1f}pp). "
                        f"Consider rebalancing."
                    ),
                    triggered_at=report.timestamp,
                    metadata={
                        "overweight_class": over.value,
                        "underweight_class": under.value,
                        "overweight_deviation_pct": float(over_dev.deviation_pct),
                        "underweight_deviation_pct": float(under_dev.deviation_pct),
                        "combined_divergence_pct": float(combined),
                    },
                )
            )

        return signals
