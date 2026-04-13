"""Run listing page — displays all saved backtest results."""

from __future__ import annotations

from nicegui import run, ui

from pac.backtester.dashboard.components.layout import render_layout
from pac.backtester.dashboard.state import RunSummary, state


@ui.page("/")
def results_list_page() -> None:
    """Render the run listing page."""
    render_layout(active="/")

    ui.label("Backtest Results").classes("text-h4 q-mb-md")

    with ui.element("div").classes("w-full") as container:
        ui.spinner("dots", size="xl").classes("q-ma-xl")

    async def load_data() -> None:
        summaries = await run.io_bound(state.list_run_summaries)
        container.clear()
        with container:
            if not summaries:
                _render_empty_state()
                return
            _render_results_table(summaries)

    ui.timer(0.1, load_data, once=True)


def _render_empty_state() -> None:
    """Render the empty state card."""
    with ui.card().classes("w-full q-pa-lg text-center"):
        ui.icon("inbox").classes("text-6xl text-grey")
        ui.label("No backtest results found").classes("text-h6 text-grey")
        ui.label("Run a backtest from the CLI or the Run Backtest page.").classes(
            "text-grey"
        )


def _render_results_table(summaries: list[RunSummary]) -> None:
    """Render the results table with summaries."""
    columns = [
        {
            "name": "strategy",
            "label": "Strategy",
            "field": "strategy",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "start_date",
            "label": "Start",
            "field": "start_date",
            "sortable": True,
        },
        {
            "name": "end_date",
            "label": "End",
            "field": "end_date",
            "sortable": True,
        },
        {
            "name": "final_value",
            "label": "Final Value (€)",
            "field": "final_value",
            "sortable": True,
        },
        {
            "name": "cagr",
            "label": "CAGR",
            "field": "cagr",
            "sortable": True,
        },
        {
            "name": "iterations",
            "label": "MC Iters",
            "field": "iterations",
            "sortable": True,
        },
        {
            "name": "created",
            "label": "Created",
            "field": "created",
            "sortable": True,
        },
        {
            "name": "actions",
            "label": "",
            "field": "actions",
            "sortable": False,
            "align": "center",
        },
    ]

    rows = [
        {
            "run_id": s.run_id,
            "strategy": s.strategy,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "final_value": f"{s.final_value_median:,.0f}",
            "cagr": (f"{s.cagr_median:.1%}" if s.cagr_median is not None else "—"),
            "iterations": s.iterations,
            "created": s.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for s in summaries
    ]

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="run_id",
        selection="multiple",
        pagination={"rowsPerPage": 15},
    ).classes("w-full")

    table.add_slot(
        "body-cell-actions",
        r"""
        <q-td :props="props">
            <q-btn flat dense icon="visibility" color="primary"
                   @click.stop="$parent.$emit('view', props.row)" />
        </q-td>
        """,
    )
    table.on(
        "view",
        lambda e: ui.navigate.to(f"/results/{e.args['run_id']}"),
    )

    with ui.row().classes("q-mt-md gap-2"):
        ui.button(
            "Compare Selected",
            icon="compare_arrows",
            on_click=lambda: _navigate_compare(table),
        )
        ui.button("Refresh", icon="refresh", on_click=_refresh_list)


def _navigate_compare(table: ui.table) -> None:
    """Navigate to compare page with selected runs."""
    selected = table.selected
    if len(selected) < 2:
        ui.notify("Select at least 2 runs to compare", type="warning")
        return
    ids = ",".join(row["run_id"] for row in selected)
    ui.navigate.to(f"/compare?runs={ids}")


async def _refresh_list() -> None:
    """Clear cache and reload the page."""
    state.refresh()
    ui.navigate.to("/")
