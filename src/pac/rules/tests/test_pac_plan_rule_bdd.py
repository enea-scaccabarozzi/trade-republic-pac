from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pytest_bdd import given, parsers, scenarios, then, when
from tests.conftest import make_settings

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.rules.builtin.pac_plan import PacPlanParams, PacPlanRule

scenarios("../features/pac_plan_rule.feature")


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


@given(
    "a portfolio with target allocation 70/15/15 for stocks/gold/bonds",
    target_fixture="settings",
)
def target_allocation() -> Settings:
    return make_settings()


@given(
    "a balanced portfolio at target allocation",
    target_fixture="snapshot",
)
def balanced_portfolio() -> PortfolioSnapshot:
    return _snapshot(Decimal("7000"), Decimal("1500"), Decimal("1500"))


@given(
    "the portfolio has only stocks worth 10000",
    target_fixture="snapshot",
)
def single_asset_portfolio() -> PortfolioSnapshot:
    return _snapshot(Decimal("10000"), Decimal("0"), Decimal("0"))


@when(
    "the PAC plan rule evaluates with default params",
    target_fixture="signals",
)
def evaluate_default(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = PacPlanRule()
    return rule.evaluate(report, snapshot, PacPlanParams())


@when(
    "the PAC plan rule evaluates with monthly_budget=1000.00",
    target_fixture="signals",
)
def evaluate_custom_budget(
    settings: Settings,
    snapshot: PortfolioSnapshot,
) -> list[Signal]:
    report = calculate_deviations(snapshot, settings)
    rule = PacPlanRule()
    params = PacPlanParams(monthly_budget=Decimal("1000.00"))
    return rule.evaluate(report, snapshot, params)


@then("exactly 1 signal is emitted")
def one_signal(signals: list[Signal]) -> None:
    assert len(signals) == 1


@then(parsers.parse('the signal name is "{name}"'))
def signal_name(signals: list[Signal], name: str) -> None:
    assert signals[0].name == name


@then("the signal severity is INFO")
def signal_is_info(signals: list[Signal]) -> None:
    assert signals[0].severity == SignalSeverity.INFO


@then(parsers.parse("the signal metadata contains a monthly_budget of {budget:g}"))
def metadata_budget(signals: list[Signal], budget: float) -> None:
    assert signals[0].metadata["monthly_budget"] == budget


@then("the signal metadata contains allocations for all 3 assets")
def metadata_has_all_assets(signals: list[Signal]) -> None:
    allocations = signals[0].metadata["allocations"]
    assert "stocks" in allocations
    assert "gold" in allocations
    assert "bonds" in allocations
    for alloc in allocations.values():
        assert "name" in alloc
        assert "amount" in alloc
        assert "pct_of_budget" in alloc


@then(parsers.parse('the signal message contains "{text}"'))
def message_contains(signals: list[Signal], text: str) -> None:
    assert text in signals[0].message


@then("each allocation percentage sums to 100")
def allocations_sum_to_100(signals: list[Signal]) -> None:
    allocations = signals[0].metadata["allocations"]
    total_pct = sum(a["pct_of_budget"] for a in allocations.values())
    assert abs(total_pct - 100.0) < 0.01
