from __future__ import annotations

import math

import pandas as pd
import pytest
import quantstats as qs

from pac.backtester.metrics.calculator import MetricsCalculator
from pac.backtester.metrics.tests.conftest import _make_iteration


class TestMetricsCalculatorInit:
    def test_unknown_metric_raises(self) -> None:
        with pytest.raises(ValueError, match=r"Unknown metrics.*bogus"):
            MetricsCalculator(["bogus"])

    def test_valid_metrics_accepted(self) -> None:
        calc = MetricsCalculator(["sharpe", "max_drawdown", "cagr"])
        assert calc._metric_names == ["sharpe", "max_drawdown", "cagr"]


class TestComputeIteration:
    def test_compute_iteration_returns_all_metrics(
        self,
        known_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["sharpe", "max_drawdown", "cagr"])
        result = calc.compute_iteration(known_returns)

        assert set(result) == {"sharpe", "max_drawdown", "cagr"}

    def test_sharpe_positive_for_positive_returns(
        self,
        known_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["sharpe"])
        result = calc.compute_iteration(known_returns)

        assert result["sharpe"] > 0

    def test_max_drawdown_negative(
        self,
        known_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["max_drawdown"])
        result = calc.compute_iteration(known_returns)

        assert result["max_drawdown"] <= 0

    def test_cagr_positive_for_uptrending_series(
        self,
        known_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["cagr"])
        result = calc.compute_iteration(known_returns)

        assert result["cagr"] > 0

    def test_sortino_high_for_no_downside(
        self,
        flat_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["sortino"])
        result = calc.compute_iteration(flat_returns)

        # Sortino should be very high (or NaN/inf) with no downside deviation
        assert result["sortino"] > 10 or math.isnan(result["sortino"])

    def test_wrapper_matches_quantstats_directly(
        self,
        known_returns: pd.Series,
    ) -> None:
        calc = MetricsCalculator(["sharpe"])
        result = calc.compute_iteration(known_returns)

        expected = float(qs.stats.sharpe(known_returns, periods=252))
        assert result["sharpe"] == pytest.approx(expected)


class TestComputeAll:
    def test_compute_all_aggregates_correctly(self) -> None:
        iterations = [
            _make_iteration([100, 105, 110, 115, 120], iteration=0),
            _make_iteration([100, 103, 107, 110, 113], iteration=1),
            _make_iteration([100, 106, 112, 118, 124], iteration=2),
        ]
        calc = MetricsCalculator(["sharpe", "max_drawdown"])
        metric_set = calc.compute_all(iterations, scenario="test")

        assert metric_set.scenario == "test"
        assert "sharpe" in metric_set.metrics
        assert "max_drawdown" in metric_set.metrics

        sharpe = metric_set.metrics["sharpe"]
        assert len(sharpe.per_iteration) == 3
        assert sharpe.p5 <= sharpe.median <= sharpe.p95

    def test_single_iteration_aggregation(self) -> None:
        iterations = [
            _make_iteration([100, 105, 110, 115, 120], iteration=0),
        ]
        calc = MetricsCalculator(["sharpe"])
        metric_set = calc.compute_all(iterations, scenario="single")

        sharpe = metric_set.metrics["sharpe"]
        assert sharpe.median == pytest.approx(sharpe.p5)
        assert sharpe.median == pytest.approx(sharpe.p95)
        assert len(sharpe.per_iteration) == 1

    def test_nan_handling(self) -> None:
        # Create iterations where one produces NaN-like results
        # (constant equity → zero returns → NaN sharpe)
        iterations = [
            _make_iteration([100, 100, 100, 100, 100], iteration=0),
            _make_iteration([100, 105, 110, 115, 120], iteration=1),
        ]
        calc = MetricsCalculator(["sharpe"])
        metric_set = calc.compute_all(iterations, scenario="nan_test")

        sharpe = metric_set.metrics["sharpe"]
        # Should produce a valid result (not crash)
        assert len(sharpe.per_iteration) == 2

    def test_compute_all_empty_iterations_raises(self) -> None:
        calc = MetricsCalculator(["sharpe"])
        with pytest.raises(ValueError, match="iterations must be non-empty"):
            calc.compute_all([], scenario="x")
