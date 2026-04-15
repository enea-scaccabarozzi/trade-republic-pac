"""Shared fixtures for backtester API tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pac.backtester.api.app import create_app
from pac.backtester.api.deps import BacktestManager
from pac.backtester.config import BacktestConfig
from pac.backtester.results.models import (
    ConfidenceInterval,
    MetricValue,
    MonteCarloInfo,
    OOSMetadata,
    RunResult,
    SummaryStats,
)
from pac.backtester.results.store import ResultStore


@pytest.fixture()
def tmp_store(tmp_path: Path) -> ResultStore:
    """ResultStore backed by a temporary directory."""
    return ResultStore(base_dir=tmp_path / "backtests")


@pytest.fixture()
def test_app(tmp_store: ResultStore) -> TestClient:
    """TestClient wired to the API with a temp ResultStore."""
    app = create_app(static_dir=None)
    # Replace the default manager with one using the tmp store
    app.state.manager = BacktestManager(store=tmp_store)
    return TestClient(app)


@pytest.fixture()
def make_run_result() -> Callable[..., RunResult]:
    """Factory for minimal RunResult fixtures."""

    def _make(
        *,
        run_id: str = "test-run-001",
        strategy: str = "pac_alignment",
        experiment_id: str | None = None,
        quantstats_metrics: dict[str, float] | None = None,
        quantstats_report_path: str | None = None,
        oos_metadata: OOSMetadata | None = None,
    ) -> RunResult:
        return RunResult(
            run_id=run_id,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            config=BacktestConfig(
                strategy=strategy,
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31),
            ),
            monte_carlo=MonteCarloInfo(
                iterations=10,
                slippage_range=(0, 3),
            ),
            metrics={
                "strategy": {
                    "cagr": MetricValue(
                        p5=0.05,
                        median=0.08,
                        p95=0.11,
                    ),
                    "sharpe": MetricValue(
                        p5=0.8,
                        median=1.2,
                        p95=1.5,
                    ),
                    "max_drawdown": MetricValue(
                        p5=-0.25,
                        median=-0.15,
                        p95=-0.08,
                    ),
                },
            },
            equity_curve=[],
            allocations=[],
            trades=[],
            summary=SummaryStats(
                total_invested=10000.0,
                final_value=ConfidenceInterval(
                    p5=12000,
                    median=15000,
                    p95=18000,
                ),
                total_fees=ConfidenceInterval(
                    p5=50,
                    median=80,
                    p95=120,
                ),
                total_trades=ConfidenceInterval(
                    p5=20,
                    median=30,
                    p95=40,
                ),
                total_pac_executions=24,
            ),
            experiment_id=experiment_id,
            quantstats_metrics=quantstats_metrics,
            quantstats_report_path=quantstats_report_path,
            oos_metadata=oos_metadata,
        )

    return _make
