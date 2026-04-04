from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pac.models.portfolio import Allocation, PortfolioSnapshot, Position, SavingsPlan
from pac.models.signals import ActionType, RebalanceAction, Signal, SignalSeverity

_ASSET_IDS = ["stocks", "gold", "bonds"]


class TestPosition:
    def test_create_position(self) -> None:
        pos = Position(
            isin="IE00BK5BQT80",
            name="FTSE All-World",
            quantity=Decimal("10"),
            price=Decimal("100.00"),
            market_value=Decimal("1000.00"),
            asset_id="stocks",
        )
        assert pos.isin == "IE00BK5BQT80"
        assert pos.asset_id == "stocks"

    def test_position_serialization(self) -> None:
        pos = Position(
            isin="IE00BK5BQT80",
            name="FTSE All-World",
            quantity=Decimal("10"),
            price=Decimal("100.00"),
            market_value=Decimal("1000.00"),
            asset_id="stocks",
        )
        data = pos.model_dump()
        assert data["asset_id"] == "stocks"
        assert isinstance(data["quantity"], Decimal)


class TestPortfolioSnapshot:
    def test_total_value(self, sample_snapshot: PortfolioSnapshot) -> None:
        # positions: 1000 + 200 + 100 = 1300, cash: 200 → total 1500
        assert sample_snapshot.total_value == Decimal("1500.00")

    def test_allocations(self, sample_snapshot: PortfolioSnapshot) -> None:
        allocs = sample_snapshot.allocations(_ASSET_IDS)
        # stocks: 1000/1500 ≈ 66.67%, gold: 200/1500 ≈ 13.33%, bonds: 100/1500 ≈ 6.67%
        assert isinstance(allocs["stocks"], Allocation)
        assert allocs["stocks"].actual_pct > Decimal("66")
        assert allocs["stocks"].actual_pct < Decimal("67")
        assert allocs["gold"].actual_pct > Decimal("13")
        assert allocs["bonds"].actual_pct > Decimal("6")

    def test_empty_portfolio(self) -> None:
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal("0"),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert snapshot.total_value == Decimal("0")
        allocs = snapshot.allocations(_ASSET_IDS)
        assert all(a.actual_pct == Decimal(0) for a in allocs.values())

    def test_serialization_roundtrip(self, sample_snapshot: PortfolioSnapshot) -> None:
        data = sample_snapshot.model_dump(mode="json")
        restored = PortfolioSnapshot.model_validate(data)
        assert restored.total_value == sample_snapshot.total_value


class TestSignal:
    def test_create_signal(self) -> None:
        signal = Signal(
            name="threshold_breach",
            severity=SignalSeverity.WARNING,
            message="Stocks allocation deviates by 5%",
            triggered_at=datetime(2026, 4, 1, tzinfo=UTC),
            metadata={"deviation_pct": 5.0},
        )
        assert signal.severity == SignalSeverity.WARNING
        assert signal.metadata["deviation_pct"] == 5.0

    def test_signal_default_metadata(self) -> None:
        signal = Signal(
            name="test",
            severity=SignalSeverity.INFO,
            message="Test signal",
            triggered_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert signal.metadata == {}


class TestRebalanceAction:
    def test_create_action(self) -> None:
        action = RebalanceAction(
            asset_id="stocks",
            action=ActionType.BUY,
            reason="Under target by 3.5%",
            current_pct=66.5,
            target_pct=70.0,
        )
        assert action.action == ActionType.BUY
        assert action.current_pct == 66.5


class TestSavingsPlan:
    def test_create_savings_plan(self) -> None:
        plan = SavingsPlan(
            isin="IE00BK5BQT80",
            name="Vanguard FTSE All-World",
            amount=Decimal("250.00"),
            interval="monthly",
        )
        assert plan.isin == "IE00BK5BQT80"
        assert plan.amount == Decimal("250.00")
        assert plan.interval == "monthly"
        assert plan.asset_id is None

    def test_savings_plan_with_asset_id(self) -> None:
        plan = SavingsPlan(
            isin="IE00BK5BQT80",
            name="Vanguard FTSE All-World",
            amount=Decimal("250.00"),
            interval="monthly",
            asset_id="stocks",
        )
        assert plan.asset_id == "stocks"


class TestPortfolioSnapshotEdgeCases:
    def test_cash_only_total_value(self) -> None:
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal("500.00"),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert snapshot.total_value == Decimal("500.00")

    def test_allocations_missing_asset_returns_zero(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        allocs = sample_snapshot.allocations(["stocks", "gold", "bonds", "crypto"])
        assert allocs["crypto"].actual_pct == Decimal(0)

    def test_signal_serialization_roundtrip(self) -> None:
        signal = Signal(
            name="test_signal",
            severity=SignalSeverity.WARNING,
            message="Something happened",
            triggered_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
            metadata={"key": "value"},
        )
        data = signal.model_dump(mode="json")
        restored = Signal.model_validate(data)
        assert restored.name == signal.name
        assert restored.severity == signal.severity
        assert restored.metadata == signal.metadata
