from __future__ import annotations

from pac.backtester.data.models import PriceSeries
from pac.backtester.engine.simulator import SimulationResult
from pac.backtester.metrics.benchmark import run_benchmark
from pac.backtester.metrics.calculator import MetricsCalculator
from pac.backtester.metrics.models import BacktestReport
from pac.config import Settings


def compute_report(
    strategy_result: SimulationResult,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    *,
    rng_seed: int | None = None,
) -> BacktestReport:
    """Compute a full backtest report from simulation results.

    Steps:
      1. Compute strategy metrics (per-iteration → aggregate)
      2. If config.benchmark is True: run benchmark simulation
      3. Compute benchmark metrics (per-iteration → aggregate)
      4. Build BacktestReport

    Args:
        strategy_result: Completed strategy simulation.
        settings: Application settings (for benchmark simulation).
        price_data: Market data (for benchmark simulation).
        rng_seed: Optional seed for benchmark reproducibility.

    Returns:
        BacktestReport with strategy metrics, benchmark metrics (if enabled),
        and full iteration data for downstream consumption.
    """
    config = strategy_result.config
    calculator = MetricsCalculator(config.metrics)

    strategy_metrics = calculator.compute_all(
        strategy_result.iterations,
        scenario="strategy",
    )

    benchmark_metrics = None
    benchmark_iterations = None

    if config.benchmark:
        benchmark_result = run_benchmark(
            config,
            settings,
            price_data,
            rng_seed=rng_seed,
        )
        benchmark_metrics = calculator.compute_all(
            benchmark_result.iterations,
            scenario="benchmark",
        )
        benchmark_iterations = benchmark_result.iterations

    return BacktestReport(
        strategy=strategy_metrics,
        benchmark=benchmark_metrics,
        config=config,
        strategy_iterations=strategy_result.iterations,
        benchmark_iterations=benchmark_iterations,
    )
