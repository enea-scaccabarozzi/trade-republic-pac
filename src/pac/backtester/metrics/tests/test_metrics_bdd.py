from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import BacktestSimulator, SimulationResult
from pac.backtester.engine.tests.conftest import (
    NoopStrategy,
    _NoopParams,
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.metrics.calculator import MetricsCalculator
from pac.backtester.metrics.models import BacktestReport, MetricSet
from pac.backtester.metrics.report import compute_report
from pac.rules.registry import SignalRegistry

scenarios("../features/metrics_framework.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# -- Background steps --------------------------------------------------------


@given("a portfolio with 3 assets: stocks (70%), gold (15%), bonds (15%)")
def _portfolio_3_assets(ctx: dict[str, Any]) -> None:
    ctx["settings"] = make_settings()
    ctx["price_data"] = make_three_asset_price_data(date(2024, 1, 1), 90)


@given("initial cash of €10,000")
def _initial_cash(ctx: dict[str, Any]) -> None:
    ctx["initial_cash"] = Decimal("10000")


@given("a monthly contribution of €500")
def _monthly_contribution(ctx: dict[str, Any]) -> None:
    ctx["monthly_contribution"] = Decimal("500")


@given("configured metrics: sharpe, max_drawdown, cagr")
def _configured_metrics(ctx: dict[str, Any]) -> None:
    ctx["metrics"] = ["sharpe", "max_drawdown", "cagr"]


# -- Given steps --------------------------------------------------------------


def _run_simulation(ctx: dict[str, Any], iterations: int) -> SimulationResult:
    """Helper to run a noop simulation with given iteration count."""
    benchmark = ctx.get("benchmark", True)
    config = BacktestConfig(
        strategy="noop",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_cash=ctx.get("initial_cash", Decimal("10000")),
        monthly_contribution=ctx.get("monthly_contribution", Decimal("500")),
        pac_execution_days=[2, 16],
        monte_carlo_iterations=iterations,
        slippage_days=(0, 0),
        metrics=ctx.get("metrics", ["sharpe", "max_drawdown", "cagr"]),
        benchmark=benchmark,
    )
    simulator = BacktestSimulator(
        config=config,
        settings=ctx["settings"],
        price_data=ctx["price_data"],
        signal_registry=SignalRegistry(),
        strategy=NoopStrategy(_NoopParams()),
        rng_seed=42,
    )
    return simulator.run()


@given(
    parsers.parse("a completed strategy simulation with {n:d} iterations"),
    target_fixture="simulation_result",
)
def _simulation_with_n_iterations(
    ctx: dict[str, Any],
    n: int,
) -> SimulationResult:
    result = _run_simulation(ctx, n)
    ctx["simulation_result"] = result
    return result


@given(
    "a completed strategy simulation",
    target_fixture="simulation_result",
)
def _simulation_default(ctx: dict[str, Any]) -> SimulationResult:
    result = _run_simulation(ctx, 3)
    ctx["simulation_result"] = result
    return result


@given("benchmark comparison is enabled")
def _benchmark_enabled(ctx: dict[str, Any]) -> None:
    ctx["benchmark"] = True
    # Re-run simulation with benchmark enabled
    result = _run_simulation(ctx, 3)
    ctx["simulation_result"] = result


@given("benchmark comparison is disabled")
def _benchmark_disabled(ctx: dict[str, Any]) -> None:
    ctx["benchmark"] = False
    # Re-run simulation with benchmark disabled
    result = _run_simulation(ctx, 3)
    ctx["simulation_result"] = result


@given(
    "a completed simulation with varying market conditions",
    target_fixture="simulation_result",
)
def _simulation_varying_conditions(ctx: dict[str, Any]) -> SimulationResult:
    result = _run_simulation(ctx, 3)
    ctx["simulation_result"] = result
    return result


# -- When steps ---------------------------------------------------------------


@when("metrics are computed")
def _compute_metrics(ctx: dict[str, Any]) -> None:
    result = ctx["simulation_result"]
    calculator = MetricsCalculator(result.config.metrics)
    ctx["metric_set"] = calculator.compute_all(
        result.iterations,
        scenario="strategy",
    )


@when("a backtest report is computed")
def _compute_report(ctx: dict[str, Any]) -> None:
    result = ctx["simulation_result"]
    ctx["report"] = compute_report(
        result,
        ctx["settings"],
        ctx["price_data"],
        rng_seed=42,
    )


# -- Then steps ---------------------------------------------------------------


@then(parsers.parse('the report contains metrics for "{metrics_str}"'))
def _report_contains_metrics(ctx: dict[str, Any], metrics_str: str) -> None:
    metric_set: MetricSet = ctx["metric_set"]
    expected = [m.strip().strip('"') for m in metrics_str.split(",")]
    for name in expected:
        assert name in metric_set.metrics, (
            f"Expected metric '{name}' not found in {list(metric_set.metrics)}"
        )


@then("each metric has median, P5, and P95 values")
def _metrics_have_percentiles(ctx: dict[str, Any]) -> None:
    metric_set: MetricSet = ctx["metric_set"]
    for name, result in metric_set.metrics.items():
        assert isinstance(result.median, float), f"{name} median is not float"
        assert isinstance(result.p5, float), f"{name} p5 is not float"
        assert isinstance(result.p95, float), f"{name} p95 is not float"


@then("the report includes both strategy and benchmark metric sets")
def _report_has_both_sets(ctx: dict[str, Any]) -> None:
    report: BacktestReport = ctx["report"]
    assert report.strategy is not None
    assert report.benchmark is not None


@then("both sets contain the same metric names")
def _both_sets_same_metrics(ctx: dict[str, Any]) -> None:
    report: BacktestReport = ctx["report"]
    assert report.benchmark is not None
    assert set(report.strategy.metrics) == set(report.benchmark.metrics)


@then("the report has no benchmark metrics")
def _report_no_benchmark(ctx: dict[str, Any]) -> None:
    report: BacktestReport = ctx["report"]
    assert report.benchmark is None


@then("max_drawdown median is less than or equal to 0")
def _max_drawdown_median_nonpositive(ctx: dict[str, Any]) -> None:
    metric_set: MetricSet = ctx["metric_set"]
    assert metric_set.metrics["max_drawdown"].median <= 0


@then("max_drawdown P95 is less than or equal to 0")
def _max_drawdown_p95_nonpositive(ctx: dict[str, Any]) -> None:
    metric_set: MetricSet = ctx["metric_set"]
    assert metric_set.metrics["max_drawdown"].p95 <= 0


@then("for each metric, median equals P5 and P95")
def _single_iteration_equal_bounds(ctx: dict[str, Any]) -> None:
    metric_set: MetricSet = ctx["metric_set"]
    for name, result in metric_set.metrics.items():
        assert result.median == pytest.approx(result.p5), (
            f"{name}: median ({result.median}) != p5 ({result.p5})"
        )
        assert result.median == pytest.approx(result.p95), (
            f"{name}: median ({result.median}) != p95 ({result.p95})"
        )
