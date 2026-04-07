from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from pytest_bdd import given, parsers, scenarios, then, when

from pac.backtester.data.models import (
    DataRequest,
    Interval,
    PriceBar,
    PriceSeries,
)
from pac.backtester.data.provider import MarketDataProvider, resolve_tickers
from pac.config.models import Settings

scenarios("../features/market_data.feature")


def _make_settings(**overrides: Any) -> Settings:
    """Build a Settings instance with test defaults."""
    base: dict[str, Any] = {
        "version": 1,
        "broker": {
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
        },
        "assets": [
            {
                "id": "stocks",
                "name": "Stocks ETF",
                "isin": "IE00BK5BQT80",
                "ticker": "EUNL.DE",
                "target_pct": 70,
            },
            {
                "id": "gold",
                "name": "Gold ETC",
                "isin": "IE00B4ND3602",
                "ticker": "4GLD.DE",
                "target_pct": 15,
            },
            {
                "id": "bonds",
                "name": "Bond ETF",
                "isin": "IE00B3F81409",
                "ticker": "EUN4.DE",
                "target_pct": 15,
            },
        ],
        "app": {"job_secret": "test-job-secret"},
        "channels": {},
        "signals": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _make_df(rows: list[dict[str, Any]]) -> Any:
    """Build a pandas DataFrame from row dicts."""
    import pandas as pd

    df = pd.DataFrame(rows)
    if rows:
        df.index = pd.to_datetime(df.pop("Date"))
    return df


def _generate_sample_rows(
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Generate daily OHLCV rows for trading days in range."""
    rows: list[dict[str, Any]] = []
    current = start
    while current <= end:
        # Skip weekends (approximate trading days)
        if current.weekday() < 5:
            rows.append(
                {
                    "Date": current.isoformat(),
                    "Open": 100.0 + len(rows),
                    "High": 105.0 + len(rows),
                    "Low": 99.0 + len(rows),
                    "Close": 103.0 + len(rows),
                    "Volume": 1_000_000,
                }
            )
        from datetime import timedelta

        current += timedelta(days=1)
    return rows


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# -- Background ----------------------------------------------------------


@given("the backtest dependency group is installed")
def _backtest_installed() -> None:
    """Prerequisite — yfinance is available in the test environment."""


# -- Fetch daily price data -----------------------------------------------


@given(
    parsers.parse('a data request for "{ticker}" from "{start}" to "{end}"'),
    target_fixture="ctx",
)
def _data_request(
    ctx: dict[str, Any],
    ticker: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    ctx["request"] = DataRequest(
        ticker=ticker,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
    )
    return ctx


@when("market data is fetched", target_fixture="ctx")
def _fetch_market_data(ctx: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    request: DataRequest = ctx["request"]

    # Simulate empty data for obviously invalid tickers
    if request.ticker.startswith("XXXXX"):
        rows: list[dict[str, Any]] = []
    else:
        rows = _generate_sample_rows(request.start, request.end)
    df = _make_df(rows)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("pac.backtester.data.provider.yf") as mock_yf:
        mock_yf.Ticker.return_value = mock_ticker
        provider = MarketDataProvider(cache_dir=tmp_path)
        try:
            ctx["result"] = provider.fetch(request)
        except (ValueError, ImportError) as exc:
            ctx["error"] = exc

    return ctx


@then(
    parsers.parse("a price series is returned with at least {count:d} bars"),
)
def _check_bar_count(ctx: dict[str, Any], count: int) -> None:
    series: PriceSeries = ctx["result"]
    assert len(series) >= count


@then("each bar has open, high, low, close, and volume fields")
def _check_bar_fields(ctx: dict[str, Any]) -> None:
    series: PriceSeries = ctx["result"]
    for bar in series.bars:
        assert bar.open is not None
        assert bar.high is not None
        assert bar.low is not None
        assert bar.close is not None
        assert bar.volume is not None


@then("all prices are positive decimals")
def _check_positive_decimals(ctx: dict[str, Any]) -> None:
    series: PriceSeries = ctx["result"]
    for bar in series.bars:
        assert isinstance(bar.open, Decimal)
        assert bar.open > 0
        assert bar.close > 0


# -- No data returned for invalid ticker -----------------------------------


@then(parsers.parse('a ValueError is raised mentioning "{message}"'))
def _check_value_error(ctx: dict[str, Any], message: str) -> None:
    assert "error" in ctx
    assert isinstance(ctx["error"], ValueError)
    assert message in str(ctx["error"])


# -- Date range validation -------------------------------------------------


@given(
    parsers.parse(
        'a data request with start "{start}" after end "{end}"',
    ),
    target_fixture="ctx",
)
def _invalid_date_range(
    ctx: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    try:
        DataRequest(
            ticker="EUNL.DE",
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
        )
        ctx["validation_error"] = None
    except ValidationError as exc:
        ctx["validation_error"] = exc
    return ctx


@then("the request is rejected with a validation error")
def _check_validation_error(ctx: dict[str, Any]) -> None:
    assert ctx.get("validation_error") is not None


# -- Price bar rejects low above high --------------------------------------


@given(
    parsers.parse('a price bar with low "{low}" and high "{high}"'),
    target_fixture="ctx",
)
def _invalid_price_bar(
    ctx: dict[str, Any],
    low: str,
    high: str,
) -> dict[str, Any]:
    try:
        PriceBar(
            date=date(2024, 1, 2),
            open=Decimal("100"),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal("100"),
            volume=1000,
        )
        ctx["validation_error"] = None
    except ValidationError as exc:
        ctx["validation_error"] = exc
    return ctx


@then("the bar is rejected with a validation error")
def _check_bar_validation_error(ctx: dict[str, Any]) -> None:
    assert ctx.get("validation_error") is not None


# -- Resolve tickers -------------------------------------------------------


@given("assets configured with tickers in pac.yaml", target_fixture="ctx")
def _assets_with_tickers(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx["settings"] = _make_settings()
    return ctx


@when("tickers are resolved from settings", target_fixture="ctx")
def _resolve_tickers(ctx: dict[str, Any]) -> dict[str, Any]:
    try:
        ctx["ticker_map"] = resolve_tickers(ctx["settings"])
    except ValueError as exc:
        ctx["error"] = exc
    return ctx


@then("each asset ID maps to its configured ticker")
def _check_ticker_map(ctx: dict[str, Any]) -> None:
    ticker_map: dict[str, str] = ctx["ticker_map"]
    assert ticker_map["stocks"] == "EUNL.DE"
    assert ticker_map["gold"] == "4GLD.DE"
    assert ticker_map["bonds"] == "EUN4.DE"


# -- Missing ticker ---------------------------------------------------------


@given("an asset without a ticker field", target_fixture="ctx")
def _asset_without_ticker(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx["settings"] = _make_settings(
        assets=[
            {
                "id": "stocks",
                "name": "Stocks",
                "isin": "IE00BK5BQT80",
                "target_pct": 100,
            },
        ],
    )
    return ctx


@then("a ValueError is raised listing the asset missing a ticker")
def _check_missing_ticker_error(ctx: dict[str, Any]) -> None:
    assert "error" in ctx
    assert isinstance(ctx["error"], ValueError)
    assert "stocks" in str(ctx["error"])


# -- Backtester unavailable without extras ----------------------------------


@given("yfinance is not installed", target_fixture="ctx")
def _yfinance_not_installed(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx["yfinance_missing"] = True
    return ctx


@when("MarketDataProvider is instantiated", target_fixture="ctx")
def _instantiate_provider(ctx: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    if ctx.get("yfinance_missing"):
        with patch("pac.backtester.data.provider.yf", None):
            try:
                MarketDataProvider(cache_dir=tmp_path)
            except ImportError as exc:
                ctx["error"] = exc
    return ctx


@then("an ImportError is raised with install instructions")
def _check_import_error(ctx: dict[str, Any]) -> None:
    assert "error" in ctx
    assert isinstance(ctx["error"], ImportError)
    assert "uv sync --group backtest" in str(ctx["error"])


# -- Slice price series -----------------------------------------------------


@given(
    parsers.parse(
        'a price series for "{ticker}" from "{start}" to "{end}"',
    ),
    target_fixture="ctx",
)
def _price_series_for_range(
    ctx: dict[str, Any],
    ticker: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    from datetime import timedelta

    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    bars = []
    current = s
    i = 0
    while current <= e:
        if current.weekday() < 5:
            bars.append(
                PriceBar(
                    date=current,
                    open=Decimal(str(100 + i)),
                    high=Decimal(str(105 + i)),
                    low=Decimal(str(99 + i)),
                    close=Decimal(str(103 + i)),
                    volume=1_000_000,
                )
            )
            i += 1
        current += timedelta(days=1)
    ctx["series"] = PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=bars)
    return ctx


@when(
    parsers.parse(
        'the series is sliced from "{start}" to "{end}"',
    ),
    target_fixture="ctx",
)
def _slice_series(
    ctx: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    ctx["sliced"] = ctx["series"].slice(
        date.fromisoformat(start),
        date.fromisoformat(end),
    )
    return ctx


@then("the resulting series contains only bars within that range")
def _check_sliced_range(ctx: dict[str, Any]) -> None:
    sliced: PriceSeries = ctx["sliced"]
    assert len(sliced) > 0
    for bar in sliced.bars:
        assert date(2024, 3, 1) <= bar.date <= date(2024, 3, 31)


# -- Fetch multiple tickers -------------------------------------------------


@given(
    parsers.parse(
        'data requests for "{t1}" and "{t2}" from "{start}" to "{end}"',
    ),
    target_fixture="ctx",
)
def _multiple_data_requests(
    ctx: dict[str, Any],
    t1: str,
    t2: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    ctx["requests"] = [
        DataRequest(
            ticker=t1,
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
        ),
        DataRequest(
            ticker=t2,
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
        ),
    ]
    return ctx


@when("multiple market data fetches are executed", target_fixture="ctx")
def _fetch_multiple(ctx: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    requests: list[DataRequest] = ctx["requests"]
    rows = _generate_sample_rows(requests[0].start, requests[0].end)
    df = _make_df(rows)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("pac.backtester.data.provider.yf") as mock_yf:
        mock_yf.Ticker.return_value = mock_ticker
        provider = MarketDataProvider(cache_dir=tmp_path)
        ctx["result"] = provider.fetch_multiple(requests)

    return ctx


@then("a dictionary mapping each ticker to its price series is returned")
def _check_multiple_result(ctx: dict[str, Any]) -> None:
    result: dict[str, PriceSeries] = ctx["result"]
    assert len(result) == 2
    assert "EUNL.DE" in result
    assert "4GLD.DE" in result
