from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, computed_field


class Position(BaseModel):
    """A single portfolio position."""

    isin: str
    name: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    asset_id: str


class Allocation(BaseModel):
    """Allocation breakdown for a single asset."""

    asset_id: str
    actual_pct: Decimal
    target_pct: Decimal


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state."""

    positions: list[Position]
    cash: Decimal
    timestamp: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_value(self) -> Decimal:
        """Total portfolio value including cash."""
        return sum((p.market_value for p in self.positions), Decimal(0)) + self.cash

    def allocations(self, asset_ids: list[str]) -> dict[str, Allocation]:
        """Compute allocation percentages for the given asset IDs.

        Args:
            asset_ids: Dynamic list of asset IDs from config.

        Returns:
            Mapping of asset ID to its Allocation breakdown.
        """
        if self.total_value == 0:
            return {
                aid: Allocation(
                    asset_id=aid, actual_pct=Decimal(0), target_pct=Decimal(0)
                )
                for aid in asset_ids
            }
        result: dict[str, Allocation] = {}
        for aid in asset_ids:
            class_value = sum(
                (p.market_value for p in self.positions if p.asset_id == aid),
                Decimal(0),
            )
            actual_pct = (class_value / self.total_value) * 100
            result[aid] = Allocation(
                asset_id=aid, actual_pct=actual_pct, target_pct=Decimal(0)
            )
        return result


class SavingsPlan(BaseModel):
    """A configured savings plan (PAC)."""

    isin: str
    name: str
    amount: Decimal
    interval: str
    asset_id: str | None = None
