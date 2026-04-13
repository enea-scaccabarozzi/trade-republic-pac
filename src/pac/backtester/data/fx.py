"""FX conversion utilities for proxy price normalization."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from pac.backtester.data.models import DataRequest, PriceBar, PriceSeries

# yfinance FX pair tickers: 1 EUR = X <currency>
# To convert <currency>→EUR: divide by rate
_FX_TICKERS: dict[str, str] = {
    "USD": "EURUSD=X",
    "GBP": "EURGBP=X",
}

FetchFn = Callable[[DataRequest], PriceSeries]


def convert_to_eur(
    series: PriceSeries,
    source_currency: str,
    fetch_fn: FetchFn,
) -> PriceSeries:
    """Convert a PriceSeries from source_currency to EUR using daily FX rates.

    For each bar, divides OHLC prices by the EUR/source_currency rate on that
    date.  If an exact date match is missing in FX data, uses the most recent
    prior rate (forward-fill).

    Args:
        series: Price data in source_currency.
        source_currency: ISO 4217 code (e.g. "USD", "GBP").
        fetch_fn: Callable that fetches a PriceSeries for a DataRequest.

    Returns:
        New PriceSeries with EUR-denominated prices.

    Raises:
        ValueError: If source_currency is unsupported or FX data unavailable.
    """
    if source_currency == "EUR":
        return series

    fx_ticker = _FX_TICKERS.get(source_currency.upper())
    if fx_ticker is None:
        msg = (
            f"Unsupported currency '{source_currency}'. "
            f"Supported: {sorted(_FX_TICKERS)}"
        )
        raise ValueError(msg)

    if not series.bars:
        return series

    fx_request = DataRequest(
        ticker=fx_ticker,
        start=series.bars[0].date,
        end=series.bars[-1].date,
    )
    fx_series = fetch_fn(fx_request)

    # Build date → rate lookup
    fx_rates: dict[date, Decimal] = {b.date: b.close for b in fx_series.bars}

    # Sanity check: FX rate should be roughly in 0.3-3.0 range
    if fx_rates:
        sorted_rates = sorted(fx_rates.values())
        median_rate = sorted_rates[len(sorted_rates) // 2]
        if not (Decimal("0.3") < median_rate < Decimal("3.0")):
            msg = (
                f"FX rate for {fx_ticker} looks wrong "
                f"(median={median_rate}). Check ticker direction."
            )
            raise ValueError(msg)

    converted_bars: list[PriceBar] = []
    last_rate: Decimal | None = None
    for bar in series.bars:
        rate = fx_rates.get(bar.date)
        if rate is None:
            # Forward-fill: find the most recent rate before this bar
            if last_rate is not None:
                rate = last_rate
            else:
                for fx_bar in reversed(fx_series.bars):
                    if fx_bar.date <= bar.date:
                        rate = fx_bar.close
                        break
        if rate is None or rate == 0:
            msg = f"No FX rate available for {source_currency} on {bar.date}"
            raise ValueError(msg)
        last_rate = rate

        converted_bars.append(
            PriceBar(
                date=bar.date,
                open=bar.open / rate,
                high=bar.high / rate,
                low=bar.low / rate,
                close=bar.close / rate,
                volume=bar.volume,
            )
        )

    return PriceSeries(
        ticker=series.ticker,
        interval=series.interval,
        bars=converted_bars,
    )
