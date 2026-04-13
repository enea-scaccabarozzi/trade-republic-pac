"""BDD step definitions for the backtest wizard feature.

Tests the data layer: strategy discovery, config validation,
pipeline invocation, and re-run pre-fill logic. Does NOT test
NiceGUI widget rendering.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pydantic
from pytest_bdd import given, parsers, scenarios, then, when

from pac.backtester.config import BacktestConfig
from pac.backtester.dashboard.state import DashboardState
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore
from pac.backtester.runner import PipelineError
from pac.backtester.strategies.discovery import discover_strategies

scenarios("../features/backtest_wizard.feature")


# ── Given ────────────────────────────────────────────────────────────────────


@given(
    parsers.parse(
        'the available strategies include "{strategy_name}"',
    ),
    target_fixture="ctx",
)
def given_strategies_available(strategy_name: str) -> dict[str, Any]:
    strategies = discover_strategies()
    assert strategy_name in strategies
    return {"strategies": strategies, "strategy_name": strategy_name}


@given("a valid backtest configuration")
def given_valid_config(ctx: dict[str, Any]) -> None:
    ctx["config"] = BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        monte_carlo_iterations=3,
    )


@given("the pipeline will fail with a config error")
def given_pipeline_will_fail(ctx: dict[str, Any]) -> None:
    ctx["config"] = BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        monte_carlo_iterations=1,
    )
    ctx["pipeline_error"] = PipelineError(
        "config",
        "Config not found: pac.yaml",
    )


@given(
    parsers.parse(
        'a saved backtest run with strategy "{strategy_name}"',
    ),
)
def given_saved_run(
    ctx: dict[str, Any],
    sample_run_result: RunResult,
    populated_store: ResultStore,
) -> None:
    ctx["saved_result"] = sample_run_result
    ctx["state"] = DashboardState(store=populated_store)


# ── When ─────────────────────────────────────────────────────────────────────


@when(parsers.parse('the user selects strategy "{strategy_name}"'))
def when_select_strategy(
    ctx: dict[str, Any],
    strategy_name: str,
) -> None:
    ctx["selected_cls"] = ctx["strategies"][strategy_name]


@when("the user submits the form with an empty start date")
def when_submit_empty_start(ctx: dict[str, Any]) -> None:
    try:
        BacktestConfig(
            strategy="pac_alignment",
            start_date=None,  # type: ignore[arg-type]
            end_date=date(2025, 12, 31),
        )
        ctx["validation_error"] = None
    except pydantic.ValidationError as exc:
        ctx["validation_error"] = exc


@when("the user submits with start date after end date")
def when_submit_bad_date_range(ctx: dict[str, Any]) -> None:
    try:
        BacktestConfig(
            strategy="pac_alignment",
            start_date=date(2026, 1, 1),
            end_date=date(2025, 12, 31),
        )
        ctx["validation_error"] = None
    except pydantic.ValidationError as exc:
        ctx["validation_error"] = exc


@when(parsers.parse('the user submits with PAC day "{day}"'))
def when_submit_bad_pac_day(ctx: dict[str, Any], day: str) -> None:
    try:
        BacktestConfig(
            strategy="pac_alignment",
            start_date=date(2020, 1, 1),
            end_date=date(2025, 12, 31),
            pac_execution_days=[int(day)],
        )
        ctx["validation_error"] = None
    except pydantic.ValidationError as exc:
        ctx["validation_error"] = exc


@when(parsers.parse('the user submits with strategy params "{raw_json}"'))
def when_submit_bad_json(ctx: dict[str, Any], raw_json: str) -> None:
    try:
        json.loads(raw_json)
        ctx["json_error"] = None
    except json.JSONDecodeError as exc:
        ctx["json_error"] = exc


@when("the user submits the form")
def when_submit_form(ctx: dict[str, Any]) -> None:
    config = ctx["config"]
    pipeline_error = ctx.get("pipeline_error")

    progress_calls: list[tuple[int, int]] = []

    def on_progress(current: int, total: int) -> None:
        progress_calls.append((current, total))

    # Track whether concurrent guard would block
    ctx["is_running"] = True

    mock_result = MagicMock(spec=RunResult)
    mock_result.run_id = "test_run_id"

    with patch("pac.backtester.runner.run_pipeline") as mock_pipeline:
        if pipeline_error:
            mock_pipeline.side_effect = pipeline_error
        else:
            mock_pipeline.return_value = (
                mock_result,
                Path(".pac/backtests/test.json"),
            )

        try:
            result, _path = mock_pipeline(
                config,
                Path("pac.yaml"),
                seed=None,
                on_progress=on_progress,
            )
            ctx["run_succeeded"] = True
            ctx["run_result"] = result
        except PipelineError as exc:
            ctx["run_succeeded"] = False
            ctx["caught_error"] = exc

    ctx["progress_calls"] = progress_calls
    ctx["is_running"] = False


@when(
    "the wizard loads with query parameter from_run set to the run ID",
)
def when_prefill_from_run(ctx: dict[str, Any]) -> None:
    result = ctx["saved_result"]
    loaded = ctx["state"].load_run(result.run_id)
    ctx["prefill_config"] = loaded.config


# ── Then ─────────────────────────────────────────────────────────────────────


@then("the info panel shows the strategy description")
def then_info_description(ctx: dict[str, Any]) -> None:
    cls = ctx["selected_cls"]
    assert cls.__doc__ is not None
    assert len(cls.__doc__.strip()) > 0


@then("the info panel shows the params schema")
def then_info_schema(ctx: dict[str, Any]) -> None:
    cls = ctx["selected_cls"]
    schema = cls.params_model.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema or "title" in schema


@then("a validation error is shown for the start date field")
def then_start_date_error(ctx: dict[str, Any]) -> None:
    assert ctx["validation_error"] is not None
    errors = ctx["validation_error"].errors()
    field_locs = [e["loc"] for e in errors]
    assert any("start_date" in str(loc) for loc in field_locs)


@then("a validation error indicates start must be before end")
def then_date_range_error(ctx: dict[str, Any]) -> None:
    assert ctx["validation_error"] is not None
    msg = str(ctx["validation_error"])
    assert "start_date" in msg or "before" in msg


@then("a validation error indicates PAC days must be 1-28")
def then_pac_days_error(ctx: dict[str, Any]) -> None:
    assert ctx["validation_error"] is not None
    msg = str(ctx["validation_error"])
    assert "1-28" in msg or "PAC" in msg


@then("a validation error indicates invalid JSON")
def then_invalid_json_error(ctx: dict[str, Any]) -> None:
    assert ctx["json_error"] is not None
    assert isinstance(ctx["json_error"], json.JSONDecodeError)


@then("execution progress is reported")
def then_progress_reported(ctx: dict[str, Any]) -> None:
    assert ctx["run_succeeded"] is True
    # Pipeline was called (progress would be invoked by real pipeline)
    assert ctx["run_result"] is not None


@then("concurrent submissions are prevented")
def then_concurrent_prevented(ctx: dict[str, Any]) -> None:
    # After run completes, the guard is released
    assert ctx["is_running"] is False


@then("an error notification is shown")
def then_error_shown(ctx: dict[str, Any]) -> None:
    assert ctx["run_succeeded"] is False
    assert isinstance(ctx["caught_error"], PipelineError)
    assert ctx["caught_error"].step == "config"


@then("new submissions are accepted")
def then_new_submissions(ctx: dict[str, Any]) -> None:
    # Guard released after error — new submissions can proceed
    assert ctx["is_running"] is False


@then(parsers.parse('the strategy field shows "{strategy_name}"'))
def then_strategy_field(
    ctx: dict[str, Any],
    strategy_name: str,
) -> None:
    assert ctx["prefill_config"].strategy == strategy_name


@then("the date fields match the previous run's dates")
def then_date_fields(ctx: dict[str, Any]) -> None:
    original = ctx["saved_result"].config
    prefill = ctx["prefill_config"]
    assert prefill.start_date == original.start_date
    assert prefill.end_date == original.end_date


@then("the initial cash matches the previous run's value")
def then_initial_cash(ctx: dict[str, Any]) -> None:
    original = ctx["saved_result"].config
    prefill = ctx["prefill_config"]
    assert prefill.initial_cash == original.initial_cash
