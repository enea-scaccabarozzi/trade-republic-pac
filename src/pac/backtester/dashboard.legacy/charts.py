"""Plotly figure builders and filter helpers for the backtester dashboard."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go

from pac.backtester.cli_charts import HIGHER_IS_BETTER, compute_drawdown_series
from pac.backtester.results.models import (
    AllocationPoint,
    EquityCurvePoint,
    MetricValue,
    RunResult,
    TradeRecord,
)

# ── Chart builder functions ──────────────────────────────────────────────────


def _empty_figure(text: str) -> go.Figure:
    """Return an empty figure with a centred annotation."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        annotations=[
            {
                "text": text,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 16, "color": "grey"},
            },
        ],
    )
    return fig


def build_equity_figure(
    equity_curve: list[EquityCurvePoint],
) -> go.Figure:
    """Build equity curve line chart with P5/P95 confidence band.

    Args:
        equity_curve: Equity curve data points.

    Returns:
        Plotly Figure with median line + shaded P5/P95 band
        + range slider.
    """
    if not equity_curve:
        return _empty_figure("No equity data")

    dates = [pt.date for pt in equity_curve]
    p5 = [pt.p5 for pt in equity_curve]
    median = [pt.median for pt in equity_curve]
    p95 = [pt.p95 for pt in equity_curve]

    fig = go.Figure()

    # Upper bound (invisible line for fill reference)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=p95,
            mode="lines",
            line={"width": 0},
            name="P95",
            showlegend=False,
        ),
    )

    # Lower bound with fill to upper
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=p5,
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(68, 138, 255, 0.2)",
            name="P5-P95",
        ),
    )

    # Median line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=median,
            mode="lines",
            line={"color": "#448AFF", "width": 2},
            name="Median",
        ),
    )

    fig.update_layout(
        title="Equity Curve (EUR)",
        yaxis_title="EUR",
        template="plotly_dark",
        xaxis={"rangeslider": {"visible": True}},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


def build_allocation_figure(
    allocations: list[AllocationPoint],
) -> go.Figure:
    """Build stacked area chart of asset allocation over time.

    Uses median values from each asset's ConfidenceInterval.

    Args:
        allocations: Per-date allocation data.

    Returns:
        Plotly Figure with stacked area traces per asset.
    """
    if not allocations:
        return _empty_figure("No allocation data")

    dates = [pt.date for pt in allocations]
    asset_names = sorted(allocations[0].assets.keys())

    fig = go.Figure()
    for name in asset_names:
        y_vals = [pt.assets[name].median for pt in allocations]
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=y_vals,
                mode="lines",
                stackgroup="one",
                name=name,
            ),
        )

    fig.update_layout(
        title="Asset Allocation (%)",
        yaxis={"range": [0, 100], "title": "Allocation %"},
        template="plotly_dark",
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


def build_drawdown_figure(
    equity_curve: list[EquityCurvePoint],
) -> go.Figure:
    """Build drawdown from peak chart (area fill to zero).

    Reuses compute_drawdown_series() from cli_charts.

    Args:
        equity_curve: Equity curve data points.

    Returns:
        Plotly Figure with filled area chart of drawdown %.
    """
    if not equity_curve:
        return _empty_figure("No equity data")

    dd_series = compute_drawdown_series(equity_curve)
    dates = [d for d, _ in dd_series]
    values = [v for _, v in dd_series]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(244, 67, 54, 0.3)",
            line={"color": "#F44336"},
            name="Drawdown",
        ),
    )

    fig.update_layout(
        title="Drawdown from Peak",
        yaxis_title="Drawdown %",
        template="plotly_dark",
    )
    return fig


# ── Filter functions ─────────────────────────────────────────────────────────


def filter_equity_curve(
    equity_curve: list[EquityCurvePoint],
    start: date | None = None,
    end: date | None = None,
) -> list[EquityCurvePoint]:
    """Filter equity curve points to a date range.

    Args:
        equity_curve: Full equity curve.
        start: Inclusive start date (None = no lower bound).
        end: Inclusive end date (None = no upper bound).

    Returns:
        Filtered list of points.
    """
    result = equity_curve
    if start is not None:
        result = [pt for pt in result if pt.date >= start]
    if end is not None:
        result = [pt for pt in result if pt.date <= end]
    return result


def filter_allocations(
    allocations: list[AllocationPoint],
    start: date | None = None,
    end: date | None = None,
    assets: set[str] | None = None,
) -> list[AllocationPoint]:
    """Filter allocation points by date range and asset set.

    Since AllocationPoint is frozen=True, new instances are
    constructed when asset filtering is applied.

    Args:
        allocations: Full allocation series.
        start: Inclusive start date.
        end: Inclusive end date.
        assets: Asset IDs to include (None = all).

    Returns:
        Filtered list of AllocationPoint.
    """
    result = allocations
    if start is not None:
        result = [pt for pt in result if pt.date >= start]
    if end is not None:
        result = [pt for pt in result if pt.date <= end]
    if assets is not None:
        result = [
            AllocationPoint(
                date=pt.date,
                assets={k: v for k, v in pt.assets.items() if k in assets},
            )
            for pt in result
        ]
    return result


