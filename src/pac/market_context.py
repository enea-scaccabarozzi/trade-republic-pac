from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pac.models.market_data import PriceSeries


class MarketContext(Protocol):
    """Date-aware access to historical price data.

    Rules call get_prices() with a ticker and lookback window.
    The implementation controls what "now" means:
      - Production: today
      - Backtesting: the simulated date (look-ahead protection)
    """

    @property
    def current_date(self) -> date:
        """The reference date for this context."""
        ...

    def get_prices(self, ticker: str, lookback_days: int) -> PriceSeries:
        """Return price bars ending at current_date.

        Args:
            ticker: Yahoo Finance ticker symbol.
            lookback_days: Number of calendar days to look back from current_date.

        Returns:
            PriceSeries filtered to [current_date - lookback_days, current_date].
        """
        ...

    def get_asset_prices(self, asset_id: str, lookback_days: int) -> PriceSeries:
        """Convenience: resolve asset_id -> ticker, then call get_prices().

        Args:
            asset_id: Internal asset identifier (e.g. "stocks").
            lookback_days: Number of calendar days to look back.

        Returns:
            PriceSeries for the resolved ticker.

        Raises:
            KeyError: If asset_id has no ticker mapping.
        """
        ...
