"""Shared dependencies — BacktestManager and FastAPI DI wiring."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from fastapi import Request

from pac.backtester.config import BacktestConfig
from pac.backtester.results.store import ResultStore
from pac.backtester.runner import run_pipeline


@dataclass
class BacktestJob:
    """Tracks an in-flight backtest."""

    run_id: str
    current: int = 0
    total: int = 0
    status: str = "running"  # running | completed | failed
    error: str | None = None
    final_run_id: str | None = None
    _lock: Lock = field(default_factory=Lock)

    def snapshot(self) -> dict[str, object]:
        """Return a thread-safe progress snapshot."""
        with self._lock:
            return {
                "current": self.current,
                "total": self.total,
                "status": self.status,
                "run_id": self.final_run_id,
                "error": self.error,
            }


class BacktestManager:
    """Manages backtest execution and progress tracking.

    Runs backtests in a thread pool (max 1 concurrent).
    Tracks progress per job_id for SSE consumers.
    """

    def __init__(self, store: ResultStore) -> None:
        self._store = store
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="backtest",
        )
        self._jobs: dict[str, BacktestJob] = {}
        self._lock = Lock()

    @property
    def store(self) -> ResultStore:
        return self._store

    def start(
        self,
        config: BacktestConfig,
        config_path: Path,
        seed: int | None = None,
    ) -> str:
        """Submit a backtest to the thread pool. Returns job_id."""
        job_id = uuid.uuid4().hex[:12]
        job = BacktestJob(
            run_id=job_id,
            total=config.monte_carlo_iterations,
        )
        with self._lock:
            self._jobs[job_id] = job

        self._executor.submit(self._run, job_id, config, config_path, seed)
        return job_id

    def get_job(self, job_id: str) -> BacktestJob | None:
        """Look up a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def shutdown(self) -> None:
        """Shut down the executor, waiting for in-flight jobs."""
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(
        self,
        job_id: str,
        config: BacktestConfig,
        config_path: Path,
        seed: int | None,
    ) -> None:
        """Execute pipeline in worker thread — updates job state."""
        job = self._jobs[job_id]

        def on_progress(current: int, total: int) -> None:
            with job._lock:
                job.current = current
                job.total = total

        try:
            result, _path = run_pipeline(
                config,
                config_path,
                seed=seed,
                on_progress=on_progress,
            )
            with job._lock:
                job.status = "completed"
                job.final_run_id = result.run_id
        except Exception as e:
            with job._lock:
                job.status = "failed"
                job.error = str(e)


def get_manager(request: Request) -> BacktestManager:
    """FastAPI dependency — retrieves BacktestManager from app state."""
    manager: BacktestManager = request.app.state.manager
    return manager
