"""Tests for backtester API routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore


class TestListRuns:
    def test_empty_store_returns_empty_list(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.get("/api/runs")

        assert resp.status_code == 200
        body = resp.json()
        assert body == {"runs": [], "total": 0}

    def test_returns_summaries_for_saved_runs(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        tmp_store.save(make_run_result(run_id="run-aaa"))
        tmp_store.save(make_run_result(run_id="run-bbb"))

        resp = test_app.get("/api/runs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        ids = {r["run_id"] for r in body["runs"]}
        assert ids == {"run-aaa", "run-bbb"}
        # Verify summary fields
        first = body["runs"][0]
        assert "strategy" in first
        assert "final_value_median" in first
        assert "cagr_median" in first


class TestGetRun:
    def test_returns_full_run_detail(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        tmp_store.save(make_run_result(run_id="detail-run"))

        resp = test_app.get("/api/runs/detail-run")

        assert resp.status_code == 200
        body = resp.json()
        assert body["run"]["run_id"] == "detail-run"
        assert body["run"]["config"]["strategy"] == "pac_alignment"

    def test_not_found_returns_404(self, test_app: TestClient) -> None:
        resp = test_app.get("/api/runs/nonexistent")

        assert resp.status_code == 404

    def test_invalid_id_returns_400(self, test_app: TestClient) -> None:
        resp = test_app.get("/api/runs/invalid..id!@#")

        assert resp.status_code == 400


class TestDeleteRun:
    def test_deletes_existing_run(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        tmp_store.save(make_run_result(run_id="to-delete"))

        resp = test_app.delete("/api/runs/to-delete")

        assert resp.status_code == 204

        # Verify it's gone
        get_resp = test_app.get("/api/runs/to-delete")
        assert get_resp.status_code == 404

    def test_delete_not_found_returns_404(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.delete("/api/runs/nonexistent")

        assert resp.status_code == 404


class TestStartBacktest:
    def test_rejects_absolute_config_path(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.post(
            "/api/runs",
            json={
                "config": {
                    "strategy": "pac_alignment",
                    "start_date": "2020-01-01",
                    "end_date": "2023-12-31",
                },
                "config_path": "/etc/passwd",
            },
        )

        assert resp.status_code == 400
        assert "relative" in resp.json()["detail"].lower()

    def test_rejects_path_traversal(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.post(
            "/api/runs",
            json={
                "config": {
                    "strategy": "pac_alignment",
                    "start_date": "2020-01-01",
                    "end_date": "2023-12-31",
                },
                "config_path": "../../../etc/passwd",
            },
        )

        assert resp.status_code == 400

    def test_rejects_missing_config_file(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.post(
            "/api/runs",
            json={
                "config": {
                    "strategy": "pac_alignment",
                    "start_date": "2020-01-01",
                    "end_date": "2023-12-31",
                },
                "config_path": "nonexistent.yaml",
            },
        )

        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()


class TestListStrategies:
    def test_returns_discovered_strategies(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.get("/api/strategies")

        assert resp.status_code == 200
        body = resp.json()
        names = {s["name"] for s in body["strategies"]}
        assert "pac_alignment" in names

    def test_strategy_schema_has_properties(
        self,
        test_app: TestClient,
    ) -> None:
        resp = test_app.get("/api/strategies")

        body = resp.json()
        for strat in body["strategies"]:
            schema = strat["params_schema"]
            assert "properties" in schema or "title" in schema
