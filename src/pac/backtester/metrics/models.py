from __future__ import annotations

from pydantic import BaseModel

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import IterationResult


class MetricResult(BaseModel, frozen=True):
    """A single metric's aggregated value across MC iterations."""

    name: str
    median: float
    p5: float
    p95: float
    per_iteration: list[float]


class MetricSet(BaseModel, frozen=True):
    """All computed metrics for a single scenario."""

    scenario: str
    metrics: dict[str, MetricResult]


class BacktestReport(BaseModel, frozen=True):
    """Complete backtest report with strategy + benchmark comparison."""

    strategy: MetricSet
    benchmark: MetricSet | None
    config: BacktestConfig
    strategy_iterations: list[IterationResult]
    benchmark_iterations: list[IterationResult] | None
