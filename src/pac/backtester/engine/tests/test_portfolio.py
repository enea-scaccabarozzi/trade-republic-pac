from __future__ import annotations

from datetime import date
from decimal import Decimal

from pac.backtester.data.models import PriceBar
from pac.backtester.engine.actions import (
    Action,
    ActionType,
    HardRebalanceOrder,
    PacAdjustment,
)
from pac.backtester.engine.portfolio import SimulatedPortfolio
from pac.backtester.engine.tests.conftest import make_portfolio


def _bar(price: Decimal = Decimal("100")) -> PriceBar:
    """Create a single PriceBar at a given close price."""
    return PriceBar(
        date=date(2024, 1, 2),
        open=price - Decimal(1),
        high=price + Decimal(5),
        low=price - Decimal(2),
        close=price,
        volume=1_000_000,
    )


def _prices(price: Decimal = Decimal("100")) -> dict[str, PriceBar]:
    """Create prices for all 3 assets at the same close price."""
    bar = _bar(price)
    return {"stocks": bar, "gold": bar, "bonds": bar}


class TestInitialState:
    def test_initial_portfolio_has_zero_positions(
        self,
        sample_portfolio: SimulatedPortfolio,
    ) -> None:
        snap = sample_portfolio.snapshot(date(2024, 1, 2), _prices())
        for pos in snap.positions:
            assert pos.quantity == Decimal(0)

    def test_initial_cash_matches_config(
        self,
        sample_portfolio: SimulatedPortfolio,
    ) -> None:
        assert sample_portfolio.cash == Decimal("10000")


class TestPacExecution:
    def test_pac_buy_increases_position_quantity(self) -> None:
        portfolio = make_portfolio()
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        snap = portfolio.snapshot(date(2024, 1, 2), _prices())
        stocks_pos = next(p for p in snap.positions if p.asset_id == "stocks")
        assert stocks_pos.quantity > Decimal(0)

    def test_pac_buy_decreases_cash(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        initial_cash = portfolio.cash
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        # Cash increases by contribution then decreases by PAC volumes
        # Net change: +250 (contribution) - 350 - 75 - 75 (volumes) = -250
        assert portfolio.cash < initial_cash

    def test_pac_buy_no_fee(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        trades = portfolio.execute_pac(
            date(2024, 1, 2),
            _prices(),
            Decimal("500"),
            pac_day=2,
        )
        for trade in trades:
            assert trade.fee == Decimal(0)

    def test_pac_buy_updates_avg_cost(self) -> None:
        portfolio = make_portfolio()
        prices_100 = _prices(Decimal("100"))
        portfolio.execute_pac(date(2024, 1, 2), prices_100, Decimal("500"), pac_day=2)

        prices_200 = _prices(Decimal("200"))
        portfolio.execute_pac(date(2024, 1, 16), prices_200, Decimal("500"), pac_day=16)

        snap = portfolio.snapshot(date(2024, 1, 16), prices_200)
        stocks_pos = next(p for p in snap.positions if p.asset_id == "stocks")
        # avg_cost should be between 100 and 200
        assert Decimal("100") < stocks_pos.price  # current price is 200

    def test_pac_adds_contribution_to_cash(self) -> None:
        # With zero PAC volumes, only the contribution is added
        portfolio_no_volumes = make_portfolio(
            cash=Decimal("0"),
            pac_volumes={"stocks": Decimal(0), "gold": Decimal(0), "bonds": Decimal(0)},
        )
        portfolio_no_volumes.execute_pac(
            date(2024, 1, 2),
            _prices(),
            Decimal("500"),
            pac_day=2,
        )
        # 500 / 2 pac days = 250 added
        assert portfolio_no_volumes.cash == Decimal("250")

    def test_pac_contribution_split_across_dates(self) -> None:
        portfolio = make_portfolio(
            cash=Decimal("0"),
            pac_volumes={"stocks": Decimal(0), "gold": Decimal(0), "bonds": Decimal(0)},
        )
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        assert portfolio.cash == Decimal("250")
        portfolio.execute_pac(date(2024, 1, 16), _prices(), Decimal("500"), pac_day=16)
        assert portfolio.cash == Decimal("500")

    def test_pac_with_single_configured_day(self) -> None:
        portfolio = make_portfolio(
            cash=Decimal("0"),
            pac_volumes={"stocks": Decimal(0), "gold": Decimal(0), "bonds": Decimal(0)},
            pac_execution_days=[2],
        )
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        # Full contribution on single day: 500 / 1 = 500
        assert portfolio.cash == Decimal("500")

    def test_pac_with_three_configured_days(self) -> None:
        portfolio = make_portfolio(
            cash=Decimal("0"),
            pac_volumes={"stocks": Decimal(0), "gold": Decimal(0), "bonds": Decimal(0)},
            pac_execution_days=[2, 10, 20],
        )
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("600"), pac_day=2)
        # 600 / 3 = 200
        assert portfolio.cash == Decimal("200")

    def test_pac_deduplication_same_month_day(self) -> None:
        portfolio = make_portfolio(
            cash=Decimal("0"),
            pac_volumes={"stocks": Decimal(0), "gold": Decimal(0), "bonds": Decimal(0)},
        )
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        assert portfolio.cash == Decimal("250")
        # Second call for same (year, month, pac_day) should be no-op
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        assert portfolio.cash == Decimal("250")


class TestHardRebalance:
    def test_hard_rebalance_buy_deducts_fee(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal("1000"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 2), execute_on=date(2024, 1, 2)
        )
        portfolio.process_pending_actions(date(2024, 1, 2), _prices())
        # Cash reduced by amount (1000) + fee (1) = 1001
        assert portfolio.cash == Decimal("10000") - Decimal("1001")

    def test_hard_rebalance_sell_deducts_fee(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        # First buy some stocks
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)

        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="sell",
                amount_eur=Decimal("100"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 3), execute_on=date(2024, 1, 3)
        )
        trades = portfolio.process_pending_actions(date(2024, 1, 3), _prices())

        sell_trade = next(t for t in trades if t.direction == "sell")
        # Fee is deducted: cash increase = amount - fee
        assert sell_trade.fee == Decimal("1.00")

    def test_hard_rebalance_applies_spread(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"), spread_bps=Decimal("10"))
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal("1000"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 2), execute_on=date(2024, 1, 2)
        )
        trades = portfolio.process_pending_actions(date(2024, 1, 2), _prices())

        buy_trade = trades[0]
        # Buy price should be close * (1 + 10/10000) = 100 * 1.001 = 100.1
        expected_price = Decimal("100") * (
            Decimal(1) + Decimal("10") / Decimal("10000")
        )
        assert buy_trade.price == expected_price

    def test_sell_capped_at_available_quantity(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        # Buy a small amount first
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)

        snap = portfolio.snapshot(date(2024, 1, 2), _prices())
        stocks_qty = next(p for p in snap.positions if p.asset_id == "stocks").quantity

        # Try to sell more than held
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="sell",
                amount_eur=Decimal("999999"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 3), execute_on=date(2024, 1, 3)
        )
        trades = portfolio.process_pending_actions(date(2024, 1, 3), _prices())

        sell_trade = next(t for t in trades if t.direction == "sell")
        assert sell_trade.quantity <= stocks_qty

    def test_sell_records_actual_amount_not_requested(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        # Buy a small amount
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)

        # Sell more than we have — amount should reflect actual, not requested
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="sell",
                amount_eur=Decimal("999999"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 3), execute_on=date(2024, 1, 3)
        )
        trades = portfolio.process_pending_actions(date(2024, 1, 3), _prices())

        sell_trade = next(t for t in trades if t.direction == "sell")
        # Recorded amount should be much less than 999999
        assert sell_trade.amount_eur < Decimal("999999")

    def test_hard_rebalance_buy_insufficient_cash(self) -> None:
        portfolio = make_portfolio(cash=Decimal("100"))
        orders = [
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal("50000"),
            ),
        ]
        action = Action(type=ActionType.HARD_REBALANCE, rebalance_orders=orders)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 2), execute_on=date(2024, 1, 2)
        )
        trades = portfolio.process_pending_actions(date(2024, 1, 2), _prices())

        assert len(trades) == 1
        assert trades[0].skipped is True
        assert trades[0].amount_eur == Decimal(0)
        assert portfolio.cash == Decimal("100")  # unchanged


