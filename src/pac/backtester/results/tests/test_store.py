from __future__ import annotations

import json
from pathlib import Path

import pytest

from pac.backtester.metrics.models import BacktestReport
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore


@pytest.fixture
def store(tmp_path: Path) -> ResultStore:
    return ResultStore(base_dir=tmp_path)


@pytest.fixture
def sample_result(three_iteration_report: BacktestReport) -> RunResult:
    return build_run_result(three_iteration_report)


class TestSave:
    def test_creates_directory_and_file(
        self, tmp_path: Path, sample_result: RunResult,
    ) -> None:
        sub = tmp_path / "nested" / "dir"
        store = ResultStore(base_dir=sub)
        path = store.save(sample_result)
        assert path.exists()
        assert path.parent == sub

    def test_returns_path(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        path = store.save(sample_result)
        assert path.name == f"{sample_result.run_id}.json"

    def test_json_is_valid(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        path = store.save(sample_result)
        data = json.loads(path.read_text())
        assert isinstance(data, dict)
        assert "run_id" in data

    def test_overwrites_existing(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        store.save(sample_result)
        store.save(sample_result)  # no error
        runs = store.list_runs()
        assert len(runs) == 1


class TestLoad:
    def test_round_trip(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        store.save(sample_result)
        loaded = store.load(sample_result.run_id)
        assert loaded == sample_result

    def test_nonexistent_raises(self, store: ResultStore) -> None:
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent-run-id")

    def test_validates_run_id_path_traversal(
        self, store: ResultStore,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            store.load("../../etc/passwd")

    def test_rejects_special_characters(self, store: ResultStore) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            store.load("run id with spaces!")

    def test_corrupt_json_raises(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        store.save(sample_result)
        path = store._base_dir / f"{sample_result.run_id}.json"
        path.write_text('{"invalid": "data"}')
        with pytest.raises(Exception):  # noqa: B017
            store.load(sample_result.run_id)


class TestListRuns:
    def test_empty(self, store: ResultStore) -> None:
        assert store.list_runs() == []

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        store = ResultStore(base_dir=tmp_path / "does_not_exist")
        assert store.list_runs() == []

    def test_returns_newest_first(
        self,
        store: ResultStore,
        three_iteration_report: BacktestReport,
        single_iteration_report: BacktestReport,
    ) -> None:
        import time

        r1 = build_run_result(three_iteration_report)
        store.save(r1)

        r2 = build_run_result(single_iteration_report)
        # Give r2 a distinct run_id to avoid overwrite
        r2_distinct = r2.model_copy(
            update={"run_id": r2.run_id + "_second"},
        )
        time.sleep(0.05)
        store.save(r2_distinct)
        runs = store.list_runs()
        assert len(runs) == 2
        # newest first — r2 was saved second
        assert runs[0] == r2_distinct.run_id

    def test_ignores_non_json(
        self,
        store: ResultStore,
        sample_result: RunResult,
    ) -> None:
        store.save(sample_result)
        (store._base_dir / "notes.txt").write_text("not json")
        runs = store.list_runs()
        assert len(runs) == 1


class TestDelete:
    def test_removes_file(
        self, store: ResultStore, sample_result: RunResult,
    ) -> None:
        store.save(sample_result)
        store.delete(sample_result.run_id)
        with pytest.raises(FileNotFoundError):
            store.load(sample_result.run_id)

    def test_nonexistent_raises(self, store: ResultStore) -> None:
        with pytest.raises(FileNotFoundError):
            store.delete("nonexistent-run-id")

    def test_validates_run_id_path_traversal(
        self, store: ResultStore,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            store.delete("../../../important")
