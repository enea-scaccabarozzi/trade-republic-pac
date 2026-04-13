from __future__ import annotations

import json
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast

import structlog

from pac.backtester.data.fx import convert_to_eur
from pac.backtester.data.models import (
    DataRequest,
    Interval,
    PriceBar,
    PriceSeries,
)
from pac.config import Settings

if TYPE_CHECKING:
    from pac.config.models import ProxySpec

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

    def fetch_with_proxy(
        self,
        ticker: str,
        start: date,
        end: date,
        proxy_chain: list[ProxySpec] | None = None,
        primary_currency: str | None = None,
        # Legacy compat (ignored if proxy_chain provided):
        proxy_ticker: str | None = None,
        proxy_end: date | None = None,
    ) -> PriceSeries:
        """Fetch price data, stitching chained proxy data for early dates.

        Two-pass right-to-left algorithm:
          Pass 1 — Build segment specs, fetch each independently, FX-convert.
          Pass 2 — Right-to-left normalization anchored to primary prices.

        Backward-compatible: if proxy_chain is None, falls back to
        legacy proxy_ticker/proxy_end behavior (converted to chain of 1).
        """
        from pac.config.models import ProxySpec

        # Legacy fallback
        if proxy_chain is None and proxy_ticker and proxy_end:
            proxy_chain = [ProxySpec(ticker=proxy_ticker, end=proxy_end)]

        if not proxy_chain or start > proxy_chain[-1].end:
            # No proxy needed — entire range is primary
            series = self.fetch(DataRequest(ticker=ticker, start=start, end=end))
            if primary_currency and primary_currency != "EUR":
                series = convert_to_eur(series, primary_currency, self.fetch)
            return series

        # ── Pass 1: Build segment specs and fetch each ──
        SegmentSpec = tuple[
            str, date, date, str | None
        ]  # (ticker, start, end, currency)
        segment_specs: list[SegmentSpec] = []

        for i, spec in enumerate(proxy_chain):
            seg_start = start if i == 0 else proxy_chain[i - 1].end + timedelta(days=1)
            seg_end = min(spec.end, end)
            if seg_start <= seg_end:
                segment_specs.append((spec.ticker, seg_start, seg_end, spec.currency))

        # Primary segment (after last proxy)
        if end > proxy_chain[-1].end:
            primary_start = proxy_chain[-1].end + timedelta(days=1)
            segment_specs.append((ticker, primary_start, end, primary_currency))

        # Fetch & FX-convert each segment independently
        segments: list[list[PriceBar]] = []
        for seg_ticker, seg_start, seg_end, seg_currency in segment_specs:
            series = self.fetch(
                DataRequest(ticker=seg_ticker, start=seg_start, end=seg_end)
            )
            if seg_currency and seg_currency != "EUR":
                series = convert_to_eur(series, seg_currency, self.fetch)
            segments.append(list(series.bars))

        if not segments:
            return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=[])

        # ── Pass 2: Right-to-left normalization ──
        for i in range(len(segments) - 2, -1, -1):
            left_seg = segments[i]
            right_seg = segments[i + 1]

            if not left_seg or not right_seg:
                continue

            # Validate continuity at this handoff boundary
            handoff_date = segment_specs[i][2]
            validate_handoff(
                proxy_bars=left_seg,
                primary_bars=right_seg,
                handoff_date=handoff_date,
                proxy_ticker=segment_specs[i][0],
                primary_ticker=segment_specs[i + 1][0],
            )

            if left_seg[-1].close == 0:
                msg = f"Proxy close price is 0 on {left_seg[-1].date}, cannot normalize"
                raise ValueError(msg)

            ratio = right_seg[0].close / left_seg[-1].close

            segments[i] = [
                PriceBar(
                    date=b.date,
                    open=b.open * ratio,
                    high=b.high * ratio,
                    low=b.low * ratio,
                    close=b.close * ratio,
                    volume=b.volume,
                )
                for b in left_seg
            ]

        # Concatenate in chronological order
        all_bars: list[PriceBar] = []
        for seg in segments:
            all_bars.extend(seg)

        return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=all_bars)


_MAX_GAP_DAYS = 5  # Max allowed gap between proxy end and primary start


def normalize_and_stitch(
    primary_bars: list[PriceBar],
    proxy_bars: list[PriceBar],
    handoff_date: date,
) -> list[PriceBar]:
    """Stitch proxy bars onto primary bars with ratio-based normalization.

    At the handoff point:
    1. Find the last proxy bar on or before handoff_date
    2. Find the first primary bar after handoff_date
    3. Compute ratio = primary_first_close / proxy_last_close
    4. Scale ALL proxy bar prices by this ratio
    5. Concatenate: scaled_proxy_bars + primary_bars
    """
    proxy_before = [b for b in proxy_bars if b.date <= handoff_date]
    primary_after = [b for b in primary_bars if b.date > handoff_date]

    if not proxy_before or not primary_after:
        return proxy_before + primary_after

    proxy_last_close = proxy_before[-1].close
    primary_first_close = primary_after[0].close

    if proxy_last_close == 0:
        msg = f"Proxy close price is 0 on {proxy_before[-1].date}, cannot normalize"
        raise ValueError(msg)

    ratio = primary_first_close / proxy_last_close

    scaled_proxy = [
        PriceBar(
            date=b.date,
            open=b.open * ratio,
            high=b.high * ratio,
            low=b.low * ratio,
            close=b.close * ratio,
            volume=b.volume,
        )
        for b in proxy_before
    ]

    return scaled_proxy + primary_after


def validate_handoff(
    proxy_bars: list[PriceBar],
    primary_bars: list[PriceBar],
    handoff_date: date,
    proxy_ticker: str,
    primary_ticker: str,
) -> None:
    """Validate data continuity at a proxy→primary handoff point.

    Raises:
        ValueError: If gap between last proxy bar and first primary bar
                     exceeds _MAX_GAP_DAYS.
    """
    proxy_end_bars = [b for b in proxy_bars if b.date <= handoff_date]
    primary_start_bars = [b for b in primary_bars if b.date > handoff_date]

    if not proxy_end_bars:
        msg = (
            f"No proxy data for '{proxy_ticker}' on or before handoff "
            f"date {handoff_date}"
        )
        raise ValueError(msg)

    if not primary_start_bars:
        msg = (
            f"No primary data for '{primary_ticker}' after handoff date {handoff_date}"
        )
        raise ValueError(msg)

    gap = (primary_start_bars[0].date - proxy_end_bars[-1].date).days
    if gap > _MAX_GAP_DAYS:
        msg = (
            f"Data gap of {gap} days at handoff {handoff_date}: "
            f"'{proxy_ticker}' ends {proxy_end_bars[-1].date}, "
            f"'{primary_ticker}' starts {primary_start_bars[0].date}. "
            f"Max allowed: {_MAX_GAP_DAYS} days."
        )
        raise ValueError(msg)


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
