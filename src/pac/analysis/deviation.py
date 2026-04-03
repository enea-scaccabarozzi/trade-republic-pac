from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from pac.config import Settings
from pac.models.portfolio import AssetClass, PortfolioSnapshot
from pac.models.signals import SignalSeverity

_SEVERITY_ORDER: dict[SignalSeverity, int] = {
    SignalSeverity.INFO: 0,
    SignalSeverity.WARNING: 1,
    SignalSeverity.CRITICAL: 2,
}


class DeviationResult(BaseModel):
    """Deviation analysis for a single asset class."""

    asset_class: AssetClass
    actual_pct: Decimal
    target_pct: Decimal
    deviation_pct: Decimal
    abs_deviation_pct: Decimal
    severity: SignalSeverity


class DeviationReport(BaseModel):
    """Aggregated deviation analysis for the whole portfolio."""

    deviations: dict[AssetClass, DeviationResult]
    max_severity: SignalSeverity
    timestamp: datetime


def get_target_allocations(settings: Settings) -> dict[AssetClass, Decimal]:
    """Extract target percentages from Settings as Decimal values.

    Args:
        settings: Application settings containing target allocation ints.

    Returns:
        Mapping of each asset class to its target percentage as Decimal.
    """
    return {
        AssetClass.STOCKS: Decimal(settings.target_stocks_pct),
        AssetClass.GOLD: Decimal(settings.target_gold_pct),
        AssetClass.BONDS: Decimal(settings.target_bonds_pct),
    }


def classify_severity(
    abs_deviation: Decimal,
    warning_threshold: Decimal,
    critical_threshold: Decimal,
) -> SignalSeverity:
    """Classify deviation severity based on absolute deviation value.

    Args:
        abs_deviation: Absolute deviation percentage.
        warning_threshold: Threshold at or above which severity is WARNING.
        critical_threshold: Threshold at or above which severity is CRITICAL.

    Returns:
        The appropriate SignalSeverity level.
    """
    if abs_deviation >= critical_threshold:
        return SignalSeverity.CRITICAL
    if abs_deviation >= warning_threshold:
        return SignalSeverity.WARNING
    return SignalSeverity.INFO


def calculate_deviations(
    snapshot: PortfolioSnapshot,
    settings: Settings,
) -> DeviationReport:
    """Calculate portfolio deviations from target allocations.

    Cash is intentionally included in ``total_value`` (the denominator).
    When cash > 0, ``actual_pct`` values sum to less than 100%, correctly
    signalling underinvestment — idle cash drags all allocations down,
    surfacing "deploy your cash" pressure through negative deviations.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets and thresholds.

    Returns:
        A DeviationReport with per-class results and the worst severity.
    """
    targets = get_target_allocations(settings)
    deviations: dict[AssetClass, DeviationResult] = {}

    for ac in AssetClass:
        actual_pct = snapshot.allocations[ac].actual_pct
        target_pct = targets[ac]
        deviation_pct = actual_pct - target_pct
        abs_deviation_pct = abs(deviation_pct)
        severity = classify_severity(
            abs_deviation_pct,
            settings.deviation_warning_pct,
            settings.deviation_critical_pct,
        )
        deviations[ac] = DeviationResult(
            asset_class=ac,
            actual_pct=actual_pct,
            target_pct=target_pct,
            deviation_pct=deviation_pct,
            abs_deviation_pct=abs_deviation_pct,
            severity=severity,
        )

    max_severity = max(
        deviations.values(),
        key=lambda r: _SEVERITY_ORDER[r.severity],
    ).severity

    return DeviationReport(
        deviations=deviations,
        max_severity=max_severity,
        timestamp=snapshot.timestamp,
    )
