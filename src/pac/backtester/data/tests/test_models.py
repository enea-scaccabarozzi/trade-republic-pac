from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pac.backtester.data.models import DataRequest, Interval, PriceBar, PriceSeries


class TestPriceBar:
    def test_price_bar_construction(self, sample_bar: PriceBar) -> None:
        assert sample_bar.date == date(2024, 1, 2)
        assert sample_bar.open == Decimal("100.00")
        assert sample_bar.high == Decimal("105.00")
        assert sample_bar.low == Decimal("99.00")
        assert sample_bar.close == Decimal("103.50")
        assert sample_bar.volume == 1_000_000

    def test_price_bar_frozen(self, sample_bar: PriceBar) -> None:
        with pytest.raises(ValidationError):
            sample_bar.close = Decimal("999")  # type: ignore[misc]

    def test_price_bar_rejects_low_above_high(self) -> None:
        with pytest.raises(ValidationError, match=r"low.*high"):
            PriceBar(
                date=date(2024, 1, 2),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("110"),
                close=Decimal("100"),
                volume=1000,
            )

    def test_price_bar_allows_equal_low_high(self) -> None:
        bar = PriceBar(
            date=date(2024, 1, 2),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=1000,
        )
        assert bar.low == bar.high


class TestPriceSeries:
    def test_price_series_start_end_date(
        self,
        sample_series: PriceSeries,
    ) -> None:
        assert sample_series.start_date == date(2024, 1, 2)
        assert sample_series.end_date == date(2024, 1, 6)

    def test_price_series_empty_dates_none(self) -> None:
        series = PriceSeries(ticker="X", interval=Interval.DAILY, bars=[])
        assert series.start_date is None
        assert series.end_date is None

    def test_price_series_len(self, sample_series: PriceSeries) -> None:
        assert len(sample_series) == 5

    def test_price_series_slice_filters_by_date(
        self,
        sample_series: PriceSeries,
    ) -> None:
        sliced = sample_series.slice(date(2024, 1, 3), date(2024, 1, 5))
        assert len(sliced) == 3
        assert sliced.start_date == date(2024, 1, 3)
        assert sliced.end_date == date(2024, 1, 5)
        assert sliced.ticker == sample_series.ticker

    def test_price_series_slice_empty_range(
        self,
        sample_series: PriceSeries,
    ) -> None:
        sliced = sample_series.slice(date(2025, 1, 1), date(2025, 12, 31))
        assert len(sliced) == 0


class TestDataRequest:
    def test_data_request_rejects_start_after_end(self) -> None:
        with pytest.raises(ValidationError, match=r"start.*must not be after.*end"):
            DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 12, 31),
                end=date(2024, 1, 1),
            )

    def test_data_request_defaults_to_daily(self) -> None:
        req = DataRequest(
            ticker="EUNL.DE",
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
        )
        assert req.interval == Interval.DAILY

    def test_data_request_valid_construction(
        self,
        sample_request: DataRequest,
    ) -> None:
        assert sample_request.ticker == "EUNL.DE"
        assert sample_request.start == date(2024, 1, 1)
        assert sample_request.end == date(2024, 12, 31)
        assert sample_request.interval == Interval.DAILY


class TestInterval:
    def test_interval_values(self) -> None:
        assert Interval.DAILY.value == "1d"
        assert Interval.WEEKLY.value == "1wk"
        assert Interval.MONTHLY.value == "1mo"
