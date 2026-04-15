from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

import structlog

from pac.backtester.results.models import (
    ComparisonResult,
    MetricDelta,
    RunResult,
)

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

    def search(
        self,
        *,
        strategy: str | None = None,
        tags: list[str] | None = None,
        experiment_id: str | None = None,
        after: date | None = None,
        before: date | None = None,
        label_contains: str | None = None,
    ) -> list[RunResult]:
        """Filter saved runs by metadata.

        All filters are AND-combined. Tags use subset matching
        (all requested tags must be present on the run).

        Args:
            strategy: Filter by config.strategy name.
            tags: Filter runs that contain ALL of these tags.
            experiment_id: Filter by experiment_id field.
            after: Only runs created on or after this date.
            before: Only runs created on or before this date.
            label_contains: Case-insensitive substring match on label.

        Returns:
            Matching RunResult objects, newest first.
        """
        results: list[RunResult] = []
        for run_id in self.list_runs():
            try:
                r = self.load(run_id)
            except Exception:
                log.warning("search_skip_corrupt", run_id=run_id)
                continue

            if strategy is not None and r.config.strategy != strategy:
                continue
            if tags is not None and not set(tags).issubset(set(r.tags)):
                continue
            if experiment_id is not None and r.experiment_id != experiment_id:
                continue
            if after is not None and r.created_at.date() < after:
                continue
            if before is not None and r.created_at.date() > before:
                continue
            if (
                label_contains is not None
                and label_contains.lower() not in (r.label or "").lower()
            ):
                continue

            results.append(r)
        return results

    def compare(self, run_id_a: str, run_id_b: str) -> ComparisonResult:
        """Load two runs and compute metric deltas.

        Args:
            run_id_a: First (baseline) run ID.
            run_id_b: Second (candidate) run ID.

        Returns:
            ComparisonResult with both runs' key metrics and deltas.

        Raises:
            FileNotFoundError: If either run doesn't exist.
        """
        baseline = self.load(run_id_a)
        candidate = self.load(run_id_b)

        baseline_metrics = baseline.metrics.get("strategy", {})
        candidate_metrics = candidate.metrics.get("strategy", {})

        all_keys = sorted(set(baseline_metrics) | set(candidate_metrics))

        deltas: list[MetricDelta] = []
        for key in all_keys:
            b_mv = baseline_metrics.get(key)
            c_mv = candidate_metrics.get(key)
            if b_mv is None or c_mv is None:
                continue
            b_val = b_mv.median
            c_val = c_mv.median
            delta = c_val - b_val
            delta_pct = delta / abs(b_val) * 100 if b_val != 0 else None
            deltas.append(
                MetricDelta(
                    metric=key,
                    baseline=b_val,
                    candidate=c_val,
                    delta=delta,
                    delta_pct=delta_pct,
                )
            )

        # Synthetic final_value delta
        b_fv = baseline.summary.final_value.median
        c_fv = candidate.summary.final_value.median
        fv_delta = c_fv - b_fv
        fv_delta_pct = fv_delta / abs(b_fv) * 100 if b_fv != 0 else None
        deltas.append(
            MetricDelta(
                metric="final_value",
                baseline=b_fv,
                candidate=c_fv,
                delta=fv_delta,
                delta_pct=fv_delta_pct,
            )
        )

        return ComparisonResult(
            baseline_run_id=run_id_a,
            candidate_run_id=run_id_b,
            baseline_label=baseline.label,
            candidate_label=candidate.label,
            deltas=deltas,
        )

    def export_csv(
        self,
        run_ids: list[str] | None = None,
        output: Path | None = None,
    ) -> Path:
        """Export metric summary for one or more runs as CSV.

        Columns: run_id, label, strategy, created_at, experiment_id,
        tags, then one column per metric (from strategy group).

        Args:
            run_ids: Specific runs to export. None = all runs.
            output: Output path. Defaults to base_dir / "export.csv".

        Returns:
            Path to the written CSV file.
        """
        ids = run_ids if run_ids is not None else self.list_runs()
        runs: list[RunResult] = []
        for rid in ids:
            try:
                runs.append(self.load(rid))
            except Exception:
                log.warning("export_csv_skip_corrupt", run_id=rid)

        # Collect all metric keys across runs
        all_metric_keys: list[str] = []
        seen: set[str] = set()
        for r in runs:
            for key in r.metrics.get("strategy", {}):
                if key not in seen:
                    all_metric_keys.append(key)
                    seen.add(key)

        base_columns = [
            "run_id",
            "label",
            "strategy",
            "created_at",
            "experiment_id",
            "tags",
        ]
        fieldnames = base_columns + all_metric_keys

        out_path = output if output is not None else self._base_dir / "export.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in runs:
                row: dict[str, str] = {
                    "run_id": r.run_id,
                    "label": r.label or "",
                    "strategy": r.config.strategy,
                    "created_at": r.created_at.isoformat(),
                    "experiment_id": r.experiment_id or "",
                    "tags": ";".join(r.tags),
                }
                strategy_metrics = r.metrics.get("strategy", {})
                for key in all_metric_keys:
                    mv = strategy_metrics.get(key)
                    row[key] = str(mv.median) if mv is not None else ""
                writer.writerow(row)

        log.info("export_csv_written", path=str(out_path), runs=len(runs))
        return out_path
