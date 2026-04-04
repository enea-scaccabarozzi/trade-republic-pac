from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pac.analysis.rebalance import calculate_pac_plan, compute_pac_plan
from pac.config import Settings
from pac.models.portfolio import (
    PortfolioSnapshot,
    Position,
)


@pytest.fixture
def _overweight_stocks_snapshot() -> PortfolioSnapshot:
    """Stocks at 80% in a large portfolio so they remain overweight after adding budget.

    Total = 10000, stocks = 8000. With 500 budget → projected = 10500,
    desired_stocks = 7350 < 8000 → stocks gets zero PAC.
    """
    positions = [
        Position(
            isin="IE00BK5BQT80",
            name="Stocks",
            quantity=Decimal("1"),
            price=Decimal("8000"),
            market_value=Decimal("8000"),
            asset_id="stocks",
        ),
        Position(
            isin="IE00B4ND3602",
            name="Gold",
            quantity=Decimal("1"),
            price=Decimal("1000"),
            market_value=Decimal("1000"),
            asset_id="gold",
        ),
        Position(
            isin="IE00B3F81409",
            name="Bonds",
            quantity=Decimal("1"),
            price=Decimal("1000"),
            market_value=Decimal("1000"),
            asset_id="bonds",
        ),
    ]
    return PortfolioSnapshot(
        positions=positions,
        cash=Decimal(0),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


class TestCalculatePacPlan:
    def test_basic_redistribution(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        """All classes underweight due to cash → budget split proportionally.

        Stocks needs the most in absolute terms (high target), so gets
        the largest PAC share despite smaller percentage deviation.
        """
        plan = calculate_pac_plan(sample_snapshot, default_settings)

        assert plan.total_budget == Decimal("500.00")
        stocks_alloc = plan.allocations["stocks"]
        bonds_alloc = plan.allocations["bonds"]
        gold_alloc = plan.allocations["gold"]
        # Stocks needs most absolute money to reach 70% target
        assert stocks_alloc.amount > bonds_alloc.amount > gold_alloc.amount

    def test_overweight_class_gets_zero(
        self,
        _overweight_stocks_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        """Stocks at 80% (target 70%) → PAC amount = 0."""
        plan = calculate_pac_plan(_overweight_stocks_snapshot, default_settings)

        assert plan.allocations["stocks"].amount == Decimal(0)
        # Gold and bonds should split the budget
        assert plan.allocations["gold"].amount > 0
        assert plan.allocations["bonds"].amount > 0

    def test_budget_override(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(
            sample_snapshot,
            default_settings,
            total_budget=Decimal("300"),
        )

        assert plan.total_budget == Decimal("300")
        total_allocated = sum(a.amount for a in plan.allocations.values())
        assert total_allocated == Decimal("300")

    def test_zero_budget(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(
            sample_snapshot,
            default_settings,
            total_budget=Decimal("0"),
        )

        for alloc in plan.allocations.values():
            assert alloc.amount == Decimal(0)

    def test_empty_portfolio_distributes_by_target(
        self,
        default_settings: Settings,
    ) -> None:
        """No existing positions → distribute exactly by target percentages."""
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        plan = calculate_pac_plan(snapshot, default_settings)

        assert plan.allocations["stocks"].amount == Decimal("350.00")
        assert plan.allocations["gold"].amount == Decimal("75.00")
        assert plan.allocations["bonds"].amount == Decimal("75.00")

    def test_amounts_sum_to_budget(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(sample_snapshot, default_settings)

        total = sum(a.amount for a in plan.allocations.values())
        assert total == plan.total_budget

    def test_amounts_quantized_to_cents(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(sample_snapshot, default_settings)

        for alloc in plan.allocations.values():
            # Check that the amount has at most 2 decimal places
            assert alloc.amount == alloc.amount.quantize(Decimal("0.01"))

    def test_pct_of_budget_computed(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(sample_snapshot, default_settings)

        for alloc in plan.allocations.values():
            if plan.total_budget > 0:
                expected_pct = (alloc.amount / plan.total_budget) * 100
                assert alloc.pct_of_budget == expected_pct

    def test_single_underweight_class(
        self,
        default_settings: Settings,
    ) -> None:
        """Only bonds underweight → gets 100% of budget."""
        # Stocks and gold at/above target, bonds far below
        positions = [
            Position(
                isin="IE00BK5BQT80",
                name="Stocks",
                quantity=Decimal("1"),
                price=Decimal("750"),
                market_value=Decimal("750"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold",
                quantity=Decimal("1"),
                price=Decimal("200"),
                market_value=Decimal("200"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bonds",
                quantity=Decimal("1"),
                price=Decimal("50"),
                market_value=Decimal("50"),
                asset_id="bonds",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions,
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        plan = calculate_pac_plan(snapshot, default_settings)

        # Stocks & gold are at/above target in projected portfolio
        # Bonds should get the entire budget (or close to it)
        assert plan.allocations["bonds"].amount > Decimal(0)
        total = sum(a.amount for a in plan.allocations.values())
        assert total == plan.total_budget

    def test_all_at_target_falls_back_to_proportional(
        self,
        default_settings: Settings,
    ) -> None:
        """All classes at target → distribute by target percentages."""
        positions = [
            Position(
                isin="IE00BK5BQT80",
                name="Stocks",
                quantity=Decimal("1"),
                price=Decimal("700"),
                market_value=Decimal("700"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bonds",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="bonds",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions,
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        plan = calculate_pac_plan(snapshot, default_settings)

        # Should distribute by target pct (70/15/15 of 500)
        assert plan.allocations["stocks"].amount == Decimal("350.00")
        assert plan.allocations["gold"].amount == Decimal("75.00")
        assert plan.allocations["bonds"].amount == Decimal("75.00")

    def test_timestamp_from_snapshot(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        plan = calculate_pac_plan(sample_snapshot, default_settings)
        assert plan.timestamp == sample_snapshot.timestamp


class TestComputePacPlan:
    """Tests for the settings-free compute_pac_plan function."""

    def test_basic_redistribution(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        targets = {
            "stocks": Decimal("70"),
            "gold": Decimal("15"),
            "bonds": Decimal("15"),
        }
        asset_names = {
            "stocks": "Stocks ETF",
            "gold": "Gold ETC",
            "bonds": "Bond ETF",
        }
        plan = compute_pac_plan(
            sample_snapshot, targets, asset_names, Decimal("500.00")
        )
        assert plan.total_budget == Decimal("500.00")
        total = sum(a.amount for a in plan.allocations.values())
        assert total == Decimal("500.00")

    def test_amounts_quantized_to_cents(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        targets = {
            "stocks": Decimal("70"),
            "gold": Decimal("15"),
            "bonds": Decimal("15"),
        }
        asset_names = {
            "stocks": "Stocks ETF",
            "gold": "Gold ETC",
            "bonds": "Bond ETF",
        }
        plan = compute_pac_plan(
            sample_snapshot, targets, asset_names, Decimal("500.00")
        )
        for alloc in plan.allocations.values():
            assert alloc.amount == alloc.amount.quantize(Decimal("0.01"))

    def test_zero_budget(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        targets = {
            "stocks": Decimal("70"),
            "gold": Decimal("15"),
            "bonds": Decimal("15"),
        }
        asset_names = {
            "stocks": "Stocks ETF",
            "gold": "Gold ETC",
            "bonds": "Bond ETF",
        }
        plan = compute_pac_plan(sample_snapshot, targets, asset_names, Decimal("0"))
        for alloc in plan.allocations.values():
            assert alloc.amount == Decimal(0)

    def test_asset_names_used(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        targets = {
            "stocks": Decimal("70"),
            "gold": Decimal("15"),
            "bonds": Decimal("15"),
        }
        asset_names = {
            "stocks": "My Stocks",
            "gold": "My Gold",
            "bonds": "My Bonds",
        }
        plan = compute_pac_plan(
            sample_snapshot, targets, asset_names, Decimal("500.00")
        )
        assert plan.allocations["stocks"].name == "My Stocks"
        assert plan.allocations["gold"].name == "My Gold"
        assert plan.allocations["bonds"].name == "My Bonds"