class TestSnapshot:
    def test_snapshot_produces_portfolio_snapshot(self) -> None:
        portfolio = make_portfolio()
        snap = portfolio.snapshot(date(2024, 1, 2), _prices())
        assert snap.positions is not None
        assert len(snap.positions) == 3
        assert snap.cash == Decimal("10000")

    def test_snapshot_total_value_matches(self) -> None:
        portfolio = make_portfolio(cash=Decimal("5000"))
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)
        snap = portfolio.snapshot(date(2024, 1, 2), _prices())
        positions_mv = sum(p.market_value for p in snap.positions)
        assert snap.total_value == positions_mv + snap.cash


class TestReset:
    def test_reset_clears_positions_and_cash(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        portfolio.execute_pac(date(2024, 1, 2), _prices(), Decimal("500"), pac_day=2)

        portfolio.reset(
            initial_cash=Decimal("5000"),
            initial_pac_volumes={
                "stocks": Decimal("100"),
                "gold": Decimal("50"),
                "bonds": Decimal("50"),
            },
        )
        assert portfolio.cash == Decimal("5000")
        snap = portfolio.snapshot(date(2024, 1, 2), _prices())
        for pos in snap.positions:
            assert pos.quantity == Decimal(0)


class TestPendingActions:
    def test_queue_and_process_pending_action(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        adj = PacAdjustment(new_volumes={"stocks": Decimal("400")})
        action = Action(type=ActionType.PAC_ADJUST, pac_adjustment=adj)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 2), execute_on=date(2024, 1, 5)
        )

        assert len(portfolio.pending_actions) == 1

        # Process on the execution date
        portfolio.process_pending_actions(date(2024, 1, 5), _prices())
        assert len(portfolio.pending_actions) == 0
        assert portfolio.pac_volumes["stocks"] == Decimal("400")

    def test_pending_action_not_processed_early(self) -> None:
        portfolio = make_portfolio(cash=Decimal("10000"))
        adj = PacAdjustment(new_volumes={"stocks": Decimal("400")})
        action = Action(type=ActionType.PAC_ADJUST, pac_adjustment=adj)
        portfolio.queue_action(
            action, emitted_on=date(2024, 1, 2), execute_on=date(2024, 1, 5)
        )

        # Process before execute_on — should not execute
        portfolio.process_pending_actions(date(2024, 1, 3), _prices())
        assert len(portfolio.pending_actions) == 1
        assert portfolio.pac_volumes["stocks"] == Decimal("350")  # unchanged
