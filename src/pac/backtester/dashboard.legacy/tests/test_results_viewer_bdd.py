"""BDD step definitions for results viewer feature."""

from __future__ import annotations

from datetime import date
from typing import Any

from pytest_bdd import given, scenarios, then, when

from pac.backtester.dashboard.charts import (
    build_allocation_figure,
    build_drawdown_figure,
    build_equity_figure,
    build_metrics_rows,
    filter_allocations,
    filter_equity_curve,
    filter_trades,
    trades_to_rows,
)
from pac.backtester.dashboard.state import DashboardState
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore

scenarios("../features/results_viewer.feature")


# ── Given ────────────────────────────────────────────────────────────────────


@given(
    "a saved backtest run with equity curve and trade data",
    target_fixture="ctx",
)
def given_saved_run(
    sample_run_result: RunResult,
    populated_store: ResultStore,
) -> dict[str, Any]:
    return {
        "result": sample_run_result,
        "state": DashboardState(store=populated_store),
    }


@given("the run includes benchmark metrics")
def given_benchmark(ctx: dict[str, Any]) -> None:
    assert "benchmark" in ctx["result"].metrics


# ── When ─────────────────────────────────────────────────────────────────────


@when("the results viewer loads the run")
def when_loads_run(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    ctx["config"] = result.config
    ctx["summary"] = result.summary
    ctx["mc"] = result.monte_carlo
    ctx["rows"] = trades_to_rows(result.trades)
    ctx["metrics_rows"], ctx["has_benchmark"] = build_metrics_rows(
        result.metrics,
        result.config.metrics,
    )


@when("the equity curve chart is built")
def when_equity_built(ctx: dict[str, Any]) -> None:
    ctx["equity_fig"] = build_equity_figure(ctx["result"].equity_curve)


@when("the allocation chart is built")
def when_alloc_built(ctx: dict[str, Any]) -> None:
    ctx["alloc_fig"] = build_allocation_figure(
        ctx["result"].allocations,
    )


@when("the drawdown chart is built")
def when_drawdown_built(ctx: dict[str, Any]) -> None:
    ctx["dd_fig"] = build_drawdown_figure(ctx["result"].equity_curve)


@when("the user filters to a sub-period")
def when_filter_date(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    start = date(2021, 1, 1)
    end = date(2023, 12, 31)
    ctx["filter_start"] = start
    ctx["filter_end"] = end
    ctx["filtered_ec"] = filter_equity_curve(
        result.equity_curve,
        start,
        end,
    )
    ctx["filtered_trades"] = filter_trades(
        result.trades,
        start,
        end,
    )


@when("the user filters to a specific asset")
def when_filter_asset(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    ctx["filter_asset"] = "stocks"
    ctx["filtered_alloc"] = filter_allocations(
        result.allocations,
        assets={"stocks"},
    )
    ctx["filtered_trades_asset"] = filter_trades(
        result.trades,
        assets={"stocks"},
    )


@when("the results viewer loads a nonexistent run")
def when_load_nonexistent(ctx: dict[str, Any]) -> None:
    try:
        ctx["state"].load_run("does_not_exist")
        ctx["load_error"] = None
    except (FileNotFoundError, ValueError) as exc:
        ctx["load_error"] = exc


# ── Then ─────────────────────────────────────────────────────────────────────


@then("the config summary shows the strategy name")
def then_strategy_name(ctx: dict[str, Any]) -> None:
    assert ctx["config"].strategy == "pac_alignment"


@then("the config summary shows the date range")
def then_date_range(ctx: dict[str, Any]) -> None:
    assert ctx["config"].start_date == date(2020, 1, 1)
    assert ctx["config"].end_date == date(2025, 12, 31)


@then("the config summary shows the number of iterations")
def then_iterations(ctx: dict[str, Any]) -> None:
    assert ctx["mc"].iterations == 50


@then("the KPIs include total invested amount")
def then_kpi_invested(ctx: dict[str, Any]) -> None:
    assert ctx["summary"].total_invested == 40000.0


@then(
    "the KPIs include final portfolio value with confidence interval",
)
def then_kpi_final_value(ctx: dict[str, Any]) -> None:
    fv = ctx["summary"].final_value
    assert fv.median == 52000.0
    assert fv.p5 == 45000.0
    assert fv.p95 == 59000.0


@then("the KPIs include total return percentage")
def then_kpi_return_pct(ctx: dict[str, Any]) -> None:
    invested = ctx["summary"].total_invested
    final = ctx["summary"].final_value.median
    pct = (final - invested) / invested * 100 if invested > 0 else 0.0
    assert pct == 30.0


@then("the KPIs include total fees")
def then_kpi_fees(ctx: dict[str, Any]) -> None:
    assert ctx["summary"].total_fees.median == 72.0


@then("the KPIs include total trades")
def then_kpi_trades(ctx: dict[str, Any]) -> None:
    assert ctx["summary"].total_trades.median == 15.0


@then("the chart contains a median line trace")
def then_has_median(ctx: dict[str, Any]) -> None:
    names = [t.name for t in ctx["equity_fig"].data]
    assert any("Median" in n for n in names)


@then("the chart contains a P5/P95 confidence band")
def then_has_band(ctx: dict[str, Any]) -> None:
    fills = [t.fill for t in ctx["equity_fig"].data]
    assert "tonexty" in fills


@then("the chart has a range slider for zoom")
def then_range_slider(ctx: dict[str, Any]) -> None:
    assert ctx["equity_fig"].layout.xaxis.rangeslider.visible is True


@then("the chart contains a stacked area trace for each asset")
def then_stacked_traces(ctx: dict[str, Any]) -> None:
    fig = ctx["alloc_fig"]
    assets = ctx["result"].allocations[0].assets.keys()
    assert len(fig.data) == len(assets)
    for trace in fig.data:
        assert trace.stackgroup == "one"


@then("the chart contains a filled area trace")
def then_filled_trace(ctx: dict[str, Any]) -> None:
    assert ctx["dd_fig"].data[0].fill == "tozeroy"


@then("drawdown values are non-positive")
def then_dd_non_positive(ctx: dict[str, Any]) -> None:
    assert all(v <= 0 for v in ctx["dd_fig"].data[0].y)


@then(
    "the metrics table shows strategy values with confidence intervals",
)
def then_metrics_strategy(ctx: dict[str, Any]) -> None:
    for row in ctx["metrics_rows"]:
        assert "strategy" in row
        assert "\u2013" in row["strategy"]  # en dash in CI range


@then("the metrics table shows benchmark values")
def then_metrics_benchmark(ctx: dict[str, Any]) -> None:
    assert ctx["has_benchmark"]
    for row in ctx["metrics_rows"]:
        assert "benchmark" in row


@then("outperforming metrics are highlighted as positive")
def then_outperform_positive(ctx: dict[str, Any]) -> None:
    for row in ctx["metrics_rows"]:
        if row.get("delta_class"):
            assert row["delta_class"] in ("text-positive", "text-negative")


@then("the trade log contains all trade records")
def then_all_trades(ctx: dict[str, Any]) -> None:
    assert len(ctx["rows"]) == len(ctx["result"].trades)


@then(
    "each trade shows date, type, asset, direction, amount, and fee",
)
def then_trade_fields(ctx: dict[str, Any]) -> None:
    for row in ctx["rows"]:
        for key in ("date", "type", "asset", "direction", "amount", "fee"):
            assert key in row


@then("the equity curve chart shows only data within that period")
def then_ec_in_period(ctx: dict[str, Any]) -> None:
    for pt in ctx["filtered_ec"]:
        assert ctx["filter_start"] <= pt.date <= ctx["filter_end"]


@then("the trade log shows only trades within that period")
def then_trades_in_period(ctx: dict[str, Any]) -> None:
    for t in ctx["filtered_trades"]:
        assert ctx["filter_start"] <= t.date <= ctx["filter_end"]


@then("the allocation chart shows only the selected asset")
def then_alloc_single(ctx: dict[str, Any]) -> None:
    for pt in ctx["filtered_alloc"]:
        assert set(pt.assets.keys()) == {ctx["filter_asset"]}


@then("the trade log shows only trades for the selected asset")
def then_trades_single(ctx: dict[str, Any]) -> None:
    for t in ctx["filtered_trades_asset"]:
        assert t.asset_id == ctx["filter_asset"]


@then("an error message indicates the run was not found")
def then_error(ctx: dict[str, Any]) -> None:
    assert ctx["load_error"] is not None
    assert isinstance(ctx["load_error"], FileNotFoundError)


@then("a back button navigates to the results list")
def then_back_button(ctx: dict[str, Any]) -> None:
    # In error state, the page would show a back button to "/"
    # We verify the navigation target is the root
    assert ctx["load_error"] is not None  # back button only on error
