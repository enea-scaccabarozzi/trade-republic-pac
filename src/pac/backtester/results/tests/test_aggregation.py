from __future__ import annotations

import re
from datetime import UTC, date

import pytest

from pac.backtester.metrics.models import BacktestReport
from pac.backtester.results.aggregation import (
    _build_allocations,
    _build_equity_curve,
    _compute_summary,
    _extract_trades,
    _find_median_iteration,
    _map_metrics,
    build_run_result,
)
from pac.backtester.results.tests.conftest import (
    _make_config,
    _make_iteration,
    _make_metric_set,
    _make_pac_trade,
    _make_rebalance_trade,
    _make_taxed_rebalance_trade,
)


class TestFindMedianIteration:
    def test_picks_closest_to_median(self) -> None:
        iterations = [
            _make_iteration([10000, 10500], iteration=0),
            _make_iteration([10000, 11000], iteration=1),
            _make_iteration([10000, 11800], iteration=2),
        ]
        result = _find_median_iteration(iterations)
        assert float(result.final_value) == 11000.0

    def test_single_iteration(self) -> None:
        iterations = [_make_iteration([10000, 10500], iteration=0)]
        result = _find_median_iteration(iterations)
        assert result.iteration == 0

    def test_even_count(self) -> None:
        iterations = [
            _make_iteration([10000, 10000], iteration=0),
            _make_iteration([10000, 11000], iteration=1),
            _make_iteration([10000, 12000], iteration=2),
            _make_iteration([10000, 13000], iteration=3),
        ]
        # median of [10000, 11000, 12000, 13000] = 11500
        # closest is 11000 (dist=500) vs 12000 (dist=500) — first match wins
        result = _find_median_iteration(iterations)
        assert float(result.final_value) == 11000.0

    def test_tied_final_values_returns_first(self) -> None:
        iterations = [
            _make_iteration([10000, 10000], iteration=0),
            _make_iteration([10000, 10000], iteration=1),
            _make_iteration([10000, 10000], iteration=2),
        ]
        result = _find_median_iteration(iterations)
        assert result.iteration == 0


class TestEquityCurve:
    def test_single_iteration_p5_equals_p95(self) -> None:
        iterations = [_make_iteration([10000, 10500, 11000], iteration=0)]
        curve = _build_equity_curve(iterations)
        for point in curve:
            assert point.p5 == point.median == point.p95

    def test_three_iterations_has_spread(self) -> None:
        iterations = [
            _make_iteration([10000, 10500], iteration=0),
            _make_iteration([10000, 11000], iteration=1),
            _make_iteration([10000, 11800], iteration=2),
        ]
        curve = _build_equity_curve(iterations)
        last = curve[-1]
        assert last.p5 <= last.median <= last.p95

    def test_length_matches_trading_days(self) -> None:
        values = [10000, 10100, 10200, 10300, 10400]
        iterations = [_make_iteration(values, iteration=0)]
        curve = _build_equity_curve(iterations)
        assert len(curve) == len(iterations[0].daily_values)


class TestAllocations:
    def test_includes_all_assets_and_cash(self) -> None:
        iterations = [
            _make_iteration([10000, 10500], iteration=0),
        ]
        allocs = _build_allocations(iterations)
        for point in allocs:
            assert "stocks" in point.assets
            assert "gold" in point.assets
            assert "bonds" in point.assets
            assert "cash" in point.assets

    def test_single_iteration_p5_equals_p95(self) -> None:
        iterations = [_make_iteration([10000, 10500], iteration=0)]
        allocs = _build_allocations(iterations)
        for point in allocs:
            for ci in point.assets.values():
                assert ci.p5 == ci.median == ci.p95

    def test_percentages_reasonable(self) -> None:
        iterations = [
            _make_iteration([10000, 10500], iteration=0),
            _make_iteration([10000, 11000], iteration=1),
        ]
        allocs = _build_allocations(iterations)
        for point in allocs:
            for ci in point.assets.values():
                assert 0 <= ci.p5 <= 100
                assert 0 <= ci.median <= 100
                assert 0 <= ci.p95 <= 100


class TestExtractTrades:
    def test_converts_decimal_to_float(self) -> None:
        trades = [
            _make_pac_trade(date(2024, 1, 2), "stocks", 175.0),
        ]
        iteration = _make_iteration(
            [10000, 10500],
            iteration=0,
            trades=trades,
        )
        records = _extract_trades(iteration)
        for r in records:
            assert isinstance(r.amount_eur, float)
            assert isinstance(r.quantity, float)
            assert isinstance(r.price, float)
            assert isinstance(r.fee, float)

    def test_preserves_count(self) -> None:
        trades = [
            _make_pac_trade(date(2024, 1, 2), "stocks"),
            _make_rebalance_trade(date(2024, 1, 5), "bonds"),
        ]
        iteration = _make_iteration(
            [10000, 10500],
            iteration=0,
            trades=trades,
        )
        records = _extract_trades(iteration)
        assert len(records) == len(trades)


