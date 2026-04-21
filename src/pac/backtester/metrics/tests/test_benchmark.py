from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import SimulationResult
from pac.backtester.engine.tests.conftest import (
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.metrics.benchmark import run_benchmark


@pytest.fixture
def benchmark_config() -> BacktestConfig:
    return BacktestConfig(
        strategy="test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        pac_execution_days=[2, 16],
        monte_carlo_iterations=3,
        slippage_days=(1, 3),
    )


class TestRunBenchmark:
    def test_benchmark_produces_simulation_result(
        self,
        benchmark_config: BacktestConfig,
    ) -> None:
        settings = make_settings()
        price_data = make_three_asset_price_data(date(2024, 1, 1), 90)

        result = run_benchmark(
            benchmark_config,
            settings,
            price_data,
            rng_seed=42,
        )

        assert isinstance(result, SimulationResult)
        assert len(result.iterations) == 3

    def test_benchmark_has_no_rebalance_trades(
        self,
        benchmark_config: BacktestConfig,
    ) -> None:
        settings = make_settings()
        price_data = make_three_asset_price_data(date(2024, 1, 1), 90)

        result = run_benchmark(
            benchmark_config,
            settings,
            price_data,
            rng_seed=42,
        )

        for iteration in result.iterations:
            for trade in iteration.trades:
                assert trade.type == "pac_execution", (
                    f"Benchmark should only have PAC trades, got {trade.type}"
                )

    def test_benchmark_is_deterministic(
        self,
        benchmark_config: BacktestConfig,
    ) -> None:
        settings = make_settings()
        price_data = make_three_asset_price_data(date(2024, 1, 1), 90)

        result1 = run_benchmark(benchmark_config, settings, price_data, rng_seed=42)
        result2 = run_benchmark(benchmark_config, settings, price_data, rng_seed=42)

        for it1, it2 in zip(result1.iterations, result2.iterations, strict=False):
            assert it1.final_value == it2.final_value

    def test_benchmark_all_iterations_have_positive_growth(
        self,
        benchmark_config: BacktestConfig,
    ) -> None:
        settings = make_settings()
        price_data = make_three_asset_price_data(date(2024, 1, 1), 90)

        result = run_benchmark(
            benchmark_config,
            settings,
            price_data,
            rng_seed=42,
        )

        # All iterations should produce positive final values above initial cash.
        # Intraday random PAC pricing means iterations are no longer identical
        # even with slippage=(0,0); determinism across runs is verified separately.
        initial_cash = benchmark_config.initial_cash
        for iteration in result.iterations:
            assert iteration.final_value > initial_cash
