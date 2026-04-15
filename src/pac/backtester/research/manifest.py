"""ExperimentManifest — scan experiments directory and return all experiment states."""

from __future__ import annotations

from pathlib import Path

import structlog

from pac.backtester.research.experiment import ExperimentState, load_experiment

logger = structlog.get_logger()


class ExperimentManifest:
    """Scan experiments directory and return all experiment states.

    Skips directories starting with '_' (e.g., _template/).
    """

    def __init__(self, experiments_dir: Path) -> None:
        self._experiments_dir = experiments_dir

    def scan(self) -> list[ExperimentState]:
        """Scan all experiment directories and return their states.

        Returns experiments sorted by ID (ascending).
        Skips directories that don't contain experiment.toml
        (logs a warning via structlog).
        """
        if not self._experiments_dir.exists():
            return []

        experiments: list[ExperimentState] = []
        for entry in sorted(self._experiments_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("_"):
                continue
            if not (entry / "experiment.toml").exists():
                logger.warning(
                    "experiment_missing_toml",
                    directory=str(entry),
                )
                continue
            state = load_experiment(entry)
            experiments.append(state)

        return sorted(experiments, key=lambda e: e.id)

    def get(self, experiment_id: str) -> ExperimentState | None:
        """Load a single experiment by ID.

        Scans directory names for NNN-slug pattern matching the given ID.
        Returns None if not found.

        After loading, validates that the directory name prefix matches
        the TOML id field. Logs a structlog warning if they diverge.
        """
        if not self._experiments_dir.exists():
            return None

        prefix = f"{experiment_id}-"
        for entry in self._experiments_dir.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.startswith("_"):
                continue
            if not entry.name.startswith(prefix):
                continue
            if not (entry / "experiment.toml").exists():
                continue

            state = load_experiment(entry)

            # Validate ID consistency
            dir_id = entry.name.split("-", 1)[0]
            if dir_id != state.id:
                logger.warning(
                    "experiment_id_mismatch",
                    dir_id=dir_id,
                    toml_id=state.id,
                )

            return state

        return None
