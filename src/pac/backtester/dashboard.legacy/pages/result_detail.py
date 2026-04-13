"""Result detail page — interactive viewer for a single backtest run."""

from __future__ import annotations

from datetime import date

import structlog
from nicegui import run, ui

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
from pac.backtester.dashboard.components.layout import render_layout
from pac.backtester.dashboard.state import state
from pac.backtester.results.models import RunResult

log = structlog.get_logger()


@ui.page("/results/{run_id}")
def result_detail_page(run_id: str) -> None:
    """Render the full result detail page."""
    render_layout(active="/")

    with ui.element("div").classes("w-full") as container:
        ui.spinner("dots", size="xl").classes("q-ma-xl")

    async def load_data() -> None:
        try:
            result = await run.io_bound(state.load_run, run_id)
        except (FileNotFoundError, ValueError) as exc:
            log.warning("run_not_found", run_id=run_id, exc=str(exc))
            container.clear()
            with container:
                ui.label("Run not found").classes("text-h4 text-negative")
                ui.label(
                    "The requested backtest run does not exist or has been deleted."
                ).classes("text-caption text-grey q-mt-sm")
                ui.button(
                    "Back to results",
                    on_click=lambda: ui.navigate.to("/"),
                )
            return
        except Exception as exc:
            log.error("load_failed", run_id=run_id, exc=str(exc))
            container.clear()
            with container:
                ui.label("Error loading run").classes("text-h4 text-negative")
                ui.label("The data file could not be loaded.").classes(
                    "text-caption text-grey q-mt-sm"
                )
                ui.button(
                    "Back to results",
                    on_click=lambda: ui.navigate.to("/"),
                )
            return

        container.clear()
        with container:
            _render_detail(run_id, result)

    ui.timer(0.1, load_data, once=True)


