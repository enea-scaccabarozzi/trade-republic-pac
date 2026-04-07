from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ActionType(StrEnum):
    """Types of actions a strategy can emit."""

    PAC_ADJUST = "pac_adjust"
    HARD_REBALANCE = "hard_rebalance"


class PacAdjustment(BaseModel, frozen=True):
    """Adjust PAC volumes — applied on next PAC date, fee-free.

    new_volumes maps asset_id → monthly EUR amount per PAC execution.
    """

    new_volumes: dict[str, Decimal]


class HardRebalanceOrder(BaseModel, frozen=True):
    """Single buy/sell order — €1 fee + spread per order."""

    asset_id: str
    direction: Literal["buy", "sell"]
    amount_eur: Decimal = Field(gt=0)


class Action(BaseModel, frozen=True):
    """A strategy-emitted action."""

    type: ActionType
    pac_adjustment: PacAdjustment | None = None
    rebalance_orders: list[HardRebalanceOrder] | None = None


class PendingAction(BaseModel):
    """An action delayed by human slippage.

    execute_on is the date when the action should fire
    (original date + sampled slippage days).
    """

    action: Action
    emitted_on: date
    execute_on: date


class ExecutedTrade(BaseModel, frozen=True):
    """Record of a single executed trade (for trade log).

    amount_eur is the *actual* executed amount — for partial sells
    (capped at held quantity), this may be less than the requested
    amount. For skipped trades, amount_eur and quantity are zero.
    """

    date: date
    type: Literal["pac_execution", "hard_rebalance"]
    asset_id: str
    direction: Literal["buy", "sell"]
    amount_eur: Decimal
    quantity: Decimal
    price: Decimal
    fee: Decimal
    skipped: bool = False
