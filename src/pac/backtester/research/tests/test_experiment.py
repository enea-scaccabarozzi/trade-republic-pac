from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from pac.backtester.research.experiment import load_experiment

_MINIMAL_TOML = """\
[experiment]
id = "001"
slug = "test-idea"
title = "Test Idea"
hypothesis = "This is a hypothesis"
created = 2026-04-13
tags = ["test"]
"""

_TOML_WITH_STRATEGY = """\
[experiment]
id = "002"
slug = "strategy-test"
title = "Strategy Test"
hypothesis = "Testing strategy config"
created = 2026-04-13
tags = []

[experiment.strategy]
name = "crisis_exploit"
params_file = "../../strategies/params.yaml"
"""


def _write_toml(experiment_dir: Path, content: str) -> None:
    experiment_dir.mkdir(parents=True, exist_ok=True)
    (experiment_dir / "experiment.toml").write_text(content, encoding="utf-8")


class TestLoadExperiment:
    def test_loads_minimal_toml(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)

        state = load_experiment(exp_dir)

        assert state.id == "001"
        assert state.slug == "test-idea"
        assert state.title == "Test Idea"
        assert state.hypothesis == "This is a hypothesis"
        assert state.created == date(2026, 4, 13)
        assert state.tags == ["test"]
        assert state.status == "exploring"
        assert state.strategy_name is None
        assert state.strategy_params_file is None

    def test_loads_with_strategy_section(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "002-strategy-test"
        _write_toml(exp_dir, _TOML_WITH_STRATEGY)

        state = load_experiment(exp_dir)

        assert state.strategy_name == "crisis_exploit"
        assert state.strategy_params_file == "../../strategies/params.yaml"

    def test_status_exploring_when_no_results(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)

        state = load_experiment(exp_dir)

        assert state.status == "exploring"

    def test_status_validated_when_results_exist(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        results_dir = exp_dir / "results"
        results_dir.mkdir()
        (results_dir / "run_001.json").write_text("{}", encoding="utf-8")

        state = load_experiment(exp_dir)

        assert state.status == "validated"

    def test_status_manual_override(self, tmp_path: Path) -> None:
        toml_content = """\
[experiment]
id = "001"
slug = "rejected-idea"
title = "Rejected Idea"
hypothesis = "Bad hypothesis"
created = 2026-04-13
tags = []
status = "rejected"
"""
        exp_dir = tmp_path / "001-rejected-idea"
        _write_toml(exp_dir, toml_content)

        state = load_experiment(exp_dir)

        assert state.status == "rejected"

    def test_artifacts_lists_files(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        (exp_dir / "explore.py").write_text("# notebook", encoding="utf-8")
        (exp_dir / "notes.md").write_text("# notes", encoding="utf-8")

        state = load_experiment(exp_dir)

        assert "explore.py" in state.artifacts
        assert "notes.md" in state.artifacts
        assert "experiment.toml" not in state.artifacts

    def test_artifacts_excludes_pycache(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        pycache = exp_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-311.pyc").write_text("", encoding="utf-8")
        (exp_dir / "explore.py").write_text("# notebook", encoding="utf-8")

        state = load_experiment(exp_dir)

        assert not any("__pycache__" in a for a in state.artifacts)
        assert not any(".pyc" in a for a in state.artifacts)
        assert "explore.py" in state.artifacts

    def test_reports_lists_html(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        reports_dir = exp_dir / "reports"
        reports_dir.mkdir()
        (reports_dir / "tearsheet.html").write_text("<html>", encoding="utf-8")
        (reports_dir / "summary.html").write_text("<html>", encoding="utf-8")

        state = load_experiment(exp_dir)

        assert len(state.reports) == 2
        assert "reports/summary.html" in state.reports
        assert "reports/tearsheet.html" in state.reports

    def test_reports_empty_when_no_dir(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)

        state = load_experiment(exp_dir)

        assert state.reports == []

    def test_result_files_lists_json_csv(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        results_dir = exp_dir / "results"
        results_dir.mkdir()
        (results_dir / "run_001.json").write_text("{}", encoding="utf-8")
        (results_dir / "metrics.csv").write_text("a,b\n1,2", encoding="utf-8")

        state = load_experiment(exp_dir)

        assert len(state.result_files) == 2
        assert "results/metrics.csv" in state.result_files
        assert "results/run_001.json" in state.result_files

    def test_concluded_from_result_mtime(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)
        results_dir = exp_dir / "results"
        results_dir.mkdir()
        result_file = results_dir / "run.json"
        result_file.write_text("{}", encoding="utf-8")
        # Set a known mtime: 2026-01-15 12:00:00 UTC
        os.utime(result_file, (1768507200, 1768507200))

        state = load_experiment(exp_dir)

        assert state.concluded == date(2026, 1, 15)

    def test_concluded_none_when_no_results(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-test-idea"
        _write_toml(exp_dir, _MINIMAL_TOML)

        state = load_experiment(exp_dir)

        assert state.concluded is None


class TestLoadExperimentValidation:
    def test_missing_toml_raises(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-bad"
        exp_dir.mkdir()

        with pytest.raises(FileNotFoundError, match=r"experiment\.toml not found"):
            load_experiment(exp_dir)

    def test_malformed_toml_raises(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "001-bad"
        exp_dir.mkdir()
        (exp_dir / "experiment.toml").write_text(
            "this is not valid toml [[[", encoding="utf-8"
        )

        with pytest.raises(ValueError, match=r"Malformed experiment\.toml"):
            load_experiment(exp_dir)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        toml_without_title = """\
[experiment]
id = "001"
slug = "no-title"
hypothesis = "Missing title"
created = 2026-04-13
tags = []
"""
        exp_dir = tmp_path / "001-no-title"
        _write_toml(exp_dir, toml_without_title)

        with pytest.raises(ValueError, match="Missing required field 'title'"):
            load_experiment(exp_dir)
