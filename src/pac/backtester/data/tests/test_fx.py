from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from pac.backtester.data.fx import convert_to_eur
from pac.backtester.data.models import DataRequest, Interval, PriceBar, PriceSeries


def _bar(d: date, close: Decimal, **kw: Decimal | int) -> PriceBar:
    return PriceBar(
        date=d,
        open=Decimal(str(kw.get("open", close))),
        high=Decimal(str(kw.get("high", close))),
        low=Decimal(str(kw.get("low", close))),
        close=close,
        volume=int(kw.get("volume", 1000)),
    )


def _series(ticker: str, bars: list[PriceBar]) -> PriceSeries:
    return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=bars)


def _stub_fetch(
    responses: dict[str, PriceSeries],
) -> Callable[[DataRequest], PriceSeries]:
    """Return a callable that returns canned PriceSeries by ticker."""

    def _fetch(req: DataRequest) -> PriceSeries:
        if req.ticker not in responses:
            msg = f"No stub data for {req.ticker}"
            raise ValueError(msg)
        return responses[req.ticker]

    return _fetch


class TestConvertToEur:
    def test_usd_to_eur_conversion(self) -> None:
        """USD prices divided by EURUSD rate."""
        d = date(2024, 1, 2)
        series = _series("AAPL", [_bar(d, Decimal("200.00"))])
        fx_series = _series("EURUSD=X", [_bar(d, Decimal("1.10"))])
        fetch = _stub_fetch({"EURUSD=X": fx_series})

        result = convert_to_eur(series, "USD", fetch)

        expected = Decimal("200.00") / Decimal("1.10")
        assert result.bars[0].close == expected

    def test_gbp_to_eur_conversion(self) -> None:
        """GBP prices divided by EURGBP rate."""
        d = date(2024, 1, 2)
        series = _series("SGLN.L", [_bar(d, Decimal("30.00"))])
        fx_series = _series("EURGBP=X", [_bar(d, Decimal("0.86"))])
        fetch = _stub_fetch({"EURGBP=X": fx_series})

        result = convert_to_eur(series, "GBP", fetch)

        expected = Decimal("30.00") / Decimal("0.86")
        assert result.bars[0].close == expected

    def test_eur_to_eur_is_noop(self) -> None:
        """EUR→EUR returns same series unchanged."""
        d = date(2024, 1, 2)
        series = _series("VWCE.DE", [_bar(d, Decimal("100.00"))])

        result = convert_to_eur(series, "EUR", lambda _: None)  # type: ignore[arg-type,return-value]

        assert result is series

    def test_unsupported_currency_raises(self) -> None:
        """Unsupported currency code raises ValueError."""
        d = date(2024, 1, 2)
        series = _series("X", [_bar(d, Decimal("50.00"))])

        with pytest.raises(ValueError, match="Unsupported currency 'JPY'"):
            convert_to_eur(series, "JPY", lambda _: None)  # type: ignore[arg-type,return-value]

    def test_forward_fill_on_missing_fx_date(self) -> None:
        """Uses prior rate when FX data is missing for a date."""
        d1 = date(2024, 1, 2)  # Tuesday
        d2 = date(2024, 1, 3)  # Wednesday
        d3 = date(2024, 1, 4)  # Thursday — FX missing
        series = _series(
            "AAPL",
            [
                _bar(d1, Decimal("100.00")),
                _bar(d2, Decimal("101.00")),
                _bar(d3, Decimal("102.00")),
            ],
        )
        # FX data only for d1 and d2
        fx_series = _series(
            "EURUSD=X",
            [
                _bar(d1, Decimal("1.10")),
                _bar(d2, Decimal("1.12")),
            ],
        )
        fetch = _stub_fetch({"EURUSD=X": fx_series})

        result = convert_to_eur(series, "USD", fetch)

        # d3 should use d2's rate (forward-fill)
        assert result.bars[2].close == Decimal("102.00") / Decimal("1.12")

    def test_no_fx_data_raises(self) -> None:
        """Raises ValueError when FX series has no bars."""
        d = date(2024, 1, 2)
        series = _series("AAPL", [_bar(d, Decimal("100.00"))])
        fx_series = _series("EURUSD=X", [])
        fetch = _stub_fetch({"EURUSD=X": fx_series})

        with pytest.raises(ValueError, match="No FX rate available"):
            convert_to_eur(series, "USD", fetch)

    def test_empty_series_returns_empty(self) -> None:
        """Empty input series returns empty output."""
        series = _series("AAPL", [])

        result = convert_to_eur(series, "USD", lambda _: None)  # type: ignore[arg-type,return-value]

        assert len(result) == 0

    def test_sanity_check_rejects_bad_rate(self) -> None:
        """Raises ValueError when median FX rate is outside 0.3-3.0."""
        d = date(2024, 1, 2)
        series = _series("X", [_bar(d, Decimal("100.00"))])
        # Rate of 100 is obviously wrong
        fx_series = _series("EURUSD=X", [_bar(d, Decimal("100.0"))])
        fetch = _stub_fetch({"EURUSD=X": fx_series})

        with pytest.raises(ValueError, match="looks wrong"):
            convert_to_eur(series, "USD", fetch)
