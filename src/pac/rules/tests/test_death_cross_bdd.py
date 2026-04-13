from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.market_data import Interval, PriceBar, PriceSeries
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.rules.builtin.death_cross import DeathCrossParams, DeathCrossRule
from pac.rules.tests.conftest import REF_DATE, FakeMarketContext, make_price_series

scenarios("../features/death_cross_rule.feature")


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


def _make_death_cross_series(
    *,
    bullish: bool = False,
    cross_today: bool = False,
    bearish_regime: bool = False,
) -> PriceSeries:
    """Build a price series for death cross scenarios.

    - bullish: 50d SMA > 200d SMA throughout (steady uptrend)
    - cross_today: 50d SMA just crossed below 200d SMA on the last bar
    - bearish_regime: 50d SMA has been below 200d SMA for a while
    """
    from datetime import timedelta

    total_bars = 250  # enough for 200d + some earlier history
    start = REF_DATE - timedelta(days=total_bars - 1)
    bars: list[PriceBar] = []

    if bullish:
        # Steady uptrend — 50d SMA always above 200d SMA
        for i in range(total_bars):
            price = 100.0 + i * 0.2
            close = Decimal(str(round(price, 4)))
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
    elif cross_today:
        # Uptrend for 200 bars at 0.5/day, then steady decline at
        # calibrated rate so SMA_50 crosses below SMA_200 on the last bar.
        # Rate 1.47/day verified via binary search to trigger cross_event.
        rate_rise = 0.5
        rate_decline = 1.47
        rise_bars = 200
        for i in range(total_bars):
            if i < rise_bars:
                price = 100.0 + i * rate_rise
            else:
                peak = 100.0 + (rise_bars - 1) * rate_rise
                price = peak - (i - rise_bars + 1) * rate_decline
            close = Decimal(str(round(max(price, 10.0), 4)))
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
    elif bearish_regime:
        # Peaked early, declining for a long time — 50d SMA well below 200d SMA
        for i in range(total_bars):
            price = 100.0 + i * 0.5 if i < 50 else 125.0 - (i - 50) * 0.3
            close = Decimal(str(round(max(price, 10.0), 4)))
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


@given(
    "a market context with at least 200 days of equity price data",
    target_fixture="market_ctx",
)
def given_market_ctx() -> FakeMarketContext:
    series = _make_death_cross_series(bullish=True)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "the 50-day SMA is above the 200-day SMA",
    target_fixture="market_ctx",
)
def bullish_trend() -> FakeMarketContext:
    series = _make_death_cross_series(bullish=True)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "the 50-day SMA just crossed below the 200-day SMA today",
    target_fixture="market_ctx",
)
def cross_today() -> FakeMarketContext:
    series = _make_death_cross_series(cross_today=True)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "the 50-day SMA has been below the 200-day SMA for 30 days",
    target_fixture="market_ctx",
)
def bearish_30_days() -> FakeMarketContext:
    series = _make_death_cross_series(bearish_regime=True)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given("no market context is available", target_fixture="market_ctx")
def no_market_ctx() -> None:
    return None


@given(
    "only 100 days of price data are available",
    target_fixture="market_ctx",
)
def short_data() -> FakeMarketContext:
    series = make_price_series("EUNL.DE", 100, daily_return=0.001, end_date=REF_DATE)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the death cross rule evaluates", target_fixture="signals")
def evaluate(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = DeathCrossRule()
    return rule.evaluate(report, snapshot, DeathCrossParams(), market_ctx)


@when(
    "the death cross rule evaluates with long_window=200",
    target_fixture="signals",
)
def evaluate_long_200(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = DeathCrossRule()
    params = DeathCrossParams(long_window=200)
    return rule.evaluate(report, snapshot, params, market_ctx)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("no signals are emitted")
def no_signals(signals: list[Signal]) -> None:
    assert signals == []


@then("a CRITICAL signal is emitted")
def critical_emitted(signals: list[Signal]) -> None:
    criticals = [s for s in signals if s.severity == SignalSeverity.CRITICAL]
    assert len(criticals) >= 1


@then("a WARNING signal is emitted")
def warning_emitted(signals: list[Signal]) -> None:
    warnings = [s for s in signals if s.severity == SignalSeverity.WARNING]
    assert len(warnings) >= 1


@then("the signal metadata includes cross_event as true")
def metadata_cross_true(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    assert signals[0].metadata["cross_event"] is True


@then("the signal metadata includes bearish_regime as true")
def metadata_bearish_true(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    assert signals[0].metadata["bearish_regime"] is True


@then("the signal metadata includes cross_event as false")
def metadata_cross_false(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    assert signals[0].metadata["cross_event"] is False
