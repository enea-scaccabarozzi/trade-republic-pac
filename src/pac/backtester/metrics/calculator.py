from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import pandas as pd

from pac.backtester.engine.simulator import IterationResult
from pac.backtester.metrics.models import MetricResult, MetricSet
from pac.backtester.metrics.returns import equity_to_returns

try:
    import quantstats as qs
except ImportError as e:
    msg = (
        "quantstats is required for metrics computation. "
        "Install with: uv sync --group backtest"
    )
    raise ImportError(msg) from e

import numpy as np

_METRIC_FUNCTIONS: dict[str, Callable[[pd.Series[float]], float]] = {
    "sharpe": lambda r: float(qs.stats.sharpe(r, periods=252)),
    "sortino": lambda r: float(qs.stats.sortino(r, periods=252)),
    "calmar": lambda r: float(qs.stats.calmar(r)),
    "max_drawdown": lambda r: float(qs.stats.max_drawdown(r)),
    "cagr": lambda r: float(qs.stats.cagr(r, periods=252)),
    "volatility": lambda r: float(qs.stats.volatility(r, periods=252)),
}


class MetricsCalculator:
    """Compute performance metrics from simulation results.

    Wraps quantstats.stats functions, computes per-iteration values,
    and aggregates across MC iterations using percentiles.
    """

    def __init__(self, metric_names: list[str]) -> None:
        """Initialize with selected metric names.

        Args:
            metric_names: Which metrics to compute (from BacktestConfig.metrics).

        Raises:
            ValueError: If any metric_name is not in the supported registry.
        """
        unknown = set(metric_names) - set(_METRIC_FUNCTIONS)
        if unknown:
            msg = (
                f"Unknown metrics: {sorted(unknown)}. "
                f"Supported: {sorted(_METRIC_FUNCTIONS)}"
            )
            raise ValueError(msg)
        self._metric_names = list(metric_names)

    def compute_iteration(self, returns: pd.Series[float]) -> dict[str, float]:
        """Compute all selected metrics for a single return series.

        Returns:
            Dict of metric_name -> float value.
            NaN-safe: if quantstats returns NaN, stores float('nan').
        """
        result: dict[str, float] = {}
        for name in self._metric_names:
            fn = _METRIC_FUNCTIONS[name]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                val: Any = fn(returns)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                result[name] = float("nan")
            else:
                result[name] = float(val)
        return result

    def compute_all(
        self,
        iterations: list[IterationResult],
        *,
        scenario: str,
    ) -> MetricSet:
        """Compute metrics for all iterations and aggregate.

        For each iteration:
          1. Convert equity curve -> daily returns via equity_to_returns()
          2. Compute all selected metrics

        Then aggregate across iterations:
          - median = np.nanpercentile(values, 50)
          - p5 = np.nanpercentile(values, 5)
          - p95 = np.nanpercentile(values, 95)

        Args:
            iterations: All MC iteration results. Must be non-empty.
            scenario: Name embedded in the returned MetricSet.

        Returns:
            MetricSet with the given scenario name.

        Raises:
            ValueError: If iterations is empty.
        """
        if not iterations:
            msg = "iterations must be non-empty"
            raise ValueError(msg)

        # Compute per-iteration metrics
        per_iter_metrics: list[dict[str, float]] = []
        for iteration in iterations:
            returns = equity_to_returns(iteration)
            metrics = self.compute_iteration(returns)
            per_iter_metrics.append(metrics)

        # Aggregate across iterations
        metric_results: dict[str, MetricResult] = {}
        for name in self._metric_names:
            values = np.array([m[name] for m in per_iter_metrics])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if np.all(np.isnan(values)):
                    median = float("nan")
                    p5 = float("nan")
                    p95 = float("nan")
                else:
                    median = float(np.nanpercentile(values, 50))
                    p5 = float(np.nanpercentile(values, 5))
                    p95 = float(np.nanpercentile(values, 95))

            metric_results[name] = MetricResult(
                name=name,
                median=median,
                p5=p5,
                p95=p95,
                per_iteration=values.tolist(),
            )

        return MetricSet(scenario=scenario, metrics=metric_results)
