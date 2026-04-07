from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from pac.backtester.config import BacktestConfig


class ConfidenceInterval(BaseModel, frozen=True):
    """P5/median/P95 confidence interval from MC aggregation."""

    p5: float
    median: float
    p95: float


class MonteCarloInfo(BaseModel, frozen=True):
    """Monte Carlo simulation parameters."""

    iterations: int
    slippage_range: tuple[int, int]


class MetricValue(BaseModel, frozen=True):
    """A single metric value with P5/median/P95 confidence interval.

    For deterministic results (e.g., benchmark with zero slippage),
    set p5 = p95 = median to give frontend consumers a uniform shape.
    """

    p5: float
    median: float
    p95: float


class EquityCurvePoint(BaseModel, frozen=True):
    """Single day in the equity curve with MC confidence bands."""

    date: date
    p5: float
    median: float
    p95: float


class AllocationPoint(BaseModel, frozen=True):
    """Per-asset allocation percentages at a single date with MC bands."""

    date: date
    assets: dict[str, ConfidenceInterval]


class TradeRecord(BaseModel, frozen=True):
    """A single trade from the median iteration's trade log."""

    date: date
    type: Literal["pac_execution", "hard_rebalance"]
    asset_id: str
    direction: Literal["buy", "sell"]
    amount_eur: float
    quantity: float
    price: float
    fee: float
    skipped: bool = False


class SummaryStats(BaseModel, frozen=True):
    """Aggregate summary statistics across MC iterations."""

    total_invested: float
    final_value: ConfidenceInterval
    total_fees: ConfidenceInterval
    total_trades: ConfidenceInterval
    total_pac_executions: int


class RunResult(BaseModel, frozen=True):
    """Complete backtest run result — the JSON sidecar schema.

    Designed for frontend-agnostic consumption: equity curve bands
    for graphing, allocation percentages for pie/area charts, and
    a full trade list from the median iteration.
    """

    run_id: str
    created_at: datetime
    config: BacktestConfig
    monte_carlo: MonteCarloInfo
    metrics: dict[str, dict[str, MetricValue]]
    equity_curve: list[EquityCurvePoint]
    allocations: list[AllocationPoint]
    trades: list[TradeRecord]
    summary: SummaryStats
