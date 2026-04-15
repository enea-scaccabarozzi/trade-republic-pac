"""Tests for ResultStore research enhancements (Phase 8).

Covers backward compatibility, search, compare, export_csv,
build_run_result kwargs, and RunSummary new fields.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from pac.backtester.config import BacktestConfig
from pac.backtester.metrics.models import BacktestReport
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import (
    ComparisonResult,
    ConfidenceInterval,
    MetricValue,
    MonteCarloInfo,
    OOSMetadata,
    RunResult,
    SummaryStats,
)
from pac.backtester.results.store import ResultStore


def _make_run(
    *,
    run_id: str = "test-run-001",
    strategy: str = "pac_alignment",
    label: str | None = None,
    tags: list[str] | None = None,
    experiment_id: str | None = None,
    created_at: datetime | None = None,
    quantstats_metrics: dict[str, float] | None = None,
    oos_metadata: OOSMetadata | None = None,
    metrics: dict[str, dict[str, MetricValue]] | None = None,
    final_value_median: float = 15000.0,
) -> RunResult:
    """Factory for minimal RunResult fixtures with research fields."""
    return RunResult(
        run_id=run_id,
        created_at=created_at or datetime(2024, 1, 15, 10, 30, 0),
        config=BacktestConfig(
            strategy=strategy,
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
        ),
        monte_carlo=MonteCarloInfo(iterations=10, slippage_range=(0, 3)),
        metrics=metrics
        or {
            "strategy": {
                "cagr": MetricValue(p5=0.05, median=0.08, p95=0.11),
                "sharpe": MetricValue(p5=0.8, median=1.2, p95=1.5),
                "max_drawdown": MetricValue(p5=-0.25, median=-0.15, p95=-0.08),
            },
        },
        equity_curve=[],
        allocations=[],
        trades=[],
        summary=SummaryStats(
            total_invested=10000.0,
            final_value=ConfidenceInterval(
                p5=12000, median=final_value_median, p95=18000
            ),
            total_fees=ConfidenceInterval(p5=50, median=80, p95=120),
            total_trades=ConfidenceInterval(p5=20, median=30, p95=40),
            total_pac_executions=24,
        ),
        label=label,
        tags=tags or [],
        experiment_id=experiment_id,
        quantstats_metrics=quantstats_metrics,
        oos_metadata=oos_metadata,
    )


@pytest.fixture()
def store(tmp_path: Path) -> ResultStore:
    return ResultStore(base_dir=tmp_path)


class TestBackwardCompatibility:
    def test_load_legacy_json_without_new_fields(self, store: ResultStore) -> None:
        """JSON missing new fields deserializes with defaults."""
        r = _make_run()
        store.save(r)
        path = store._base_dir / f"{r.run_id}.json"
        data = json.loads(path.read_text())
        # Remove new fields to simulate legacy JSON
        for key in [
            "label",
            "tags",
            "experiment_id",
            "quantstats_report_path",
            "quantstats_metrics",
            "oos_metadata",
        ]:
            data.pop(key, None)
        path.write_text(json.dumps(data))
        loaded = store.load(r.run_id)
        assert loaded.label is None
        assert loaded.tags == []
        assert loaded.experiment_id is None
        assert loaded.quantstats_report_path is None
        assert loaded.quantstats_metrics is None
        assert loaded.oos_metadata is None

    def test_round_trip_with_new_fields(self, store: ResultStore) -> None:
        oos = OOSMetadata(
            method="holdout",
            holdout_date=date(2022, 1, 1),
            degradation_ratio=0.85,
        )
        r = _make_run(
            label="H1 PAC tilt",
            tags=["crisis", "pac-tilt"],
            experiment_id="exp-001",
            quantstats_metrics={"sharpe": 1.2, "cagr": 0.08},
            oos_metadata=oos,
        )
        store.save(r)
        loaded = store.load(r.run_id)
        assert loaded.label == "H1 PAC tilt"
        assert loaded.tags == ["crisis", "pac-tilt"]
        assert loaded.experiment_id == "exp-001"
        assert loaded.quantstats_metrics == {"sharpe": 1.2, "cagr": 0.08}
        assert loaded.oos_metadata is not None
        assert loaded.oos_metadata.method == "holdout"
        assert loaded.oos_metadata.holdout_date == date(2022, 1, 1)
        assert loaded.oos_metadata.degradation_ratio == 0.85

    @pytest.mark.parametrize(
        "method",
        ["holdout", "walk_forward", "leave_one_event_out"],
    )
    def test_oos_metadata_serialization(self, store: ResultStore, method: str) -> None:
        oos = OOSMetadata(method=method)  # type: ignore[arg-type]
        r = _make_run(run_id=f"oos-{method}", oos_metadata=oos)
        store.save(r)
        loaded = store.load(f"oos-{method}")
        assert loaded.oos_metadata is not None
        assert loaded.oos_metadata.method == method


class TestSearch:
    def test_search_no_filters_returns_all(self, store: ResultStore) -> None:
        for i in range(3):
            store.save(_make_run(run_id=f"run-{i}"))
            time.sleep(0.02)
        results = store.search()
        assert len(results) == 3

    def test_search_by_strategy(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1", strategy="strat_a"))
        store.save(_make_run(run_id="r2", strategy="strat_b"))
        results = store.search(strategy="strat_a")
        assert len(results) == 1
        assert results[0].run_id == "r1"

    def test_search_by_tags_subset(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1", tags=["crisis", "pac"]))
        store.save(_make_run(run_id="r2", tags=["other"]))
        assert len(store.search(tags=["crisis"])) == 1
        assert len(store.search(tags=["crisis", "pac"])) == 1
        assert len(store.search(tags=["foo"])) == 0

    def test_search_by_experiment_id(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1", experiment_id="exp-001"))
        store.save(_make_run(run_id="r2", experiment_id="exp-002"))
        results = store.search(experiment_id="exp-001")
        assert len(results) == 1
        assert results[0].experiment_id == "exp-001"

    def test_search_by_date_range(self, store: ResultStore) -> None:
        store.save(
            _make_run(
                run_id="old",
                created_at=datetime(2023, 6, 1, 12, 0, 0),
            )
        )
        store.save(
            _make_run(
                run_id="new",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
            )
        )
        results = store.search(after=date(2024, 1, 1))
        assert len(results) == 1
        assert results[0].run_id == "new"

        results = store.search(before=date(2023, 12, 31))
        assert len(results) == 1
        assert results[0].run_id == "old"

    def test_search_by_label_contains(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1", label="H1 PAC tilt"))
        store.save(_make_run(run_id="r2", label="Baseline"))
        results = store.search(label_contains="pac")
        assert len(results) == 1
        assert results[0].run_id == "r1"

    def test_search_combined_filters(self, store: ResultStore) -> None:
        store.save(
            _make_run(
                run_id="r1",
                strategy="strat_a",
                tags=["crisis"],
                label="H1",
            )
        )
        store.save(
            _make_run(
                run_id="r2",
                strategy="strat_b",
                tags=["crisis"],
                label="H2",
            )
        )
        results = store.search(strategy="strat_a", tags=["crisis"], label_contains="h1")
        assert len(results) == 1
        assert results[0].run_id == "r1"

    def test_search_empty_result(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1"))
        assert store.search(strategy="nonexistent") == []

    def test_search_skips_corrupt_files(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="good"))
        # Write corrupt JSON
        store._base_dir.mkdir(parents=True, exist_ok=True)
        (store._base_dir / "corrupt.json").write_text("{bad json!!")
        results = store.search()
        assert len(results) == 1
        assert results[0].run_id == "good"


class TestCompare:
    def test_compare_computes_deltas(self, store: ResultStore) -> None:
        store.save(
            _make_run(
                run_id="baseline",
                metrics={
                    "strategy": {
                        "cagr": MetricValue(p5=0.05, median=0.08, p95=0.11),
                        "sharpe": MetricValue(p5=0.8, median=1.0, p95=1.5),
                    },
                },
                final_value_median=10000.0,
            )
        )
        store.save(
            _make_run(
                run_id="candidate",
                metrics={
                    "strategy": {
                        "cagr": MetricValue(p5=0.06, median=0.10, p95=0.14),
                        "sharpe": MetricValue(p5=0.9, median=1.5, p95=2.0),
                    },
                },
                final_value_median=12000.0,
            )
        )
        result = store.compare("baseline", "candidate")
        assert isinstance(result, ComparisonResult)
        assert result.baseline_run_id == "baseline"
        assert result.candidate_run_id == "candidate"

        deltas_by_metric = {d.metric: d for d in result.deltas}
        assert "cagr" in deltas_by_metric
        cagr = deltas_by_metric["cagr"]
        assert cagr.baseline == 0.08
        assert cagr.candidate == 0.10
        assert cagr.delta == pytest.approx(0.02)
        assert cagr.delta_pct == pytest.approx(25.0)

        assert "final_value" in deltas_by_metric
        fv = deltas_by_metric["final_value"]
        assert fv.delta == pytest.approx(2000.0)

    def test_compare_labels_propagated(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="a", label="Baseline run"))
        store.save(_make_run(run_id="b", label="Candidate run"))
        result = store.compare("a", "b")
        assert result.baseline_label == "Baseline run"
        assert result.candidate_label == "Candidate run"

    def test_compare_missing_run_raises(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="exists"))
        with pytest.raises(FileNotFoundError):
            store.compare("exists", "nonexistent")

    def test_compare_zero_baseline_delta_pct_is_none(self, store: ResultStore) -> None:
        store.save(
            _make_run(
                run_id="zero",
                metrics={
                    "strategy": {
                        "cagr": MetricValue(p5=0.0, median=0.0, p95=0.0),
                    },
                },
            )
        )
        store.save(
            _make_run(
                run_id="nonzero",
                metrics={
                    "strategy": {
                        "cagr": MetricValue(p5=0.05, median=0.10, p95=0.15),
                    },
                },
            )
        )
        result = store.compare("zero", "nonzero")
        deltas_by_metric = {d.metric: d for d in result.deltas}
        assert deltas_by_metric["cagr"].delta_pct is None


class TestExportCsv:
    def test_export_all_runs(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1"))
        store.save(_make_run(run_id="r2"))
        path = store.export_csv()
        assert path.exists()
        with path.open() as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2

    def test_export_specific_runs(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1"))
        store.save(_make_run(run_id="r2"))
        store.save(_make_run(run_id="r3"))
        path = store.export_csv(run_ids=["r1", "r3"])
        with path.open() as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2
        ids = {row["run_id"] for row in reader}
        assert ids == {"r1", "r3"}

    def test_export_csv_tags_serialization(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="tagged", tags=["a", "b", "c"]))
        path = store.export_csv(run_ids=["tagged"])
        with path.open() as f:
            reader = list(csv.DictReader(f))
        assert reader[0]["tags"] == "a;b;c"

    def test_export_default_path(self, store: ResultStore) -> None:
        store.save(_make_run(run_id="r1"))
        path = store.export_csv()
        assert path == store._base_dir / "export.csv"

    def test_export_custom_path(self, store: ResultStore, tmp_path: Path) -> None:
        store.save(_make_run(run_id="r1"))
        custom = tmp_path / "custom" / "out.csv"
        path = store.export_csv(output=custom)
        assert path == custom
        assert path.exists()

    def test_export_empty_store(self, store: ResultStore) -> None:
        path = store.export_csv()
        assert path.exists()
        with path.open() as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 0


class TestBuildRunResult:
    def test_build_run_result_with_new_kwargs(
        self, three_iteration_report: BacktestReport
    ) -> None:
        result = build_run_result(
            three_iteration_report,
            label="test label",
            tags=["a", "b"],
            experiment_id="exp-001",
        )
        assert result.label == "test label"
        assert result.tags == ["a", "b"]
        assert result.experiment_id == "exp-001"

    def test_build_run_result_without_new_kwargs(
        self, three_iteration_report: BacktestReport
    ) -> None:
        result = build_run_result(three_iteration_report)
        assert result.label is None
        assert result.tags == []
        assert result.experiment_id is None
