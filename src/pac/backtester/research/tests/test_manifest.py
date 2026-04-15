from __future__ import annotations

from pathlib import Path

from pac.backtester.research.manifest import ExperimentManifest

_TOML_TEMPLATE = """\
[experiment]
id = "{id}"
slug = "{slug}"
title = "{title}"
hypothesis = "Testing"
created = 2026-04-13
tags = []
"""


def _create_experiment(
    experiments_dir: Path,
    exp_id: str,
    slug: str,
    title: str,
) -> Path:
    exp_dir = experiments_dir / f"{exp_id}-{slug}"
    exp_dir.mkdir(parents=True, exist_ok=True)
    content = _TOML_TEMPLATE.format(id=exp_id, slug=slug, title=title)
    (exp_dir / "experiment.toml").write_text(content, encoding="utf-8")
    return exp_dir


class TestManifestScan:
    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        experiments_dir.mkdir()

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.scan()

        assert result == []

    def test_scan_finds_experiments(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        _create_experiment(experiments_dir, "001", "first", "First")
        _create_experiment(experiments_dir, "002", "second", "Second")

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.scan()

        assert len(result) == 2
        assert result[0].id == "001"
        assert result[1].id == "002"

    def test_scan_skips_template(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        _create_experiment(experiments_dir, "001", "real", "Real")
        template_dir = experiments_dir / "_template"
        template_dir.mkdir()
        (template_dir / "experiment.toml").write_text(
            _TOML_TEMPLATE.format(id="000", slug="template", title="Template"),
            encoding="utf-8",
        )

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.scan()

        assert len(result) == 1
        assert result[0].id == "001"

    def test_scan_skips_files(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        experiments_dir.mkdir()
        _create_experiment(experiments_dir, "001", "real", "Real")
        (experiments_dir / ".gitkeep").write_text("", encoding="utf-8")

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.scan()

        assert len(result) == 1

    def test_scan_skips_dirs_without_toml(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        _create_experiment(experiments_dir, "001", "valid", "Valid")
        bad_dir = experiments_dir / "002-no-toml"
        bad_dir.mkdir()

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.scan()

        assert len(result) == 1
        assert result[0].id == "001"


class TestManifestGet:
    def test_get_by_id(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        _create_experiment(experiments_dir, "001", "first", "First")
        _create_experiment(experiments_dir, "002", "second", "Second")

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.get("002")

        assert result is not None
        assert result.id == "002"
        assert result.slug == "second"

    def test_get_unknown_id(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        _create_experiment(experiments_dir, "001", "first", "First")

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.get("999")

        assert result is None

    def test_get_warns_on_id_mismatch(self, tmp_path: Path) -> None:
        experiments_dir = tmp_path / "experiments"
        # Directory says 002, but TOML says id = "001"
        exp_dir = experiments_dir / "002-mismatched"
        exp_dir.mkdir(parents=True)
        toml_content = _TOML_TEMPLATE.format(
            id="001", slug="mismatched", title="Mismatched"
        )
        (exp_dir / "experiment.toml").write_text(toml_content, encoding="utf-8")

        manifest = ExperimentManifest(experiments_dir)
        result = manifest.get("002")

        # Still returns the state despite mismatch
        assert result is not None
        assert result.id == "001"
