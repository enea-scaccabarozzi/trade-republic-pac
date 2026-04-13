from __future__ import annotations

from datetime import date, timedelta

import structlog

from pac.models.market_data import Interval, PriceSeries

logger = structlog.get_logger()


class BacktestMarketContext:
    """MarketContext for backtesting — slices pre-loaded data to simulated date.

    Guarantees zero look-ahead bias: get_prices() returns only bars <= current_date.
    """

    def __init__(
        self,
        price_data: dict[str, PriceSeries],
        current_date: date,
        ticker_map: dict[str, str],
    ) -> None:
        self._price_data = price_data
        self._current_date = current_date
        self._ticker_map = ticker_map

    @property
    def current_date(self) -> date:
        return self._current_date

    def get_prices(self, ticker: str, lookback_days: int) -> PriceSeries:
        series = self._price_data.get(ticker)
        if series is None:
            logger.warning(
                "unknown_ticker_requested",
                ticker=ticker,
                current_date=str(self._current_date),
            )
            return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=[])
        start = self._current_date - timedelta(days=lookback_days)
        return series.slice(start, self._current_date)

    def get_asset_prices(self, asset_id: str, lookback_days: int) -> PriceSeries:
        ticker = self._ticker_map[asset_id]
        return self.get_prices(ticker, lookback_days)
