"""Compare view page — multi-run comparison with overlaid charts."""

from __future__ import annotations

import structlog
from nicegui import run, ui

from pac.backtester.dashboard.charts import (
    build_allocation_figure,
    build_comparison_metrics_rows,
    build_overlay_equity_figure,
    build_summary_comparison,
)
from pac.backtester.dashboard.components.layout import render_layout
from pac.backtester.dashboard.state import RunSummary, state
from pac.backtester.results.models import RunResult

log = structlog.get_logger()

_PALETTE = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
    "#FF97FF",
    "#FECB52",
]


def _union_metrics(metric_lists: list[list[str]]) -> list[str]:
    """Union of metric names preserving first-seen order.

    Args:
        metric_lists: Per-run metric name lists.

    Returns:
        Deduplicated list preserving insertion order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for metrics in metric_lists:
        for m in metrics:
            if m not in seen:
                seen.add(m)
                result.append(m)
    return result


def _make_label(run: RunResult) -> str:
    """Build a short label for a run."""
    return f"{run.config.strategy} ({run.config.start_date}\u2013{run.config.end_date})"


@ui.page("/compare")
def compare_page(runs: str | None = None) -> None:
    """Render the compare view page."""
    render_layout(active="/compare")

    ui.label("Compare Runs").classes("text-h4 q-mb-md")

    with ui.element("div").classes("w-full") as container:
        ui.spinner("dots", size="xl").classes("q-ma-xl")

    async def load_data() -> None:
        summaries = await run.io_bound(state.list_run_summaries)
        container.clear()
        with container:
            _render_compare_content(summaries, runs)

    ui.timer(0.1, load_data, once=True)


def _render_compare_content(
    summaries: list[RunSummary],
    runs: str | None,
) -> None:
    """Render the compare view content after summaries are loaded."""
    # Build selector options from all available runs
    options: dict[str, str] = {
        s.run_id: f"{s.strategy} ({s.start_date}\u2013{s.end_date})" for s in summaries
    }

    # Parse initial selection from URL
    initial_ids: list[str] = []
    if runs:
        valid_ids = {s.run_id for s in summaries}
        for rid in runs.split(","):
            rid = rid.strip()
            if rid in valid_ids:
                initial_ids.append(rid)

    # ── Reactive state ───────────────────────────────────────
    selected_ids: list[str] = list(initial_ids)

    # Placeholders for reactive updates
    equity_plot: ui.plotly | None = None
    summary_container: ui.row | None = None
    metrics_container: ui.card | None = None
    alloc_container: ui.card | None = None
    empty_card: ui.card | None = None
    info_banner: ui.element | None = None
    equity_container: ui.card | None = None

    def _load_selected() -> list[tuple[str, RunResult]]:
        """Load RunResults for selected IDs, skipping invalid."""
        loaded: list[tuple[str, RunResult]] = []
        for rid in selected_ids:
            try:
                result = state.load_run(rid)
                loaded.append((_make_label(result), result))
            except (FileNotFoundError, ValueError) as exc:
                log.warning("skipped_invalid_run", run_id=rid, exc=str(exc))
                ui.notify(
                    "A selected run could not be loaded and was skipped.",
                    type="warning",
                )
        return loaded

    def update_views() -> None:
        nonlocal equity_plot
        loaded = _load_selected()
        n = len(loaded)

        # Toggle empty state vs content
        if empty_card is not None:
            empty_card.set_visibility(n == 0)
        if info_banner is not None:
            info_banner.set_visibility(n == 1)
        for container in (
            equity_container,
            summary_container,
            metrics_container,
            alloc_container,
        ):
            if container is not None:
                container.set_visibility(n >= 1)

        if n == 0:
            return

        # Equity overlay
        runs_data = [(lbl, r.equity_curve) for lbl, r in loaded]
        fig = build_overlay_equity_figure(
            runs_data,
            show_bands=bands_toggle.value,
        )
        if equity_plot is not None:
            equity_plot.figure = fig
            equity_plot.update()

        # Summary cards
        if summary_container is not None:
            summary_container.clear()
            summaries_data = build_summary_comparison(loaded)
            with summary_container:
                for idx, s in enumerate(summaries_data):
                    color = _PALETTE[idx % len(_PALETTE)]
                    with (
                        ui.card()
                        .classes(
                            "q-pa-md text-center",
                        )
                        .style(f"border-left: 4px solid {color}")
                    ):
                        ui.label(s["label"]).classes(
                            "text-subtitle2 text-grey",
                        )
                        ui.label(s["final_value"]).classes("text-h5")
                        ui.label(s["final_value_ci"]).classes(
                            "text-caption text-grey",
                        )
                        ui.label(
                            f"Return: {s['total_return_pct']}",
                        ).classes("text-body2")
                        ui.label(
                            f"CAGR: {s['cagr']}",
                        ).classes("text-body2")
                        ui.label(
                            f"Invested: {s['total_invested']}",
                        ).classes("text-caption text-grey")
                        ui.label(
                            f"Fees: {s['total_fees']} | Trades: {s['total_trades']}",
                        ).classes("text-caption text-grey")

        # Metrics comparison table
        if metrics_container is not None:
            metrics_container.clear()
            config_metrics = _union_metrics(
                [r.config.metrics for _, r in loaded],
            )
            runs_metrics = [(lbl, r.metrics) for lbl, r in loaded]
            rows, labels = build_comparison_metrics_rows(
                runs_metrics,
                config_metrics,
            )
            if rows:
                cols: list[dict[str, object]] = [
                    {
                        "name": "metric",
                        "label": "Metric",
                        "field": "metric",
                        "align": "left",
                    },
                ]
                for lbl in labels:
                    cols.append(
                        {
                            "name": lbl,
                            "label": lbl,
                            "field": lbl,
                        }
                    )
                with metrics_container:
                    ui.label("Performance Metrics").classes("text-h6")
                    tbl = ui.table(
                        columns=cols,
                        rows=rows,
                    ).classes("w-full")
                    for lbl in labels:
                        tbl.add_slot(
                            f"body-cell-{lbl}",
                            '<q-td :props="props">'
                            f'  <span :class="props.row.{lbl}_class">'
                            "    {{ props.row['" + lbl + "'] }}"
                            "  </span>"
                            "</q-td>",
                        )

        # Allocation tabs
        if alloc_container is not None:
            alloc_container.clear()
            with alloc_container:
                ui.label("Asset Allocation").classes("text-h6")
                with ui.tabs().classes("w-full") as tabs:
                    tab_items = []
                    for lbl, _ in loaded:
                        tab_items.append(ui.tab(lbl))
                with ui.tab_panels(tabs).classes("w-full"):
                    for (_lbl, run), tab in zip(
                        loaded,
                        tab_items,
                        strict=True,
                    ):
                        with ui.tab_panel(tab):
                            ui.plotly(
                                build_allocation_figure(
                                    run.allocations,
                                ),
                            ).classes("w-full")

    def on_selection_change(e: object) -> None:
        nonlocal selected_ids
        val = run_selector.value
        selected_ids = list(val) if val else []
        ids_str = ",".join(selected_ids)
        ui.run_javascript(
            f"history.replaceState(null, '', '/compare?runs={ids_str}')",
        )
        update_views()

    # ── Run Selector ─────────────────────────────────────────
    with ui.card().classes("w-full q-mb-md"):
        ui.label("Select Runs").classes("text-h6")
        run_selector = ui.select(
            options=options,
            value=initial_ids,
            multiple=True,
            label="Runs to compare",
            on_change=on_selection_change,
        ).classes("w-full")

    # Bands toggle
    bands_toggle = ui.switch(
        "Show confidence bands",
        value=False,
        on_change=lambda _: update_views(),
    )

    # ── Empty state ──────────────────────────────────────────
    empty_card = ui.card().classes("w-full q-pa-lg text-center")
    with empty_card:
        ui.icon("compare_arrows").classes("text-6xl text-grey")
        ui.label("Select 2 or more runs to compare").classes(
            "text-h6 text-grey",
        )
    empty_card.set_visibility(len(selected_ids) == 0)

    # ── Info banner for single run ───────────────────────────
    info_banner = ui.element("div").classes("w-full")
    with info_banner:
        ui.html(
            '<div class="q-banner q-banner--dense q-mb-md">'
            '<div class="q-banner__avatar">'
            '<i class="q-icon material-icons">info</i></div>'
            '<div class="q-banner__content">'
            "Add more runs for comparison</div></div>"
        )
    info_banner.set_visibility(len(selected_ids) == 1)

    # ── Equity Curve ─────────────────────────────────────────
    equity_container = ui.card().classes("w-full")
    with equity_container:
        ui.label("Equity Curve Comparison").classes("text-h6")
        equity_plot = ui.plotly(
            build_overlay_equity_figure([]),
        ).classes("w-full")
    equity_container.set_visibility(len(selected_ids) >= 1)

    # ── Summary Cards ────────────────────────────────────────
    summary_container = ui.row().classes("w-full gap-4 q-mt-md")
    summary_container.set_visibility(len(selected_ids) >= 1)

    # ── Metrics Table ────────────────────────────────────────
    metrics_container = ui.card().classes("w-full q-mt-md")
    metrics_container.set_visibility(len(selected_ids) >= 1)

    # ── Allocation Tabs ──────────────────────────────────────
    alloc_container = ui.card().classes("w-full q-mt-md")
    alloc_container.set_visibility(len(selected_ids) >= 1)

    # Initial render
    if selected_ids:
        update_views()