def _render_detail(run_id: str, result: RunResult) -> None:
    """Render the full detail view for a loaded run."""

    ui.label(f"Results: {result.config.strategy}").classes("text-h4")
    ui.label(f"Run ID: {run_id}").classes("text-subtitle1 text-grey")

    # ── Section 1: Config Summary Card ───────────────────────
    _render_config_summary(result)

    # ── Section 2: KPI Row ───────────────────────────────────
    _render_kpi_row(result)

    # ── Section 3: Filters ───────────────────────────────────
    asset_options: list[str] = []
    if result.allocations:
        asset_options = sorted(result.allocations[0].assets.keys())

    # Placeholders — assigned inside build, referenced in callback
    equity_plot: ui.plotly | None = None
    alloc_plot: ui.plotly | None = None
    dd_plot: ui.plotly | None = None
    trade_grid: ui.aggrid | None = None

    def update_views() -> None:
        start_dt = (
            date.fromisoformat(start_picker.value) if start_picker.value else None
        )
        end_dt = date.fromisoformat(end_picker.value) if end_picker.value else None
        selected = set(asset_select.value) if asset_select.value else None

        filtered_ec = filter_equity_curve(
            result.equity_curve,
            start_dt,
            end_dt,
        )
        filtered_alloc = filter_allocations(
            result.allocations,
            start_dt,
            end_dt,
            selected,
        )
        filtered_tr = filter_trades(
            result.trades,
            start_dt,
            end_dt,
            selected,
        )

        if equity_plot is not None:
            equity_plot.figure = build_equity_figure(filtered_ec)
            equity_plot.update()
        if alloc_plot is not None:
            alloc_plot.figure = build_allocation_figure(filtered_alloc)
            alloc_plot.update()
        if dd_plot is not None:
            dd_plot.figure = build_drawdown_figure(filtered_ec)
            dd_plot.update()
        if trade_grid is not None:
            trade_grid.options["rowData"] = trades_to_rows(filtered_tr)
            trade_grid.update()

    with ui.row().classes("w-full items-end gap-4 q-mt-md"):
        ui.label("Start Date").classes("text-caption text-grey")
        start_picker = ui.date(
            value=str(result.config.start_date),
            mask="YYYY-MM-DD",
            on_change=lambda _: update_views(),
        )
        ui.label("End Date").classes("text-caption text-grey")
        end_picker = ui.date(
            value=str(result.config.end_date),
            mask="YYYY-MM-DD",
            on_change=lambda _: update_views(),
        )
        asset_select = ui.select(
            options=asset_options,
            value=asset_options,
            multiple=True,
            label="Assets",
            on_change=lambda _: update_views(),
        ).classes("min-w-[200px]")

    # ── Section 4: Charts ────────────────────────────────────
    if result.equity_curve:
        with ui.card().classes("w-full"):
            ui.label("Equity Curve").classes("text-h6")
            equity_plot = ui.plotly(
                build_equity_figure(result.equity_curve),
            ).classes("w-full")
    else:
        with ui.card().classes("w-full"):
            ui.label("Equity Curve").classes("text-h6")
            ui.label("No equity data").classes("text-grey")

    if result.allocations:
        with ui.card().classes("w-full"):
            ui.label("Asset Allocation").classes("text-h6")
            alloc_plot = ui.plotly(
                build_allocation_figure(result.allocations),
            ).classes("w-full")
    else:
        with ui.card().classes("w-full"):
            ui.label("Asset Allocation").classes("text-h6")
            ui.label("No allocation data").classes("text-grey")

    if result.equity_curve:
        with ui.card().classes("w-full"):
            ui.label("Drawdown from Peak").classes("text-h6")
            dd_plot = ui.plotly(
                build_drawdown_figure(result.equity_curve),
            ).classes("w-full")

    # ── Section 5: Metrics Comparison Table ──────────────────
    _render_metrics_table(result)

    # ── Section 6: Trade Log (AG Grid) ───────────────────────
    trade_grid = ui.aggrid(
        {
            "columnDefs": [
                {
                    "headerName": "Date",
                    "field": "date",
                    "sortable": True,
                    "filter": True,
                },
                {
                    "headerName": "Type",
                    "field": "type",
                    "sortable": True,
                    "filter": True,
                },
                {
                    "headerName": "Asset",
                    "field": "asset",
                    "sortable": True,
                    "filter": True,
                },
                {
                    "headerName": "Direction",
                    "field": "direction",
                    "sortable": True,
                    "filter": True,
                },
                {
                    "headerName": "Amount (€)",
                    "field": "amount",
                    "sortable": True,
                    "filter": "agNumberColumnFilter",
                    "valueFormatter": (
                        "x.value?.toLocaleString("
                        "'de-DE',{style:'currency',currency:'EUR'})"
                    ),
                },
                {
                    "headerName": "Qty",
                    "field": "quantity",
                    "sortable": True,
                    "filter": "agNumberColumnFilter",
                    "valueFormatter": "x.value?.toFixed(4)",
                },
                {
                    "headerName": "Price (€)",
                    "field": "price",
                    "sortable": True,
                    "filter": "agNumberColumnFilter",
                    "valueFormatter": (
                        "x.value?.toLocaleString("
                        "'de-DE',{style:'currency',currency:'EUR'})"
                    ),
                },
                {
                    "headerName": "Fee (€)",
                    "field": "fee",
                    "sortable": True,
                    "filter": "agNumberColumnFilter",
                    "valueFormatter": "x.value?.toFixed(2)",
                },
                {
                    "headerName": "Skipped",
                    "field": "skipped",
                    "sortable": True,
                    "filter": True,
                },
            ],
            "rowData": trades_to_rows(result.trades),
            "defaultColDef": {"resizable": True},
            ":getRowStyle": """params => {
                if (params.data.direction === 'buy')
                    return {'background-color': 'rgba(76,175,80,0.1)'};
                if (params.data.direction === 'sell')
                    return {'background-color': 'rgba(244,67,54,0.1)'};
            }""",
            "pagination": True,
            "paginationPageSize": 25,
        },
    ).classes("w-full")

    # ── Back Button ──────────────────────────────────────────
    with ui.row().classes("gap-4 q-mt-md"):
        ui.button(
            "Back to results",
            icon="arrow_back",
            on_click=lambda: ui.navigate.to("/"),
        )
        ui.button(
            "Re-run with different params",
            icon="replay",
            on_click=lambda: ui.navigate.to(
                f"/run?from_run={run_id}",
            ),
        )


