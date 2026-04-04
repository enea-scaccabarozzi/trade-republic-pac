from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pac.models.portfolio import PortfolioSnapshot, Position


@pytest.fixture
def sample_positions() -> list[Position]:
    return [
        Position(
            isin="IE00BK5BQT80",
            name="Vanguard FTSE All-World",
            quantity=Decimal("10"),
            price=Decimal("100.00"),
            market_value=Decimal("1000.00"),
            asset_id="stocks",
        ),
        Position(
            isin="IE00B4ND3602",
            name="iShares Physical Gold",
            quantity=Decimal("5"),
            price=Decimal("40.00"),
            market_value=Decimal("200.00"),
            asset_id="gold",
        ),
        Position(
            isin="IE00B3F81409",
            name="Vanguard Gov Bond",
            quantity=Decimal("5"),
            price=Decimal("20.00"),
            market_value=Decimal("100.00"),
            asset_id="bonds",
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_positions: list[Position]) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=sample_positions,
        cash=Decimal("200.00"),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )
