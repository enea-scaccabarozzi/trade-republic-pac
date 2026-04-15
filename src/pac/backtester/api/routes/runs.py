"""Routes for backtest run CRUD and SSE progress streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse, Response

from pac.backtester.api.deps import BacktestManager, get_manager
from pac.backtester.api.models import (
    ProgressEvent,
    RunDetailResponse,
    RunListResponse,
    RunSummary,
    StartBacktestRequest,
    StartBacktestResponse,
)
from pac.backtester.results.models import MetricValue, RunResult

router = APIRouter()

_depends_manager = Depends(get_manager)


def _to_summary(r: RunResult) -> RunSummary:
    """Extract summary fields from a full RunResult."""
    strategy_metrics = r.metrics.get("strategy", {})

    cagr_mv = strategy_metrics.get("cagr")
    cagr = cagr_mv.median if isinstance(cagr_mv, MetricValue) else None

    sharpe_mv = strategy_metrics.get("sharpe")
    sharpe = sharpe_mv.median if isinstance(sharpe_mv, MetricValue) else None

    max_dd_mv = strategy_metrics.get("max_drawdown")
    max_dd = max_dd_mv.median if isinstance(max_dd_mv, MetricValue) else None

    return RunSummary(
        run_id=r.run_id,
        created_at=r.created_at,
        strategy=r.config.strategy,
        start_date=r.config.start_date,
        end_date=r.config.end_date,
        iterations=r.config.monte_carlo_iterations,
        final_value_median=r.summary.final_value.median,
        cagr_median=cagr,
        sharpe_median=sharpe,
        max_drawdown_median=max_dd,
        label=r.label,
        tags=list(r.tags),
        experiment_id=r.experiment_id,
        quantstats_metrics=r.quantstats_metrics,
    )


@router.get("/runs", response_model=RunListResponse)
def list_runs(
    manager: BacktestManager = _depends_manager,
) -> RunListResponse:
    """List all saved backtest runs."""
    store = manager.store
    run_ids = store.list_runs()
    summaries: list[RunSummary] = []
    for run_id in run_ids:
        try:
            r = store.load(run_id)
            summaries.append(_to_summary(r))
        except (FileNotFoundError, ValueError):
            continue  # skip corrupted entries
    return RunListResponse(runs=summaries, total=len(summaries))


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(
    run_id: str,
    manager: BacktestManager = _depends_manager,
) -> RunDetailResponse:
    """Get full details for a single backtest run."""
    try:
        result = manager.store.load(run_id)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run ID: '{run_id}'",
        ) from err
    return RunDetailResponse(run=result)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(
    run_id: str,
    manager: BacktestManager = _depends_manager,
) -> Response:
    """Delete a saved backtest run."""
    try:
        manager.store.delete(run_id)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run ID: '{run_id}'",
        ) from err
    return Response(status_code=204)


@router.post("/runs", response_model=StartBacktestResponse, status_code=202)
def start_backtest(
    body: StartBacktestRequest,
    manager: BacktestManager = _depends_manager,
) -> StartBacktestResponse:
    """Start a new backtest run. Returns job ID for progress tracking."""
    config_path = Path(body.config_path)
    if config_path.is_absolute() or ".." in config_path.parts:
        raise HTTPException(
            status_code=400,
            detail="config_path must be a relative path without '..'",
        )
    if not config_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Config file not found: {config_path}",
        )
    job_id = manager.start(body.config, config_path, body.seed)
    return StartBacktestResponse(run_id=job_id, status="running")


@router.get("/runs/{job_id}/progress")
async def run_progress(
    job_id: str,
    manager: BacktestManager = _depends_manager,
) -> EventSourceResponse:
    """Stream backtest progress as Server-Sent Events."""
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active job '{job_id}'",
        )

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        while True:
            snap = job.snapshot()
            current = snap["current"]
            total = snap["total"]
            status = snap["status"]
            run_id_val = snap["run_id"]
            error_val = snap["error"]
            event = ProgressEvent(
                current=int(current) if isinstance(current, int) else 0,
                total=int(total) if isinstance(total, int) else 0,
                status=str(status),
                run_id=str(run_id_val) if run_id_val else None,
                error=str(error_val) if error_val else None,
            )
            yield {"data": event.model_dump_json()}
            if event.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.get("/runs/{run_id}/quantstats")
def get_run_quantstats(
    run_id: str,
    format: str = Query("json"),
    manager: BacktestManager = _depends_manager,
) -> Response:
    """Serve quantstats report or metrics for a run."""
    try:
        result = manager.store.load(run_id)
    except FileNotFoundError as err:
        raise HTTPException(404, f"Run '{run_id}' not found") from err
    except ValueError as err:
        raise HTTPException(400, f"Invalid run ID: '{run_id}'") from err

    if format == "html":
        if not result.quantstats_report_path:
            raise HTTPException(404, "No quantstats report for this run")
        store_base = manager.store._base_dir.resolve()
        report_path = (
            manager.store._base_dir / result.quantstats_report_path
        ).resolve()
        if not report_path.is_relative_to(store_base):
            raise HTTPException(400, "Invalid report path: outside store directory")
        if not report_path.is_file():
            raise HTTPException(404, "Quantstats report file not found")
        content = report_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            headers={"Content-Security-Policy": "sandbox"},
        )

    # Default: JSON format
    metrics: dict[str, Any] = result.quantstats_metrics or {}
    return Response(
        content=_json_response(metrics),
        media_type="application/json",
    )


def _json_response(data: dict[str, Any]) -> str:
    """Serialize a dict to JSON string."""
    import json

    return json.dumps(data)


@router.get("/runs/{run_id}/oos")
def get_run_oos(
    run_id: str,
    manager: BacktestManager = _depends_manager,
) -> dict[str, Any] | None:
    """Return OOS metadata for a run."""
    try:
        result = manager.store.load(run_id)
    except FileNotFoundError as err:
        raise HTTPException(404, f"Run '{run_id}' not found") from err
    except ValueError as err:
        raise HTTPException(400, f"Invalid run ID: '{run_id}'") from err

    if result.oos_metadata is None:
        return None
    return result.oos_metadata.model_dump(mode="json")
