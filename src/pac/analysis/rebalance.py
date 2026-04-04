from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from pac.analysis.deviation import get_target_allocations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot

_CENTS = Decimal("0.01")


class PacAllocation(BaseModel):
    """Computed PAC amount for a single asset."""

    asset_id: str
    name: str
    amount: Decimal
    pct_of_budget: Decimal
    target_pct: Decimal
    current_pct: Decimal


class PacPlan(BaseModel):
    """Aggregated PAC allocations for the month."""

    total_budget: Decimal
    allocations: dict[str, PacAllocation]
    timestamp: datetime


def _distribute_by_targets(
    total_budget: Decimal,
    targets: dict[str, Decimal],
    snapshot: PortfolioSnapshot,
    asset_names: dict[str, str],
) -> dict[str, PacAllocation]:
    """Fallback: distribute budget proportionally to target percentages."""
    raw: dict[str, Decimal] = {}
    for aid, pct in targets.items():
        raw[aid] = total_budget * pct / Decimal(100)

    return _quantize_and_build(raw, total_budget, targets, snapshot, asset_names)


def _quantize_and_build(
    raw: dict[str, Decimal],
    total_budget: Decimal,
    targets: dict[str, Decimal],
    snapshot: PortfolioSnapshot,
    asset_names: dict[str, str],
) -> dict[str, PacAllocation]:
    """Quantize amounts to cents and absorb remainder into the largest."""
    quantized = {
        aid: amt.quantize(_CENTS, rounding=ROUND_HALF_UP) for aid, amt in raw.items()
    }

    # Rounding each allocation independently can cause the sum to differ
    # from total_budget by a few cents. Absorb the remainder into the
    # largest allocation to guarantee exact budget coverage.
    remainder = total_budget - sum(quantized.values())
    if remainder != 0:
        largest_aid = max(raw, key=lambda aid: raw[aid])
        quantized[largest_aid] += remainder

    asset_ids = list(targets.keys())
    allocs = snapshot.allocations(asset_ids)
    allocations: dict[str, PacAllocation] = {}
    for aid in asset_ids:
        amount = quantized.get(aid, Decimal(0))
        pct_of_budget = (
            (amount / total_budget * 100) if total_budget > 0 else Decimal(0)
        )
        allocations[aid] = PacAllocation(
            asset_id=aid,
            name=asset_names[aid],
            amount=amount,
            pct_of_budget=pct_of_budget,
            target_pct=targets[aid],
            current_pct=allocs[aid].actual_pct,
        )

    return allocations


def compute_pac_plan(
    snapshot: PortfolioSnapshot,
    targets: dict[str, Decimal],
    asset_names: dict[str, str],
    total_budget: Decimal,
) -> PacPlan:
    """Compute optimal PAC distribution to steer toward target allocation.

    Uses a projection-based algorithm: projects what the portfolio would
    look like after investing ``total_budget``, then allocates new money
    proportionally to each class's shortfall from its target in the
    projected portfolio. Overweight classes receive zero.

    Args:
        snapshot: Current portfolio state.
        targets: Mapping of asset ID to target percentage.
        asset_names: Mapping of asset ID to human-readable name.
        total_budget: Monthly budget to distribute.

    Returns:
        A PacPlan with per-asset allocations summing exactly to the budget.
    """
    asset_ids = list(targets.keys())

    if total_budget == 0:
        allocs = snapshot.allocations(asset_ids)
        zero_allocs: dict[str, PacAllocation] = {}
        for aid in asset_ids:
            zero_allocs[aid] = PacAllocation(
                asset_id=aid,
                name=asset_names[aid],
                amount=Decimal(0),
                pct_of_budget=Decimal(0),
                target_pct=targets[aid],
                current_pct=allocs[aid].actual_pct,
            )
        return PacPlan(
            total_budget=total_budget,
            allocations=zero_allocs,
            timestamp=snapshot.timestamp,
        )

    # Current value per asset
    current_values: dict[str, Decimal] = {}
    for aid in asset_ids:
        current_values[aid] = sum(
            (p.market_value for p in snapshot.positions if p.asset_id == aid),
            Decimal(0),
        )

    projected_total = snapshot.total_value + total_budget

    # How much each asset needs to reach target in the projected portfolio
    needed: dict[str, Decimal] = {}
    for aid in asset_ids:
        desired_value = projected_total * targets[aid] / Decimal(100)
        needed[aid] = max(Decimal(0), desired_value - current_values[aid])

    total_needed = sum(needed.values())

    # Fallback: all at/above target → distribute by target percentages
    if total_needed == 0:
        allocations = _distribute_by_targets(
            total_budget,
            targets,
            snapshot,
            asset_names,
        )
        return PacPlan(
            total_budget=total_budget,
            allocations=allocations,
            timestamp=snapshot.timestamp,
        )

    # Proportionally distribute budget based on shortfall
    raw: dict[str, Decimal] = {}
    for aid in asset_ids:
        raw[aid] = total_budget * needed[aid] / total_needed

    allocations = _quantize_and_build(
        raw,
        total_budget,
        targets,
        snapshot,
        asset_names,
    )

    return PacPlan(
        total_budget=total_budget,
        allocations=allocations,
        timestamp=snapshot.timestamp,
    )


def calculate_pac_plan(
    snapshot: PortfolioSnapshot,
    settings: Settings,
    total_budget: Decimal | None = None,
) -> PacPlan:
    """Convenience wrapper — extracts targets and asset names from Settings.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets.
        total_budget: Override for budget. Falls back to Decimal("500.00").

    Returns:
        A PacPlan with per-asset allocations summing exactly to the budget.
    """
    targets = get_target_allocations(settings)
    asset_names = {a.id: a.name for a in settings.assets}
    budget = total_budget if total_budget is not None else Decimal("500.00")
    return compute_pac_plan(snapshot, targets, asset_names, budget)
