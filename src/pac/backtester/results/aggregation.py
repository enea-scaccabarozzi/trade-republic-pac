from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy as np

from pac.backtester.config import BacktestConfig
from pac.backtester.results.models import (
    AllocationPoint,
    ConfidenceInterval,
    EquityCurvePoint,
    IndicatorMeta,
    IndicatorSeries,
    MetricValue,
    MonteCarloInfo,
    RunResult,
    StrategyEventMeta,
    SummaryStats,
    TradeRecord,
)

if TYPE_CHECKING:
    from pac.backtester.engine.simulator import IterationResult
    from pac.backtester.metrics.models import BacktestReport, MetricSet


def build_run_result(
    report: BacktestReport,
    *,
    indicator_meta: list[IndicatorMeta] | None = None,
    strategy_event_meta: list[StrategyEventMeta] | None = None,
    label: str | None = None,
    tags: list[str] | None = None,
    experiment_id: str | None = None,
) -> RunResult:
    """Convert a BacktestReport into a frontend-agnostic RunResult.

    Aggregation steps:
      0. Guard: raise ValueError if iterations list is empty
      1. Find median iteration (by final_value)
      2. Build equity curve bands (P5/median/P95 of total_value per date)
      3. Build allocation bands (P5/median/P95 per asset per date)
      4. Extract trade list from median iteration
      5. Compute summary statistics (using median iteration for PAC counts)
      6. Map metric sets to the JSON schema format
      7. Generate run_id and created_at
      8. Extract indicator, signal, and event data from median iteration

    Args:
        report: Complete backtest report from Phase 4.
        indicator_meta: Indicator metadata from rules' indicator_specs().
        strategy_event_meta: Strategy event metadata from strategy.event_meta().

    Returns:
        RunResult ready for JSON serialization.

    Raises:
        ValueError: If report contains no iterations.
    """
    iterations = report.strategy_iterations
    if not iterations:
        msg = "Cannot build RunResult from empty iterations list"
        raise ValueError(msg)

    now = datetime.now(UTC)
    median_iter = _find_median_iteration(iterations)

    # Extract enrichment data from median iteration
    indicator_series = _build_indicator_series(
        median_iter,
        indicator_meta or [],
    )
    signal_log = list(median_iter.signal_log)
    strategy_events = list(median_iter.strategy_events)

    # Build benchmark equity curve if available
    benchmark_equity_curve = (
        _build_equity_curve(report.benchmark_iterations)
        if report.benchmark_iterations
        else None
    )

    return RunResult(
        run_id=_generate_run_id(report.config.strategy, now),
        created_at=now,
        config=report.config,
        monte_carlo=MonteCarloInfo(
            iterations=report.config.monte_carlo_iterations,
            slippage_range=report.config.slippage_days,
        ),
        metrics=_map_metrics(report.strategy, report.benchmark),
        equity_curve=_build_equity_curve(iterations),
        allocations=_build_allocations(iterations),
        trades=_extract_trades(median_iter),
        summary=_compute_summary(iterations, median_iter, report.config),
        signal_log=signal_log,
        indicator_series=indicator_series,
        strategy_events=strategy_events,
        strategy_event_meta=strategy_event_meta or [],
        benchmark_equity_curve=benchmark_equity_curve,
        label=label,
        tags=tags or [],
        experiment_id=experiment_id,
    )


def _build_indicator_series(
    median_iter: IterationResult,
    indicator_meta: list[IndicatorMeta],
) -> list[IndicatorSeries]:
    """Build indicator series from the median iteration's snapshots."""
    snapshots = median_iter.indicator_snapshots
    return [
        IndicatorSeries(meta=meta, data=snapshots.get(meta.key, []))
        for meta in indicator_meta
    ]


def _find_median_iteration(
    iterations: list[IterationResult],
) -> IterationResult:
    """Find the iteration whose final_value is closest to the overall median.

    Args:
        iterations: Non-empty list of MC iterations.

    Returns:
        The single IterationResult closest to median performance.
    """
    final_values = [float(it.final_value) for it in iterations]
    median_val = float(np.median(final_values))
    return min(iterations, key=lambda it: abs(float(it.final_value) - median_val))


def _build_equity_curve(
    iterations: list[IterationResult],
) -> list[EquityCurvePoint]:
    """Build equity curve with MC confidence bands.

    For each trading date, computes P5/median/P95 of total_value
    across all iterations.

    Returns:
        List of EquityCurvePoint ordered by date.
    """
    dates = [dv.date for dv in iterations[0].daily_values]
    n_dates = len(dates)
    n_iters = len(iterations)

    matrix = np.empty((n_iters, n_dates))
    for i, it in enumerate(iterations):
        for j, dv in enumerate(it.daily_values):
            matrix[i, j] = float(dv.total_value)

    p5 = np.percentile(matrix, 5, axis=0)
    med = np.percentile(matrix, 50, axis=0)
    p95 = np.percentile(matrix, 95, axis=0)

    return [
        EquityCurvePoint(date=dates[j], p5=p5[j], median=med[j], p95=p95[j])
        for j in range(n_dates)
    ]


