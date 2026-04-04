from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import SignalSeverity
from pac.rules.builtin.threshold import ThresholdDeviationRule, ThresholdParams

scenarios("../features/threshold_rule.feature")


def _snapshot(
    stocks_value: Decimal,
    gold_value: Decimal,
    bonds_value: Decimal,
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
        cash=Decimal(0),
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
    "the portfolio is perfectly balanced at 70/15/15",
    target_fixture="snapshot",
)
def balanced_portfolio() -> PortfolioSnapshot:
    return _snapshot(Decimal("7000"), Decimal("1500"), Decimal("1500"))


@given(
    "stocks are at 73% (3pp above target)",
    target_fixture="snapshot",
)
def stocks_73() -> PortfolioSnapshot:
    return _snapshot(Decimal("7300"), Decimal("1500"), Decimal("1200"))


@given(
    "stocks are at 76% (6pp above target)",
    target_fixture="snapshot",
)
def stocks_76() -> PortfolioSnapshot:
    return _snapshot(Decimal("7600"), Decimal("1500"), Decimal("900"))


@given(
    "bonds are at 9% (6pp below target)",
    target_fixture="snapshot",
)
def bonds_9() -> PortfolioSnapshot:
    return _snapshot(Decimal("7600"), Decimal("1500"), Decimal("900"))


@given(
    "stocks are at 72% (2pp above target)",
    target_fixture="snapshot",
)
def stocks_72() -> PortfolioSnapshot:
    return _snapshot(Decimal("7200"), Decimal("1500"), Decimal("1300"))


@given(
    parsers.parse("an asset deviating by {deviation}pp"),
    target_fixture="snapshot",
)
def deviating_asset(deviation: str) -> PortfolioSnapshot:
    dev = Decimal(deviation)
    # stocks at 70 + dev, rest adjusts
    stocks_val = (Decimal("70") + dev) * 100
    remaining = Decimal("10000") - stocks_val
    return _snapshot(stocks_val, remaining / 2, remaining / 2)


@when(
    "the threshold rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    report = calculate_deviations(snapshot, settings)
    rule = ThresholdDeviationRule()
    return rule.evaluate(report, snapshot, ThresholdParams())


@when(
    "the threshold rule evaluates with warning_pct=1.0 and critical_pct=3.0",
    target_fixture="signals",
)
def evaluate_custom_thresholds(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    report = calculate_deviations(snapshot, settings)
    rule = ThresholdDeviationRule()
    params = ThresholdParams(
        warning_pct=Decimal("1.0"),
        critical_pct=Decimal("3.0"),
    )
    return rule.evaluate(report, snapshot, params)


@when(
    "the threshold rule evaluates with warning_pct=3.0 and critical_pct=5.0",
    target_fixture="signals",
)
def evaluate_explicit_defaults(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    report = calculate_deviations(snapshot, settings)
    rule = ThresholdDeviationRule()
    params = ThresholdParams(
        warning_pct=Decimal("3.0"),
        critical_pct=Decimal("5.0"),
    )
    return rule.evaluate(report, snapshot, params)


@then("no signals are emitted")
@then("no signal is emitted")
def no_signals(signals: list[Any]) -> None:
    assert signals == []


@then(parsers.parse("a WARNING signal is emitted for {asset}"))
@then("a WARNING signal is emitted")
def warning_for_asset(signals: list[Any], asset: str = "") -> None:
    warnings = [s for s in signals if s.severity == SignalSeverity.WARNING]
    assert len(warnings) >= 1
    if asset:
        asset_warnings = [s for s in warnings if s.metadata.get("asset_id") == asset]
        assert len(asset_warnings) >= 1


@then(parsers.parse("a CRITICAL signal is emitted for {asset}"))
@then("a CRITICAL signal is emitted")
def critical_for_asset(signals: list[Any], asset: str = "") -> None:
    criticals = [s for s in signals if s.severity == SignalSeverity.CRITICAL]
    assert len(criticals) >= 1
    if asset:
        asset_criticals = [s for s in criticals if s.metadata.get("asset_id") == asset]
        assert len(asset_criticals) >= 1


@then(parsers.parse('the signal indicates "{direction}"'))
def signal_direction(signals: list[Any], direction: str) -> None:
    assert any(s.metadata.get("direction") == direction for s in signals)
