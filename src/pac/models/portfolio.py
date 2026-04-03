from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, computed_field


class AssetClass(StrEnum):
    """Supported asset classes for portfolio allocation."""

    STOCKS = "stocks"
    GOLD = "gold"
    BONDS = "bonds"


class Position(BaseModel):
    """A single portfolio position."""

    isin: str
    name: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    asset_class: AssetClass


class Allocation(BaseModel):
    """Allocation breakdown for a single asset class."""

    asset_class: AssetClass
    actual_pct: Decimal
    target_pct: Decimal


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state with computed allocations."""

    positions: list[Position]
    cash: Decimal
    timestamp: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_value(self) -> Decimal:
        """Total portfolio value including cash."""
        return sum((p.market_value for p in self.positions), Decimal(0)) + self.cash

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allocations(self) -> dict[AssetClass, Allocation]:
        """Current allocation percentages per asset class."""
        if self.total_value == 0:
            return {
                ac: Allocation(
                    asset_class=ac, actual_pct=Decimal(0), target_pct=Decimal(0)
                )
                for ac in AssetClass
            }
        result: dict[AssetClass, Allocation] = {}
        for ac in AssetClass:
            class_value = sum(
                (p.market_value for p in self.positions if p.asset_class == ac),
                Decimal(0),
            )
            actual_pct = (class_value / self.total_value) * 100
            result[ac] = Allocation(
                asset_class=ac, actual_pct=actual_pct, target_pct=Decimal(0)
            )
        return result


class SavingsPlan(BaseModel):
    """A configured savings plan (PAC)."""

    isin: str
    name: str
    amount: Decimal
    interval: str
    asset_class: AssetClass | None = None
