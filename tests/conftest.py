from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pac.config import Settings
from pac.models.portfolio import AssetClass, PortfolioSnapshot, Position


@pytest.fixture
def sample_positions() -> list[Position]:
    return [
        Position(
            isin="IE00BK5BQT80",
            name="Vanguard FTSE All-World",
            quantity=Decimal("10"),
            price=Decimal("100.00"),
            market_value=Decimal("1000.00"),
            asset_class=AssetClass.STOCKS,
        ),
        Position(
            isin="IE00B4ND3602",
            name="iShares Physical Gold",
            quantity=Decimal("5"),
            price=Decimal("40.00"),
            market_value=Decimal("200.00"),
            asset_class=AssetClass.GOLD,
        ),
        Position(
            isin="IE00B3F81409",
            name="Vanguard Gov Bond",
            quantity=Decimal("5"),
            price=Decimal("20.00"),
            market_value=Decimal("100.00"),
            asset_class=AssetClass.BONDS,
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_positions: list[Position]) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=sample_positions,
        cash=Decimal("200.00"),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


@pytest.fixture
def default_settings() -> Settings:
    return Settings(
        tr_phone_number="+491234567890",
        tr_pin="1234",
        telegram_bot_token="fake-token",
        telegram_chat_id="12345",
        webhook_secret="test-secret",
        job_secret="test-job-secret",
    )
