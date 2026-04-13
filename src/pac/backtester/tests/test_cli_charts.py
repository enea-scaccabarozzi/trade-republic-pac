"""Unit tests for cli_charts — pure data functions and table builders."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console

from pac.backtester.cli_charts import (
    METRIC_LABELS,
    PCT_METRICS,
    build_metrics_table,
    build_trade_table,
    compute_drawdown_series,
    sample_points,
)
from pac.backtester.results.models import (
    EquityCurvePoint,
    MetricValue,
    TradeRecord,
)


def _render_table_to_str(table: object) -> str:
    """Capture Rich Table output as plain string."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=True, width=200)
    con.print(table)
    return buf.getvalue()


# ── compute_drawdown_series ───────────────────────────────────────────────


class TestComputeDrawdownSeries:
    def test_monotonically_increasing_equity_has_zero_drawdown(self) -> None:
        """If equity only goes up, drawdown is 0% at every point."""
        curve = [
            EquityCurvePoint(
                date=date(2020, 1, i + 1), p5=0, median=100 + i * 10, p95=0
            )
            for i in range(5)
        ]
        result = compute_drawdown_series(curve)
        assert all(dd == 0.0 for _, dd in result)

    def test_50pct_drop_produces_minus_50_drawdown(self) -> None:
        """Peak 100 → drop to 50 → drawdown is -50%."""
        curve = [
            EquityCurvePoint(date=date(2020, 1, 1), p5=0, median=100, p95=0),
            EquityCurvePoint(date=date(2020, 1, 2), p5=0, median=50, p95=0),
        ]
        result = compute_drawdown_series(curve)
        assert result[0][1] == 0.0
        assert result[1][1] == -50.0

    def test_recovery_after_drawdown_returns_to_zero(self) -> None:
        """Peak 100 → drop to 80 → recover to 100 → drawdown back to 0%."""
        curve = [
            EquityCurvePoint(date=date(2020, 1, 1), p5=0, median=100, p95=0),
            EquityCurvePoint(date=date(2020, 1, 2), p5=0, median=80, p95=0),
            EquityCurvePoint(date=date(2020, 1, 3), p5=0, median=100, p95=0),
        ]
        result = compute_drawdown_series(curve)
        assert result[0][1] == 0.0
        assert result[1][1] == -20.0
        assert result[2][1] == 0.0

    def test_empty_equity_curve_returns_empty_list(self) -> None:
        """Edge case: no data points."""
        assert compute_drawdown_series([]) == []

    def test_single_point_returns_zero_drawdown(self) -> None:
        """Single point is its own peak → 0%."""
        curve = [
            EquityCurvePoint(date=date(2020, 1, 1), p5=0, median=100, p95=0),
        ]
        result = compute_drawdown_series(curve)
        assert len(result) == 1
        assert result[0][1] == 0.0

    def test_multiple_drawdowns_tracks_correct_peaks(self) -> None:
        """Peak 100 → 90 → 110 → 80: second drawdown measured from 110."""
        curve = [
            EquityCurvePoint(date=date(2020, 1, 1), p5=0, median=100, p95=0),
            EquityCurvePoint(date=date(2020, 1, 2), p5=0, median=90, p95=0),
            EquityCurvePoint(date=date(2020, 1, 3), p5=0, median=110, p95=0),
            EquityCurvePoint(date=date(2020, 1, 4), p5=0, median=80, p95=0),
        ]
        result = compute_drawdown_series(curve)
        assert result[0][1] == 0.0
        assert result[1][1] == -10.0  # (90 - 100) / 100 * 100
        assert result[2][1] == 0.0
        # (80 - 110) / 110 * 100 ≈ -27.27
        assert abs(result[3][1] - (-30 / 110 * 100)) < 0.01


# ── sample_points ─────────────────────────────────────────────────────────


class TestSamplePoints:
    def test_fewer_points_than_max_returns_all_indices(self) -> None:
        """10 points, max 80 → [0, 1, ..., 9]."""
        assert sample_points(10, max_points=80) == list(range(10))

    def test_exact_max_returns_all_indices(self) -> None:
        """80 points, max 80 → [0, 1, ..., 79]."""
        assert sample_points(80, max_points=80) == list(range(80))

    def test_more_than_max_returns_max_evenly_spaced(self) -> None:
        """200 points, max 80 → 80 elements, includes 0 and 199."""
        result = sample_points(200, max_points=80)
        assert len(result) == 80
        assert result[0] == 0
        assert result[-1] == 199

    def test_sampled_indices_include_first_and_last(self) -> None:
        """Always includes index 0 and n_total-1."""
        result = sample_points(500, max_points=50)
        assert 0 in result
        assert 499 in result

    def test_sampled_indices_are_sorted_and_unique(self) -> None:
        """Result is strictly increasing."""
        result = sample_points(1000, max_points=100)
        assert result == sorted(set(result))


# ── build_trade_table ─────────────────────────────────────────────────────


def _make_trade(
    *,
    direction: str = "buy",
    trade_type: str = "pac_execution",
    skipped: bool = False,
) -> TradeRecord:
    return TradeRecord(
        date=date(2020, 6, 15),
        type=trade_type,  # type: ignore[arg-type]
        asset_id="EUNL",
        direction=direction,  # type: ignore[arg-type]
        amount_eur=500.0,
        quantity=5.1234,
        price=97.89,
        fee=1.0,
        skipped=skipped,
    )