def filter_trades(
    trades: list[TradeRecord],
    start: date | None = None,
    end: date | None = None,
    assets: set[str] | None = None,
) -> list[TradeRecord]:
    """Filter trade records by date range and asset.

    Args:
        trades: Full trade log.
        start: Inclusive start date.
        end: Inclusive end date.
        assets: Asset IDs to include (None = all).

    Returns:
        Filtered list of TradeRecord.
    """
    result = trades
    if start is not None:
        result = [t for t in result if t.date >= start]
    if end is not None:
        result = [t for t in result if t.date <= end]
    if assets is not None:
        result = [t for t in result if t.asset_id in assets]
    return result


# ── Data transform functions ─────────────────────────────────────────────────


def trades_to_rows(
    trades: list[TradeRecord],
) -> list[dict[str, object]]:
    """Convert TradeRecord list to AG Grid row data dicts.

    Args:
        trades: Trade records to convert.

    Returns:
        List of dicts with keys: date, type, asset, direction,
        amount, quantity, price, fee, skipped.
    """
    return [
        {
            "date": str(t.date),
            "type": "PAC" if t.type == "pac_execution" else "Rebalance",
            "asset": t.asset_id,
            "direction": t.direction,
            "amount": t.amount_eur,
            "quantity": t.quantity,
            "price": t.price,
            "fee": t.fee,
            "skipped": "Yes" if t.skipped else "No",
        }
        for t in trades
    ]


def build_metrics_rows(
    metrics: dict[str, dict[str, MetricValue]],
    config_metrics: list[str],
) -> tuple[list[dict[str, str]], bool]:
    """Transform metrics dict into table row dicts with formatted values.

    Args:
        metrics: Nested dict of group -> metric_name -> MetricValue.
        config_metrics: Ordered list of metric names to display.

    Returns:
        Tuple of (rows, has_benchmark). When benchmark group is absent,
        rows contain only 'metric' and 'strategy' keys.
    """
    from pac.backtester.cli_charts import METRIC_LABELS, PCT_METRICS

    strategy_metrics = metrics.get("strategy", {})
    benchmark_metrics = metrics.get("benchmark", {})
    has_benchmark = bool(benchmark_metrics)

    rows: list[dict[str, str]] = []
    for name in config_metrics:
        mv = strategy_metrics.get(name)
        if mv is None:
            continue

        label = METRIC_LABELS.get(name, name.title())
        is_pct = name in PCT_METRICS

        row: dict[str, str] = {
            "metric": label,
            "strategy": _fmt_ci(mv, is_pct=is_pct),
        }

        if has_benchmark:
            bv = benchmark_metrics.get(name)
            if bv is not None:
                row["benchmark"] = _fmt_single(bv.median, is_pct=is_pct)
                delta = mv.median - bv.median
                higher = name in HIGHER_IS_BETTER
                good = (delta > 0 and higher) or (delta < 0 and not higher)
                sign = "positive" if good else "negative"
                row["delta"] = _fmt_delta(delta, is_pct=is_pct)
                row["delta_class"] = f"text-{sign}" if delta != 0 else ""
            else:
                row["benchmark"] = "\u2014"
                row["delta"] = "\u2014"
                row["delta_class"] = ""

        rows.append(row)

    return rows, has_benchmark


def _fmt_ci(mv: MetricValue, *, is_pct: bool) -> str:
    """Format a MetricValue as 'median [P5 - P95]'."""
    if is_pct:
        return f"{mv.median * 100:.1f}% [{mv.p5 * 100:.1f}% \u2013 {mv.p95 * 100:.1f}%]"
    return f"{mv.median:.2f} [{mv.p5:.2f} \u2013 {mv.p95:.2f}]"


def _fmt_single(val: float, *, is_pct: bool) -> str:
    """Format a single metric value."""
    if is_pct:
        return f"{val * 100:.1f}%"
    return f"{val:.2f}"


def _fmt_delta(delta: float, *, is_pct: bool) -> str:
    """Format a delta value with sign."""
    if is_pct:
        return f"{delta * 100:+.1f}%"
    return f"{delta:+.2f}"


# ── Multi-run comparison builders ────────────────────────────────────────────

_PALETTE = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
    "#FF97FF",
    "#FECB52",
]


