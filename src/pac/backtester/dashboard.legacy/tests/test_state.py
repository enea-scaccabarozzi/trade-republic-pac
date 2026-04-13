"""Unit tests for dashboard state management."""

from __future__ import annotations

from pathlib import Path

import pytest

from pac.backtester.dashboard.state import (
    DashboardState,
    _to_summary,
)
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore


class TestToSummary:
    """Tests for _to_summary() pure function."""

    def test_extracts_fields(self, sample_run_result: RunResult) -> None:
        summary = _to_summary(sample_run_result)
        assert summary.run_id == sample_run_result.run_id
        assert summary.strategy == "pac_alignment"
        assert summary.start_date == "2020-01-01"
        assert summary.end_date == "2025-12-31"
        assert summary.final_value_median == 52000.0
        assert summary.iterations == 50

    def test_extracts_cagr(self, sample_run_result: RunResult) -> None:
        summary = _to_summary(sample_run_result)
        assert summary.cagr_median == 0.08

    def test_cagr_none_when_missing(self, sample_run_result: RunResult) -> None:
        result = sample_run_result.model_copy(update={"metrics": {"strategy": {}}})
        summary = _to_summary(result)
        assert summary.cagr_median is None


class TestDashboardState:
    """Tests for DashboardState."""

    def test_list_run_summaries(self, dashboard_state: DashboardState) -> None:
        summaries = dashboard_state.list_run_summaries()
        assert len(summaries) == 1
        assert summaries[0].strategy == "pac_alignment"

    def test_list_empty_store(self, tmp_path: Path) -> None:
        ds = DashboardState(store=ResultStore(base_dir=tmp_path / "empty"))
        assert ds.list_run_summaries() == []

    def test_load_run_not_found(self, tmp_path: Path) -> None:
        ds = DashboardState(store=ResultStore(base_dir=tmp_path / "empty"))
        with pytest.raises(FileNotFoundError):
            ds.load_run("nonexistent")

    def test_load_run(self, dashboard_state: DashboardState) -> None:
        result = dashboard_state.load_run("20260401_120000_pac_alignment")
        assert result.config.strategy == "pac_alignment"

    def test_load_run_cached(self, dashboard_state: DashboardState) -> None:
        r1 = dashboard_state.load_run("20260401_120000_pac_alignment")
        r2 = dashboard_state.load_run("20260401_120000_pac_alignment")
        assert r1 is r2  # same object reference = cached

    def test_refresh_clears_cache(self, dashboard_state: DashboardState) -> None:
        dashboard_state.load_run("20260401_120000_pac_alignment")
        dashboard_state.refresh()
        assert dashboard_state._cache == {}

    def test_skips_corrupt_files(self, tmp_path: Path) -> None:
        """Corrupt JSON files are skipped with a warning."""
        base = tmp_path / "backtests"
        base.mkdir(parents=True)
        (base / "corrupt_run.json").write_text("not valid json{{{")
        ds = DashboardState(store=ResultStore(base_dir=base))
        summaries = ds.list_run_summaries()
        assert summaries == []
