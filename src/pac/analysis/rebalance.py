from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from pac.analysis.deviation import get_target_allocations
from pac.config import Settings
from pac.models.portfolio import AssetClass, PortfolioSnapshot

_CENTS = Decimal("0.01")


class PacAllocation(BaseModel):
    """Computed PAC amount for a single asset class."""

    asset_class: AssetClass
    amount: Decimal
    pct_of_budget: Decimal
    target_pct: Decimal
    current_pct: Decimal


class PacPlan(BaseModel):
    """Aggregated PAC allocations for the month."""

    total_budget: Decimal
    allocations: dict[AssetClass, PacAllocation]
    timestamp: datetime


def _distribute_by_targets(
    total_budget: Decimal,
    targets: dict[AssetClass, Decimal],
    snapshot: PortfolioSnapshot,
) -> dict[AssetClass, PacAllocation]:
    """Fallback: distribute budget proportionally to target percentages."""
    raw: dict[AssetClass, Decimal] = {}
    for ac, pct in targets.items():
        raw[ac] = total_budget * pct / Decimal(100)

    return _quantize_and_build(raw, total_budget, targets, snapshot)


def _quantize_and_build(
    raw: dict[AssetClass, Decimal],
    total_budget: Decimal,
    targets: dict[AssetClass, Decimal],
    snapshot: PortfolioSnapshot,
) -> dict[AssetClass, PacAllocation]:
    """Quantize amounts to cents and absorb remainder into the largest."""
    quantized = {
        ac: amt.quantize(_CENTS, rounding=ROUND_HALF_UP) for ac, amt in raw.items()
    }

    remainder = total_budget - sum(quantized.values())
    if remainder != 0:
        # Absorb remainder into the largest pre-quantized allocation
        largest_ac = max(raw, key=lambda ac: raw[ac])
        quantized[largest_ac] += remainder

    allocations: dict[AssetClass, PacAllocation] = {}
    for ac in AssetClass:
        amount = quantized.get(ac, Decimal(0))
        pct_of_budget = (
            (amount / total_budget * 100) if total_budget > 0 else Decimal(0)
        )
        allocations[ac] = PacAllocation(
            asset_class=ac,
            amount=amount,
            pct_of_budget=pct_of_budget,
            target_pct=targets[ac],
            current_pct=snapshot.allocations[ac].actual_pct,
        )

    return allocations


def calculate_pac_plan(
    snapshot: PortfolioSnapshot,
    settings: Settings,
    available_budget: Decimal | None = None,
) -> PacPlan:
    """Compute optimal PAC distribution to steer toward target allocation.

    Uses a projection-based algorithm: projects what the portfolio would
    look like after investing ``total_budget``, then allocates new money
    proportionally to each class's shortfall from its target in the
    projected portfolio. Overweight classes receive zero.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets and PAC config.
        available_budget: Override for budget (e.g., actual TR bank balance).
            Falls back to ``settings.pac_monthly_budget``.

    Returns:
        A PacPlan with per-class allocations summing exactly to the budget.
    """
    total_budget = (
        available_budget
        if available_budget is not None
        else settings.pac_monthly_budget
    )
    targets = get_target_allocations(settings)

    if total_budget == 0:
        zero_allocs: dict[AssetClass, PacAllocation] = {}
        for ac in AssetClass:
            zero_allocs[ac] = PacAllocation(
                asset_class=ac,
                amount=Decimal(0),
                pct_of_budget=Decimal(0),
                target_pct=targets[ac],
                current_pct=snapshot.allocations[ac].actual_pct,
            )
        return PacPlan(
            total_budget=total_budget,
            allocations=zero_allocs,
            timestamp=snapshot.timestamp,
        )

    # Current value per asset class
    current_values: dict[AssetClass, Decimal] = {}
    for ac in AssetClass:
        current_values[ac] = sum(
            (p.market_value for p in snapshot.positions if p.asset_class == ac),
            Decimal(0),
        )

    projected_total = snapshot.total_value + total_budget

    # How much each class needs to reach target in the projected portfolio
    needed: dict[AssetClass, Decimal] = {}
    for ac in AssetClass:
        desired_value = projected_total * targets[ac] / Decimal(100)
        needed[ac] = max(Decimal(0), desired_value - current_values[ac])

    total_needed = sum(needed.values())

    # Fallback: all at/above target → distribute by target percentages
    if total_needed == 0:
        allocations = _distribute_by_targets(total_budget, targets, snapshot)
        return PacPlan(
            total_budget=total_budget,
            allocations=allocations,
            timestamp=snapshot.timestamp,
        )

    # Proportionally distribute budget based on shortfall
    raw: dict[AssetClass, Decimal] = {}
    for ac in AssetClass:
        raw[ac] = total_budget * needed[ac] / total_needed

    allocations = _quantize_and_build(raw, total_budget, targets, snapshot)

    return PacPlan(
        total_budget=total_budget,
        allocations=allocations,
        timestamp=snapshot.timestamp,
    )
