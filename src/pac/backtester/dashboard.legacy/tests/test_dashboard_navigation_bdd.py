"""BDD step definitions for dashboard navigation feature."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when

from pac.backtester.dashboard.state import DashboardState
from pac.backtester.results.store import ResultStore

scenarios("../features/dashboard_navigation.feature")


@given("the result store contains saved backtest runs", target_fixture="ctx")
def given_populated_store(populated_store: ResultStore) -> dict[str, Any]:
    return {"state": DashboardState(store=populated_store)}


@given("the result store is empty")
def given_empty_store(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["state"] = DashboardState(store=ResultStore(base_dir=tmp_path / "empty"))


@given("the result store contains a corrupted JSON file")
def given_corrupt_store(
    ctx: dict[str, Any], populated_store: ResultStore, tmp_path: Path
) -> None:
    corrupt_file = tmp_path / "backtests" / "corrupt.json"
    corrupt_file.write_text("{invalid json")
    ctx["state"] = DashboardState(store=populated_store)


@when("the results page is loaded")
def when_page_loaded(ctx: dict[str, Any]) -> None:
    ctx["summaries"] = ctx["state"].list_run_summaries()


@when("the user clicks on a run row")
def when_click_row(ctx: dict[str, Any]) -> None:
    ctx["selected_run_id"] = ctx["summaries"][0].run_id


@then("a table displays the saved runs")
def then_table_shows_runs(ctx: dict[str, Any]) -> None:
    assert len(ctx["summaries"]) > 0


@then("each row shows the strategy name")
def then_row_has_strategy(ctx: dict[str, Any]) -> None:
    for s in ctx["summaries"]:
        assert s.strategy


@then("each row shows the date range")
def then_row_has_dates(ctx: dict[str, Any]) -> None:
    for s in ctx["summaries"]:
        assert s.start_date
        assert s.end_date


@then("each row shows the final value")
def then_row_has_value(ctx: dict[str, Any]) -> None:
    for s in ctx["summaries"]:
        assert s.final_value_median > 0


@then("a message indicates no results are available")
def then_empty_message(ctx: dict[str, Any]) -> None:
    assert ctx["summaries"] == []


@then("the detail URL contains the run ID")
def then_navigates_to_detail(ctx: dict[str, Any]) -> None:
    run_id = ctx["selected_run_id"]
    expected_path = f"/results/{run_id}"
    assert expected_path.startswith("/results/")
    assert run_id in expected_path


@then("the corrupted run is not shown in the table")
def then_no_corrupt(ctx: dict[str, Any]) -> None:
    for s in ctx["summaries"]:
        assert s.run_id != "corrupt"


@then("remaining valid runs are still displayed")
def then_valid_shown(ctx: dict[str, Any]) -> None:
    assert len(ctx["summaries"]) >= 1
