"""Chart rendering and table building helpers for the backtester CLI."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from rich.table import Table

if TYPE_CHECKING:
    from pac.backtester.results.models import (
        AllocationPoint,
        EquityCurvePoint,
        MetricValue,
        TradeRecord,
    )

METRIC_LABELS: dict[str, str] = {
    "sortino": "Sortino",
    "calmar": "Calmar",
    "max_drawdown": "Max Drawdown",
    "cagr": "CAGR",
    "sharpe": "Sharpe",
    "volatility": "Volatility",
}

PCT_METRICS = frozenset({"max_drawdown", "cagr"})

HIGHER_IS_BETTER = frozenset({"sortino", "calmar", "cagr", "sharpe"})

_TRADE_TYPE_LABELS: dict[str, str] = {
    "pac_execution": "PAC",
    "hard_rebalance": "Rebalance",
}


# ── Pure data functions ───────────────────────────────────────────────────────


def compute_drawdown_series(
    equity_curve: list[EquityCurvePoint],
) -> list[tuple[date, float]]:
    """Compute drawdown from peak of the median equity curve.

    Returns:
        List of (date, drawdown_pct) where drawdown_pct is negative
        (0.0 = at peak).
    """
    if not equity_curve:
        return []

    result: list[tuple[date, float]] = []
    peak = equity_curve[0].median
    for pt in equity_curve:
        peak = max(peak, pt.median)
        dd = (pt.median - peak) / peak * 100 if peak > 0 else 0.0
        result.append((pt.date, dd))
    return result


def sample_points(n_total: int, max_points: int = 80) -> list[int]:
    """Return evenly-spaced indices for sampling long time series.

    Args:
        n_total: Total number of data points.
        max_points: Maximum number of indices to return.

    Returns:
        Sorted list of unique indices including first and last.
    """
    if n_total <= max_points:
        return list(range(n_total))
    step = (n_total - 1) / (max_points - 1)
    return sorted(set(round(i * step) for i in range(max_points)))


# ── Plotext chart functions ───────────────────────────────────────────────────


def plot_equity_curve(equity_curve: list[EquityCurvePoint]) -> str:
    """Render equity curve with P5/median/P95 bands using plotext.

    Args:
        equity_curve: List of equity curve points with confidence bands.

    Returns:
        The chart as a string.

    Raises:
        ImportError: If plotext is not installed.
    """
    import plotext as plt

    indices = sample_points(len(equity_curve))
    dates = [equity_curve[i].date.strftime("%Y-%m-%d") for i in indices]
    medians = [equity_curve[i].median for i in indices]
    p5_vals = [equity_curve[i].p5 for i in indices]
    p95_vals = [equity_curve[i].p95 for i in indices]

    plt.clf()
    plt.date_form("Y-m-d")
    plt.plot(dates, medians, label="Median")
    plt.plot(dates, p5_vals, label="P5")
    plt.plot(dates, p95_vals, label="P95")
    plt.title("Equity Curve (EUR)")
    plt.xlabel("Date")
    plt.ylabel("EUR")
    plt.theme("pro")
    plt.plotsize(None, 20)
    return plt.build()  # type: ignore[no-any-return]


def plot_drawdown(equity_curve: list[EquityCurvePoint]) -> str:
    """Render drawdown chart from equity curve median using plotext.

    Args:
        equity_curve: List of equity curve points.

    Returns:
        The chart as a string.

    Raises:
        ImportError: If plotext is not installed.
    """
    import plotext as plt

    dd_series = compute_drawdown_series(equity_curve)
    indices = sample_points(len(dd_series))
    dates = [dd_series[i][0].strftime("%Y-%m-%d") for i in indices]
    drawdowns = [dd_series[i][1] for i in indices]

    plt.clf()
    plt.date_form("Y-m-d")
    plt.plot(dates, drawdowns, label="Drawdown %", fillx=0)
    plt.title("Drawdown from Peak")
    plt.xlabel("Date")
    plt.ylabel("Drawdown %")
    plt.theme("pro")
    plt.plotsize(None, 20)
    return plt.build()  # type: ignore[no-any-return]


def plot_allocation(allocations: list[AllocationPoint]) -> str:
    """Render allocation stacked bar chart using plotext.

    Stacked bars used because plotext doesn't support stacked area
    charts natively.

    Args:
        allocations: List of allocation points with per-asset CIs.

    Returns:
        The chart as a string.

    Raises:
        ImportError: If plotext is not installed.
    """
    import plotext as plt

    indices = sample_points(len(allocations))
    date_labels = [allocations[i].date.strftime("%Y-%m-%d") for i in indices]
    asset_names = sorted(allocations[0].assets.keys())
    data: list[list[float]] = [
        [allocations[i].assets[name].median for i in indices] for name in asset_names
    ]

    plt.clf()
    plt.stacked_bar(date_labels, data, labels=asset_names)
    plt.title("Asset Allocation (%)")
    plt.xlabel("Date")
    plt.ylabel("Allocation %")
    plt.theme("pro")
    plt.plotsize(None, 20)
    return plt.build()  # type: ignore[no-any-return]


# ── Rich table builders ──────────────────────────────────────────────────────


def build_trade_table(trades: list[TradeRecord]) -> Table:
    """Build Rich Table for the trade log.

    Args:
        trades: List of trade records to display.

    Returns:
        A Rich Table ready for printing.
    """
    table = Table(show_header=True, header_style="bold", show_edge=False)
    table.add_column("Date")
    table.add_column("Type")
    table.add_column("Asset")
    table.add_column("Direction")
    table.add_column("Amount (€)")
    table.add_column("Qty")
    table.add_column("Price")
    table.add_column("Fee")
    table.add_column("Skipped")

    for t in trades:
        direction = "[green]BUY[/green]" if t.direction == "buy" else "[red]SELL[/red]"
        type_label = _TRADE_TYPE_LABELS.get(t.type, t.type)
        style = "dim" if t.skipped else ""
        table.add_row(
            str(t.date),
            type_label,
            t.asset_id,
            direction,
            f"€{t.amount_eur:,.2f}",
            f"{t.quantity:.4f}",
            f"€{t.price:,.2f}",
            f"€{t.fee:,.2f}",
            "Yes" if t.skipped else "No",
            style=style,
        )

    return table


def _fmt_strategy_value(mv: MetricValue, *, is_pct: bool) -> str:
    """Format a strategy MetricValue with P5-P95 confidence interval."""
    if is_pct:
        return f"{mv.median * 100:.1f}% [{mv.p5 * 100:.1f}% \u2013 {mv.p95 * 100:.1f}%]"
    return f"{mv.median:.2f} [{mv.p5:.2f} \u2013 {mv.p95:.2f}]"


def _fmt_benchmark_value(mv: MetricValue, *, is_pct: bool) -> str:
    """Format a benchmark MetricValue (median only)."""
    if is_pct:
        return f"{mv.median * 100:.1f}%"
    return f"{mv.median:.2f}"


def _fmt_delta(delta: float, *, higher_is_better: bool, is_pct: bool) -> str:
    """Format a delta value with color markup."""
    text = f"{delta * 100:+.1f}%" if is_pct else f"{delta:+.2f}"

    good = (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better)
    color = "green" if good else "red"
    if delta == 0:
        return text
    return f"[{color}]{text}[/{color}]"


def build_metrics_table(
    metrics: dict[str, dict[str, MetricValue]],
    config_metrics: list[str],
    benchmark_enabled: bool,
) -> Table:
    """Build Rich Table for metrics with colored strategy-vs-benchmark deltas.

    Args:
        metrics: Nested dict of group → metric_name → MetricValue.
        config_metrics: Ordered list of metric names to display.
        benchmark_enabled: Whether to show Benchmark and Delta columns.

    Returns:
        A Rich Table ready for printing.
    """
    table = Table(show_header=True, header_style="bold", show_edge=False)
    table.add_column("Metric")
    table.add_column("Strategy [P5\u2013P95]")
    if benchmark_enabled:
        table.add_column("Benchmark")
        table.add_column("Delta")

    strategy_metrics = metrics.get("strategy", {})
    benchmark_metrics = metrics.get("benchmark", {})

    for metric_name in config_metrics:
        label = METRIC_LABELS.get(metric_name, metric_name.title())
        is_pct = metric_name in PCT_METRICS
        mv = strategy_metrics.get(metric_name)
        if mv is None:
            continue

        row: list[str] = [label, _fmt_strategy_value(mv, is_pct=is_pct)]

        if benchmark_enabled:
            bv = benchmark_metrics.get(metric_name)
            if bv is not None:
                row.append(_fmt_benchmark_value(bv, is_pct=is_pct))
                delta = mv.median - bv.median
                higher_is_better = metric_name in HIGHER_IS_BETTER
                row.append(
                    _fmt_delta(
                        delta,
                        higher_is_better=higher_is_better,
                        is_pct=is_pct,
                    )
                )
            else:
                row.extend(["\u2014", "\u2014"])

        table.add_row(*row)

    return table