class TestComputeSummary:
    def test_total_invested_correct(self) -> None:
        # 4 PAC executions x 250 per PAC + 10000 initial = 11000
        pac_trades = [
            _make_pac_trade(date(2024, 1, 2)),
            _make_pac_trade(date(2024, 1, 2)),
            _make_pac_trade(date(2024, 1, 16)),
            _make_pac_trade(date(2024, 1, 16)),
        ]
        config = _make_config()
        iterations = [
            _make_iteration(
                [10000, 11000],
                iteration=0,
                trades=pac_trades,
            ),
        ]
        median_iter = iterations[0]
        summary = _compute_summary(iterations, median_iter, config)
        # contribution_per_pac = 500/2 = 250, 4 PAC trades x 250 = 1000
        assert summary.total_invested == 11000.0

    def test_total_invested_partial_month(self) -> None:
        # Only 2 PAC trades (one PAC date in a partial month)
        pac_trades = [
            _make_pac_trade(date(2024, 1, 16)),
            _make_pac_trade(date(2024, 1, 16)),
        ]
        config = _make_config()
        iterations = [
            _make_iteration(
                [10000, 10500],
                iteration=0,
                trades=pac_trades,
            ),
        ]
        summary = _compute_summary(iterations, iterations[0], config)
        # 2 PAC trades x 250 + 10000 = 10500
        assert summary.total_invested == 10500.0

    def test_final_value_matches_equity_curve_last(
        self,
        three_iteration_report: BacktestReport,
    ) -> None:
        iterations = three_iteration_report.strategy_iterations
        median_iter = _find_median_iteration(iterations)
        curve = _build_equity_curve(iterations)
        summary = _compute_summary(
            iterations,
            median_iter,
            three_iteration_report.config,
        )
        assert abs(summary.final_value.median - curve[-1].median) < 0.01

    def test_fees_non_negative(
        self,
        three_iteration_report: BacktestReport,
    ) -> None:
        iterations = three_iteration_report.strategy_iterations
        median_iter = _find_median_iteration(iterations)
        summary = _compute_summary(
            iterations,
            median_iter,
            three_iteration_report.config,
        )
        assert summary.total_fees.p5 >= 0
        assert summary.total_fees.median >= 0
        assert summary.total_fees.p95 >= 0

    def test_total_tax_is_none_when_no_tax(self) -> None:
        # Trades with zero tax — summary.total_tax must be None
        config = _make_config()
        iterations = [
            _make_iteration(
                [10000, 11000],
                iteration=0,
                trades=[_make_pac_trade(date(2024, 1, 2))],
            ),
        ]
        summary = _compute_summary(iterations, iterations[0], config)
        assert summary.total_tax is None

    def test_total_tax_ci_when_trades_have_tax(self) -> None:
        # One iteration with 10.0 tax — CI should report that value
        config = _make_config()
        taxed = _make_taxed_rebalance_trade(date(2024, 1, 5), tax=10.0)
        iterations = [
            _make_iteration(
                [10000, 11000],
                iteration=0,
                trades=[taxed],
            ),
        ]
        summary = _compute_summary(iterations, iterations[0], config)
        assert summary.total_tax is not None
        assert summary.total_tax.median == pytest.approx(10.0)


class TestMapMetrics:
    def test_strategy_has_ci(self) -> None:
        strategy = _make_metric_set("strategy")
        result = _map_metrics(strategy, None)
        for mv in result["strategy"].values():
            assert hasattr(mv, "p5")
            assert hasattr(mv, "median")
            assert hasattr(mv, "p95")

    def test_benchmark_uniform_shape(self) -> None:
        strategy = _make_metric_set("strategy")
        benchmark = _make_metric_set("benchmark")
        result = _map_metrics(strategy, benchmark)
        for mv in result["benchmark"].values():
            assert mv.p5 == mv.median == mv.p95

    def test_benchmark_absent_when_disabled(self) -> None:
        strategy = _make_metric_set("strategy")
        result = _map_metrics(strategy, None)
        assert "benchmark" not in result


class TestBuildRunResult:
    def test_run_id_format(
        self,
        three_iteration_report: BacktestReport,
    ) -> None:
        result = build_run_result(three_iteration_report)
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_\w+",
            result.run_id,
        )

    def test_created_at_is_utc(
        self,
        three_iteration_report: BacktestReport,
    ) -> None:
        result = build_run_result(three_iteration_report)
        assert result.created_at.tzinfo is not None
        assert result.created_at.tzinfo == UTC

    def test_end_to_end(
        self,
        three_iteration_report: BacktestReport,
    ) -> None:
        result = build_run_result(three_iteration_report)
        assert result.run_id
        assert result.created_at
        assert result.config == three_iteration_report.config
        assert len(result.equity_curve) > 0
        assert len(result.allocations) > 0
        assert "strategy" in result.metrics
        assert result.summary.total_invested > 0

    def test_empty_iterations_raises(self) -> None:
        config = _make_config()
        report = BacktestReport(
            strategy=_make_metric_set("strategy"),
            benchmark=None,
            config=config,
            strategy_iterations=[],
            benchmark_iterations=None,
        )
        with pytest.raises(ValueError, match="empty iterations"):
            build_run_result(report)