def _build_allocations(
    iterations: list[IterationResult],
) -> list[AllocationPoint]:
    """Build per-asset allocation percentages with MC bands.

    Includes a synthetic "cash" pseudo-asset computed as
    (cash / total_value) * 100.

    Returns:
        List of AllocationPoint ordered by date.
    """
    dates = [dv.date for dv in iterations[0].daily_values]
    n_dates = len(dates)
    n_iters = len(iterations)

    asset_ids = list(iterations[0].daily_values[0].allocations.keys())

    asset_matrices: dict[str, np.ndarray] = {}
    for aid in asset_ids:
        m = np.empty((n_iters, n_dates))
        for i, it in enumerate(iterations):
            for j, dv in enumerate(it.daily_values):
                m[i, j] = float(dv.allocations.get(aid, Decimal(0)))
        asset_matrices[aid] = m

    cash_matrix = np.empty((n_iters, n_dates))
    for i, it in enumerate(iterations):
        for j, dv in enumerate(it.daily_values):
            total = float(dv.total_value)
            cash = float(dv.cash)
            cash_matrix[i, j] = (cash / total * 100) if total > 0 else 0.0
    asset_matrices["cash"] = cash_matrix

    points: list[AllocationPoint] = []
    for j in range(n_dates):
        assets: dict[str, ConfidenceInterval] = {}
        for aid, m in asset_matrices.items():
            col = m[:, j]
            assets[aid] = ConfidenceInterval(
                p5=float(np.percentile(col, 5)),
                median=float(np.percentile(col, 50)),
                p95=float(np.percentile(col, 95)),
            )
        points.append(AllocationPoint(date=dates[j], assets=assets))
    return points


def _extract_trades(median_iteration: IterationResult) -> list[TradeRecord]:
    """Convert ExecutedTrade list from median iteration to TradeRecord list."""
    return [
        TradeRecord(
            date=t.date,
            type=t.type,
            asset_id=t.asset_id,
            direction=t.direction,
            amount_eur=float(t.amount_eur),
            quantity=float(t.quantity),
            price=float(t.price),
            fee=float(t.fee),
            skipped=t.skipped,
        )
        for t in median_iteration.trades
    ]


def _compute_summary(
    iterations: list[IterationResult],
    median_iter: IterationResult,
    config: BacktestConfig,
) -> SummaryStats:
    """Compute aggregate summary statistics.

    Uses the median iteration for PAC-related counts and total_invested.
    """
    final_values = [float(it.final_value) for it in iterations]

    fees_per_iter = [sum(float(t.fee) for t in it.trades) for it in iterations]

    trade_counts = [
        sum(1 for t in it.trades if t.type == "hard_rebalance" and not t.skipped)
        for it in iterations
    ]

    pac_trades = [t for t in median_iter.trades if t.type == "pac_execution"]
    pac_count = len(pac_trades)

    contribution_per_pac = config.monthly_contribution / Decimal(
        len(config.pac_execution_days),
    )
    total_invested = (
        float(config.initial_cash)
        + float(
            contribution_per_pac,
        )
        * pac_count
    )

    return SummaryStats(
        total_invested=total_invested,
        final_value=ConfidenceInterval(
            p5=float(np.percentile(final_values, 5)),
            median=float(np.percentile(final_values, 50)),
            p95=float(np.percentile(final_values, 95)),
        ),
        total_fees=ConfidenceInterval(
            p5=float(np.percentile(fees_per_iter, 5)),
            median=float(np.percentile(fees_per_iter, 50)),
            p95=float(np.percentile(fees_per_iter, 95)),
        ),
        total_trades=ConfidenceInterval(
            p5=float(np.percentile(trade_counts, 5)),
            median=float(np.percentile(trade_counts, 50)),
            p95=float(np.percentile(trade_counts, 95)),
        ),
        total_pac_executions=pac_count,
    )


def _map_metrics(
    strategy: MetricSet,
    benchmark: MetricSet | None,
) -> dict[str, dict[str, MetricValue]]:
    """Convert MetricSet models to the sidecar JSON metrics shape.

    Both strategy and benchmark metrics use the uniform {p5, median, p95}
    shape. For deterministic benchmarks (zero slippage), p5 = p95 = median.
    """
    result: dict[str, dict[str, MetricValue]] = {}

    result["strategy"] = {
        name: MetricValue(
            p5=mr.p5,
            median=mr.median,
            p95=mr.p95,
            distribution=mr.per_iteration,
        )
        for name, mr in strategy.metrics.items()
    }

    if benchmark is not None:
        result["benchmark"] = {
            name: MetricValue(
                p5=mr.median,
                median=mr.median,
                p95=mr.median,
                distribution=mr.per_iteration,
            )
            for name, mr in benchmark.metrics.items()
        }

    return result


def _generate_run_id(strategy_name: str, now: datetime) -> str:
    """Generate a filesystem-safe run ID.

    Format: YYYY-MM-DDTHH-MM-SS_{strategy_name}
    Colons replaced with hyphens for cross-platform filesystem safety.
    """
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    return f"{timestamp}_{strategy_name}"
