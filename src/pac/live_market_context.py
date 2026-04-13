from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from pac.models.market_data import DataRequest, Interval, PriceSeries


class LiveMarketContext:
    """MarketContext for production — fetches from yfinance with caching.

    current_date = today (or injected for testing).
    MarketDataProvider is lazy-imported at construction time so this module
    can be imported without yfinance installed.
    """

    def __init__(
        self,
        ticker_map: dict[str, str],
        *,
        reference_date: date | None = None,
    ) -> None:
        # Lazy-import to avoid hard yfinance dependency at module level.
        from pac.backtester.data.provider import MarketDataProvider

        self._provider: Any = MarketDataProvider()
        self._ticker_map = ticker_map
        self._reference_date = reference_date or date.today()

    @property
    def current_date(self) -> date:
        return self._reference_date

    def get_prices(self, ticker: str, lookback_days: int) -> PriceSeries:
        start = self._reference_date - timedelta(days=lookback_days)
        request = DataRequest(
            ticker=ticker,
            start=start,
            end=self._reference_date,
            interval=Interval.DAILY,
        )
        return cast(PriceSeries, self._provider.fetch(request))

    def get_asset_prices(self, asset_id: str, lookback_days: int) -> PriceSeries:
        ticker = self._ticker_map[asset_id]
        return self.get_prices(ticker, lookback_days)
