from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from math import sqrt

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.market_data import Interval, PriceBar, PriceSeries
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.rules.builtin.volatility_regime import (
    VolatilityRegimeParams,
    VolatilityRegimeRule,
)
from pac.rules.tests.conftest import REF_DATE, FakeMarketContext

scenarios("../features/volatility_regime_rule.feature")


def _snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal(1),
                price=Decimal("7000"),
                market_value=Decimal("7000"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold ETC",
                quantity=Decimal(1),
                price=Decimal("1500"),
                market_value=Decimal("1500"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal(1),
                price=Decimal("1500"),
                market_value=Decimal("1500"),
                asset_id="bonds",
            ),
        ],
        cash=Decimal(0),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


def _make_vol_series(
    short_vol_ann: float,
    long_vol_ann: float,
    short_window: int = 20,
    long_window: int = 60,
) -> PriceSeries:
    """Build a price series where the last short_window days have different vol.

    Strategy: generate enough calm bars so that rolling_std over long_window
    is dominated by calm returns, then short_window bars at short_vol.
    Total bars = long_window + short_window + 1 so rolling_std(long_window)
    captures long_window - short_window calm returns + short_window volatile.
    """
    import random

    rng = random.Random(42)
    daily_long = (long_vol_ann / 100) / sqrt(252)
    daily_short = (short_vol_ann / 100) / sqrt(252)

    prices = [100.0]

    # First (long_window) returns at long_vol
    for _ in range(long_window):
        ret = rng.gauss(0.0, daily_long)
        prices.append(prices[-1] * (1.0 + ret))

    # Then short_window returns at short_vol
    for _ in range(short_window):
        ret = rng.gauss(0.0, daily_short)
        prices.append(prices[-1] * (1.0 + ret))

    from datetime import timedelta

    start = REF_DATE - timedelta(days=len(prices) - 1)
    bars: list[PriceBar] = []
    for i, p in enumerate(prices):
        close = Decimal(str(round(max(p, 0.01), 4)))
        bars.append(
            PriceBar(
                date=start + timedelta(days=i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1_000_000,
            ),
        )

    return PriceSeries(ticker="EUNL.DE", interval=Interval.DAILY, bars=bars)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def snapshot() -> PortfolioSnapshot:
    return _snapshot()


@pytest.fixture
def market_ctx() -> FakeMarketContext | None:
    return None


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a market context with equity price history", target_fixture="market_ctx")
def given_market_ctx_equity() -> FakeMarketContext:
    series = _make_vol_series(15.0, 15.0)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "equity volatility has been steady at ~15% annualized for 60 days",
    target_fixture="market_ctx",
)
def steady_vol() -> FakeMarketContext:
    series = _make_vol_series(15.0, 15.0)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "20-day vol is 27% and 60-day vol is 15% (ratio ~1.8)",
    target_fixture="market_ctx",
)
def vol_ratio_1_8() -> FakeMarketContext:
    series = _make_vol_series(27.0, 14.0, long_window=200)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "20-day vol is 50% and 60-day vol is 18% (ratio ~2.8)",
    target_fixture="market_ctx",
)
def vol_ratio_2_8() -> FakeMarketContext:
    series = _make_vol_series(60.0, 8.0, long_window=200)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "20-day vol is 25% and 60-day vol is 22% (ratio ~1.1)",
    target_fixture="market_ctx",
)
def vol_ratio_1_1() -> FakeMarketContext:
    series = _make_vol_series(25.0, 22.0)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given("no market context is available", target_fixture="market_ctx")
def no_market_ctx() -> None:
    return None


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the volatility regime rule evaluates", target_fixture="signals")
def evaluate(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = VolatilityRegimeRule()
    return rule.evaluate(report, snapshot, VolatilityRegimeParams(), market_ctx)


@when(
    "the volatility regime rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = VolatilityRegimeRule()
    params = VolatilityRegimeParams(long_window=200, lookback_days=500)
    return rule.evaluate(report, snapshot, params, market_ctx)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("no signals are emitted")
def no_signals(signals: list[Signal]) -> None:
    assert signals == []


@then("a WARNING signal is emitted")
def warning_emitted(signals: list[Signal]) -> None:
    warnings = [s for s in signals if s.severity == SignalSeverity.WARNING]
    assert len(warnings) >= 1


@then("a CRITICAL signal is emitted")
def critical_emitted(signals: list[Signal]) -> None:
    criticals = [s for s in signals if s.severity == SignalSeverity.CRITICAL]
    assert len(criticals) >= 1
