"""Request/response Pydantic models for the backtester API."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field

from pac.backtester.config import BacktestConfig
from pac.backtester.results.models import RunResult


class RunSummary(BaseModel):
    """Lightweight run entry for the list endpoint."""

    run_id: str
    created_at: dt.datetime
    strategy: str
    start_date: dt.date
    end_date: dt.date
    iterations: int
    final_value_median: float
    cagr_median: float | None = None
    sharpe_median: float | None = None
    max_drawdown_median: float | None = None
    label: str | None = None
    tags: list[str] = []
    experiment_id: str | None = None
    quantstats_metrics: dict[str, float] | None = None


class RunListResponse(BaseModel):
    """Paginated list of run summaries."""

    runs: list[RunSummary]
    total: int


class RunDetailResponse(BaseModel):
    """Full RunResult passthrough — the frontend gets everything."""

    run: RunResult


class StartBacktestRequest(BaseModel):
    """Request body for POST /api/runs."""

    config: BacktestConfig
    config_path: str = Field(
        default="pac.yaml",
        description="Path to pac.yaml (relative to CWD).",
    )
    seed: int | None = None


class StartBacktestResponse(BaseModel):
    """Response for POST /api/runs — returns job ID for progress tracking."""

    run_id: str
    status: str = "running"


class ProgressEvent(BaseModel):
    """Shape of each SSE data payload."""

    current: int
    total: int
    status: str  # "running" | "completed" | "failed"
    run_id: str | None = None
    error: str | None = None


class StrategyInfo(BaseModel):
    """Metadata about a single backtest strategy."""

    name: str
    description: str
    params_schema: dict[str, Any]


class StrategiesResponse(BaseModel):
    """List of available strategies with JSON Schema for params."""

    strategies: list[StrategyInfo]


class ErrorResponse(BaseModel):
    """Standard error response shape."""

    detail: str


# ── Research models ──


class ExperimentSummary(BaseModel):
    """Lightweight experiment entry for the list endpoint."""

    id: str
    slug: str
    title: str
    status: str
    strategy_name: str | None = None
    tags: list[str] = []
    created: dt.date
    concluded: dt.date | None = None
    artifact_count: int = 0
    report_count: int = 0
    result_file_count: int = 0


class ExperimentListResponse(BaseModel):
    """List of experiment summaries."""

    experiments: list[ExperimentSummary]
    total: int


class ExperimentDetailResponse(BaseModel):
    """Full experiment detail with computed state and linked runs."""

    id: str
    slug: str
    title: str
    hypothesis: str
    status: str
    strategy_name: str | None = None
    strategy_params_file: str | None = None
    tags: list[str] = []
    created: dt.date
    concluded: dt.date | None = None
    artifacts: list[str] = []
    reports: list[str] = []
    result_files: list[str] = []
    linked_run_ids: list[str] = []
    readme_html: str | None = None


class PaperSummary(BaseModel):
    """Lightweight paper entry."""

    slug: str
    title: str
    has_figures: bool = False


class PaperListResponse(BaseModel):
    """List of research papers."""

    papers: list[PaperSummary]


class StrategySnapshotSummary(BaseModel):
    """A strategy parameter snapshot file."""

    filename: str
    strategy_name: str | None = None
    params: dict[str, Any] = {}


class StrategySnapshotListResponse(BaseModel):
    """List of strategy snapshots."""

    snapshots: list[StrategySnapshotSummary]
