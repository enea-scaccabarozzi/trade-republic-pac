from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import SignalSeverity
from pac.rules.builtin.cycle import CycleInversionParams, CycleInversionRule

scenarios("../features/cycle_rule.feature")


def _snapshot(
    stocks_value: Decimal,
    gold_value: Decimal,
    bonds_value: Decimal,
    cash: Decimal = Decimal(0),
) -> PortfolioSnapshot:
    positions = []
    for isin, name, value, aid in [
        ("IE00BK5BQT80", "Stocks ETF", stocks_value, "stocks"),
        ("IE00B4ND3602", "Gold ETC", gold_value, "gold"),
        ("IE00B3F81409", "Bond ETF", bonds_value, "bonds"),
    ]:
        if value > 0:
            positions.append(
                Position(
                    isin=isin,
                    name=name,
                    quantity=Decimal(1),
                    price=value,
                    market_value=value,
                    asset_id=aid,
                )
            )
    return PortfolioSnapshot(
        positions=positions,
        cash=cash,
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@given(
    "a portfolio with target allocation 70/15/15 for stocks/gold/bonds",
    target_fixture="settings",
)
def target_allocation() -> Settings:
    return make_settings()


@given(
    "all assets are slightly underweight due to cash drag",
    target_fixture="snapshot",
)
def cash_drag_portfolio() -> PortfolioSnapshot:
    return _snapshot(
        Decimal("6800"),
        Decimal("1450"),
        Decimal("1450"),
        cash=Decimal("300"),
    )


@given(
    "stocks are 6pp overweight and bonds are 6pp underweight",
    target_fixture="snapshot",
)
def stocks_over_bonds_under() -> PortfolioSnapshot:
    return _snapshot(Decimal("7600"), Decimal("1500"), Decimal("900"))


@given(
    "all deviations are below 2pp",
    target_fixture="snapshot",
)
def small_deviations() -> PortfolioSnapshot:
    return _snapshot(Decimal("7100"), Decimal("1500"), Decimal("1400"))


@given(
    "deviations of 1.5pp in opposing directions",
    target_fixture="snapshot",
)
def small_opposing() -> PortfolioSnapshot:
    return _snapshot(Decimal("7150"), Decimal("1500"), Decimal("1350"))


@when(
    "the cycle inversion rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    report = calculate_deviations(snapshot, settings)
    rule = CycleInversionRule()
    return rule.evaluate(report, snapshot, CycleInversionParams())


@when(
    "the cycle inversion rule evaluates with min_pct=1.0",
    target_fixture="signals",
)
def evaluate_custom_min(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    report = calculate_deviations(snapshot, settings)
    rule = CycleInversionRule()
    params = CycleInversionParams(min_pct=Decimal("1.0"))
    return rule.evaluate(report, snapshot, params)


@then("no signals are emitted")
def no_signals(signals: list[Any]) -> None:
    assert signals == []


@then("a cycle inversion signal is emitted")
def inversion_emitted(signals: list[Any]) -> None:
    assert len(signals) >= 1
    assert any(s.name == "cycle_inversion" for s in signals)


@then("the signal identifies stocks as overweight and bonds as underweight")
def stocks_over_bonds_under_check(signals: list[Any]) -> None:
    s = signals[0]
    assert s.metadata["overweight_class"] == "stocks"
    assert s.metadata["underweight_class"] == "bonds"


@then("the signal severity is CRITICAL")
def severity_critical(signals: list[Any]) -> None:
    assert any(s.severity == SignalSeverity.CRITICAL for s in signals)
