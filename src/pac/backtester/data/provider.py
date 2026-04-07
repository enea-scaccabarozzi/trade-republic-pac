from __future__ import annotations

import json
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import structlog

from pac.backtester.data.models import (
    DataRequest,
    PriceBar,
    PriceSeries,
)
from pac.config import Settings

try:
    import yfinance as yf
except ImportError:
    _yf_import_error: ImportError | None = ImportError("yfinance not installed")
    yf = None  # type: ignore[unused-ignore,assignment]
else:
    _yf_import_error = None

log = structlog.get_logger()

_DEFAULT_CACHE_DIR = Path.home() / ".pac" / "cache"
_DEFAULT_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds


class MarketDataProvider:
    """Fetches historical OHLCV data via yfinance with filesystem JSON caching.

    Fetched ``PriceSeries`` results are serialized as JSON to a configurable
    cache directory (default ``~/.pac/cache/``).  Cache key is
    ``{ticker}_{interval}_{start}_{end}.json``.  Entries older than
    ``cache_ttl`` seconds are treated as stale and re-fetched.

    Raises:
        ImportError: If yfinance is not installed (backtest extras missing).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = _DEFAULT_CACHE_TTL,
    ) -> None:
        if yf is None:
            msg = (
                "yfinance is required for backtesting. "
                "Install with: uv sync --group backtest"
            )
            raise ImportError(msg) from _yf_import_error
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = cache_ttl

    # -- cache helpers --------------------------------------------------- #

    def _cache_key(self, request: DataRequest) -> Path:
        name = (
            f"{request.ticker}_{request.interval.value}"
            f"_{request.start}_{request.end}.json"
        )
        return self._cache_dir / name

    def _read_cache(self, key: Path) -> PriceSeries | None:
        if not key.exists():
            return None
        age = time.time() - key.stat().st_mtime
        if age > self._cache_ttl:
            return None
        raw = json.loads(key.read_text())
        return PriceSeries.model_validate(raw)

    def _write_cache(self, key: Path, series: PriceSeries) -> None:
        key.write_text(series.model_dump_json(indent=2))

    def clear_cache(self) -> int:
        """Delete all cached JSON files. Returns the number of files removed."""
        count = 0
        for p in self._cache_dir.glob("*.json"):
            p.unlink()
            count += 1
        return count

    # -- public API ------------------------------------------------------ #

    def fetch(self, request: DataRequest) -> PriceSeries:
        """Fetch OHLCV data for a single ticker.

        Checks the filesystem cache first.  On a miss, fetches from yfinance,
        caches the result, and returns it.

        Note: ``DataRequest.end`` is **inclusive** (user-facing contract).
        Internally we add one day because yfinance treats ``end`` as exclusive.

        Args:
            request: Validated data request with ticker, date range, interval.

        Returns:
            PriceSeries with one PriceBar per trading day in range.

        Raises:
            ValueError: If yfinance returns no data for the ticker/range.
        """
        cache_key = self._cache_key(request)
        cached = self._read_cache(cache_key)
        if cached is not None:
            log.debug("cache_hit", ticker=request.ticker, key=cache_key.name)
            return cached

        # yfinance treats `end` as exclusive — add one day so the user's
        # inclusive end date is actually included in the result.
        yf_end = (request.end + timedelta(days=1)).isoformat()

        ticker = yf.Ticker(request.ticker)
        df = ticker.history(
            start=request.start.isoformat(),
            end=yf_end,
            interval=request.interval.value,
            auto_adjust=True,
        )
        if df.empty:
            msg = (
                f"No data returned for {request.ticker} "
                f"from {request.start} to {request.end}"
            )
            raise ValueError(msg)

        bars = [
            PriceBar(
                date=idx.date(),
                open=Decimal(str(row["Open"])),
                high=Decimal(str(row["High"])),
                low=Decimal(str(row["Low"])),
                close=Decimal(str(row["Close"])),
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]
        series = PriceSeries(
            ticker=request.ticker,
            interval=request.interval,
            bars=bars,
        )

        self._write_cache(cache_key, series)
        log.info(
            "fetched_market_data",
            ticker=request.ticker,
            bars=len(bars),
            start=str(request.start),
            end=str(request.end),
        )
        return series

    def fetch_multiple(
        self,
        requests: list[DataRequest],
    ) -> dict[str, PriceSeries]:
        """Fetch data for multiple tickers.

        Args:
            requests: List of data requests (one per ticker).

        Returns:
            Mapping of ticker → PriceSeries.
        """
        return {req.ticker: self.fetch(req) for req in requests}


def resolve_tickers(settings: Settings) -> dict[str, str]:
    """Build asset_id → ticker mapping from config.

    Args:
        settings: App settings with asset configs.

    Returns:
        Mapping of asset_id → Yahoo ticker.

    Raises:
        ValueError: If any asset is missing a ticker.
    """
    missing = [a.id for a in settings.assets if a.ticker is None]
    if missing:
        msg = (
            f"Assets missing 'ticker' field (required for backtesting): "
            f"{', '.join(missing)}. Add ticker to each asset in pac.yaml."
        )
        raise ValueError(msg)
    # All tickers are non-None after the missing check above.
    return {a.id: cast(str, a.ticker) for a in settings.assets}
