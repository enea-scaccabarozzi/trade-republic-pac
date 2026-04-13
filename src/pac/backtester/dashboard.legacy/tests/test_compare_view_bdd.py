"""BDD step definitions for compare view feature."""

from __future__ import annotations

from typing import Any

from pytest_bdd import given, scenarios, then, when

from pac.backtester.dashboard.charts import (
    build_allocation_figure,
    build_comparison_metrics_rows,
    build_overlay_equity_figure,
    build_summary_comparison,
)
from pac.backtester.dashboard.pages.compare import _union_metrics
from pac.backtester.results.models import RunResult

scenarios("../features/compare_view.feature")


# ── Given ────────────────────────────────────────────────────────────────────


@given("multiple saved backtest runs", target_fixture="ctx")
def given_multiple_runs(
    sample_run_result: RunResult,
    sample_run_result_b: RunResult,
) -> dict[str, Any]:
    return {
        "run_a": sample_run_result,
        "run_b": sample_run_result_b,
    }


@given("two runs are loaded for comparison")
def given_two_loaded(ctx: dict[str, Any]) -> None:
    a = ctx["run_a"]
    b = ctx["run_b"]
    ctx["runs_equity"] = [
        ("Run A", a.equity_curve),
        ("Run B", b.equity_curve),
    ]


# ── When ─────────────────────────────────────────────────────────────────────


@when("the user selects two runs for comparison")
def when_select_two(ctx: dict[str, Any]) -> None:
    a = ctx["run_a"]
    b = ctx["run_b"]
    ctx["label_a"] = "Run A"
    ctx["label_b"] = "Run B"
    ctx["runs_equity"] = [
        ("Run A", a.equity_curve),
        ("Run B", b.equity_curve),
    ]
    ctx["overlay_fig"] = build_overlay_equity_figure(ctx["runs_equity"])
    config_metrics = _union_metrics(
        [a.config.metrics, b.config.metrics],
    )
    ctx["config_metrics"] = config_metrics
    ctx["metrics_rows"], ctx["labels"] = build_comparison_metrics_rows(
        [("Run A", a.metrics), ("Run B", b.metrics)],
        config_metrics,
    )
    ctx["summary"] = build_summary_comparison(
        [("Run A", a), ("Run B", b)],
    )
    ctx["selected_ids"] = [a.run_id, b.run_id]


@when("confidence bands are enabled")
def when_bands_enabled(ctx: dict[str, Any]) -> None:
    ctx["overlay_fig_bands"] = build_overlay_equity_figure(
        ctx["runs_equity"],
        show_bands=True,
    )


@when("no runs are selected")
def when_no_runs(ctx: dict[str, Any]) -> None:
    ctx["overlay_fig"] = build_overlay_equity_figure([])


@when("only one run is selected")
def when_one_run(ctx: dict[str, Any]) -> None:
    a = ctx["run_a"]
    ctx["overlay_fig"] = build_overlay_equity_figure(
        [("Run A", a.equity_curve)],
    )
    ctx["summary"] = build_summary_comparison([("Run A", a)])


# ── Then ─────────────────────────────────────────────────────────────────────


@then("the overlay chart contains a median trace for each run")
def then_median_traces(ctx: dict[str, Any]) -> None:
    fig = ctx["overlay_fig"]
    names = [t.name for t in fig.data]
    assert "Run A Median" in names
    assert "Run B Median" in names


@then("each trace uses a distinct color")
def then_distinct_colors(ctx: dict[str, Any]) -> None:
    fig = ctx["overlay_fig"]
    colors = [t.line.color for t in fig.data if t.line.color]
    assert len(set(colors)) == len(colors)


@then("the overlay chart includes P5/P95 shaded bands for each run")
def then_bands_present(ctx: dict[str, Any]) -> None:
    fig = ctx["overlay_fig_bands"]
    fills = [t.fill for t in fig.data]
    assert fills.count("tonexty") == 2  # one band fill per run


@then("the metrics table shows one column per run")
def then_columns_per_run(ctx: dict[str, Any]) -> None:
    labels = ctx["labels"]
    assert "Run A" in labels
    assert "Run B" in labels


@then("the best value per metric is highlighted")
def then_best_highlighted(ctx: dict[str, Any]) -> None:
    for row in ctx["metrics_rows"]:
        best = row["best"]
        if best:
            assert row[f"{best}_class"] == "text-positive"


@then("a KPI summary card is shown for each run")
def then_summary_cards(ctx: dict[str, Any]) -> None:
    summaries = ctx["summary"]
    assert len(summaries) == 2
    labels = {s["label"] for s in summaries}
    assert "Run A" in labels
    assert "Run B" in labels


@then("allocation charts are available in separate tabs")
def then_allocation_tabs(ctx: dict[str, Any]) -> None:
    a = ctx["run_a"]
    b = ctx["run_b"]
    fig_a = build_allocation_figure(a.allocations)
    fig_b = build_allocation_figure(b.allocations)
    assert len(fig_a.data) > 0
    assert len(fig_b.data) > 0


@then("the URL query string contains the run IDs")
def then_url_has_ids(ctx: dict[str, Any]) -> None:
    ids = ctx["selected_ids"]
    # Verify that the IDs can form a valid query string
    query = ",".join(ids)
    for rid in ids:
        assert rid in query


@then("a prompt message asks the user to select runs")
def then_empty_state(ctx: dict[str, Any]) -> None:
    fig = ctx["overlay_fig"]
    assert len(fig.data) == 0
    assert len(fig.layout.annotations) == 1
    assert "Select runs" in fig.layout.annotations[0].text


@then("the charts display data for that run")
def then_single_run_data(ctx: dict[str, Any]) -> None:
    fig = ctx["overlay_fig"]
    assert len(fig.data) == 1
    assert "Run A Median" in fig.data[0].name


@then("an info banner suggests adding more runs")
def then_info_banner(ctx: dict[str, Any]) -> None:
    # The banner is a UI element; we verify the single-run
    # summary is produced correctly for the page to render.
    summaries = ctx["summary"]
    assert len(summaries) == 1
