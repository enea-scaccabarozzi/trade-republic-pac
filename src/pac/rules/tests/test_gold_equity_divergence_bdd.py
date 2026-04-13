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
from pac.rules.builtin.gold_equity_divergence import (
    GoldEquityDivergenceParams,
    GoldEquityDivergenceRule,
)
from pac.rules.tests.conftest import REF_DATE, FakeMarketContext, make_price_series

scenarios("../features/gold_equity_divergence_rule.feature")


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


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def snapshot() -> PortfolioSnapshot:
    return _snapshot()


@pytest.fixture
def market_ctx() -> FakeMarketContext | None:
    return None


def _make_ctx(
    gold_return: float,
    equity_return: float,
    lookback: int = 41,
) -> FakeMarketContext:
    """Build a FakeMarketContext with gold and equity at specified returns."""
    gold_daily = (
        (1 + gold_return) ** (1.0 / (lookback - 1)) - 1 if lookback > 1 else 0.0
    )
    equity_daily = (
        (1 + equity_return) ** (1.0 / (lookback - 1)) - 1 if lookback > 1 else 0.0
    )
    gold_series = make_price_series(
        "4GLD.DE",
        lookback,
        start_price=100.0,
        daily_return=gold_daily,
        end_date=REF_DATE,
    )
    equity_series = make_price_series(
        "EUNL.DE",
        lookback,
        start_price=100.0,
        daily_return=equity_daily,
        end_date=REF_DATE,
    )
    return FakeMarketContext(
        _prices={"4GLD.DE": gold_series, "EUNL.DE": equity_series},
        _ticker_map={"gold": "4GLD.DE", "stocks": "EUNL.DE"},
    )


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "a market context with gold and equity price history",
    target_fixture="market_ctx",
)
def given_market_ctx() -> FakeMarketContext:
    return _make_ctx(0.02, 0.02)


@given(
    "gold and equities both returned +5% over 40 trading days",
    target_fixture="market_ctx",
)
def both_up_5() -> FakeMarketContext:
    return _make_ctx(0.05, 0.05)


@given(
    "gold returned +5% and equities returned -8% over 40 days",
    target_fixture="market_ctx",
)
def gold_up5_equity_down8() -> FakeMarketContext:
    return _make_ctx(0.05, -0.08)


@given(
    "gold returned +10% and equities returned -15% over 40 days",
    target_fixture="market_ctx",
)
def gold_up10_equity_down15() -> FakeMarketContext:
    return _make_ctx(0.10, -0.15)


@given(
    "gold returned -5% and equities returned -15% over 40 days",
    target_fixture="market_ctx",
)
def gold_down5_equity_down15() -> FakeMarketContext:
    return _make_ctx(-0.05, -0.15)


@given("no market context is available", target_fixture="market_ctx")
def no_market_ctx() -> None:
    return None


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the gold-equity divergence rule evaluates", target_fixture="signals")
def evaluate(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = GoldEquityDivergenceRule()
    return rule.evaluate(report, snapshot, GoldEquityDivergenceParams(), market_ctx)


@when(
    "the gold-equity divergence rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = GoldEquityDivergenceRule()
    return rule.evaluate(report, snapshot, GoldEquityDivergenceParams(), market_ctx)


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


@then("the signal metadata includes divergence_pct of approximately 13.0")
def metadata_divergence_13(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    div_pct = signals[0].metadata["divergence_pct"]
    assert 10.0 < div_pct < 16.0, f"Expected divergence ≈ 13%, got {div_pct}"


@then("the divergence is 10% (gold declined less)")
def divergence_10(signals: list[Signal]) -> None:
    assert len(signals) >= 1
    div_pct = signals[0].metadata["divergence_pct"]
    assert 7.0 < div_pct < 13.0, f"Expected divergence ≈ 10%, got {div_pct}"
