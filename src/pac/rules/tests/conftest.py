from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from tests.conftest import make_settings

from pac.config import Settings
from pac.models.market_data import Interval, PriceBar, PriceSeries
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


@pytest.fixture
def default_settings() -> Settings:
    return make_settings()


# ---------------------------------------------------------------------------
# Shared helpers for crisis rule BDD tests
# ---------------------------------------------------------------------------

# Reference date for all crisis rule tests — must match FakeMarketContext default
REF_DATE = date(2026, 4, 1)


def make_price_series(
    ticker: str,
    days: int,
    *,
    start_price: float = 100.0,
    daily_return: float = 0.0,
    start_date: date | None = None,
    crash_at_day: int | None = None,
    crash_pct: float = 0.0,
    crash_duration: int = 1,
    end_date: date | None = None,
) -> PriceSeries:
    """Generate synthetic PriceSeries for testing.

    Args:
        ticker: Ticker symbol for the series.
        days: Number of bars to generate.
        start_price: Opening price on day 0.
        daily_return: Constant daily return (0.001 = +0.1%/day).
        start_date: First bar date. If None and end_date is set, computed
            from end_date. Otherwise defaults to 2025-01-02.
        crash_at_day: Day index to start a crash.
        crash_pct: Total crash percentage (negative, e.g. -0.25 = -25%).
        crash_duration: Days over which the crash occurs.
        end_date: Last bar date. Useful for aligning with FakeMarketContext.
    """
    if start_date is None:
        if end_date is not None:
            start_date = end_date - timedelta(days=days - 1)
        else:
            start_date = date(2025, 1, 2)

    bars: list[PriceBar] = []
    price = start_price

    for i in range(days):
        bar_date = start_date + timedelta(days=i)

        if (
            crash_at_day is not None
            and crash_duration > 0
            and crash_at_day <= i < crash_at_day + crash_duration
        ):
            daily_crash = crash_pct / crash_duration
            price = price * (1.0 + daily_crash)
        else:
            price = price * (1.0 + daily_return)

        close = Decimal(str(round(price, 4)))
        bars.append(
            PriceBar(
                date=bar_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1_000_000,
            ),
        )

    return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=bars)


@dataclass
class FakeMarketContext:
    """Fake MarketContext for testing crisis rules.

    Implements the MarketContext protocol with configurable PriceSeries
    per asset_id.
    """

    _prices: dict[str, PriceSeries] = field(default_factory=dict)
    _ticker_map: dict[str, str] = field(default_factory=dict)
    _current_date: date = field(default_factory=lambda: date(2026, 4, 1))

    @property
    def current_date(self) -> date:
        return self._current_date

    def get_prices(self, ticker: str, lookback_days: int) -> PriceSeries:
        if ticker not in self._prices:
            raise KeyError(ticker)
        series = self._prices[ticker]
        cutoff = self._current_date - timedelta(days=lookback_days)
        return series.slice(cutoff, self._current_date)

    def get_asset_prices(self, asset_id: str, lookback_days: int) -> PriceSeries:
        if asset_id not in self._ticker_map:
            raise KeyError(asset_id)
        ticker = self._ticker_map[asset_id]
        return self.get_prices(ticker, lookback_days)
