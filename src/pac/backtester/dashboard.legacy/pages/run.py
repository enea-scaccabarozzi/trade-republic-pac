"""Run backtest page — wizard form to configure, launch, and monitor backtests."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pydantic
from nicegui import run, ui

from pac.backtester.config import VALID_METRICS, BacktestConfig
from pac.backtester.dashboard.components.layout import render_layout
from pac.backtester.dashboard.state import state
from pac.backtester.runner import PipelineError, run_pipeline
from pac.backtester.strategies.discovery import discover_strategies


def _build_defaults() -> dict[str, Any]:
    """Return default values for all form fields."""
    return {
        "config_path": "pac.yaml",
        "strategy": "",
        "start_date": "2020-01-01",
        "end_date": date.today().isoformat(),
        "initial_cash": 10000.0,
        "monthly_contribution": 500.0,
        "pac_days": "2, 16",
        "settlement_fee": 1.0,
        "spread_bps": 10.0,
        "slippage_min": 0,
        "slippage_max": 3,
        "iterations": 100,
        "metrics": [
            "sortino",
            "calmar",
            "max_drawdown",
            "cagr",
            "sharpe",
        ],
        "benchmark": True,
        "strategy_params": "{}",
    }


def _prefill_from_config(
    cfg: BacktestConfig,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Merge a BacktestConfig into a field-defaults dict."""
    fields["strategy"] = cfg.strategy
    fields["start_date"] = cfg.start_date.isoformat()
    fields["end_date"] = cfg.end_date.isoformat()
    fields["initial_cash"] = float(cfg.initial_cash)
    fields["monthly_contribution"] = float(cfg.monthly_contribution)
    fields["pac_days"] = ", ".join(str(d) for d in cfg.pac_execution_days)
    fields["settlement_fee"] = float(cfg.settlement_fee)
    fields["spread_bps"] = float(cfg.spread_bps)
    fields["slippage_min"] = cfg.slippage_days[0]
    fields["slippage_max"] = cfg.slippage_days[1]
    fields["iterations"] = cfg.monte_carlo_iterations
    fields["metrics"] = list(cfg.metrics)
    fields["benchmark"] = cfg.benchmark
    fields["strategy_params"] = json.dumps(
        cfg.strategy_params,
        indent=2,
    )
    return fields