def _render_config_summary(result: RunResult) -> None:
    """Render the config summary card."""
    cfg = result.config
    mc = result.monte_carlo
    with ui.card().classes("w-full q-mt-md"):
        ui.label("Configuration").classes("text-h6")
        with ui.grid(columns=4).classes("w-full gap-4"):
            _config_item("Strategy", cfg.strategy)
            _config_item(
                "Date Range",
                f"{cfg.start_date} \u2013 {cfg.end_date}",
            )
            _config_item("MC Iterations", str(mc.iterations))
            _config_item(
                "Slippage Range",
                f"{mc.slippage_range[0]}\u2013{mc.slippage_range[1]} days",
            )
            _config_item("Initial Cash", f"\u20ac{cfg.initial_cash:,}")
            _config_item(
                "Monthly Contribution",
                f"\u20ac{cfg.monthly_contribution:,}",
            )
            _config_item(
                "PAC Execution Days",
                ", ".join(str(d) for d in cfg.pac_execution_days),
            )
            _config_item(
                "Settlement Fee",
                f"\u20ac{cfg.settlement_fee}",
            )


def _config_item(label: str, value: str) -> None:
    """Render a single config label/value pair."""
    with ui.column().classes("gap-0"):
        ui.label(label).classes("text-caption text-grey")
        ui.label(value).classes("text-body1")


def _render_kpi_row(result: RunResult) -> None:
    """Render the KPI cards row."""
    s = result.summary
    invested = s.total_invested
    final_median = s.final_value.median
    return_pct = (final_median - invested) / invested * 100 if invested > 0 else 0.0

    with ui.row().classes("w-full gap-4 q-mt-md"):
        _kpi_card("Total Invested", f"\u20ac{invested:,.0f}")
        _kpi_card(
            "Final Value",
            f"\u20ac{final_median:,.0f}",
            f"[\u20ac{s.final_value.p5:,.0f} \u2013 \u20ac{s.final_value.p95:,.0f}]",
        )
        _kpi_card("Total Return", f"{return_pct:.1f}%")
        _kpi_card(
            "Total Fees",
            f"\u20ac{s.total_fees.median:,.0f}",
            f"[\u20ac{s.total_fees.p5:,.0f} \u2013 \u20ac{s.total_fees.p95:,.0f}]",
        )
        _kpi_card(
            "Total Trades",
            f"{s.total_trades.median:.0f}",
            f"[{s.total_trades.p5:.0f} \u2013 {s.total_trades.p95:.0f}]",
        )


def _kpi_card(
    label: str,
    value: str,
    subtitle: str | None = None,
) -> None:
    """Render a single KPI card."""
    with ui.card().classes("text-center q-pa-md"):
        ui.label(label).classes("text-caption text-grey")
        ui.label(value).classes("text-h5")
        if subtitle:
            ui.label(subtitle).classes("text-caption text-grey")


def _render_metrics_table(result: RunResult) -> None:
    """Render the metrics comparison table."""
    rows, has_benchmark = build_metrics_rows(
        result.metrics,
        result.config.metrics,
    )
    if not rows:
        return

    columns = [
        {"name": "metric", "label": "Metric", "field": "metric"},
        {
            "name": "strategy",
            "label": "Strategy [P5\u2013P95]",
            "field": "strategy",
        },
    ]
    if has_benchmark:
        columns.append(
            {
                "name": "benchmark",
                "label": "Benchmark",
                "field": "benchmark",
            },
        )
        columns.append(
            {"name": "delta", "label": "Delta", "field": "delta"},
        )

    with ui.card().classes("w-full q-mt-md"):
        ui.label("Performance Metrics").classes("text-h6")
        table = ui.table(columns=columns, rows=rows).classes("w-full")

        if has_benchmark:
            table.add_slot(
                "body-cell-delta",
                """
                <q-td :props="props">
                  <span :class="props.row.delta_class">
                    {{ props.row.delta }}
                  </span>
                </q-td>
                """,
            )
