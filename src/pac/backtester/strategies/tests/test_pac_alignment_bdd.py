from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.analysis.deviation import DeviationReport, DeviationResult
from pac.backtester.engine.actions import PacAdjustment
from pac.backtester.strategies.builtin.pac_alignment import (
    PacAlignmentParams,
    PacAlignmentStrategy,
)
from pac.backtester.strategies.discovery import discover_strategies
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

scenarios("../features/pac_alignment.feature")

_NOW = datetime(2024, 3, 2, tzinfo=UTC)

_DEFAULT_PAC_VOLUMES: dict[str, Decimal] = {
    "stocks": Decimal("350"),
    "gold": Decimal("75"),
    "bonds": Decimal("75"),
}


def _make_deviation_result(
    asset_id: str,
    actual: float,
    target: float,
) -> DeviationResult:
    actual_d = Decimal(str(actual))
    target_d = Decimal(str(target))
    dev = target_d - actual_d
    return DeviationResult(
        asset_id=asset_id,
        name=asset_id.capitalize(),
        actual_pct=actual_d,
        target_pct=target_d,
        deviation_pct=dev,
        abs_deviation_pct=abs(dev),
        severity=SignalSeverity.INFO,
    )


def _make_report(
    stocks_actual: float,
    gold_actual: float,
    bonds_actual: float,
) -> DeviationReport:
    deviations = {
        "stocks": _make_deviation_result("stocks", stocks_actual, 70.0),
        "gold": _make_deviation_result("gold", gold_actual, 15.0),
        "bonds": _make_deviation_result("bonds", bonds_actual, 15.0),
    }
    return DeviationReport(
        deviations=deviations,
        max_severity=SignalSeverity.INFO,
        timestamp=_NOW,
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {
        "pac_volumes": dict(_DEFAULT_PAC_VOLUMES),
        "snapshot": PortfolioSnapshot(positions=[], cash=Decimal("0"), timestamp=_NOW),
    }


# -- Given steps ----------------------------------------------------------


@given("a three-asset portfolio with targets 70% stocks / 15% gold / 15% bonds")
def _three_asset_portfolio(ctx: dict[str, Any]) -> None:
    ctx["report"] = _make_report(70.0, 15.0, 15.0)


@given("a PacAlignmentStrategy with default params")
def _default_strategy(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = PacAlignmentStrategy(PacAlignmentParams())


@given("the portfolio is at exactly the target allocation")
def _portfolio_at_target(ctx: dict[str, Any]) -> None:
    ctx["report"] = _make_report(70.0, 15.0, 15.0)


@given(parsers.re(r"stocks is overweight at (?P<stocks>\d+(?:\.\d+)?)% \(target 70%\)"))
def _stocks_overweight(ctx: dict[str, Any], stocks: str) -> None:
    ctx["stocks_actual"] = float(stocks)


@given(parsers.re(r"gold is underweight at (?P<gold>\d+(?:\.\d+)?)% \(target 15%\)"))
def _gold_underweight(ctx: dict[str, Any], gold: str) -> None:
    ctx["gold_actual"] = float(gold)


@given(parsers.re(r"bonds is underweight at (?P<bonds>\d+(?:\.\d+)?)% \(target 15%\)"))
def _bonds_underweight(ctx: dict[str, Any], bonds: str) -> None:
    ctx["bonds_actual"] = float(bonds)
    # Build full report now that all three values are set
    ctx["report"] = _make_report(
        ctx.get("stocks_actual", 70.0),
        ctx.get("gold_actual", 15.0),
        ctx["bonds_actual"],
    )


@given("any set of signals including cycle_inversion")
def _any_signals(ctx: dict[str, Any]) -> None:
    ctx["signals"] = [
        Signal(
            name="cycle_inversion",
            severity=SignalSeverity.WARNING,
            message="test",
            triggered_at=_NOW,
        )
    ]


# -- When steps -----------------------------------------------------------


@when("on_pac_date is called")
def _call_on_pac_date(ctx: dict[str, Any]) -> None:
    strategy: PacAlignmentStrategy = ctx["strategy"]
    ctx["result"] = strategy.on_pac_date(
        snapshot=ctx["snapshot"],
        report=ctx["report"],
        current_date=_NOW.date(),
        current_pac_volumes=ctx["pac_volumes"],
    )


@when(parsers.re(r"on_pac_date is called with blend_factor (?P<blend>\d+(?:\.\d+)?)"))
def _call_on_pac_date_with_blend(ctx: dict[str, Any], blend: str) -> None:
    params = PacAlignmentParams(blend_factor=Decimal(blend))
    strategy = PacAlignmentStrategy(params)
    ctx["strategy"] = strategy
    # Build report from partial values already set
    stocks = ctx.get("stocks_actual", 70.0)
    gold = ctx.get("gold_actual", 15.0)
    bonds = ctx.get("bonds_actual", 15.0)
    ctx["report"] = _make_report(stocks, gold, bonds)
    ctx["result"] = strategy.on_pac_date(
        snapshot=ctx["snapshot"],
        report=ctx["report"],
        current_date=_NOW.date(),
        current_pac_volumes=ctx["pac_volumes"],
    )


@when("on_signals is called")
def _call_on_signals(ctx: dict[str, Any]) -> None:
    strategy: PacAlignmentStrategy = ctx["strategy"]
    ctx["result"] = strategy.on_signals(
        signals=ctx.get("signals", []),
        snapshot=ctx["snapshot"],
        report=ctx["report"],
        current_date=_NOW.date(),
    )


@when("the builtin strategies package is scanned")
def _scan_builtin(ctx: dict[str, Any]) -> None:
    ctx["discovered"] = discover_strategies()


# -- Then steps -----------------------------------------------------------


@then("no PAC adjustment is returned")
def _check_no_pac_adjustment(ctx: dict[str, Any]) -> None:
    assert ctx["result"] is None


@then("the PAC allocation for stocks is the minimum (€1)")
def _check_stocks_minimum(ctx: dict[str, Any]) -> None:
    result: PacAdjustment = ctx["result"]
    assert result.new_volumes["stocks"] == Decimal("1.00")


@then("gold and bonds receive the majority of the PAC budget")
def _check_gold_bonds_majority(ctx: dict[str, Any]) -> None:
    result: PacAdjustment = ctx["result"]
    stocks_vol = result.new_volumes["stocks"]
    gold_vol = result.new_volumes.get("gold", Decimal("0"))
    bonds_vol = result.new_volumes.get("bonds", Decimal("0"))
    assert gold_vol + bonds_vol > stocks_vol


@then("a PacAdjustment is returned with volumes proportional to target weights")
def _check_pac_adjustment_returned(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["result"], PacAdjustment)


@then("the stocks allocation is 70% of the total PAC budget")
def _check_stocks_70_pct(ctx: dict[str, Any]) -> None:
    result: PacAdjustment = ctx["result"]
    total = sum(result.new_volumes.values())
    stocks_pct = result.new_volumes["stocks"] / total * 100
    assert abs(stocks_pct - Decimal("70")) <= Decimal("0.1")


@then("an empty list is returned")
def _check_empty_list(ctx: dict[str, Any]) -> None:
    assert ctx["result"] == []


@then(parsers.parse('"{name}" is in the discovered strategies'))
def _check_strategy_in_discovered(ctx: dict[str, Any], name: str) -> None:
    assert name in ctx["discovered"]