class TestBuildTradeTable:
    def test_empty_trades_returns_table_with_header_only(self) -> None:
        """No trades → table has columns but no rows."""
        table = build_trade_table([])
        assert table.row_count == 0
        assert len(table.columns) == 9

    def test_buy_direction_has_green_markup(self) -> None:
        """Buy trades rendered with [green] Rich markup."""
        table = build_trade_table([_make_trade(direction="buy")])
        output = _render_table_to_str(table)
        assert "BUY" in output

    def test_sell_direction_has_red_markup(self) -> None:
        """Sell trades rendered with [red] Rich markup."""
        table = build_trade_table([_make_trade(direction="sell")])
        output = _render_table_to_str(table)
        assert "SELL" in output

    def test_skipped_trade_has_dim_style(self) -> None:
        """Skipped trades shown with 'Yes' in skipped column."""
        table = build_trade_table([_make_trade(skipped=True)])
        output = _render_table_to_str(table)
        assert "Yes" in output

    def test_pac_type_label(self) -> None:
        """pac_execution → 'PAC'."""
        table = build_trade_table([_make_trade(trade_type="pac_execution")])
        output = _render_table_to_str(table)
        assert "PAC" in output

    def test_rebalance_type_label(self) -> None:
        """hard_rebalance → 'Rebalance'."""
        table = build_trade_table([_make_trade(trade_type="hard_rebalance")])
        output = _render_table_to_str(table)
        assert "Rebalance" in output


# ── build_metrics_table ───────────────────────────────────────────────────


def _make_mv(p5: float, median: float, p95: float) -> MetricValue:
    return MetricValue(p5=p5, median=median, p95=p95)


class TestBuildMetricsTable:
    def test_no_benchmark_omits_benchmark_columns(self) -> None:
        """When benchmark_enabled=False, table has 2 columns."""
        metrics = {"strategy": {"sortino": _make_mv(0.5, 1.0, 1.5)}}
        table = build_metrics_table(metrics, ["sortino"], benchmark_enabled=False)
        assert len(table.columns) == 2

    def test_with_benchmark_has_delta_column(self) -> None:
        """When benchmark_enabled=True, table has 4 columns."""
        metrics = {
            "strategy": {"sortino": _make_mv(0.5, 1.0, 1.5)},
            "benchmark": {"sortino": _make_mv(0.3, 0.8, 1.0)},
        }
        table = build_metrics_table(metrics, ["sortino"], benchmark_enabled=True)
        assert len(table.columns) == 4

    def test_positive_delta_on_higher_is_better_metric_is_green(self) -> None:
        """Strategy Sortino > Benchmark Sortino → green delta."""
        metrics = {
            "strategy": {"sortino": _make_mv(0.5, 1.0, 1.5)},
            "benchmark": {"sortino": _make_mv(0.3, 0.8, 1.0)},
        }
        table = build_metrics_table(metrics, ["sortino"], benchmark_enabled=True)
        output = _render_table_to_str(table)
        assert "+0.20" in output

    def test_negative_delta_on_higher_is_better_metric_is_red(self) -> None:
        """Strategy CAGR < Benchmark CAGR → red delta."""
        metrics = {
            "strategy": {"cagr": _make_mv(0.03, 0.05, 0.08)},
            "benchmark": {"cagr": _make_mv(0.06, 0.10, 0.12)},
        }
        table = build_metrics_table(metrics, ["cagr"], benchmark_enabled=True)
        output = _render_table_to_str(table)
        assert "-5.0%" in output

    def test_lower_is_better_metric_reversed_coloring(self) -> None:
        """Strategy max_drawdown < Benchmark → green (lower drawdown is better)."""
        metrics = {
            "strategy": {"max_drawdown": _make_mv(-0.20, -0.15, -0.10)},
            "benchmark": {"max_drawdown": _make_mv(-0.30, -0.25, -0.20)},
        }
        table = build_metrics_table(metrics, ["max_drawdown"], benchmark_enabled=True)
        output = _render_table_to_str(table)
        # Strategy -15% is better than benchmark -25%, delta = +10.0%
        assert "+10.0%" in output

    def test_pct_metrics_formatted_with_percent(self) -> None:
        """CAGR and max_drawdown values shown as percentages."""
        metrics = {"strategy": {"cagr": _make_mv(0.05, 0.08, 0.12)}}
        table = build_metrics_table(metrics, ["cagr"], benchmark_enabled=False)
        output = _render_table_to_str(table)
        assert "8.0%" in output
        assert METRIC_LABELS["cagr"] in output

    def test_non_pct_metric_formatted_without_percent(self) -> None:
        """Sortino formatted as decimal, not percentage."""
        metrics = {"strategy": {"sortino": _make_mv(0.5, 1.0, 1.5)}}
        table = build_metrics_table(metrics, ["sortino"], benchmark_enabled=False)
        output = _render_table_to_str(table)
        assert "1.00" in output
        assert "sortino" not in PCT_METRICS
