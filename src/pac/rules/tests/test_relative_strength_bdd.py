from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.rules.builtin.relative_strength import (
    RelativeStrengthParams,
    RelativeStrengthRule,
)
from pac.rules.tests.conftest import REF_DATE, FakeMarketContext, make_price_series

scenarios("../features/relative_strength_rule.feature")


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


def _make_rs_ctx(
    breakout_pct: float,
    ma_window: int = 120,
) -> FakeMarketContext:
    """Build a FakeMarketContext where gold/equity RS ratio is breakout_pct above MA.

    Strategy: gold and equity flat for the MA period, then gold surges
    (or equity drops) to create the specified breakout over the last few bars.
    """
    total_bars = ma_window + 20  # extra bars for stability
    # Equity flat at 100
    equity_series = make_price_series(
        "EUNL.DE",
        total_bars,
        start_price=100.0,
        daily_return=0.0,
        end_date=REF_DATE,
    )
    # Gold flat at 50 for most of the period (RS = 0.5), then rise
    # to get breakout_pct above the MA of 0.5
    # target RS_current = RS_MA * (1 + breakout_pct / 100)
    base_rs = 0.5
    target_rs = base_rs * (1.0 + breakout_pct / 100.0)
    target_gold_price = target_rs * 100.0  # equity is at 100

    gold_series = make_price_series(
        "4GLD.DE",
        total_bars,
        start_price=50.0,
        daily_return=0.0,
        end_date=REF_DATE,
    )
    # Adjust last 5 bars to target gold price for a clear breakout

    from pac.models.market_data import Interval, PriceBar, PriceSeries

    bars = list(gold_series.bars)
    for i in range(max(0, len(bars) - 5), len(bars)):
        close = Decimal(str(round(target_gold_price, 4)))
        bars[i] = PriceBar(
            date=bars[i].date,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
        )
    gold_series = PriceSeries(ticker="4GLD.DE", interval=Interval.DAILY, bars=bars)

    return FakeMarketContext(
        _prices={"4GLD.DE": gold_series, "EUNL.DE": equity_series},
        _ticker_map={"gold": "4GLD.DE", "stocks": "EUNL.DE"},
    )


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
    "a market context with gold and equity price history",
    target_fixture="market_ctx",
)
def given_market_ctx() -> FakeMarketContext:
    return _make_rs_ctx(0.0)


@given(
    "the gold/equity ratio is within 2% of its 120-day MA",
    target_fixture="market_ctx",
)
def rs_near_ma() -> FakeMarketContext:
    return _make_rs_ctx(2.0)


@given(
    "the gold/equity ratio is 6% above its 120-day MA",
    target_fixture="market_ctx",
)
def rs_breakout_6() -> FakeMarketContext:
    return _make_rs_ctx(6.0)


@given(
    "the gold/equity ratio is 12% above its 120-day MA",
    target_fixture="market_ctx",
)
def rs_breakout_12() -> FakeMarketContext:
    return _make_rs_ctx(12.0)


@given(
    "both gold and equities have fallen, keeping the ratio near its MA",
    target_fixture="market_ctx",
)
def both_fallen_rs_flat() -> FakeMarketContext:
    # Both decline equally — RS ratio stays ~constant
    total_bars = 140
    gold_series = make_price_series(
        "4GLD.DE",
        total_bars,
        start_price=50.0,
        daily_return=-0.0005,
        end_date=REF_DATE,
    )
    equity_series = make_price_series(
        "EUNL.DE",
        total_bars,
        start_price=100.0,
        daily_return=-0.0005,
        end_date=REF_DATE,
    )
    return FakeMarketContext(
        _prices={"4GLD.DE": gold_series, "EUNL.DE": equity_series},
        _ticker_map={"gold": "4GLD.DE", "stocks": "EUNL.DE"},
    )


@given("no market context is available", target_fixture="market_ctx")
def no_market_ctx() -> None:
    return None


@given(
    "only 30 days of price data are available",
    target_fixture="market_ctx",
)
def short_data() -> FakeMarketContext:
    gold_series = make_price_series("4GLD.DE", 30, start_price=50.0, end_date=REF_DATE)
    equity_series = make_price_series(
        "EUNL.DE", 30, start_price=100.0, end_date=REF_DATE
    )
    return FakeMarketContext(
        _prices={"4GLD.DE": gold_series, "EUNL.DE": equity_series},
        _ticker_map={"gold": "4GLD.DE", "stocks": "EUNL.DE"},
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the relative strength rule evaluates", target_fixture="signals")
def evaluate(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = RelativeStrengthRule()
    return rule.evaluate(report, snapshot, RelativeStrengthParams(), market_ctx)


@when(
    "the relative strength rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = RelativeStrengthRule()
    return rule.evaluate(report, snapshot, RelativeStrengthParams(), market_ctx)


@when(
    "the relative strength rule evaluates with ma_window=120",
    target_fixture="signals",
)
def evaluate_ma_120(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = RelativeStrengthRule()
    params = RelativeStrengthParams(ma_window=120)
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


@then("the signal metadata includes breakout_pct of approximately 6.0")
def metadata_breakout_6(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    bp = signals[0].metadata["breakout_pct"]
    assert 4.0 < bp < 9.0, f"Expected breakout ≈ 6%, got {bp}"
