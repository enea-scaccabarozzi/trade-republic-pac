"""Tests for TWRR and MWRR computation."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from pac.backtester.engine.actions import ExecutedTrade
from pac.backtester.engine.simulator import DayResult, IterationResult
from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr


def _make_iteration_with_contributions(
    daily_values: list[tuple[int, float]],
    contributions: list[tuple[int, float]],
    start: date = date(2024, 1, 2),
) -> IterationResult:
    """Build iteration with daily values and PAC contributions.

    Args:
        daily_values: ``[(day_offset, total_value), ...]``
        contributions: ``[(day_offset, amount), ...]`` — creates
            PAC trades on those days.
        start: Reference date for day offsets.

    Returns:
        An IterationResult with DayResults and pac_execution trades.
    """
    dvs: list[DayResult] = []
    for offset, value in daily_values:
        dvs.append(
            DayResult(
                date=start + timedelta(days=offset),
                total_value=Decimal(str(value)),
                allocations={
                    "stocks": Decimal("70"),
                    "gold": Decimal("15"),
                    "bonds": Decimal("15"),
                },
                cash=Decimal("0"),
            )
        )

    trades: list[ExecutedTrade] = []
    for offset, amount in contributions:
        trades.append(
            ExecutedTrade(
                date=start + timedelta(days=offset),
                type="pac_execution",
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal(str(amount)),
                quantity=Decimal("1"),
                price=Decimal(str(amount)),
                fee=Decimal("0"),
            )
        )

    return IterationResult(
        iteration=0,
        daily_values=dvs,
        trades=trades,
        final_value=dvs[-1].total_value if dvs else Decimal("0"),
    )


class TestComputeTwrr:
    def test_no_contributions_equals_simple_return(self) -> None:
        """Without cash flows, TWRR = simple annualized return."""
        it = _make_iteration_with_contributions(
            daily_values=[(0, 1000), (365, 1100)],
            contributions=[],
        )
        twrr = compute_twrr(it)
        # 10% over 1 year
        assert twrr == pytest.approx(0.10, abs=0.01)

    def test_contribution_does_not_inflate_twrr(self) -> None:
        """Adding cash mid-period should not inflate TWRR."""
        # Day 0: 1000, Day 183 (mid-year): contribute 500 → value jumps to 1550,
        # Day 365: value 1650. Without contribution, pure market return is ~10%.
        it = _make_iteration_with_contributions(
            daily_values=[(0, 1000), (182, 1050), (183, 1550), (365, 1650)],
            contributions=[(183, 500)],
        )
        twrr = compute_twrr(it)
        # Sub-period 1: 1050/1000 = 1.05
        # Sub-period 2: 1650/(1050+500) = 1650/1550 ≈ 1.0645
        # Chained: 1.05 * 1.0645 ≈ 1.1177 → ~11.77% annual
        assert twrr == pytest.approx(0.1177, abs=0.02)

    def test_leading_zeros_handled(self) -> None:
        it = _make_iteration_with_contributions(
            daily_values=[(0, 0), (1, 0), (2, 500), (367, 550)],
            contributions=[(2, 500)],
        )
        twrr = compute_twrr(it)
        # ~10% over 1 year from first nonzero
        assert twrr == pytest.approx(0.10, abs=0.02)

    def test_empty_iteration_returns_nan(self) -> None:
        it = IterationResult(
            iteration=0,
            daily_values=[],
            trades=[],
            final_value=Decimal("0"),
        )
        assert math.isnan(compute_twrr(it))

    def test_all_zeros_returns_nan(self) -> None:
        it = _make_iteration_with_contributions(
            daily_values=[(0, 0), (1, 0)],
            contributions=[],
        )
        assert math.isnan(compute_twrr(it))


class TestComputeMwrr:
    def test_no_contributions_matches_simple_return(self) -> None:
        it = _make_iteration_with_contributions(
            daily_values=[(0, 1000), (365, 1100)],
            contributions=[],
        )
        mwrr = compute_mwrr(it, initial_cash=Decimal("1000"))
        assert mwrr == pytest.approx(0.10, abs=0.01)

    def test_contribution_timing_affects_mwrr(self) -> None:
        """MWRR should differ from TWRR when contributions are timed."""
        # Day 0: 1000, Day 183 (mid-year): contribute 500 → value jumps to 1550,
        # Day 365: value 1650.
        it = _make_iteration_with_contributions(
            daily_values=[(0, 1000), (182, 1050), (183, 1550), (365, 1650)],
            contributions=[(183, 500)],
        )
        mwrr = compute_mwrr(it, initial_cash=Decimal("1000"))
        # MWRR considers that 500 was invested later, so it's different from TWRR
        assert not math.isnan(mwrr)
        assert mwrr > 0

    def test_empty_iteration_returns_nan(self) -> None:
        it = IterationResult(
            iteration=0,
            daily_values=[],
            trades=[],
            final_value=Decimal("0"),
        )
        assert math.isnan(compute_mwrr(it))

    def test_zero_initial_cash_with_contributions(self) -> None:
        it = _make_iteration_with_contributions(
            daily_values=[(0, 0), (1, 500), (366, 550)],
            contributions=[(1, 500)],
        )
        mwrr = compute_mwrr(it, initial_cash=Decimal("0"))
        assert not math.isnan(mwrr)
        assert mwrr == pytest.approx(0.10, abs=0.02)
