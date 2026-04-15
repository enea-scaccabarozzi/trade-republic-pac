from __future__ import annotations

import ast
import shutil
import tomllib
from pathlib import Path

import pytest


def _setup_template(base: Path) -> None:
    """Copy _template/ into the tmp_path so scaffold can read it."""
    template_src = Path("research/experiments/_template")
    template_dst = base / "research" / "experiments" / "_template"
    template_dst.mkdir(parents=True, exist_ok=True)
    for f in template_src.iterdir():
        shutil.copy2(f, template_dst / f.name)


class TestScaffoldExperimentCreatesFiles:
    def test_creates_toml_and_notebook(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        created = scaffold_experiment("my_test_idea", output_dir=tmp_path)

        assert len(created) == 2
        toml_file = tmp_path / "research/experiments/001-my-test-idea/experiment.toml"
        explore_file = tmp_path / "research/experiments/001-my-test-idea/explore.py"
        assert toml_file.exists()
        assert explore_file.exists()


class TestScaffoldExperimentStructure:
    def test_generated_toml_is_valid(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("sample_idea", output_dir=tmp_path)

        toml_file = tmp_path / "research/experiments/001-sample-idea/experiment.toml"
        with open(toml_file, "rb") as f:
            data = tomllib.load(f)
        assert "experiment" in data
        assert "id" in data["experiment"]
        assert "slug" in data["experiment"]
        assert "title" in data["experiment"]

    def test_generated_toml_has_correct_id(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("first_idea", output_dir=tmp_path)

        toml_file = tmp_path / "research/experiments/001-first-idea/experiment.toml"
        with open(toml_file, "rb") as f:
            data = tomllib.load(f)
        assert data["experiment"]["id"] == "001"

    def test_generated_toml_has_correct_slug(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("crisis_timing", output_dir=tmp_path)

        toml_file = tmp_path / "research/experiments/001-crisis-timing/experiment.toml"
        with open(toml_file, "rb") as f:
            data = tomllib.load(f)
        assert data["experiment"]["slug"] == "crisis-timing"

    def test_generated_notebook_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("valid_idea", output_dir=tmp_path)

        explore_file = tmp_path / "research/experiments/001-valid-idea/explore.py"
        ast.parse(explore_file.read_text(encoding="utf-8"))

    def test_generated_notebook_mentions_title(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment(
            "my_experiment", title="My Cool Experiment", output_dir=tmp_path
        )

        explore_file = tmp_path / "research/experiments/001-my-experiment/explore.py"
        content = explore_file.read_text(encoding="utf-8")
        assert "My Cool Experiment" in content

    def test_id_auto_increments(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("first_idea", output_dir=tmp_path)
        scaffold_experiment("second_idea", output_dir=tmp_path)

        second_toml = tmp_path / "research/experiments/002-second-idea/experiment.toml"
        assert second_toml.exists()
        with open(second_toml, "rb") as f:
            data = tomllib.load(f)
        assert data["experiment"]["id"] == "002"

    def test_custom_title(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment(
            "crisis_timing",
            title="Crisis Timing Asymmetry",
            output_dir=tmp_path,
        )

        toml_file = tmp_path / "research/experiments/001-crisis-timing/experiment.toml"
        with open(toml_file, "rb") as f:
            data = tomllib.load(f)
        assert data["experiment"]["title"] == "Crisis Timing Asymmetry"

    def test_slug_derivation(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("crisis_timing_asymmetry", output_dir=tmp_path)

        exp_dir = tmp_path / "research/experiments/001-crisis-timing-asymmetry"
        assert exp_dir.exists()

        toml_file = exp_dir / "experiment.toml"
        with open(toml_file, "rb") as f:
            data = tomllib.load(f)
        assert data["experiment"]["slug"] == "crisis-timing-asymmetry"


class TestScaffoldExperimentValidation:
    def test_rejects_invalid_name_hyphenated(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        with pytest.raises(SystemExit):
            scaffold_experiment("my-experiment", output_dir=tmp_path)

    def test_rejects_invalid_name_uppercase(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        with pytest.raises(SystemExit):
            scaffold_experiment("MyExperiment", output_dir=tmp_path)

    def test_rejects_existing_directory(self, tmp_path: Path) -> None:
        from scripts.scaffold_experiment import scaffold_experiment

        _setup_template(tmp_path)
        scaffold_experiment("existing_idea", output_dir=tmp_path)

        with pytest.raises(SystemExit):
            scaffold_experiment("existing_idea", output_dir=tmp_path)
