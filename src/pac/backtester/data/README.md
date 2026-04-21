# Data

Market data access layer for the backtester. Fetches historical OHLCV prices via Yahoo Finance and caches results as JSON on the filesystem.

## Architectural Role

| Aspect      | Details                                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| Depends on  | [`config`](../../config/) (`Settings`, `AssetConfig.ticker`), `yfinance` (optional dep) |
| Consumed by | Backtester simulation engine (Phase 2)                                                  |
| Boundary    | HTTP fetch (yfinance), filesystem cache read/write, Pydantic OHLCV models               |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `config` | `pac.config` | Asset configuration supplies the `ticker` fields used to resolve yfinance symbols | `Settings`, `AssetConfig` |

Note: `backtester/data` defines `PriceSeries` and `PriceBar` in `data/models.py`, re-exported from `pac.models.market_data`. This module has no other internal pac dependencies.

## Key Components

| Component            | File          | Description                                                              |
| -------------------- | ------------- | ------------------------------------------------------------------------ |
| `PriceBar`           | `models.py`   | Single OHLCV bar (frozen Pydantic model, validates `low <= high`)        |
| `PriceSeries`        | `models.py`   | Ordered list of `PriceBar` for one ticker, with `slice()` helper         |
| `Interval`           | `models.py`   | `StrEnum` of supported bar intervals (`1d`, `1wk`, `1mo`)                |
| `DataRequest`        | `models.py`   | Request params: ticker, start/end dates, interval (validates date range) |
| `MarketDataProvider` | `provider.py` | Fetches data via yfinance with transparent filesystem JSON caching       |
| `resolve_tickers()`  | `provider.py` | Builds `asset_id → ticker` mapping from `Settings`, errors on missing    |

## Configuration

`MarketDataProvider` accepts two optional constructor arguments:

| Parameter   | Default            | Description                                |
| ----------- | ------------------ | ------------------------------------------ |
| `cache_dir` | `~/.pac/cache/`    | Directory for cached JSON files            |
| `cache_ttl` | `86400` (24 hours) | Seconds before a cached entry is refetched |

Assets must have a `ticker` field in `pac.yaml` to be used with the backtester:

```yaml
assets:
  - id: stocks
    name: "World ETF"
    isin: IE00B4L5Y983
    target_pct: 70
    ticker: EUNL.DE        # Yahoo Finance ticker — required for backtesting
```

## Usage

```python
from datetime import date
from pac.backtester.data import MarketDataProvider, DataRequest, Interval

provider = MarketDataProvider()

request = DataRequest(
    ticker="EUNL.DE",
    start=date(2023, 1, 1),
    end=date(2023, 12, 31),
    interval=Interval.DAILY,
)
series = provider.fetch(request)
series.bars       # list[PriceBar]
series.start_date # 2023-01-02
series.end_date   # 2023-12-29

# Fetch multiple tickers at once
results = provider.fetch_multiple([request, other_request])

# Resolve tickers from pac.yaml config
from pac.backtester.data.provider import resolve_tickers
tickers = resolve_tickers(settings)  # {"stocks": "EUNL.DE", ...}
```

### Design Notes

**Inclusive end dates:** `DataRequest.end` is user-facing inclusive. Internally, `MarketDataProvider` adds one day because yfinance treats `end` as exclusive.

**Lazy yfinance import:** `yfinance` is imported with a try/except guard. `MarketDataProvider.__init__` raises `ImportError` with install instructions if the package is missing, keeping the core `pac` package free of heavy dependencies.

**Cache key format:** `{ticker}_{interval}_{start}_{end}.json` — deterministic, human-readable filenames.

## Commands

```bash
just test -k test_models       # data model tests (backtester)
just test -k test_provider     # provider + cache tests
```

## See Also

- [Config](../../config/) — `AssetConfig.ticker` field used by `resolve_tickers()`
- [Analysis](../../analysis/) — pure portfolio math consumed by the simulation engine
