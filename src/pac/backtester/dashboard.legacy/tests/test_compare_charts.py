"""Unit tests for multi-run comparison chart builders."""

from __future__ import annotations

from pac.backtester.dashboard.charts import (
    build_comparison_metrics_rows,
    build_overlay_equity_figure,
    build_summary_comparison,
)
from pac.backtester.results.models import MetricValue, RunResult

# ── build_overlay_equity_figure ──────────────────────────────────────────────


class TestBuildOverlayEquityFigure:
    """Tests for build_overlay_equity_figure()."""

    def test_empty_runs_returns_empty_figure(self) -> None:
        fig = build_overlay_equity_figure([])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1
        assert "Select runs" in fig.layout.annotations[0].text

    def test_single_run_has_one_median_trace(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [("Run A", sample_run_result.equity_curve)],
        )
        assert len(fig.data) == 1
        assert "Run A Median" in fig.data[0].name

    def test_two_runs_have_two_median_traces(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [
                ("Run A", sample_run_result.equity_curve),
                ("Run B", sample_run_result_b.equity_curve),
            ]
        )
        assert len(fig.data) == 2
        names = {t.name for t in fig.data}
        assert "Run A Median" in names
        assert "Run B Median" in names

    def test_show_bands_adds_fill_traces(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [("Run A", sample_run_result.equity_curve)],
            show_bands=True,
        )
        # 2 band traces + 1 median = 3
        assert len(fig.data) == 3
        fills = [t.fill for t in fig.data]
        assert "tonexty" in fills

    def test_no_bands_only_median_traces(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [
                ("A", sample_run_result.equity_curve),
                ("B", sample_run_result_b.equity_curve),
            ]
        )
        for trace in fig.data:
            assert trace.fill is None

    def test_distinct_colors_per_run(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [
                ("A", sample_run_result.equity_curve),
                ("B", sample_run_result_b.equity_curve),
            ]
        )
        colors = [t.line.color for t in fig.data]
        assert colors[0] != colors[1]

    def test_dark_template(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [("A", sample_run_result.equity_curve)],
        )
        assert fig.layout.template.layout.paper_bgcolor == "rgb(17,17,17)"

    def test_rangeslider_enabled(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_overlay_equity_figure(
            [("A", sample_run_result.equity_curve)],
        )
        assert fig.layout.xaxis.rangeslider.visible is True


# ── build_comparison_metrics_rows ────────────────────────────────────────────


class TestBuildComparisonMetricsRows:
    """Tests for build_comparison_metrics_rows()."""

    def test_empty_runs_returns_empty(self) -> None:
        rows, labels = build_comparison_metrics_rows([], ["cagr"])
        assert rows == []
        assert labels == []

    def test_single_run_all_metrics_present(
        self,
        sample_run_result: RunResult,
    ) -> None:
        rows, labels = build_comparison_metrics_rows(
            [("A", sample_run_result.metrics)],
            sample_run_result.config.metrics,
        )
        assert labels == ["A"]
        metric_names = [r["metric"] for r in rows]
        assert "CAGR" in metric_names
        assert "Sharpe" in metric_names

    def test_two_runs_best_identified_for_higher_is_better(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        rows, _ = build_comparison_metrics_rows(
            [("A", sample_run_result.metrics), ("B", sample_run_result_b.metrics)],
            ["cagr"],
        )
        cagr_row = rows[0]
        # B has higher CAGR median (0.09 vs 0.08)
        assert cagr_row["best"] == "B"
        assert cagr_row["B_class"] == "text-positive"
        assert cagr_row["A_class"] == "text-negative"

    def test_two_runs_best_identified_for_lower_is_better(
        self,
        sample_run_result_b: RunResult,
    ) -> None:
        # max_drawdown: lower (less negative) is worse for HIGHER_IS_BETTER,
        # but max_drawdown is NOT in HIGHER_IS_BETTER, so lower is better.
        metrics_a: dict[str, dict[str, MetricValue]] = {
            "strategy": {
                "max_drawdown": MetricValue(p5=-0.30, median=-0.20, p95=-0.10),
            },
        }
        metrics_b = sample_run_result_b.metrics
        rows, _ = build_comparison_metrics_rows(
            [("A", metrics_a), ("B", metrics_b)],
            ["max_drawdown"],
        )
        dd_row = rows[0]
        # max_drawdown not in HIGHER_IS_BETTER → lower is better
        # A median=-0.20, B median=-0.18 (from fixture with -0.25 as p5)
        # Actually B has max_drawdown median=-0.18 which is higher (less negative)
        # For min (lower is better): -0.20 < -0.18, so A is best
        assert dd_row["best"] == "A"

    def test_missing_metric_in_one_run_shows_dash(
        self,
        sample_run_result: RunResult,
    ) -> None:
        metrics_b: dict[str, dict[str, MetricValue]] = {
            "strategy": {},
        }
        rows, _ = build_comparison_metrics_rows(
            [("A", sample_run_result.metrics), ("B", metrics_b)],
            ["cagr"],
        )
        assert rows[0]["B"] == "\u2014"

    def test_delta_from_best_formatted(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        rows, _ = build_comparison_metrics_rows(
            [("A", sample_run_result.metrics), ("B", sample_run_result_b.metrics)],
            ["cagr"],
        )
        cagr_row = rows[0]
        # Best is B; A's delta should be non-empty
        assert cagr_row["A_delta"] != ""
        # Best's delta is empty
        assert cagr_row["B_delta"] == ""


# ── build_summary_comparison ─────────────────────────────────────────────────


class TestBuildSummaryComparison:
    """Tests for build_summary_comparison()."""

    def test_returns_one_dict_per_run(
        self,
        sample_run_result: RunResult,
        sample_run_result_b: RunResult,
    ) -> None:
        result = build_summary_comparison(
            [
                ("A", sample_run_result),
                ("B", sample_run_result_b),
            ]
        )
        assert len(result) == 2
        assert result[0]["label"] == "A"
        assert result[1]["label"] == "B"

    def test_total_return_calculated_correctly(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = build_summary_comparison([("A", sample_run_result)])
        # invested=40000, final=52000 → 30.0%
        assert result[0]["total_return_pct"] == "30.0%"

    def test_cagr_present_when_available(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = build_summary_comparison([("A", sample_run_result)])
        # cagr median=0.08 → "8.0%"
        assert result[0]["cagr"] == "8.0%"

    def test_cagr_dash_when_missing(self) -> None:
        from datetime import date, datetime

        from pac.backtester.config import BacktestConfig
        from pac.backtester.results.models import (
            ConfidenceInterval,
            MonteCarloInfo,
            SummaryStats,
        )

        run = RunResult(
            run_id="no_cagr",
            created_at=datetime(2026, 1, 1),
            config=BacktestConfig(
                strategy="x",
                start_date=date(2020, 1, 1),
                end_date=date(2025, 1, 1),
            ),
            monte_carlo=MonteCarloInfo(iterations=1, slippage_range=(0, 0)),
            metrics={"strategy": {}},
            equity_curve=[],
            allocations=[],
            trades=[],
            summary=SummaryStats(
                total_invested=1000,
                final_value=ConfidenceInterval(p5=900, median=1000, p95=1100),
                total_fees=ConfidenceInterval(p5=0, median=0, p95=0),
                total_trades=ConfidenceInterval(p5=0, median=0, p95=0),
                total_pac_executions=0,
            ),
        )
        result = build_summary_comparison([("X", run)])
        assert result[0]["cagr"] == "\u2014"
