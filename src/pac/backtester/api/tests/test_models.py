"""Tests for API Pydantic models."""

from __future__ import annotations

from collections.abc import Callable

from pac.backtester.api.models import ProgressEvent, RunSummary
from pac.backtester.api.routes.runs import _to_summary
from pac.backtester.results.models import RunResult


class TestRunSummaryFromRunResult:
    def test_extracts_correct_fields(
        self,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        result = make_run_result(run_id="sum-001", strategy="pac_alignment")

        summary = _to_summary(result)

        assert isinstance(summary, RunSummary)
        assert summary.run_id == "sum-001"
        assert summary.strategy == "pac_alignment"
        assert summary.iterations == 100
        assert summary.final_value_median == 15000
        assert summary.cagr_median == 0.08
        assert summary.sharpe_median == 1.2
        assert summary.max_drawdown_median == -0.15

    def test_handles_missing_metrics_gracefully(
        self,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        result = make_run_result()
        # Override metrics to empty
        result_no_metrics = result.model_copy(update={"metrics": {}})

        summary = _to_summary(result_no_metrics)

        assert summary.cagr_median is None
        assert summary.sharpe_median is None
        assert summary.max_drawdown_median is None

    def test_to_summary_includes_new_fields(
        self,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        result = make_run_result()
        result = result.model_copy(
            update={
                "label": "H1 tilt",
                "tags": ["crisis", "pac"],
                "experiment_id": "exp-001",
                "quantstats_metrics": {"sharpe": 1.2},
            }
        )
        summary = _to_summary(result)
        assert summary.label == "H1 tilt"
        assert summary.tags == ["crisis", "pac"]
        assert summary.experiment_id == "exp-001"
        assert summary.quantstats_metrics == {"sharpe": 1.2}

    def test_to_summary_defaults_for_legacy_run(
        self,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        result = make_run_result()
        summary = _to_summary(result)
        assert summary.label is None
        assert summary.tags == []
        assert summary.experiment_id is None
        assert summary.quantstats_metrics is None


class TestProgressEventSerialization:
    def test_model_dump_json_shape(self) -> None:
        event = ProgressEvent(
            current=5,
            total=10,
            status="running",
            run_id=None,
            error=None,
        )

        data = event.model_dump()

        assert data == {
            "current": 5,
            "total": 10,
            "status": "running",
            "run_id": None,
            "error": None,
        }

    def test_completed_event_includes_run_id(self) -> None:
        event = ProgressEvent(
            current=10,
            total=10,
            status="completed",
            run_id="final-run-id",
            error=None,
        )

        data = event.model_dump()

        assert data["status"] == "completed"
        assert data["run_id"] == "final-run-id"
