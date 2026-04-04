from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import SignalSeverity

_SEVERITY_ORDER: dict[SignalSeverity, int] = {
    SignalSeverity.INFO: 0,
    SignalSeverity.WARNING: 1,
    SignalSeverity.CRITICAL: 2,
}


class DeviationResult(BaseModel):
    """Deviation analysis for a single asset."""

    asset_id: str
    name: str
    actual_pct: Decimal
    target_pct: Decimal
    deviation_pct: Decimal
    abs_deviation_pct: Decimal
    severity: SignalSeverity


class DeviationReport(BaseModel):
    """Aggregated deviation analysis for the whole portfolio."""

    deviations: dict[str, DeviationResult]
    max_severity: SignalSeverity
    timestamp: datetime


def get_target_allocations(settings: Settings) -> dict[str, Decimal]:
    """Extract target percentages from Settings.

    Args:
        settings: Application settings containing asset configs.

    Returns:
        Mapping of each asset ID to its target percentage as Decimal.
    """
    return settings.target_allocations


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
    *,
    warning_pct: Decimal = Decimal("3.0"),
    critical_pct: Decimal = Decimal("5.0"),
) -> DeviationReport:
    """Calculate portfolio deviations from target allocations.

    Cash is intentionally included in ``total_value`` (the denominator).
    When cash > 0, ``actual_pct`` values sum to less than 100%, correctly
    signalling underinvestment — idle cash drags all allocations down,
    surfacing "deploy your cash" pressure through negative deviations.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets.
        warning_pct: Deviation % to trigger WARNING severity.
        critical_pct: Deviation % to trigger CRITICAL severity.

    Returns:
        A DeviationReport with per-asset results and the worst severity.
    """
    targets = get_target_allocations(settings)
    asset_ids = list(targets.keys())
    allocs = snapshot.allocations(asset_ids)
    deviations: dict[str, DeviationResult] = {}

    for asset in settings.assets:
        aid = asset.id
        actual_pct = allocs[aid].actual_pct
        target_pct = targets[aid]
        deviation_pct = actual_pct - target_pct
        abs_deviation_pct = abs(deviation_pct)
        severity = classify_severity(
            abs_deviation_pct,
            warning_pct,
            critical_pct,
        )
        deviations[aid] = DeviationResult(
            asset_id=aid,
            name=asset.name,
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
