from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pac.backtester.data.models import DataRequest, Interval, PriceBar, PriceSeries


@pytest.fixture
def sample_bar() -> PriceBar:
    return PriceBar(
        date=date(2024, 1, 2),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("103.50"),
        volume=1_000_000,
    )


@pytest.fixture
def sample_bars() -> list[PriceBar]:
    return [
        PriceBar(
            date=date(2024, 1, i),
            open=Decimal(str(100 + i)),
            high=Decimal(str(105 + i)),
            low=Decimal(str(99 + i)),
            close=Decimal(str(103 + i)),
            volume=1_000_000 + i * 1000,
        )
        for i in range(2, 7)
    ]


@pytest.fixture
def sample_series(sample_bars: list[PriceBar]) -> PriceSeries:
    return PriceSeries(
        ticker="EUNL.DE",
        interval=Interval.DAILY,
        bars=sample_bars,
    )


@pytest.fixture
def sample_request() -> DataRequest:
    return DataRequest(
        ticker="EUNL.DE",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
    )
