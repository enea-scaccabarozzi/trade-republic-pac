from __future__ import annotations

from decimal import Decimal
from itertools import combinations

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import SignalRule


class CycleInversionParams(BaseModel):
    """Parameters for the cycle inversion detection rule."""

    min_pct: Decimal = Field(default=Decimal("2.0"), ge=0)
    warning_pct: Decimal = Field(default=Decimal("3.0"), ge=0)
    critical_pct: Decimal = Field(default=Decimal("5.0"), ge=0)


class CycleInversionRule(SignalRule[CycleInversionParams]):
    """Detects diverging asset pairs (one overweight, other underweight)."""

    @property
    def name(self) -> str:
        return "cycle_inversion"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: CycleInversionParams,
    ) -> list[Signal]:
        """Detect pairs of assets diverging in opposite directions.

        Checks all asset combinations for opposing deviations (one
        overweight, one underweight) where both exceed ``min_pct``.
        Severity is based on the combined divergence of the pair.
        """
        signals: list[Signal] = []

        for aid_a, aid_b in combinations(report.deviations.keys(), 2):
            dev_a = report.deviations[aid_a]
            dev_b = report.deviations[aid_b]

            # Both must exceed minimum threshold
            if dev_a.abs_deviation_pct < params.min_pct:
                continue
            if dev_b.abs_deviation_pct < params.min_pct:
                continue

            # Must be opposite signs (one positive, one negative)
            if (dev_a.deviation_pct > 0) == (dev_b.deviation_pct > 0):
                continue

            # Identify which is over and which is under
            if dev_a.deviation_pct > 0:
                over, under = aid_a, aid_b
                over_dev, under_dev = dev_a, dev_b
            else:
                over, under = aid_b, aid_a
                over_dev, under_dev = dev_b, dev_a

            # Severity uses 2x thresholds because combined divergence sums
            # two independent deviations — raw combined would trigger too easily.
            # E.g. warning_pct=3 → pair triggers WARNING at 6pp combined (3+3).
            combined = over_dev.abs_deviation_pct + under_dev.abs_deviation_pct
            if combined >= params.critical_pct * 2:
                severity = SignalSeverity.CRITICAL
            elif combined >= params.warning_pct * 2:
                severity = SignalSeverity.WARNING
            else:
                severity = SignalSeverity.INFO

            signals.append(
                Signal(
                    name=self.name,
                    severity=severity,
                    message=(
                        f"Cycle inversion: {over_dev.name} overweight "
                        f"(+{over_dev.abs_deviation_pct:.1f}pp) while "
                        f"{under_dev.name} underweight "
                        f"(-{under_dev.abs_deviation_pct:.1f}pp). "
                        f"Consider rebalancing."
                    ),
                    triggered_at=report.timestamp,
                    metadata={
                        "overweight_class": over,
                        "underweight_class": under,
                        "overweight_deviation_pct": float(over_dev.deviation_pct),
                        "underweight_deviation_pct": float(under_dev.deviation_pct),
                        "combined_divergence_pct": float(combined),
                    },
                )
            )

        return signals
