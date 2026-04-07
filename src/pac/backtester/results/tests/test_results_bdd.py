from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from pac.backtester.metrics.models import BacktestReport
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore
from pac.backtester.results.tests.conftest import (
    _make_config,
    _make_iteration,
    _make_metric_set,
    _make_pac_trade,
    _make_rebalance_trade,
)

scenarios("../features/results_persistence.feature")


@pytest.fixture
def ctx(tmp_path: Path) -> dict[str, Any]:
    return {"tmp_path": tmp_path}


# -- Background steps --------------------------------------------------------


@given("a completed backtest report with 3 Monte Carlo iterations")
def _given_report(ctx: dict[str, Any]) -> None:
    pac_trades = [
        _make_pac_trade(date(2024, 1, 2), "stocks", 175.0),
        _make_pac_trade(date(2024, 1, 2), "gold", 37.5),
        _make_pac_trade(date(2024, 1, 2), "bonds", 37.5),
        _make_pac_trade(date(2024, 1, 16), "stocks", 175.0),
        _make_pac_trade(date(2024, 1, 16), "gold", 37.5),
        _make_pac_trade(date(2024, 1, 16), "bonds", 37.5),
    ]
    rebalance = _make_rebalance_trade(date(2024, 1, 10), "bonds")

    iterations = [
        _make_iteration(
            [10000, 10100, 10200, 10300, 10400, 10500],
            iteration=0,
            trades=[*list(pac_trades), rebalance],
        ),
        _make_iteration(
            [10000, 10200, 10500, 10700, 10900, 11000],
            iteration=1,
            trades=[*list(pac_trades), rebalance],
        ),
        _make_iteration(
            [10000, 10300, 10700, 11000, 11400, 11800],
            iteration=2,
            trades=[*list(pac_trades), rebalance],
        ),
    ]

    config = _make_config(monte_carlo_iterations=3)
    ctx["report"] = BacktestReport(
        strategy=_make_metric_set("strategy"),
        benchmark=_make_metric_set("benchmark"),
        config=config,
        strategy_iterations=iterations,
        benchmark_iterations=None,
    )


@given("a result store using a temporary directory")
def _given_store(ctx: dict[str, Any]) -> None:
    ctx["store"] = ResultStore(base_dir=ctx["tmp_path"])


# -- When steps ---------------------------------------------------------------


@when("the report is converted to a run result")
def _when_convert(ctx: dict[str, Any]) -> None:
    ctx["result"] = build_run_result(ctx["report"])


@when("the run result is saved")
def _when_save(ctx: dict[str, Any]) -> None:
    ctx["saved_path"] = ctx["store"].save(ctx["result"])


@when("the run result is deleted")
def _when_delete(ctx: dict[str, Any]) -> None:
    ctx["store"].delete(ctx["result"].run_id)


@when("listing all runs")
def _when_list(ctx: dict[str, Any]) -> None:
    ctx["run_ids"] = ctx["store"].list_runs()


# -- Then steps ---------------------------------------------------------------


@then("loading the run ID returns the same result")
def _then_load_same(ctx: dict[str, Any]) -> None:
    loaded = ctx["store"].load(ctx["result"].run_id)
    assert loaded == ctx["result"]


@then("the equity curve has one point per trading day")
def _then_curve_length(ctx: dict[str, Any]) -> None:
    result: RunResult = ctx["result"]
    report: BacktestReport = ctx["report"]
    expected = len(report.strategy_iterations[0].daily_values)
    assert len(result.equity_curve) == expected


@then("each point has P5, median, and P95 values")
def _then_curve_fields(ctx: dict[str, Any]) -> None:
    for point in ctx["result"].equity_curve:
        assert hasattr(point, "p5")
        assert hasattr(point, "median")
        assert hasattr(point, "p95")


@then("P5 is less than or equal to median")
def _then_p5_le_median(ctx: dict[str, Any]) -> None:
    for point in ctx["result"].equity_curve:
        assert point.p5 <= point.median


@then("median is less than or equal to P95")
def _then_median_le_p95(ctx: dict[str, Any]) -> None:
    for point in ctx["result"].equity_curve:
        assert point.median <= point.p95


@then("each allocation point includes all asset IDs and cash")
def _then_alloc_assets(ctx: dict[str, Any]) -> None:
    for point in ctx["result"].allocations:
        assert "stocks" in point.assets
        assert "gold" in point.assets
        assert "bonds" in point.assets
        assert "cash" in point.assets


@then("each asset has P5, median, and P95 percentage values")
def _then_alloc_ci(ctx: dict[str, Any]) -> None:
    for point in ctx["result"].allocations:
        for ci in point.assets.values():
            assert hasattr(ci, "p5")
            assert hasattr(ci, "median")
            assert hasattr(ci, "p95")


@then("the trade list is non-empty")
def _then_trades_nonempty(ctx: dict[str, Any]) -> None:
    assert len(ctx["result"].trades) > 0


@then("all trades have float amounts, not Decimal")
def _then_trades_float(ctx: dict[str, Any]) -> None:
    for t in ctx["result"].trades:
        assert isinstance(t.amount_eur, float)
        assert isinstance(t.quantity, float)
        assert isinstance(t.price, float)
        assert isinstance(t.fee, float)


@then(
    "the summary has total_invested, final_value, total_fees, total_trades",
)
def _then_summary_fields(ctx: dict[str, Any]) -> None:
    s = ctx["result"].summary
    assert s.total_invested > 0
    assert s.final_value is not None
    assert s.total_fees is not None
    assert s.total_trades is not None


@then("total_invested equals initial cash plus monthly contributions")
def _then_total_invested(ctx: dict[str, Any]) -> None:
    result: RunResult = ctx["result"]
    config = result.config
    # PAC trades from median iteration
    pac_count = len([
        t for t in result.trades if t.type == "pac_execution"
    ])
    contribution_per_pac = float(
        config.monthly_contribution / Decimal(len(config.pac_execution_days)),
    )
    expected = float(config.initial_cash) + contribution_per_pac * pac_count
    assert abs(result.summary.total_invested - expected) < 0.01


# -- Scenario: List runs shows saved results ----------------------------------


@given("two backtest results are saved")
def _given_two_saved(ctx: dict[str, Any]) -> None:
    import time

    r1 = build_run_result(ctx["report"])
    ctx["store"].save(r1)
    ctx["run_id_1"] = r1.run_id

    r2 = build_run_result(ctx["report"])
    r2_distinct = r2.model_copy(update={"run_id": r2.run_id + "_second"})
    time.sleep(0.05)
    ctx["store"].save(r2_distinct)
    ctx["run_id_2"] = r2_distinct.run_id


@then("both run IDs are returned")
def _then_both_ids(ctx: dict[str, Any]) -> None:
    run_ids = ctx["run_ids"]
    assert ctx["run_id_1"] in run_ids
    assert ctx["run_id_2"] in run_ids


@then("they are ordered newest first")
def _then_newest_first(ctx: dict[str, Any]) -> None:
    run_ids = ctx["run_ids"]
    assert len(run_ids) >= 2
    # run_id_2 was saved second so should appear first
    assert run_ids[0] == ctx["run_id_2"]


# -- Scenario: Delete removes a saved result ----------------------------------


@then("loading the run ID raises an error")
def _then_load_raises(ctx: dict[str, Any]) -> None:
    with pytest.raises(FileNotFoundError):
        ctx["store"].load(ctx["result"].run_id)
