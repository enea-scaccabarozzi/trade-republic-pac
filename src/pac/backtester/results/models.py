from __future__ import annotations

import datetime as dt
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from pac.backtester.config import BacktestConfig
from pac.models.indicators import IndicatorKind, IndicatorThreshold


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
    distribution: list[float] | None = None


class EquityCurvePoint(BaseModel, frozen=True):
    """Single day in the equity curve with MC confidence bands."""

    date: dt.date
    p5: float
    median: float
    p95: float


class AllocationPoint(BaseModel, frozen=True):
    """Per-asset allocation percentages at a single date with MC bands."""

    date: dt.date
    assets: dict[str, ConfidenceInterval]


class TradeRecord(BaseModel, frozen=True):
    """A single trade from the median iteration's trade log."""

    date: dt.date
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


class IndicatorMeta(BaseModel, frozen=True):
    """Self-describing metadata for a single indicator series."""

    key: str
    display_name: str
    group: str
    kind: IndicatorKind
    unit: str = ""
    thresholds: list[IndicatorThreshold] = []
    companion_keys: list[str] = []
    rule_name: str = ""


class IndicatorDataPoint(BaseModel, frozen=True):
    """One sampled value for an indicator on a specific date."""

    date: dt.date
    value: float | bool | None


class IndicatorSeries(BaseModel, frozen=True):
    """A complete indicator timeseries with self-describing metadata."""

    meta: IndicatorMeta
    data: list[IndicatorDataPoint]


class StrategyEventKind(StrEnum):
    """Visualization hint for strategy events."""

    SPAN = "span"
    POINT = "point"


class StrategyEventMeta(BaseModel, frozen=True):
    """Metadata for a strategy event type."""

    key: str
    display_name: str
    kind: StrategyEventKind
    color: str = ""


class StrategyEvent(BaseModel, frozen=True):
    """A single strategy event occurrence."""

    date: dt.date
    event_type: str
    details: dict[str, Any] = {}
    end_date: dt.date | None = None


class SignalRecord(BaseModel, frozen=True):
    """Serializable snapshot of a signal fired during simulation."""

    date: dt.date
    rule_name: str
    severity: str
    message: str
    metadata: dict[str, Any] = {}


class OOSMetadata(BaseModel, frozen=True):
    """OOS validation info attached to a run."""

    method: Literal["holdout", "walk_forward", "leave_one_event_out"]
    """Which OOS method was used."""

    holdout_date: dt.date | None = None
    """Split date for temporal holdout."""

    walk_forward_windows: int | None = None
    """Number of expanding walk-forward windows."""

    event_calendar: str | None = None
    """Calendar name for leave-one-event-out."""

    degradation_ratio: float | None = None
    """IS-to-OOS degradation ratio (lower = better generalization)."""


class MetricDelta(BaseModel, frozen=True):
    """A single metric's values from two runs and their delta."""

    metric: str
    baseline: float
    candidate: float
    delta: float
    delta_pct: float | None = None
    """Percentage change. None if baseline is zero."""


class ComparisonResult(BaseModel, frozen=True):
    """Side-by-side comparison of two backtest runs."""

    baseline_run_id: str
    candidate_run_id: str
    baseline_label: str | None = None
    candidate_label: str | None = None
    deltas: list[MetricDelta]


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
    signal_log: list[SignalRecord] = []
    indicator_series: list[IndicatorSeries] = []
    strategy_events: list[StrategyEvent] = []
    strategy_event_meta: list[StrategyEventMeta] = []
    benchmark_equity_curve: list[EquityCurvePoint] | None = None

    # ── Research metadata (all optional, backward-compatible) ──

    label: str | None = None
    """Human-readable label, e.g. 'H1 PAC tilt 90/5/5'."""

    tags: list[str] = Field(default_factory=list)
    """Categorization tags, e.g. ['crisis', 'pac-tilt', 'exp-001']."""

    experiment_id: str | None = None
    """Links run to research/experiments/NNN-slug/."""

    quantstats_report_path: str | None = None
    """Relative path to HTML tearsheet (if generated)."""

    quantstats_metrics: dict[str, float] | None = None
    """Flat quantstats metrics dict from the median iteration."""

    oos_metadata: OOSMetadata | None = None
    """Out-of-sample validation info attached to this run."""
