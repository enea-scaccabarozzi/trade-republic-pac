from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import structlog
from pydantic import BaseModel

from pac.backtester.data.models import PriceBar
from pac.backtester.engine.actions import (
    Action,
    ActionType,
    ExecutedTrade,
    HardRebalanceOrder,
    PacAdjustment,
    PendingAction,
)
from pac.models.portfolio import PortfolioSnapshot, Position

log = structlog.get_logger()

_CENTS = Decimal("0.01")
_BPS_DIVISOR = Decimal("10000")


class SimulatedPosition(BaseModel):
    """Internal position tracking for the simulation."""

    asset_id: str
    isin: str
    name: str
    quantity: Decimal = Decimal(0)
    avg_cost: Decimal = Decimal(0)


class SimulatedPortfolio:
    """Mutable portfolio state machine for backtesting.

    Tracks positions, cash, PAC volumes, and pending (slippage-delayed)
    actions. Provides methods to execute PAC buys and hard rebalance
    orders, and to build PortfolioSnapshot instances compatible with
    the live analysis pipeline.
    """

    def __init__(
        self,
        assets: dict[str, SimulatedPosition],
        cash: Decimal,
        pac_volumes: dict[str, Decimal],
        settlement_fee: Decimal,
        spread_bps: Decimal,
        pac_execution_days: list[int],
    ) -> None:
        self._assets = assets
        self._cash = cash
        self._pac_volumes = dict(pac_volumes)
        self._settlement_fee = settlement_fee
        self._spread_bps = spread_bps
        self._pac_execution_days = pac_execution_days
        self._pending_actions: list[PendingAction] = []
        self._trade_log: list[ExecutedTrade] = []
        self._pac_months_applied: set[tuple[int, int, int]] = set()
        # Tracks (year, month, pac_day) to avoid double-contribution

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def pac_volumes(self) -> dict[str, Decimal]:
        return dict(self._pac_volumes)

    @property
    def trade_log(self) -> list[ExecutedTrade]:
        return list(self._trade_log)

    @property
    def pending_actions(self) -> list[PendingAction]:
        return list(self._pending_actions)

    def queue_action(self, action: Action, emitted_on: date, execute_on: date) -> None:
        """Queue an action for future execution (slippage delay)."""
        self._pending_actions.append(
            PendingAction(action=action, emitted_on=emitted_on, execute_on=execute_on),
        )

    def process_pending_actions(
        self,
        current_date: date,
        prices: dict[str, PriceBar],
    ) -> list[ExecutedTrade]:
        """Execute any pending actions whose execute_on <= current_date.

        Returns list of trades executed this step.
        """
        ready = [pa for pa in self._pending_actions if pa.execute_on <= current_date]
        self._pending_actions = [
            pa for pa in self._pending_actions if pa.execute_on > current_date
        ]

        trades: list[ExecutedTrade] = []
        for pa in ready:
            trades.extend(self._execute_action(pa.action, current_date, prices))
        return trades

    def _execute_action(
        self,
        action: Action,
        current_date: date,
        prices: dict[str, PriceBar],
    ) -> list[ExecutedTrade]:
        """Dispatch action to the appropriate handler."""
        if action.type == ActionType.PAC_ADJUST and action.pac_adjustment:
            self._apply_pac_adjustment(action.pac_adjustment)
            return []
        if action.type == ActionType.HARD_REBALANCE and action.rebalance_orders:
            return self._execute_rebalance_orders(
                action.rebalance_orders,
                current_date,
                prices,
            )
        return []

    def apply_pac_adjustment(self, adj: PacAdjustment) -> None:
        """Apply a PAC volume adjustment (public API for strategy hook)."""
        self._apply_pac_adjustment(adj)

    def _apply_pac_adjustment(self, adj: PacAdjustment) -> None:
        """Update PAC volumes (takes effect on next PAC date)."""
        for asset_id, amount in adj.new_volumes.items():
            self._pac_volumes[asset_id] = amount

    def _execute_rebalance_orders(
        self,
        orders: list[HardRebalanceOrder],
        current_date: date,
        prices: dict[str, PriceBar],
    ) -> list[ExecutedTrade]:
        """Execute hard rebalance orders with fee + spread.

        Buy orders are skipped if cash is insufficient (amount + fee).
        Sell orders are capped at held quantity; the recorded amount_eur
        reflects the *actual* executed amount, not the requested amount.
        """
        trades: list[ExecutedTrade] = []
        for order in orders:
            bar = prices.get(order.asset_id)
            if bar is None:
                continue  # No price data for this asset on this day

            # Apply spread to execution price
            spread_factor = self._spread_bps / _BPS_DIVISOR
            if order.direction == "buy":
                exec_price = bar.close * (1 + spread_factor)
            else:
                exec_price = bar.close * (1 - spread_factor)

            quantity = (order.amount_eur / exec_price).quantize(
                Decimal("0.000001"),
                rounding=ROUND_HALF_UP,
            )

            pos = self._assets[order.asset_id]
            if order.direction == "buy":
                # Cash-sufficiency check: skip if not enough cash
                if self._cash < order.amount_eur + self._settlement_fee:
                    log.warning(
                        "hard_rebalance_buy_skipped",
                        asset_id=order.asset_id,
                        requested=str(order.amount_eur),
                        available_cash=str(self._cash),
                        reason="insufficient_cash",
                    )
                    trades.append(
                        ExecutedTrade(
                            date=current_date,
                            type="hard_rebalance",
                            asset_id=order.asset_id,
                            direction=order.direction,
                            amount_eur=Decimal(0),
                            quantity=Decimal(0),
                            price=exec_price,
                            fee=Decimal(0),
                            skipped=True,
                        ),
                    )
                    continue

                self._cash -= order.amount_eur + self._settlement_fee
                total_cost = pos.avg_cost * pos.quantity + order.amount_eur
                pos.quantity += quantity
                pos.avg_cost = (
                    (total_cost / pos.quantity).quantize(_CENTS, rounding=ROUND_HALF_UP)
                    if pos.quantity > 0
                    else Decimal(0)
                )
                recorded_amount = order.amount_eur
            else:
                sell_qty = min(quantity, pos.quantity)
                actual_amount = (sell_qty * exec_price).quantize(
                    _CENTS,
                    rounding=ROUND_HALF_UP,
                )
                self._cash += actual_amount - self._settlement_fee
                pos.quantity -= sell_qty
                quantity = sell_qty
                # Record the actual executed amount, not the requested amount
                recorded_amount = actual_amount

            trades.append(
                ExecutedTrade(
                    date=current_date,
                    type="hard_rebalance",
                    asset_id=order.asset_id,
                    direction=order.direction,
                    amount_eur=recorded_amount,
                    quantity=quantity,
                    price=exec_price,
                    fee=self._settlement_fee,
                ),
            )

        self._trade_log.extend(trades)
        return trades

    def execute_pac(
        self,
        current_date: date,
        prices: dict[str, PriceBar],
        monthly_contribution: Decimal,
        pac_day: int,
    ) -> list[ExecutedTrade]:
        """Execute a PAC buy on a PAC date.

        Adds monthly contribution to cash, then buys each asset
        according to pac_volumes. Fee-free.

        Uses (year, month, pac_day) tracking to avoid double contributions
        when the same PAC day is processed (shouldn't happen with clock,
        but defensive).
        """
        key = (current_date.year, current_date.month, pac_day)
        if key in self._pac_months_applied:
            return []
        self._pac_months_applied.add(key)

        # Add monthly contribution (split evenly across configured PAC days)
        # Supports 1, 2, or more PAC days — not hardcoded to 2
        contribution_per_pac = monthly_contribution / Decimal(
            len(self._pac_execution_days),
        )
        self._cash += contribution_per_pac

        trades: list[ExecutedTrade] = []
        for asset_id, volume in self._pac_volumes.items():
            bar = prices.get(asset_id)
            if bar is None or volume <= 0:
                continue

            # PAC buys at close price, no spread, no fee
            quantity = (volume / bar.close).quantize(
                Decimal("0.000001"),
                rounding=ROUND_HALF_UP,
            )

            if self._cash < volume:
                # Not enough cash — buy what we can
                volume = self._cash
                quantity = (volume / bar.close).quantize(
                    Decimal("0.000001"),
                    rounding=ROUND_HALF_UP,
                )

            pos = self._assets[asset_id]
            total_cost = pos.avg_cost * pos.quantity + volume
            pos.quantity += quantity
            pos.avg_cost = (
                (total_cost / pos.quantity).quantize(_CENTS, rounding=ROUND_HALF_UP)
                if pos.quantity > 0
                else Decimal(0)
            )
            self._cash -= volume

            trades.append(
                ExecutedTrade(
                    date=current_date,
                    type="pac_execution",
                    asset_id=asset_id,
                    direction="buy",
                    amount_eur=volume,
                    quantity=quantity,
                    price=bar.close,
                    fee=Decimal(0),
                ),
            )

        self._trade_log.extend(trades)
        return trades

    def snapshot(
        self,
        current_date: date,
        prices: dict[str, PriceBar],
    ) -> PortfolioSnapshot:
        """Build a PortfolioSnapshot from current state.

        This produces the same model used by the live pipeline — signal
        rules receive this and cannot distinguish simulated from real.
        """
        positions: list[Position] = []
        for asset_id, pos in self._assets.items():
            bar = prices.get(asset_id)
            price = bar.close if bar else Decimal(0)
            market_value = (pos.quantity * price).quantize(
                _CENTS,
                rounding=ROUND_HALF_UP,
            )
            positions.append(
                Position(
                    isin=pos.isin,
                    name=pos.name,
                    quantity=pos.quantity,
                    price=price,
                    market_value=market_value,
                    asset_id=asset_id,
                ),
            )

        return PortfolioSnapshot(
            positions=positions,
            cash=self._cash,
            timestamp=datetime.combine(current_date, datetime.min.time()),
        )

    def reset(
        self,
        initial_cash: Decimal,
        initial_pac_volumes: dict[str, Decimal],
    ) -> None:
        """Reset portfolio to initial state for a new MC iteration."""
        self._cash = initial_cash
        self._pac_volumes = dict(initial_pac_volumes)
        self._pending_actions.clear()
        self._trade_log.clear()
        self._pac_months_applied.clear()
        for pos in self._assets.values():
            pos.quantity = Decimal(0)
            pos.avg_cost = Decimal(0)

    def total_value(self, prices: dict[str, PriceBar]) -> Decimal:
        """Current total portfolio value (positions + cash)."""
        position_value = sum(
            (
                pos.quantity * (prices[aid].close if aid in prices else Decimal(0))
                for aid, pos in self._assets.items()
            ),
            Decimal(0),
        )
        return position_value + self._cash
