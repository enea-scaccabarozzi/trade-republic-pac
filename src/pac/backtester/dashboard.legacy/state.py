"""Dashboard state management — ResultStore wrapper with caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import structlog

from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore

log = structlog.get_logger()

_DEFAULT_BASE_DIR = Path(".pac/backtests")


@dataclass
class RunSummary:
    """Lightweight summary of a run for the listing page."""

    run_id: str
    strategy: str
    start_date: str
    end_date: str
    created_at: datetime
    final_value_median: float
    cagr_median: float | None
    iterations: int


@dataclass
class DashboardState:
    """Shared state for the dashboard.

    Wraps ResultStore with a run cache to avoid re-reading JSON
    files on every page load.
    """

    store: ResultStore = field(
        default_factory=lambda: ResultStore(base_dir=_DEFAULT_BASE_DIR),
    )
    _cache: dict[str, RunResult] = field(default_factory=dict)

    def list_run_summaries(self) -> list[RunSummary]:
        """List all saved runs as lightweight summaries.

        Returns:
            Summaries sorted newest first (matching ResultStore.list_runs order).
        """
        run_ids = self.store.list_runs()
        summaries: list[RunSummary] = []
        for run_id in run_ids:
            try:
                result = self._load_cached(run_id)
                summaries.append(_to_summary(result))
            except Exception as exc:
                log.warning("skipped_corrupt_run", run_id=run_id, error=str(exc))
        return summaries

    def load_run(self, run_id: str) -> RunResult:
        """Load a full RunResult (cached).

        Args:
            run_id: The run identifier.

        Returns:
            The deserialized RunResult.

        Raises:
            FileNotFoundError: If no file exists for this run_id.
            ValueError: If run_id contains invalid characters.
        """
        return self._load_cached(run_id)

    def refresh(self) -> None:
        """Clear the cache so next access re-reads from disk."""
        self._cache.clear()

    def _load_cached(self, run_id: str) -> RunResult:
        if run_id not in self._cache:
            self._cache[run_id] = self.store.load(run_id)
        return self._cache[run_id]


def _to_summary(result: RunResult) -> RunSummary:
    """Extract a RunSummary from a full RunResult."""
    cagr = None
    if "strategy" in result.metrics and "cagr" in result.metrics["strategy"]:
        cagr = result.metrics["strategy"]["cagr"].median

    return RunSummary(
        run_id=result.run_id,
        strategy=result.config.strategy,
        start_date=str(result.config.start_date),
        end_date=str(result.config.end_date),
        created_at=result.created_at,
        final_value_median=result.summary.final_value.median,
        cagr_median=cagr,
        iterations=result.monte_carlo.iterations,
    )


# Module-level singleton — shared across all pages.
state = DashboardState()
