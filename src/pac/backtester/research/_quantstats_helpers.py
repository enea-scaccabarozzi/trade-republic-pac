"""Internal quantstats helpers — lazy-import, conversion, metrics registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    import matplotlib.figure
    import pandas as pd

    from pac.backtester.engine.simulator import IterationResult

log = structlog.get_logger()

# ── Lazy import ────────────────────────────────────────────


def _import_qs() -> Any:
    """Lazy-import quantstats; raise clear error if missing."""
    try:
        import quantstats as qs

        return qs
    except ImportError:
        raise ImportError(
            "quantstats is required for this feature. "
            "Install with: uv sync --group backtest"
        ) from None


def _result_to_returns(result: IterationResult) -> pd.Series:
    """Convert IterationResult → daily return Series via equity_to_returns()."""
    from pac.backtester.metrics.returns import equity_to_returns

    return equity_to_returns(result)


# ── Full metrics registry ──────────────────────────────────
# Maps metric name → qs.stats function name
_EXTENDED_METRICS: dict[str, str] = {
    "sharpe": "sharpe",
    "sortino": "sortino",
    "calmar": "calmar",
    "max_drawdown": "max_drawdown",
    "cagr": "cagr",
    "volatility": "volatility",
    "omega": "omega",
    "tail_ratio": "tail_ratio",
    "value_at_risk": "value_at_risk",
    "conditional_value_at_risk": "conditional_value_at_risk",
    "skew": "skew",
    "kurtosis": "kurtosis",
    "gain_to_pain_ratio": "gain_to_pain_ratio",
    "payoff_ratio": "payoff_ratio",
    "profit_ratio": "profit_ratio",
    "win_rate": "win_rate",
    "avg_win": "avg_win",
    "avg_loss": "avg_loss",
    "best": "best",
    "worst": "worst",
    "kelly_criterion": "kelly_criterion",
    "total_return": "comp",
}

_ANNUALIZED_METRICS = {"sharpe", "sortino", "cagr", "volatility"}

_DEFAULT_METRICS = [
    "sharpe",
    "sortino",
    "calmar",
    "max_drawdown",
    "cagr",
    "volatility",
    "omega",
]

_SUPPORTED_PLOT_KINDS = [
    "returns",
    "monthly_heatmap",
    "drawdown",
    "rolling_sharpe",
    "rolling_sortino",
    "rolling_volatility",
    "histogram",
    "daily_returns",
    "distribution",
    "drawdowns_periods",
]

_SUPPORTED_ROLLING_METRICS = {"sharpe", "sortino", "volatility"}


def compute_metrics(
    returns: pd.Series,
    metric_names: list[str] | None = None,
) -> dict[str, float]:
    """Compute selected (or all) quantstats metrics from a return series.

    For extended metrics via ResearchContext, see
    ``ResearchContext.quantstats()``.
    """
    import pandas as _pd

    qs = _import_qs()

    names = metric_names if metric_names is not None else list(_DEFAULT_METRICS)
    unknown = [n for n in names if n not in _EXTENDED_METRICS]
    if unknown:
        available = sorted(_EXTENDED_METRICS.keys())
        raise ValueError(f"Unknown metric(s): {unknown}. Available: {available}")

    result: dict[str, float] = {}
    for name in names:
        func_name = _EXTENDED_METRICS[name]
        fn = getattr(qs.stats, func_name)

        value: Any
        if name in _ANNUALIZED_METRICS:
            try:
                value = fn(returns, periods=252)
            except TypeError:
                value = fn(returns)
        else:
            value = fn(returns)

        if value is None or (_pd.notna(value) is False):
            result[name] = float("nan")
        else:
            result[name] = float(value)

    return result


def generate_html_report(
    returns: pd.Series,
    output: str | Path,
    *,
    benchmark_returns: pd.Series | None = None,
    title: str = "Quantstats Report",
) -> Path:
    """Generate HTML tearsheet via qs.reports.html()."""
    from pathlib import Path as _Path

    qs = _import_qs()

    resolved = _Path(output).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    qs.reports.html(
        returns,
        benchmark=benchmark_returns,
        output=str(resolved),
        title=title,
        download_filename=resolved.name,
    )

    return resolved


def generate_plot(
    returns: pd.Series,
    kind: str,
    *,
    benchmark_returns: pd.Series | None = None,
) -> matplotlib.figure.Figure:
    """Generate a single matplotlib figure via qs.plots.<kind>()."""
    import matplotlib.figure as _mpl_fig
    import matplotlib.pyplot as plt
    import numpy as np

    if kind not in _SUPPORTED_PLOT_KINDS:
        raise ValueError(
            f"Unknown plot kind {kind!r}. Supported: {_SUPPORTED_PLOT_KINDS}"
        )

    qs = _import_qs()
    plot_fn = getattr(qs.plots, kind)

    # Not all plot functions accept `benchmark` — try with, fall back without
    try:
        result = plot_fn(returns, benchmark=benchmark_returns, show=False)
    except TypeError:
        result = plot_fn(returns, show=False)

    # Capture the return value before falling back to plt.gcf()
    if isinstance(result, _mpl_fig.Figure):
        return result
    if isinstance(result, np.ndarray):
        # Array of Axes
        fig: matplotlib.figure.Figure | None = result.flat[0].get_figure()
        if fig is not None:
            return fig
    if hasattr(result, "get_figure"):
        fig = result.get_figure()
        if fig is not None:
            return fig

    return plt.gcf()


def compute_rolling(
    returns: pd.Series,
    metric: str,
    window: int = 252,
) -> list[tuple[date, float]]:
    """Compute a rolling metric via qs.stats.rolling_<metric>()."""
    import pandas as _pd

    if metric not in _SUPPORTED_ROLLING_METRICS:
        raise ValueError(
            f"Unknown rolling metric {metric!r}. "
            f"Supported: {sorted(_SUPPORTED_ROLLING_METRICS)}"
        )

    if len(returns) < window:
        log.warning(
            "returns_shorter_than_window",
            returns_len=len(returns),
            window=window,
        )

    qs = _import_qs()
    rolling_fn = getattr(qs.stats, f"rolling_{metric}")
    series: _pd.Series[float] = rolling_fn(returns, rolling_period=window)

    result: list[tuple[date, float]] = []
    for ts, value in series.items():
        if _pd.notna(value):
            result.append((ts.date(), float(value)))

    return result
