"""Tests for research API routes."""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from pac.backtester.api.app import create_app
from pac.backtester.api.deps import BacktestManager
from pac.backtester.api.routes.research import (
    _get_manifest,
    _validate_file_path,
)
from pac.backtester.research.manifest import ExperimentManifest
from pac.backtester.results.models import OOSMetadata, RunResult
from pac.backtester.results.store import ResultStore

_EXPERIMENT_TOML = """\
[experiment]
id = "001"
slug = "test-exp"
title = "Test Experiment"
hypothesis = "Testing is good"
created = 2024-01-15
tags = ["crisis", "test"]

[experiment.strategy]
name = "crisis_exploit"
"""

_EXPERIMENT_TOML_VALIDATED = """\
[experiment]
id = "002"
slug = "validated-exp"
title = "Validated Experiment"
hypothesis = "Validating is better"
created = 2024-02-20
tags = ["validated"]
status = "validated"
"""

_STRATEGY_YAML = """\
strategy: crisis_exploit
version: v3
description: "Final tuned params"
params:
  sell_fraction_mild: 0.05
  cooldown_days: 30
"""

_MALFORMED_YAML = """\
this is not valid: [yaml: content
  broken:
"""


@pytest.fixture()
def tmp_research_dir(tmp_path: Path) -> Path:
    """Create a temporary research/ directory with test data."""
    research = tmp_path / "research"

    # Experiment 001
    exp_dir = research / "experiments" / "001-test-exp"
    exp_dir.mkdir(parents=True)
    (exp_dir / "experiment.toml").write_text(_EXPERIMENT_TOML)
    (exp_dir / "README.md").write_text("# Test Readme\n\nSome content here.")
    figures = exp_dir / "figures"
    figures.mkdir()
    (figures / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    results = exp_dir / "results"
    results.mkdir()
    (results / "metrics.json").write_text('{"cagr": 0.08}')
    (results / "data.csv").write_text("col1,col2\n1,2\n")
    reports = exp_dir / "reports"
    reports.mkdir()
    (reports / "tearsheet.html").write_text("<html><body>Report</body></html>")

    # Experiment 002 (validated status)
    exp2_dir = research / "experiments" / "002-validated-exp"
    exp2_dir.mkdir(parents=True)
    (exp2_dir / "experiment.toml").write_text(_EXPERIMENT_TOML_VALIDATED)

    # Papers
    paper_dir = research / "papers" / "test-paper"
    paper_dir.mkdir(parents=True)
    (paper_dir / "paper.md").write_text("# My Paper\n\nAbstract here.")
    figs = paper_dir / "figures"
    figs.mkdir()
    (figs / "fig1.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    # Strategies
    strat_dir = research / "strategies"
    strat_dir.mkdir(parents=True)
    (strat_dir / "test_v1.yaml").write_text(_STRATEGY_YAML)
    (strat_dir / "broken.yaml").write_text(_MALFORMED_YAML)

    return research


@pytest.fixture()
def research_app(
    tmp_research_dir: Path,
    tmp_store: ResultStore,
) -> Generator[TestClient, None, None]:
    """TestClient wired with a temp research directory via DI override."""
    app = create_app(static_dir=None)
    app.state.manager = BacktestManager(store=tmp_store)

    manifest = ExperimentManifest(tmp_research_dir / "experiments")

    app.dependency_overrides[_get_manifest] = lambda: manifest

    # Also set env var for endpoints that use _research_dir() directly
    import os

    old_val = os.environ.get("PAC_RESEARCH_DIR")
    os.environ["PAC_RESEARCH_DIR"] = str(tmp_research_dir)

    client = TestClient(app)
    yield client

    # Cleanup
    if old_val is None:
        os.environ.pop("PAC_RESEARCH_DIR", None)
    else:
        os.environ["PAC_RESEARCH_DIR"] = old_val


@pytest.fixture()
def tmp_store(tmp_path: Path) -> ResultStore:
    """ResultStore backed by a temporary directory."""
    return ResultStore(base_dir=tmp_path / "backtests")


# ── Experiments ──


class TestListExperiments:
    def test_returns_experiments(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = {e["id"] for e in body["experiments"]}
        assert "001" in ids

    def test_empty_research_dir(
        self,
        tmp_path: Path,
        tmp_store: ResultStore,
    ) -> None:
        app = create_app(static_dir=None)
        app.state.manager = BacktestManager(store=tmp_store)
        empty = tmp_path / "empty" / "experiments"
        empty.mkdir(parents=True)
        manifest = ExperimentManifest(empty)
        app.dependency_overrides[_get_manifest] = lambda: manifest
        client = TestClient(app)

        resp = client.get("/api/research/experiments")

        assert resp.status_code == 200
        assert resp.json() == {"experiments": [], "total": 0}

    def test_filter_by_status(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments?status=validated")

        assert resp.status_code == 200
        body = resp.json()
        for exp in body["experiments"]:
            assert exp["status"] == "validated"

    def test_filter_by_tag(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments?tag=crisis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for exp in body["experiments"]:
            assert "crisis" in exp["tags"]


class TestGetExperiment:
    def test_returns_experiment_detail(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "001"
        assert body["title"] == "Test Experiment"
        assert body["hypothesis"] == "Testing is good"
        assert body["strategy_name"] == "crisis_exploit"

    def test_includes_linked_run_ids(
        self,
        research_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        run = make_run_result(run_id="linked-run", experiment_id="001")
        tmp_store.save(run)

        resp = research_app.get("/api/research/experiments/001")

        assert resp.status_code == 200
        body = resp.json()
        assert "linked-run" in body["linked_run_ids"]

    def test_includes_readme_html(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["readme_html"] is not None
        assert "<h1>" in body["readme_html"]
        assert "Test Readme" in body["readme_html"]

    def test_readme_html_is_sanitized(
        self,
        tmp_research_dir: Path,
        research_app: TestClient,
    ) -> None:
        readme = tmp_research_dir / "experiments" / "001-test-exp" / "README.md"
        readme.write_text("# Title\n\n<script>alert('xss')</script>\nSafe text.")

        resp = research_app.get("/api/research/experiments/001")

        assert resp.status_code == 200
        body = resp.json()
        assert "<script>" not in body["readme_html"]
        assert "Safe text" in body["readme_html"]

    def test_not_found_returns_404(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/999")
        assert resp.status_code == 404


# ── Experiment files ──


class TestGetExperimentFile:
    def test_serves_markdown_as_html(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001/files/README.md")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<h1>" in resp.text

    def test_serves_markdown_raw(self, research_app: TestClient) -> None:
        resp = research_app.get(
            "/api/research/experiments/001/files/README.md?raw=true"
        )

        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert resp.text.startswith("# Test Readme")
        assert "<h1>" not in resp.text

    def test_markdown_html_is_sanitized(
        self,
        tmp_research_dir: Path,
        research_app: TestClient,
    ) -> None:
        xss_md = tmp_research_dir / "experiments" / "001-test-exp" / "README.md"
        xss_md.write_text("# Title\n<img onerror='alert(1)' src='x'>")

        resp = research_app.get("/api/research/experiments/001/files/README.md")

        assert resp.status_code == 200
        assert "onerror" not in resp.text

    def test_serves_png_as_image(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001/files/figures/chart.png")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_serves_json(self, research_app: TestClient) -> None:
        resp = research_app.get(
            "/api/research/experiments/001/files/results/metrics.json"
        )

        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_serves_html_report(self, research_app: TestClient) -> None:
        resp = research_app.get(
            "/api/research/experiments/001/files/reports/tearsheet.html"
        )

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert resp.headers.get("content-security-policy") == "sandbox"

    def test_serves_csv(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001/files/results/data.csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_rejects_path_traversal_dotdot(self, tmp_research_dir: Path) -> None:
        base = tmp_research_dir / "experiments" / "001-test-exp"
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path(base, "../../../etc/passwd")
        assert exc_info.value.status_code == 400
        assert ".." in str(exc_info.value.detail)

    def test_rejects_hidden_files(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001/files/.env")
        assert resp.status_code == 400
        assert "hidden" in resp.json()["detail"].lower()

    def test_rejects_disallowed_extension(
        self,
        tmp_research_dir: Path,
        research_app: TestClient,
    ) -> None:
        bad = tmp_research_dir / "experiments" / "001-test-exp" / "script.sh"
        bad.write_text("#!/bin/bash\necho pwned")

        resp = research_app.get("/api/research/experiments/001/files/script.sh")
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower()

    def test_nonexistent_file_returns_404(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/experiments/001/files/nope.md")
        assert resp.status_code == 404

    def test_resolved_path_escape(
        self,
        tmp_research_dir: Path,
        research_app: TestClient,
    ) -> None:
        # Create a symlink that escapes the experiment directory
        exp_dir = tmp_research_dir / "experiments" / "001-test-exp"
        link = exp_dir / "escape.txt"
        target = tmp_research_dir.parent / "secret.txt"
        target.write_text("secret")
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")

        resp = research_app.get("/api/research/experiments/001/files/escape.txt")
        assert resp.status_code == 400


# ── Papers ──


class TestListPapers:
    def test_returns_papers(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/papers")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["papers"]) >= 1
        paper = body["papers"][0]
        assert paper["slug"] == "test-paper"
        assert paper["title"] == "My Paper"
        assert paper["has_figures"] is True

    def test_empty_papers_dir(
        self,
        tmp_path: Path,
        tmp_store: ResultStore,
    ) -> None:
        app = create_app(static_dir=None)
        app.state.manager = BacktestManager(store=tmp_store)
        research = tmp_path / "empty_research"
        research.mkdir()
        import os

        old = os.environ.get("PAC_RESEARCH_DIR")
        os.environ["PAC_RESEARCH_DIR"] = str(research)
        client = TestClient(app)
        resp = client.get("/api/research/papers")
        if old is None:
            os.environ.pop("PAC_RESEARCH_DIR", None)
        else:
            os.environ["PAC_RESEARCH_DIR"] = old

        assert resp.status_code == 200
        assert resp.json() == {"papers": []}


class TestPaperFiles:
    def test_serves_paper_markdown(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/papers/test-paper/files/paper.md")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "My Paper" in resp.text

    def test_serves_paper_markdown_raw(self, research_app: TestClient) -> None:
        resp = research_app.get(
            "/api/research/papers/test-paper/files/paper.md?raw=true"
        )

        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert resp.text.startswith("# My Paper")
        assert "<h1>" not in resp.text

    def test_paper_path_traversal_rejected(self, tmp_research_dir: Path) -> None:
        base = tmp_research_dir / "papers" / "test-paper"
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path(base, "../../../etc/passwd")
        assert exc_info.value.status_code == 400


# ── Strategy snapshots ──


class TestListStrategySnapshots:
    def test_returns_snapshots_with_strategy_name(
        self, research_app: TestClient
    ) -> None:
        resp = research_app.get("/api/research/strategies")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["snapshots"]) >= 1
        snap = next(s for s in body["snapshots"] if s["filename"] == "test_v1.yaml")
        assert snap["strategy_name"] == "crisis_exploit"
        assert snap["params"]["sell_fraction_mild"] == 0.05
        assert snap["params"]["cooldown_days"] == 30

    def test_malformed_yaml_skipped(self, research_app: TestClient) -> None:
        resp = research_app.get("/api/research/strategies")

        assert resp.status_code == 200
        filenames = [s["filename"] for s in resp.json()["snapshots"]]
        assert "broken.yaml" not in filenames


# ── Quantstats + OOS (on runs router) ──


class TestRunQuantstats:
    def test_json_format(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        run = make_run_result(
            run_id="qs-run",
            quantstats_metrics={"cagr": 0.08, "sharpe": 1.2},
        )
        tmp_store.save(run)

        resp = test_app.get("/api/runs/qs-run/quantstats?format=json")

        assert resp.status_code == 200
        body = resp.json()
        assert body["cagr"] == 0.08
        assert body["sharpe"] == 1.2

    def test_html_format(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        report_content = "<html><body>Tearsheet</body></html>"
        # Create the report file in the store directory
        report_rel = "reports/qs-html-run-report.html"
        report_path = tmp_store._base_dir / report_rel
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_content)

        run = make_run_result(
            run_id="qs-html-run",
            quantstats_report_path=report_rel,
        )
        tmp_store.save(run)

        resp = test_app.get("/api/runs/qs-html-run/quantstats?format=html")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Tearsheet" in resp.text
        assert resp.headers.get("content-security-policy") == "sandbox"

    def test_no_report_returns_404(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        run = make_run_result(run_id="no-report-run")
        tmp_store.save(run)

        resp = test_app.get("/api/runs/no-report-run/quantstats?format=html")
        assert resp.status_code == 404


class TestRunOOS:
    def test_returns_oos_metadata(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        from datetime import date

        oos = OOSMetadata(
            method="holdout",
            holdout_date=date(2022, 1, 1),
            degradation_ratio=0.85,
        )
        run = make_run_result(
            run_id="oos-run",
            oos_metadata=oos,
        )
        tmp_store.save(run)

        resp = test_app.get("/api/runs/oos-run/oos")

        assert resp.status_code == 200
        body = resp.json()
        assert body["method"] == "holdout"
        assert body["holdout_date"] == "2022-01-01"
        assert body["degradation_ratio"] == 0.85

    def test_no_oos_returns_null(
        self,
        test_app: TestClient,
        tmp_store: ResultStore,
        make_run_result: Callable[..., RunResult],
    ) -> None:
        run = make_run_result(run_id="no-oos-run")
        tmp_store.save(run)

        resp = test_app.get("/api/runs/no-oos-run/oos")

        assert resp.status_code == 200
        assert resp.json() is None
