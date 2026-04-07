from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Interval(StrEnum):
    """Supported OHLCV bar intervals."""

    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class PriceBar(BaseModel, frozen=True):
    """Single OHLCV bar for one trading day."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @model_validator(mode="after")
    def _check_ohlc_order(self) -> PriceBar:
        if self.low > self.high:
            msg = f"low ({self.low}) > high ({self.high}) on {self.date}"
            raise ValueError(msg)
        return self


class PriceSeries(BaseModel, frozen=True):
    """Ordered series of price bars for a single ticker."""

    ticker: str
    interval: Interval
    bars: list[PriceBar]

    @property
    def start_date(self) -> date | None:
        return self.bars[0].date if self.bars else None

    @property
    def end_date(self) -> date | None:
        return self.bars[-1].date if self.bars else None

    def __len__(self) -> int:
        return len(self.bars)

    def slice(self, start: date, end: date) -> PriceSeries:
        """Return a new PriceSeries filtered to [start, end] inclusive."""
        filtered = [b for b in self.bars if start <= b.date <= end]
        return PriceSeries(ticker=self.ticker, interval=self.interval, bars=filtered)


class DataRequest(BaseModel):
    """Request parameters for fetching market data."""

    ticker: str = Field(description="Yahoo Finance ticker symbol")
    start: date = Field(description="Start date (inclusive)")
    end: date = Field(description="End date (inclusive)")
    interval: Interval = Field(default=Interval.DAILY)

    @model_validator(mode="after")
    def _check_date_range(self) -> DataRequest:
        if self.start > self.end:
            msg = f"start ({self.start}) must not be after end ({self.end})"
            raise ValueError(msg)
        return self
