from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from pac.backtester.results.models import RunResult

log = structlog.get_logger()

_DEFAULT_BASE_DIR = Path(".pac/backtests")


class ResultStore:
    """Persist and retrieve backtest results as JSON files.

    Default location: .pac/backtests/{run_id}.json
    The .pac/ directory is gitignored.
    """

    def __init__(self, base_dir: Path = _DEFAULT_BASE_DIR) -> None:
        """Initialize the store.

        Args:
            base_dir: Directory for JSON files. Created on first save.
        """
        self._base_dir = base_dir

    def save(self, result: RunResult) -> Path:
        """Save a RunResult as JSON.

        Creates the base_dir if it doesn't exist.

        Args:
            result: The run result to persist.

        Returns:
            Path to the written JSON file.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / f"{result.run_id}.json"
        data = result.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=str))
        log.info("result_saved", run_id=result.run_id, path=str(path))
        return path

    def load(self, run_id: str) -> RunResult:
        """Load a RunResult from JSON by run_id.

        Args:
            run_id: The run identifier (filename stem).

        Returns:
            Deserialized RunResult.

        Raises:
            FileNotFoundError: If no file exists for this run_id.
            ValueError: If run_id contains invalid characters.
        """
        self._validate_run_id(run_id)
        path = self._base_dir / f"{run_id}.json"
        if not path.exists():
            msg = f"No backtest result found: {path}"
            raise FileNotFoundError(msg)
        data = json.loads(path.read_text())
        return RunResult.model_validate(data)

    def list_runs(self) -> list[str]:
        """List all saved run IDs, sorted by creation time (newest first).

        Returns:
            List of run_id strings. Empty list if base_dir doesn't exist.
        """
        if not self._base_dir.exists():
            return []
        files = sorted(
            self._base_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [f.stem for f in files]

    def delete(self, run_id: str) -> None:
        """Delete a saved backtest result.

        Args:
            run_id: The run identifier to delete.

        Raises:
            FileNotFoundError: If no file exists for this run_id.
            ValueError: If run_id contains invalid characters.
        """
        self._validate_run_id(run_id)
        path = self._base_dir / f"{run_id}.json"
        if not path.exists():
            msg = f"No backtest result found: {path}"
            raise FileNotFoundError(msg)
        path.unlink()
        log.info("result_deleted", run_id=run_id)

    def _validate_run_id(self, run_id: str) -> None:
        """Ensure run_id is a simple filename stem (no path traversal).

        Uses a positive-match allowlist: only word characters and hyphens.
        """
        if not re.fullmatch(r"[\w\-]+", run_id):
            msg = f"Invalid run_id: {run_id}"
            raise ValueError(msg)
