"""Shared test fixtures for research tests."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from pac.config.models import Settings
from pac.models.market_data import Interval, PriceBar, PriceSeries


def make_series(
    ticker: str,
    n: int,
    start_date: date,
    base_price: float = 100.0,
    pattern: str = "v_shape",
) -> PriceSeries:
    """Create a synthetic PriceSeries with non-trivial price dynamics.

    Patterns:
    - "v_shape": drops 30% to midpoint, then recovers.
    - "sine": oscillates +/-15% around base_price via sine wave.
    """
    bars: list[PriceBar] = []
    for i in range(n):
        if pattern == "v_shape":
            mid = n // 2
            if i <= mid:
                price = base_price * (1.0 - 0.30 * i / mid)
            else:
                price = base_price * (0.70 + 0.30 * (i - mid) / (n - mid))
        elif pattern == "sine":
            price = base_price * (1.0 + 0.15 * math.sin(2 * math.pi * i / n))
        else:
            price = base_price + i * 0.1

        d = Decimal(str(round(price, 4)))
        bars.append(
            PriceBar(
                date=start_date + timedelta(days=i),
                open=d,
                high=d + Decimal("0.50"),
                low=d - Decimal("0.50"),
                close=d,
                volume=1000,
            )
        )
    return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=bars)


@pytest.fixture()
def price_data() -> dict[str, PriceSeries]:
    """500 bars: V-shape stocks, sine gold, sine bonds."""
    base = date(2020, 1, 1)
    return {
        "stocks": make_series("EUNL.DE", 500, base, 100.0, pattern="v_shape"),
        "gold": make_series("4GLD.DE", 500, base, 50.0, pattern="sine"),
        "bonds": make_series("EUN4.DE", 500, base, 80.0, pattern="sine"),
    }


def make_test_settings(**overrides: Any) -> Settings:
    """Build a minimal valid Settings for research tests."""
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
