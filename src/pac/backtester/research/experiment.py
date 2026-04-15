"""ExperimentState dataclass and load_experiment() function.

Reads experiment.toml seed data and auto-computes live state from directory
contents (status, artifacts, reports, result files, concluded date).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

_REQUIRED_FIELDS = ("id", "slug", "title", "hypothesis", "created")

_EXCLUDED_PATTERNS = {"__pycache__", ".pyc"}


@dataclass(frozen=True)
class ExperimentState:
    """Immutable snapshot of an experiment's current state.

    Constructed by load_experiment() — never persisted, always fresh.
    """

    id: str
    slug: str
    title: str
    hypothesis: str
    created: date
    tags: list[str]
    status: str
    strategy_name: str | None
    strategy_params_file: str | None
    artifacts: list[str]
    reports: list[str]
    result_files: list[str]
    concluded: date | None
    directory: Path


def _compute_status(toml_data: dict[str, object], experiment_dir: Path) -> str:
    """Derive experiment status from directory contents.

    Priority:
        1. Manual override in experiment.toml wins
        2. Has result files (.json/.csv) → "validated"
        3. Default → "exploring"
    """
    exp = toml_data.get("experiment", {})
    if not isinstance(exp, dict):
        return "exploring"

    if "status" in exp:
        return str(exp["status"])

    results_dir = experiment_dir / "results"
    if results_dir.exists():
        has_results = any(
            f
            for f in results_dir.iterdir()
            if f.is_file() and f.suffix in (".json", ".csv")
        )
        if has_results:
            return "validated"

    return "exploring"


def _scan_artifacts(experiment_dir: Path) -> list[str]:
    """Recursively list files in the experiment directory.

    Excludes __pycache__ directories, .pyc files, and experiment.toml itself.
    Returns paths relative to the experiment directory, sorted.
    """
    artifacts: list[str] = []
    for path in sorted(experiment_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "experiment.toml":
            continue
        if any(part in _EXCLUDED_PATTERNS for part in path.parts):
            continue
        if path.suffix == ".pyc":
            continue
        artifacts.append(str(path.relative_to(experiment_dir)))
    return artifacts


def _list_reports(experiment_dir: Path) -> list[str]:
    """List HTML report files in reports/ subdirectory."""
    reports_dir = experiment_dir / "reports"
    if not reports_dir.exists():
        return []
    return sorted(
        str(p.relative_to(experiment_dir))
        for p in reports_dir.glob("*.html")
        if p.is_file()
    )


def _list_result_files(experiment_dir: Path) -> list[str]:
    """List result files (.json, .csv) in results/ subdirectory."""
    results_dir = experiment_dir / "results"
    if not results_dir.exists():
        return []
    files: list[str] = []
    for suffix in (".json", ".csv"):
        files.extend(
            str(p.relative_to(experiment_dir))
            for p in results_dir.glob(f"*{suffix}")
            if p.is_file()
        )
    return sorted(files)


def _compute_concluded(experiment_dir: Path) -> date | None:
    """Derive concluded date from the latest result file mtime."""
    results_dir = experiment_dir / "results"
    if not results_dir.exists():
        return None

    result_files = [
        f
        for f in results_dir.iterdir()
        if f.is_file() and f.suffix in (".json", ".csv")
    ]
    if not result_files:
        return None

    latest_mtime = max(f.stat().st_mtime for f in result_files)
    return datetime.fromtimestamp(latest_mtime, tz=UTC).date()


def load_experiment(experiment_dir: Path) -> ExperimentState:
    """Load experiment.toml seed and compute live state from directory contents.

    Args:
        experiment_dir: Path to the experiment directory (must contain experiment.toml).

    Returns:
        Fully computed ExperimentState — never persisted, always fresh.

    Raises:
        FileNotFoundError: If experiment.toml is missing.
        ValueError: If experiment.toml is malformed or missing required fields.
    """
    toml_path = experiment_dir / "experiment.toml"
    if not toml_path.exists():
        msg = f"experiment.toml not found in {experiment_dir}"
        raise FileNotFoundError(msg)

    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        msg = f"Malformed experiment.toml in {experiment_dir}: {exc}"
        raise ValueError(msg) from exc

    exp = data.get("experiment")
    if not isinstance(exp, dict):
        msg = f"Missing [experiment] table in {toml_path}"
        raise ValueError(msg)

    for field in _REQUIRED_FIELDS:
        if field not in exp:
            msg = f"Missing required field '{field}' in {toml_path}"
            raise ValueError(msg)

    # Extract strategy configuration
    strategy = exp.get("strategy")
    strategy_name: str | None = None
    strategy_params_file: str | None = None
    if isinstance(strategy, dict):
        strategy_name = strategy.get("name")
        strategy_params_file = strategy.get("params_file")

    created = exp["created"]
    if not isinstance(created, date):
        msg = f"Field 'created' must be a TOML date in {toml_path}"
        raise ValueError(msg)

    return ExperimentState(
        id=str(exp["id"]),
        slug=str(exp["slug"]),
        title=str(exp["title"]),
        hypothesis=str(exp["hypothesis"]),
        created=created,
        tags=[str(t) for t in exp.get("tags", [])],
        status=_compute_status(data, experiment_dir),
        strategy_name=strategy_name,
        strategy_params_file=strategy_params_file,
        artifacts=_scan_artifacts(experiment_dir),
        reports=_list_reports(experiment_dir),
        result_files=_list_result_files(experiment_dir),
        concluded=_compute_concluded(experiment_dir),
        directory=experiment_dir.resolve(),
    )
