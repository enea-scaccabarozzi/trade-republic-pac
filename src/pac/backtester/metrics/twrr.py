"""Time-weighted and money-weighted return metrics.

TWRR strips out the effect of external cash flows (contributions),
giving a pure measure of investment performance. MWRR (= IRR) reflects
the actual investor experience including contribution timing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pac.backtester.engine.simulator import IterationResult


def _contribution_by_date(iteration: IterationResult) -> dict[date, Decimal]:
    """Sum PAC execution buy amounts per date as a proxy for contributions."""
    by_date: dict[date, Decimal] = {}
    for trade in iteration.trades:
        if trade.type == "pac_execution" and trade.direction == "buy":
            by_date[trade.date] = by_date.get(trade.date, Decimal(0)) + trade.amount_eur
    return by_date


def compute_twrr(iteration: IterationResult) -> float:
    """Compute annualized Time-Weighted Rate of Return.

    Chains sub-period returns between contribution events.
    Each sub-period return = V_before_next_flow / V_after_prev_flow,
    eliminating the impact of cash inflows on measured performance.

    Args:
        iteration: A single backtest iteration result.

    Returns:
        Annualized TWRR as a float. NaN if insufficient data.
    """
    dvs = iteration.daily_values
    if len(dvs) < 2:
        return float("nan")

    # Skip leading zeros
    start_idx = 0
    found = False
    for i, dv in enumerate(dvs):
        if dv.total_value > 0:
            start_idx = i
            found = True
            break

    if not found:
        return float("nan")

    if start_idx >= len(dvs) - 1:
        return float("nan")

    contributions = _contribution_by_date(iteration)

    # Chain-link sub-period returns.
    # At each contribution date, close the current sub-period and start a new one.
    # Sub-period return = V_before_flow / period_start_value
    # New period starts at V_before_flow + contribution
    period_start_value = float(dvs[start_idx].total_value)
    chain = 1.0

    for i in range(start_idx + 1, len(dvs)):
        dv = dvs[i]
        prev_dv = dvs[i - 1]
        c = float(contributions.get(dv.date, Decimal(0)))

        if c > 0 and period_start_value > 0:
            # Close sub-period using previous day's value (before today's contribution)
            v_before = float(prev_dv.total_value)
            sub_return = v_before / period_start_value
            chain *= sub_return
            # Start new sub-period: value after contribution
            period_start_value = v_before + c

    # Close final sub-period
    if period_start_value > 0:
        final_return = float(dvs[-1].total_value) / period_start_value
        chain *= final_return

    first_date = dvs[start_idx].date
    last_date = dvs[-1].date
    years = (last_date - first_date).days / 365.25
    if years <= 0:
        return float("nan")

    if chain <= 0:
        return float("nan")

    return float(chain ** (1.0 / years) - 1.0)


def compute_mwrr(
    iteration: IterationResult,
    initial_cash: Decimal = Decimal(0),
) -> float:
    """Compute annualized Money-Weighted Rate of Return (IRR).

    Solves for the discount rate that makes NPV of all cash flows
    (contributions in, final value out) equal to zero.

    Args:
        iteration: A single backtest iteration result.
        initial_cash: Initial portfolio cash (treated as a cash flow at t=0).

    Returns:
        Annualized MWRR as a float. NaN if solver fails or insufficient data.
    """
    dvs = iteration.daily_values
    if len(dvs) < 2:
        return float("nan")

    first_date = dvs[0].date
    last_date = dvs[-1].date
    total_days = (last_date - first_date).days
    if total_days <= 0:
        return float("nan")

    contributions = _contribution_by_date(iteration)

    # Build cash flow list: (year_fraction, amount)
    # Negative = money going in, positive = money coming out
    flows: list[tuple[float, float]] = []

    if initial_cash > 0:
        flows.append((0.0, -float(initial_cash)))

    for d, amount in sorted(contributions.items()):
        t = (d - first_date).days / 365.25
        flows.append((t, -float(amount)))

    # Terminal value (money coming out)
    t_end = total_days / 365.25
    flows.append((t_end, float(dvs[-1].total_value)))

    # Newton's method to find IRR
    def npv(r: float) -> float:
        return float(sum(cf / (1.0 + r) ** t for t, cf in flows))

    def npv_deriv(r: float) -> float:
        return float(sum(-t * cf / (1.0 + r) ** (t + 1) for t, cf in flows))

    r = 0.10  # initial guess
    for _ in range(200):
        f = npv(r)
        fp = npv_deriv(r)
        if abs(fp) < 1e-14:
            return float("nan")
        r_new = r - f / fp
        if abs(r_new - r) < 1e-10:
            return r_new
        r = r_new
        if abs(r) > 10.0:
            return float("nan")

    return float("nan")
