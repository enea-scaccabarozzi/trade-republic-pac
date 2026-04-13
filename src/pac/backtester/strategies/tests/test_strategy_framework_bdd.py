from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import (
    Action,
    ActionType,
    HardRebalanceOrder,
    PacAdjustment,
)
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.discovery import discover_strategies
from pac.backtester.strategies.registry import StrategyRegistry
from pac.backtester.strategies.tests.conftest import SimpleParams, SimpleStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

scenarios("../features/strategy_framework.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# -- Given steps ----------------------------------------------------------


@given(
    parsers.parse(
        'a strategy class with a params model requiring "{field}"',
    ),
)
def _strategy_with_params(ctx: dict[str, Any], field: str) -> None:
    ctx["params_field"] = field
    ctx["strategy_cls"] = SimpleStrategy


@given("a strategy that emits a hard rebalance on any signal")
def _strategy_emits_rebalance(ctx: dict[str, Any]) -> None:
    from pydantic import BaseModel

    class _RebalParams(BaseModel):
        amount: Decimal = Decimal("100")

    class RebalStrategy(BacktestStrategy[_RebalParams]):
        name = "rebal_test"

        def on_signals(
            self,
            signals: list[Signal],
            snapshot: PortfolioSnapshot,
            report: DeviationReport,
            current_date: date,
        ) -> list[Action]:
            return [
                Action(
                    type=ActionType.HARD_REBALANCE,
                    rebalance_orders=[
                        HardRebalanceOrder(
                            asset_id="stocks",
                            direction="buy",
                            amount_eur=self._params.amount,
                        ),
                    ],
                ),
            ]

    ctx["strategy"] = RebalStrategy(_RebalParams())


@given("a portfolio with deviations above threshold")
def _portfolio_with_deviations(ctx: dict[str, Any]) -> None:
    ctx["snapshot"] = PortfolioSnapshot(
        positions=[],
        cash=Decimal("10000"),
        timestamp=datetime(2024, 1, 15),
    )
    ctx["report"] = DeviationReport(
        deviations={},
        max_severity=SignalSeverity.INFO,
        timestamp=datetime(2024, 1, 15),
    )


@given("a strategy that overrides on_pac_date")
def _strategy_overrides_on_pac_date(ctx: dict[str, Any]) -> None:
    from pydantic import BaseModel

    class _AdjParams(BaseModel):
        pass

    class AdjStrategy(BacktestStrategy[_AdjParams]):
        name = "adj_test"

        def on_signals(
            self,
            signals: list[Signal],
            snapshot: PortfolioSnapshot,
            report: DeviationReport,
            current_date: date,
        ) -> list[Action]:
            return []

        def on_pac_date(
            self,
            snapshot: PortfolioSnapshot,
            report: DeviationReport,
            current_date: date,
            current_pac_volumes: dict[str, Decimal],
        ) -> PacAdjustment | None:
            return PacAdjustment(
                new_volumes={"stocks": Decimal("500"), "gold": Decimal("0")},
            )

    ctx["strategy"] = AdjStrategy(_AdjParams())


@given("a strategy with default on_pac_date")
def _strategy_default_on_pac_date(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = SimpleStrategy(SimpleParams())


@given(
    parsers.parse('a registered strategy "{name}" with params model'),
)
def _registered_strategy(ctx: dict[str, Any], name: str) -> None:
    registry = StrategyRegistry()
    registry.register(SimpleStrategy)
    ctx["registry"] = registry


@given("an empty strategy registry")
def _empty_registry(ctx: dict[str, Any]) -> None:
    ctx["registry"] = StrategyRegistry()


# -- When steps -----------------------------------------------------------


@when(
    parsers.parse("the strategy is instantiated with threshold {value:f}"),
)
def _instantiate_strategy(ctx: dict[str, Any], value: float) -> None:
    params = SimpleParams(threshold=value)
    ctx["instance"] = SimpleStrategy(params)


@when("signals are fed to the strategy")
def _feed_signals(ctx: dict[str, Any]) -> None:
    strategy = ctx["strategy"]
    signal = Signal(
        name="test_signal",
        severity=SignalSeverity.WARNING,
        message="test",
        triggered_at=datetime(2024, 1, 15),
    )
    ctx["actions"] = strategy.on_signals(
        [signal],
        ctx["snapshot"],
        ctx["report"],
        date(2024, 1, 15),
    )


@when("on_pac_date is called")
def _call_on_pac_date(ctx: dict[str, Any]) -> None:
    strategy = ctx["strategy"]
    ctx["pac_result"] = strategy.on_pac_date(
        snapshot=PortfolioSnapshot(
            positions=[],
            cash=Decimal("10000"),
            timestamp=datetime(2024, 1, 2),
        ),
        report=DeviationReport(
            deviations={},
            max_severity=SignalSeverity.INFO,
            timestamp=datetime(2024, 1, 2),
        ),
        current_date=date(2024, 1, 2),
        current_pac_volumes={"stocks": Decimal("350")},
    )


@when("on_pac_date is called on the default strategy")
def _call_on_pac_date_default(ctx: dict[str, Any]) -> None:
    strategy = ctx["strategy"]
    ctx["pac_result"] = strategy.on_pac_date(
        snapshot=PortfolioSnapshot(
            positions=[],
            cash=Decimal("10000"),
            timestamp=datetime(2024, 1, 2),
        ),
        report=DeviationReport(
            deviations={},
            max_severity=SignalSeverity.INFO,
            timestamp=datetime(2024, 1, 2),
        ),
        current_date=date(2024, 1, 2),
        current_pac_volumes={"stocks": Decimal("350")},
    )


@when("the builtin strategies package is scanned")
def _scan_builtin(ctx: dict[str, Any]) -> None:
    ctx["discovered"] = discover_strategies()


@when(
    parsers.parse('the registry instantiates "{name}" with threshold {value:f}'),
)
def _registry_instantiate(ctx: dict[str, Any], name: str, value: float) -> None:
    registry: StrategyRegistry = ctx["registry"]
    ctx["instance"] = registry.instantiate(name, {"threshold": value})


@when(
    parsers.parse('instantiation is attempted for "{name}"'),
)
def _attempt_instantiate_unknown(ctx: dict[str, Any], name: str) -> None:
    registry: StrategyRegistry = ctx["registry"]
    with pytest.raises(KeyError):
        registry.instantiate(name)
    ctx["key_error_raised"] = True


# -- Then steps -----------------------------------------------------------


@then("the strategy stores the params on self")
def _check_params_on_self(ctx: dict[str, Any]) -> None:
    assert ctx["instance"]._params.threshold == 5.0


@then("the strategy returns rebalance actions")
def _check_rebalance_actions(ctx: dict[str, Any]) -> None:
    actions: list[Action] = ctx["actions"]
    assert len(actions) > 0
    assert actions[0].type == ActionType.HARD_REBALANCE


@then("a PacAdjustment is returned with new volumes")
def _check_pac_adjustment(ctx: dict[str, Any]) -> None:
    result = ctx["pac_result"]
    assert isinstance(result, PacAdjustment)
    assert "stocks" in result.new_volumes


@then("None is returned")
def _check_none(ctx: dict[str, Any]) -> None:
    assert ctx["pac_result"] is None


@then(parsers.parse('"{name}" is in the discovered strategies'))
def _check_strategy_in_discovered(ctx: dict[str, Any], name: str) -> None:
    assert name in ctx["discovered"]


@then(parsers.parse("exactly {count:d} strategies are discovered"))
def _check_exact_strategy_count(ctx: dict[str, Any], count: int) -> None:
    assert len(ctx["discovered"]) == count


@then(
    parsers.parse("the strategy has threshold {value:f}"),
)
def _check_threshold(ctx: dict[str, Any], value: float) -> None:
    assert ctx["instance"]._params.threshold == value


@then("a KeyError is raised")
def _check_key_error(ctx: dict[str, Any]) -> None:
    assert ctx["key_error_raised"] is True