def build_overlay_equity_figure(
    runs: list[tuple[str, list[EquityCurvePoint]]],
    *,
    show_bands: bool = False,
) -> go.Figure:
    """Build an overlaid equity curve comparing multiple runs.

    Args:
        runs: List of (label, equity_curve) tuples.
        show_bands: Whether to include P5/P95 confidence bands.

    Returns:
        Plotly Figure with one median line per run, optional bands.
    """
    if not runs:
        return _empty_figure("Select runs to compare")

    fig = go.Figure()

    for idx, (label, curve) in enumerate(runs):
        if not curve:
            continue
        color = _PALETTE[idx % len(_PALETTE)]
        dates = [pt.date for pt in curve]
        median = [pt.median for pt in curve]

        if show_bands:
            p95 = [pt.p95 for pt in curve]
            p5 = [pt.p5 for pt in curve]
            # Upper bound (invisible)
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=p95,
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    name=f"{label} P95",
                ),
            )
            # Lower bound with fill
            r, g, b = _hex_to_rgb(color)
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=p5,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=f"rgba({r},{g},{b},0.2)",
                    showlegend=False,
                    name=f"{label} P5",
                ),
            )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=median,
                mode="lines",
                line={"color": color, "width": 2},
                name=f"{label} Median",
            ),
        )

    fig.update_layout(
        title="Equity Curve Comparison (EUR)",
        yaxis_title="EUR",
        template="plotly_dark",
        xaxis={"rangeslider": {"visible": True}},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def build_comparison_metrics_rows(
    runs_metrics: list[tuple[str, dict[str, dict[str, MetricValue]]]],
    config_metrics: list[str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Build metrics comparison rows for a multi-run table.

    Args:
        runs_metrics: List of (label, metrics_dict) per run.
        config_metrics: Ordered list of metric names to display.

    Returns:
        Tuple of (rows, run_labels). Each row has keys: "metric",
        plus one key per label, "{label}_delta", "{label}_class",
        and "best".
    """
    from pac.backtester.cli_charts import METRIC_LABELS, PCT_METRICS

    if not runs_metrics:
        return [], []

    labels = [label for label, _ in runs_metrics]
    rows: list[dict[str, str]] = []

    for name in config_metrics:
        is_pct = name in PCT_METRICS
        label_text = METRIC_LABELS.get(name, name.title())
        row: dict[str, str] = {"metric": label_text}

        values: dict[str, float | None] = {}
        for lbl, metrics in runs_metrics:
            strat = metrics.get("strategy", {})
            mv = strat.get(name)
            if mv is not None:
                row[lbl] = _fmt_single(mv.median, is_pct=is_pct)
                values[lbl] = mv.median
            else:
                row[lbl] = "\u2014"
                values[lbl] = None

        # Determine best performer
        valid = {k: v for k, v in values.items() if v is not None}
        best_label = ""
        if valid:
            higher = name in HIGHER_IS_BETTER
            best_label = (
                max(valid, key=lambda k: valid[k])
                if higher
                else min(valid, key=lambda k: valid[k])
            )
        row["best"] = best_label

        # Compute deltas from best
        best_val = valid.get(best_label)
        for lbl in labels:
            v = values.get(lbl)
            if v is None or best_val is None:
                row[f"{lbl}_delta"] = ""
                row[f"{lbl}_class"] = ""
            elif lbl == best_label:
                row[f"{lbl}_delta"] = ""
                row[f"{lbl}_class"] = "text-positive"
            else:
                delta = v - best_val
                row[f"{lbl}_delta"] = _fmt_delta(delta, is_pct=is_pct)
                row[f"{lbl}_class"] = "text-negative"

        rows.append(row)

    return rows, labels


def build_summary_comparison(
    runs: list[tuple[str, RunResult]],
) -> list[dict[str, str]]:
    """Build side-by-side KPI summaries for multiple runs.

    Args:
        runs: List of (label, RunResult) tuples.

    Returns:
        One dict per run with pre-formatted string values for:
        label, total_invested, final_value, final_value_ci,
        total_return_pct, total_fees, total_trades, cagr.
    """
    results: list[dict[str, str]] = []

    for label, run in runs:
        s = run.summary
        invested = s.total_invested
        final_median = s.final_value.median
        return_pct = (final_median - invested) / invested * 100 if invested > 0 else 0.0

        cagr_str = "\u2014"
        strat_metrics = run.metrics.get("strategy", {})
        if "cagr" in strat_metrics:
            cagr_str = f"{strat_metrics['cagr'].median * 100:.1f}%"

        results.append(
            {
                "label": label,
                "total_invested": f"\u20ac{invested:,.0f}",
                "final_value": f"\u20ac{final_median:,.0f}",
                "final_value_ci": (
                    f"[\u20ac{s.final_value.p5:,.0f} \u2013"
                    f" \u20ac{s.final_value.p95:,.0f}]"
                ),
                "total_return_pct": f"{return_pct:.1f}%",
                "total_fees": f"\u20ac{s.total_fees.median:,.0f}",
                "total_trades": f"{s.total_trades.median:.0f}",
                "cagr": cagr_str,
            }
        )

    return results
