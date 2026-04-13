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
from pac.rules.builtin.equity_drawdown import EquityDrawdownParams, EquityDrawdownRule
from pac.rules.tests.conftest import REF_DATE, FakeMarketContext, make_price_series

scenarios("../features/equity_drawdown_rule.feature")


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


@pytest.fixture
def params() -> EquityDrawdownParams:
    return EquityDrawdownParams()


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a market context with equity price history", target_fixture="market_ctx")
def given_market_ctx_equity() -> FakeMarketContext:
    """Default market context — rising equity for 300 days."""
    series = make_price_series("EUNL.DE", 300, daily_return=0.0003, end_date=REF_DATE)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "equity prices have been rising steadily for 252 days",
    target_fixture="market_ctx",
)
def rising_equity() -> FakeMarketContext:
    series = make_price_series("EUNL.DE", 300, daily_return=0.0005, end_date=REF_DATE)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "equity has drawn down 12% from its 252-day peak",
    target_fixture="market_ctx",
)
def drawdown_12() -> FakeMarketContext:
    # Rise then crash: 260 days rising, then 40-day crash of -12%
    series = make_price_series(
        "EUNL.DE",
        300,
        daily_return=0.0005,
        crash_at_day=260,
        crash_pct=-0.12,
        crash_duration=40,
        end_date=REF_DATE,
    )
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "equity has drawn down 25% from its 252-day peak",
    target_fixture="market_ctx",
)
def drawdown_25() -> FakeMarketContext:
    series = make_price_series(
        "EUNL.DE",
        300,
        daily_return=0.0005,
        crash_at_day=260,
        crash_pct=-0.25,
        crash_duration=40,
        end_date=REF_DATE,
    )
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given(
    "equity has fallen 6% in 20 days from peak (velocity ~ -0.30%/day)",
    target_fixture="market_ctx",
)
def drawdown_velocity() -> FakeMarketContext:
    # 280 days rising, then 10-day sharp crash of -10%
    # velocity ≈ -0.10/10 = -0.01/day → *100 = -1.0%/day (well past -0.30)
    series = make_price_series(
        "EUNL.DE",
        300,
        daily_return=0.0005,
        crash_at_day=290,
        crash_pct=-0.10,
        crash_duration=10,
        end_date=REF_DATE,
    )
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


@given("no market context is available", target_fixture="market_ctx")
def no_market_ctx() -> None:
    return None


@given(
    "only 10 days of equity price data are available",
    target_fixture="market_ctx",
)
def short_data() -> FakeMarketContext:
    series = make_price_series("EUNL.DE", 10, daily_return=0.001, end_date=REF_DATE)
    return FakeMarketContext(
        _prices={"EUNL.DE": series},
        _ticker_map={"stocks": "EUNL.DE"},
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the equity drawdown rule evaluates", target_fixture="signals")
def evaluate(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = EquityDrawdownRule()
    return rule.evaluate(report, snapshot, EquityDrawdownParams(), market_ctx)


@when(
    "the equity drawdown rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = EquityDrawdownRule()
    return rule.evaluate(report, snapshot, EquityDrawdownParams(), market_ctx)


@when(
    "the equity drawdown rule evaluates with lookback_bars=252",
    target_fixture="signals",
)
def evaluate_lookback_252(
    settings: Settings,
    snapshot: PortfolioSnapshot,
    market_ctx: FakeMarketContext | None,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = EquityDrawdownRule()
    params = EquityDrawdownParams(lookback_bars=252)
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


@then("the signal metadata includes drawdown_pct of approximately -0.12")
def metadata_drawdown_12(signals: list[Signal]) -> None:
    depth_signals = [
        s for s in signals if s.metadata.get("indicator") == "equity_drawdown"
    ]
    assert len(depth_signals) >= 1
    dd = depth_signals[0].metadata["drawdown_pct"]
    assert -0.18 < dd < -0.08, f"Expected drawdown ≈ -0.12, got {dd}"


@then('a signal with metadata indicator "drawdown_velocity" is emitted')
def velocity_signal(signals: list[Signal]) -> None:
    vel_signals = [
        s for s in signals if s.metadata.get("indicator") == "drawdown_velocity"
    ]
    assert len(vel_signals) >= 1
