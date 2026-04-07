from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pac.backtester.engine.actions import (
    Action,
    ActionType,
    ExecutedTrade,
    HardRebalanceOrder,
    PacAdjustment,
    PendingAction,
)


class TestPacAdjustment:
    def test_pac_adjustment_is_frozen(self) -> None:
        adj = PacAdjustment(new_volumes={"stocks": Decimal("350")})
        with pytest.raises(ValidationError):
            adj.new_volumes = {"stocks": Decimal("400")}  # type: ignore[misc]

    def test_pac_adjustment_stores_volumes(self) -> None:
        volumes = {"stocks": Decimal("350"), "gold": Decimal("75")}
        adj = PacAdjustment(new_volumes=volumes)
        assert adj.new_volumes == volumes


class TestHardRebalanceOrder:
    def test_hard_rebalance_order_rejects_zero_amount(self) -> None:
        with pytest.raises(ValidationError):
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal(0),
            )

    def test_hard_rebalance_order_rejects_negative_amount(self) -> None:
        with pytest.raises(ValidationError):
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal("-100"),
            )

    def test_hard_rebalance_order_accepts_positive_amount(self) -> None:
        order = HardRebalanceOrder(
            asset_id="stocks",
            direction="sell",
            amount_eur=Decimal("500"),
        )
        assert order.amount_eur == Decimal("500")
        assert order.direction == "sell"


class TestAction:
    def test_action_with_pac_adjustment(self) -> None:
        adj = PacAdjustment(new_volumes={"stocks": Decimal("400")})
        action = Action(type=ActionType.PAC_ADJUST, pac_adjustment=adj)
        assert action.type == ActionType.PAC_ADJUST
        assert action.pac_adjustment == adj
        assert action.rebalance_orders is None

    def test_action_with_rebalance_orders(self) -> None:
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal("1000"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        assert action.type == ActionType.HARD_REBALANCE
        assert action.rebalance_orders == orders
        assert action.pac_adjustment is None


class TestExecutedTrade:
    def test_executed_trade_captures_all_fields(self) -> None:
        trade = ExecutedTrade(
            date=date(2024, 1, 2),
            type="pac_execution",
            asset_id="stocks",
            direction="buy",
            amount_eur=Decimal("350"),
            quantity=Decimal("3.500000"),
            price=Decimal("100.00"),
            fee=Decimal(0),
        )
        assert trade.date == date(2024, 1, 2)
        assert trade.type == "pac_execution"
        assert trade.asset_id == "stocks"
        assert trade.direction == "buy"
        assert trade.amount_eur == Decimal("350")
        assert trade.quantity == Decimal("3.500000")
        assert trade.price == Decimal("100.00")
        assert trade.fee == Decimal(0)
        assert trade.skipped is False

    def test_executed_trade_skipped_flag(self) -> None:
        trade = ExecutedTrade(
            date=date(2024, 1, 2),
            type="hard_rebalance",
            asset_id="stocks",
            direction="buy",
            amount_eur=Decimal(0),
            quantity=Decimal(0),
            price=Decimal("100.00"),
            fee=Decimal(0),
            skipped=True,
        )
        assert trade.skipped is True


class TestPendingAction:
    def test_pending_action_mutable_dates(self) -> None:
        action = Action(
            type=ActionType.PAC_ADJUST, pac_adjustment=PacAdjustment(new_volumes={})
        )
        pa = PendingAction(
            action=action,
            emitted_on=date(2024, 1, 2),
            execute_on=date(2024, 1, 5),
        )
        assert pa.execute_on == date(2024, 1, 5)
        # PendingAction is mutable — execute_on can be set
        pa.execute_on = date(2024, 1, 6)
        assert pa.execute_on == date(2024, 1, 6)
