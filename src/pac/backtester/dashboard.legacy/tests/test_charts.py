"""Unit tests for dashboard Plotly chart builders and filter functions."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go

from pac.backtester.dashboard.charts import (
    build_allocation_figure,
    build_drawdown_figure,
    build_equity_figure,
    build_metrics_rows,
    filter_allocations,
    filter_equity_curve,
    filter_trades,
    trades_to_rows,
)
from pac.backtester.results.models import (
    MetricValue,
    RunResult,
    TradeRecord,
)

# ── build_equity_figure ──────────────────────────────────────────────────────


class TestBuildEquityFigure:
    """Tests for build_equity_figure()."""

    def test_has_three_traces(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_equity_figure(sample_run_result.equity_curve)
        assert len(fig.data) == 3

    def test_median_trace_is_scatter(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_equity_figure(sample_run_result.equity_curve)
        median_trace = fig.data[2]
        assert isinstance(median_trace, go.Scatter)
        assert "Median" in median_trace.name

    def test_confidence_band_uses_fill_tonexty(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_equity_figure(sample_run_result.equity_curve)
        p5_trace = fig.data[1]
        assert p5_trace.fill == "tonexty"

    def test_rangeslider_enabled(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_equity_figure(sample_run_result.equity_curve)
        assert fig.layout.xaxis.rangeslider.visible is True

    def test_dark_template(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_equity_figure(sample_run_result.equity_curve)
        # plotly_dark sets a dark paper/plot bg
        layout = fig.layout
        assert layout.template.layout.paper_bgcolor == "rgb(17,17,17)"

    def test_empty_input_returns_empty_figure(self) -> None:
        fig = build_equity_figure([])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1
        assert "No equity data" in fig.layout.annotations[0].text


# ── build_allocation_figure ──────────────────────────────────────────────────


class TestBuildAllocationFigure:
    """Tests for build_allocation_figure()."""

    def test_one_trace_per_asset(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_allocation_figure(sample_run_result.allocations)
        asset_count = len(sample_run_result.allocations[0].assets)
        assert len(fig.data) == asset_count

    def test_traces_use_stackgroup(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_allocation_figure(sample_run_result.allocations)
        for trace in fig.data:
            assert trace.stackgroup == "one"

    def test_yaxis_range_0_to_100(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_allocation_figure(sample_run_result.allocations)
        assert fig.layout.yaxis.range == (0, 100)

    def test_empty_input_returns_empty_figure(self) -> None:
        fig = build_allocation_figure([])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1


# ── build_drawdown_figure ────────────────────────────────────────────────────


class TestBuildDrawdownFigure:
    """Tests for build_drawdown_figure()."""

    def test_single_trace_with_fill(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_drawdown_figure(sample_run_result.equity_curve)
        assert len(fig.data) == 1
        assert fig.data[0].fill == "tozeroy"

    def test_drawdown_values_are_non_positive(
        self,
        sample_run_result: RunResult,
    ) -> None:
        fig = build_drawdown_figure(sample_run_result.equity_curve)
        y_vals = list(fig.data[0].y)
        assert all(v <= 0 for v in y_vals)

    def test_empty_input_returns_empty_figure(self) -> None:
        fig = build_drawdown_figure([])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1


# ── filter_equity_curve ──────────────────────────────────────────────────────


class TestFilterEquityCurve:
    """Tests for filter_equity_curve()."""

    def test_no_filter_returns_all(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_equity_curve(sample_run_result.equity_curve)
        assert len(result) == len(sample_run_result.equity_curve)

    def test_filter_by_start_date(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_equity_curve(
            sample_run_result.equity_curve,
            start=date(2022, 1, 1),
        )
        assert all(pt.date >= date(2022, 1, 1) for pt in result)
        assert len(result) < len(sample_run_result.equity_curve)

    def test_filter_by_end_date(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_equity_curve(
            sample_run_result.equity_curve,
            end=date(2022, 12, 31),
        )
        assert all(pt.date <= date(2022, 12, 31) for pt in result)
        assert len(result) < len(sample_run_result.equity_curve)

    def test_filter_by_both_dates(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_equity_curve(
            sample_run_result.equity_curve,
            start=date(2021, 1, 1),
            end=date(2023, 12, 31),
        )
        assert all(date(2021, 1, 1) <= pt.date <= date(2023, 12, 31) for pt in result)

    def test_filter_excludes_all_returns_empty(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_equity_curve(
            sample_run_result.equity_curve,
            start=date(2030, 1, 1),
        )
        assert result == []


# ── filter_allocations ───────────────────────────────────────────────────────


class TestFilterAllocations:
    """Tests for filter_allocations()."""

    def test_filter_by_date_range(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_allocations(
            sample_run_result.allocations,
            start=date(2021, 1, 1),
            end=date(2023, 12, 31),
        )
        assert len(result) == 1
        assert result[0].date == date(2022, 1, 2)

    def test_filter_by_assets(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_allocations(
            sample_run_result.allocations,
            assets={"stocks"},
        )
        assert len(result) == 3
        for pt in result:
            assert set(pt.assets.keys()) == {"stocks"}

    def test_filter_by_date_and_assets(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_allocations(
            sample_run_result.allocations,
            start=date(2022, 1, 1),
            end=date(2025, 12, 31),
            assets={"gold"},
        )
        assert len(result) == 2
        for pt in result:
            assert set(pt.assets.keys()) == {"gold"}


# ── filter_trades ────────────────────────────────────────────────────────────


class TestFilterTrades:
    """Tests for filter_trades()."""

    def test_filter_by_date_range(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_trades(
            sample_run_result.trades,
            start=date(2022, 1, 1),
            end=date(2023, 12, 31),
        )
        assert all(date(2022, 1, 1) <= t.date <= date(2023, 12, 31) for t in result)
        assert len(result) == 2

    def test_filter_by_asset(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_trades(
            sample_run_result.trades,
            assets={"gold"},
        )
        assert all(t.asset_id == "gold" for t in result)
        assert len(result) == 2

    def test_filter_by_date_and_asset(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_trades(
            sample_run_result.trades,
            start=date(2020, 1, 1),
            end=date(2020, 12, 31),
            assets={"stocks"},
        )
        assert len(result) == 1
        assert result[0].asset_id == "stocks"

    def test_no_filter_returns_all(
        self,
        sample_run_result: RunResult,
    ) -> None:
        result = filter_trades(sample_run_result.trades)
        assert len(result) == len(sample_run_result.trades)


# ── trades_to_rows ───────────────────────────────────────────────────────────


class TestTradesToRows:
    """Tests for trades_to_rows()."""

    def test_field_mapping(self) -> None:
        trade = TradeRecord(
            date=date(2020, 1, 2),
            type="pac_execution",
            asset_id="stocks",
            direction="buy",
            amount_eur=350.0,
            quantity=3.5,
            price=100.0,
            fee=1.0,
        )
        rows = trades_to_rows([trade])
        assert len(rows) == 1
        row = rows[0]
        assert row["date"] == "2020-01-02"
        assert row["asset"] == "stocks"
        assert row["direction"] == "buy"
        assert row["amount"] == 350.0
        assert row["quantity"] == 3.5
        assert row["price"] == 100.0
        assert row["fee"] == 1.0

    def test_type_labels(self) -> None:
        pac = TradeRecord(
            date=date(2020, 1, 1),
            type="pac_execution",
            asset_id="a",
            direction="buy",
            amount_eur=100,
            quantity=1,
            price=100,
            fee=0,
        )
        rebal = TradeRecord(
            date=date(2020, 1, 1),
            type="hard_rebalance",
            asset_id="b",
            direction="sell",
            amount_eur=100,
            quantity=1,
            price=100,
            fee=0,
        )
        rows = trades_to_rows([pac, rebal])
        assert rows[0]["type"] == "PAC"
        assert rows[1]["type"] == "Rebalance"

    def test_skipped_flag_formatting(self) -> None:
        trade_ok = TradeRecord(
            date=date(2020, 1, 1),
            type="pac_execution",
            asset_id="a",
            direction="buy",
            amount_eur=100,
            quantity=1,
            price=100,
            fee=0,
            skipped=False,
        )
        trade_skip = TradeRecord(
            date=date(2020, 1, 1),
            type="pac_execution",
            asset_id="a",
            direction="buy",
            amount_eur=100,
            quantity=1,
            price=100,
            fee=0,
            skipped=True,
        )
        rows = trades_to_rows([trade_ok, trade_skip])
        assert rows[0]["skipped"] == "No"
        assert rows[1]["skipped"] == "Yes"


# ── build_metrics_rows ───────────────────────────────────────────────────────


class TestBuildMetricsRows:
    """Tests for build_metrics_rows()."""

    def test_ci_formatting(self) -> None:
        metrics = {
            "strategy": {
                "sharpe": MetricValue(p5=0.5, median=0.8, p95=1.1),
            },
        }
        rows, has_bm = build_metrics_rows(metrics, ["sharpe"])
        assert len(rows) == 1
        assert "0.80" in rows[0]["strategy"]
        assert "0.50" in rows[0]["strategy"]
        assert has_bm is False

    def test_delta_computation(self) -> None:
        metrics = {
            "strategy": {
                "sharpe": MetricValue(p5=0.5, median=0.8, p95=1.1),
            },
            "benchmark": {
                "sharpe": MetricValue(p5=0.6, median=0.6, p95=0.6),
            },
        }
        rows, has_bm = build_metrics_rows(metrics, ["sharpe"])
        assert has_bm is True
        assert "delta" in rows[0]
        assert "+0.20" in rows[0]["delta"]
        assert rows[0]["delta_class"] == "text-positive"

    def test_benchmark_absent_omits_columns(self) -> None:
        metrics = {
            "strategy": {
                "cagr": MetricValue(p5=0.05, median=0.08, p95=0.11),
            },
        }
        rows, has_bm = build_metrics_rows(metrics, ["cagr"])
        assert has_bm is False
        assert "benchmark" not in rows[0]
        assert "delta" not in rows[0]

    def test_pct_metric_formatting(self) -> None:
        metrics = {
            "strategy": {
                "cagr": MetricValue(p5=0.05, median=0.08, p95=0.11),
            },
            "benchmark": {
                "cagr": MetricValue(p5=0.06, median=0.06, p95=0.06),
            },
        }
        rows, _ = build_metrics_rows(metrics, ["cagr"])
        assert "8.0%" in rows[0]["strategy"]
        assert "6.0%" in rows[0]["benchmark"]
        assert "+2.0%" in rows[0]["delta"]

    def test_lower_is_better_metric_negative_delta_is_positive(
        self,
    ) -> None:
        metrics = {
            "strategy": {
                "max_drawdown": MetricValue(
                    p5=-0.15,
                    median=-0.10,
                    p95=-0.05,
                ),
            },
            "benchmark": {
                "max_drawdown": MetricValue(
                    p5=-0.20,
                    median=-0.20,
                    p95=-0.20,
                ),
            },
        }
        rows, _ = build_metrics_rows(metrics, ["max_drawdown"])
        # Strategy drawdown (-10%) is better (less negative) than
        # benchmark (-20%), so delta = +10% but max_drawdown is
        # lower-is-better so positive delta should be "negative"
        assert rows[0]["delta_class"] == "text-negative"