@ui.page("/run")
def run_page(from_run: str | None = None) -> None:
    """Render the run backtest wizard page."""
    render_layout(active="/run")

    # Discover strategies
    available = discover_strategies()
    strategy_names = sorted(available)

    # Build defaults, optionally pre-filling from a previous run
    defaults = _build_defaults()
    if from_run:
        try:
            prev = state.load_run(from_run)
            _prefill_from_config(prev.config, defaults)
        except (FileNotFoundError, ValueError):
            pass  # Ignore — use defaults

    ui.label("Run Backtest").classes("text-h4 q-mb-md")

    with ui.column().classes("w-full max-w-4xl mx-auto gap-4"):
        # ── Section A: Strategy Selection + Info Panel ────
        with ui.card().classes("w-full"):
            ui.label("Strategy").classes("text-h6")

            strategy_select = ui.select(
                options=strategy_names,
                value=(
                    defaults["strategy"]
                    if defaults["strategy"] in strategy_names
                    else (strategy_names[0] if strategy_names else "")
                ),
                label="Strategy",
            ).classes("w-full")

            info_card = ui.card().classes(
                "w-full bg-slate-50 dark:bg-slate-800",
            )

            def _update_info() -> None:
                info_card.clear()
                name = strategy_select.value
                if not name or name not in available:
                    return
                cls = available[name]
                doc = (cls.__doc__ or "").strip()
                first_para = doc.split("\n\n")[0] if doc else "\u2014"
                schema = cls.params_model.model_json_schema()
                props = schema.get("properties", {})

                with info_card:
                    ui.label("Strategy Info").classes(
                        "text-subtitle1 font-bold",
                    )
                    ui.label(first_para).classes(
                        "text-body2 q-mb-sm",
                    )
                    if props:
                        ui.label("Parameters schema:").classes(
                            "text-caption font-bold",
                        )
                        for pname, pinfo in props.items():
                            ptype = pinfo.get("type", "any")
                            pdefault = pinfo.get("default", "\u2014")
                            desc = pinfo.get("description", "")
                            line = f"  {pname}: {ptype}"
                            if pdefault != "\u2014":
                                line += f" (default: {pdefault})"
                            if desc:
                                line += f" \u2014 {desc}"
                            ui.label(line).classes(
                                "text-caption font-mono",
                            )
                    else:
                        ui.label(
                            "No configurable parameters.",
                        ).classes("text-caption text-grey")

            strategy_select.on_value_change(
                lambda _: _update_info(),
            )
            _update_info()  # Initial render

        # ── Section B: Configuration Fields ───────────────
        with ui.card().classes("w-full"):
            ui.label("Configuration").classes("text-h6")

            config_path_input = ui.input(
                label="Config Path",
                value=defaults["config_path"],
            ).classes("w-full")

            with ui.row().classes("w-full gap-4"):
                start_input = ui.input(
                    label="Start Date (YYYY-MM-DD)",
                    value=defaults["start_date"],
                ).classes("flex-1")
                end_input = ui.input(
                    label="End Date (YYYY-MM-DD)",
                    value=defaults["end_date"],
                ).classes("flex-1")

            with ui.row().classes("w-full gap-4"):
                initial_cash_input = ui.number(
                    label="Initial Cash (\u20ac)",
                    value=defaults["initial_cash"],
                    min=0,
                    format="%.2f",
                ).classes("flex-1")
                monthly_input = ui.number(
                    label="Monthly PAC (\u20ac)",
                    value=defaults["monthly_contribution"],
                    min=0,
                    format="%.2f",
                ).classes("flex-1")

            with ui.row().classes("w-full gap-4"):
                pac_days_input = ui.input(
                    label="PAC Days (comma-separated, 1-28)",
                    value=defaults["pac_days"],
                ).classes("flex-1")
                settlement_input = ui.number(
                    label="Settlement Fee (\u20ac)",
                    value=defaults["settlement_fee"],
                    min=0,
                    format="%.2f",
                ).classes("flex-1")

            with ui.row().classes("w-full gap-4"):
                spread_input = ui.number(
                    label="Spread (bps)",
                    value=defaults["spread_bps"],
                    min=0,
                    format="%.1f",
                ).classes("flex-1")
                slip_min_input = ui.number(
                    label="Slippage min (days)",
                    value=defaults["slippage_min"],
                    min=0,
                    step=1,
                    format="%.0f",
                ).classes("flex-1")
                slip_max_input = ui.number(
                    label="Slippage max (days)",
                    value=defaults["slippage_max"],
                    min=0,
                    step=1,
                    format="%.0f",
                ).classes("flex-1")

            iterations_input = ui.number(
                label="MC Iterations",
                value=defaults["iterations"],
                min=1,
                step=1,
                format="%.0f",
            ).classes("w-full")

            metrics_select = ui.select(
                options=sorted(VALID_METRICS),
                value=defaults["metrics"],
                multiple=True,
                label="Metrics",
            ).classes("w-full")

            benchmark_switch = ui.switch(
                "Compare against benchmark",
                value=defaults["benchmark"],
            )

            ui.label("Strategy Params (JSON)").classes(
                "text-caption q-mt-sm",
            )
            params_textarea = ui.textarea(
                value=defaults["strategy_params"],
            ).classes("w-full font-mono")

        # ── Section C: Action Bar + Progress ──────────────
        with ui.card().classes("w-full"):
            with ui.row().classes("gap-4"):
                run_button = ui.button(
                    "Run Backtest",
                    icon="play_arrow",
                    color="primary",
                )
                reset_button = ui.button(
                    "Reset to defaults",
                    icon="refresh",
                )

            progress_bar = ui.linear_progress(value=0).classes(
                "w-full q-mt-md",
            )
            progress_bar.set_visibility(False)
            status_label = ui.label("")
            status_label.set_visibility(False)

        # ── Reset handler ─────────────────────────────────
        def _on_reset() -> None:
            d = _build_defaults()
            config_path_input.value = d["config_path"]
            strategy_select.value = strategy_names[0] if strategy_names else ""
            start_input.value = d["start_date"]
            end_input.value = d["end_date"]
            initial_cash_input.value = d["initial_cash"]
            monthly_input.value = d["monthly_contribution"]
            pac_days_input.value = d["pac_days"]
            settlement_input.value = d["settlement_fee"]
            spread_input.value = d["spread_bps"]
            slip_min_input.value = d["slippage_min"]
            slip_max_input.value = d["slippage_max"]
            iterations_input.value = d["iterations"]
            metrics_select.value = d["metrics"]
            benchmark_switch.value = d["benchmark"]
            params_textarea.value = d["strategy_params"]

        reset_button.on_click(lambda _: _on_reset())

        # ── Submit handler ────────────────────────────────
        async def _on_submit() -> None:
            # Parse PAC days
            pac_parts = [
                p.strip() for p in str(pac_days_input.value).split(",") if p.strip()
            ]
            try:
                pac_day_list = [int(p) for p in pac_parts]
            except ValueError:
                ui.notify(
                    "PAC days must be comma-separated integers.",
                    type="negative",
                )
                return

            # Parse strategy params JSON
            try:
                params_dict = json.loads(
                    str(params_textarea.value or "{}"),
                )
                if not isinstance(params_dict, dict):
                    ui.notify(
                        "Strategy params must be a JSON object.",
                        type="negative",
                    )
                    return
            except json.JSONDecodeError as e:
                ui.notify(
                    f"Invalid JSON in strategy params: {e}",
                    type="negative",
                )
                return

            # Parse dates
            try:
                start_dt = date.fromisoformat(
                    str(start_input.value).strip(),
                )
            except ValueError:
                ui.notify(
                    "Invalid start date. Use YYYY-MM-DD format.",
                    type="negative",
                )
                return
            try:
                end_dt = date.fromisoformat(
                    str(end_input.value).strip(),
                )
            except ValueError:
                ui.notify(
                    "Invalid end date. Use YYYY-MM-DD format.",
                    type="negative",
                )
                return

            # Build BacktestConfig via Pydantic
            try:
                bt_config = BacktestConfig(
                    strategy=str(strategy_select.value),
                    strategy_params=params_dict,
                    start_date=start_dt,
                    end_date=end_dt,
                    initial_cash=Decimal(
                        str(initial_cash_input.value or 0),
                    ),
                    monthly_contribution=Decimal(
                        str(monthly_input.value or 0),
                    ),
                    pac_execution_days=pac_day_list,
                    settlement_fee=Decimal(
                        str(settlement_input.value or 0),
                    ),
                    spread_bps=Decimal(
                        str(spread_input.value or 0),
                    ),
                    slippage_days=(
                        int(slip_min_input.value or 0),
                        int(slip_max_input.value or 0),
                    ),
                    monte_carlo_iterations=int(
                        iterations_input.value or 100,
                    ),
                    metrics=list(metrics_select.value or []),
                    benchmark=bool(benchmark_switch.value),
                )
            except pydantic.ValidationError as e:
                for err in e.errors():
                    field = " \u2192 ".join(str(loc) for loc in err["loc"])
                    ui.notify(
                        f"{field}: {err['msg']}",
                        type="negative",
                    )
                return

            # Disable run button, show progress
            run_button.disable()
            progress_bar.value = 0
            progress_bar.set_visibility(True)
            status_label.text = "Starting pipeline..."
            status_label.set_visibility(True)

            # Shared progress state for thread-safe updates
            progress_state: dict[str, int] = {
                "current": 0,
                "total": 1,
            }

            def on_progress(current: int, total: int) -> None:
                progress_state["current"] = current
                progress_state["total"] = total

            # Timer to poll progress from the UI thread
            def _tick() -> None:
                cur = progress_state["current"]
                tot = progress_state["total"]
                if tot > 0:
                    progress_bar.value = cur / tot
                    status_label.text = f"Iteration {cur} of {tot}"

            timer = ui.timer(0.3, _tick)

            try:
                result, _path = await run.io_bound(
                    run_pipeline,
                    bt_config,
                    Path(str(config_path_input.value)),
                    seed=None,
                    on_progress=on_progress,
                )
            except PipelineError as e:
                timer.deactivate()
                run_button.enable()
                progress_bar.set_visibility(False)
                status_label.set_visibility(False)
                ui.notify(
                    f"Pipeline failed at [{e.step}]: {e.detail}",
                    type="negative",
                )
                return

            timer.deactivate()
            state.refresh()
            ui.navigate.to(f"/results/{result.run_id}")

        run_button.on_click(lambda _: _on_submit())
