from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import BacktestSimulator, SimulationResult
from pac.backtester.engine.tests.conftest import (
    NoopStrategy,
    _NoopParams,
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.metrics.models import BacktestReport, MetricSet
from pac.backtester.metrics.report import compute_report
from pac.rules.registry import SignalRegistry


def _run_strategy(*, benchmark: bool = True) -> tuple[SimulationResult, dict[str, Any]]:
    """Run a noop strategy simulation and return result + context."""
    settings = make_settings()
    price_data = make_three_asset_price_data(date(2024, 1, 1), 90)

    config = BacktestConfig(
        strategy="noop",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        pac_execution_days=[2, 16],
        monte_carlo_iterations=2,
        slippage_days=(0, 0),
        metrics=["sharpe", "max_drawdown", "cagr"],
        benchmark=benchmark,
    )

    simulator = BacktestSimulator(
        config=config,
        settings=settings,
        price_data=price_data,
        signal_registry=SignalRegistry(),
        strategy=NoopStrategy(_NoopParams()),
        rng_seed=42,
    )
    result = simulator.run()
    return result, {"settings": settings, "price_data": price_data}


class TestComputeReport:
    def test_report_has_strategy_metrics(self) -> None:
        result, ctx = _run_strategy()
        report = compute_report(
            result,
            ctx["settings"],
            ctx["price_data"],
            rng_seed=42,
        )

        assert isinstance(report, BacktestReport)
        assert isinstance(report.strategy, MetricSet)
        assert report.strategy.scenario == "strategy"
        assert set(report.strategy.metrics) == {"sharpe", "max_drawdown", "cagr"}

    def test_report_with_benchmark(self) -> None:
        result, ctx = _run_strategy(benchmark=True)
        report = compute_report(
            result,
            ctx["settings"],
            ctx["price_data"],
            rng_seed=42,
        )

        assert report.benchmark is not None
        assert isinstance(report.benchmark, MetricSet)
        assert report.benchmark.scenario == "benchmark"
        assert set(report.benchmark.metrics) == set(report.strategy.metrics)

    def test_report_without_benchmark(self) -> None:
        result, ctx = _run_strategy(benchmark=False)
        report = compute_report(
            result,
            ctx["settings"],
            ctx["price_data"],
            rng_seed=42,
        )

        assert report.benchmark is None
        assert report.benchmark_iterations is None

    def test_report_preserves_iteration_data(self) -> None:
        result, ctx = _run_strategy()
        report = compute_report(
            result,
            ctx["settings"],
            ctx["price_data"],
            rng_seed=42,
        )

        assert len(report.strategy_iterations) == 2
        assert report.strategy_iterations == result.iterations
        assert report.config == result.config
