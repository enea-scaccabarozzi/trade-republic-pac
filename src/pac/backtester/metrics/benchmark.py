from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.config import BacktestConfig
from pac.backtester.data.models import PriceSeries
from pac.backtester.engine.actions import Action
from pac.backtester.engine.simulator import BacktestSimulator, SimulationResult
from pac.backtester.strategies.base import BacktestStrategy
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.registry import SignalRegistry


class _BenchmarkParams(BaseModel):
    """Params for benchmark strategy — intentionally empty."""


class _BenchmarkStrategy(BacktestStrategy[_BenchmarkParams]):
    """Passive buy-and-hold strategy that takes no actions."""

    name = "benchmark"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


def run_benchmark(
    config: BacktestConfig,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    *,
    rng_seed: int | None = None,
) -> SimulationResult:
    """Run a benchmark simulation — PAC-only, no signals, no strategy.

    Uses the existing BacktestSimulator with:
      - A NoopStrategy (returns no actions)
      - An empty SignalRegistry (no rules → no signals)
      - slippage_days=(0, 0) — no human delay in passive investing
      - Same MC iteration count as the strategy run

    This represents the counterfactual: "What if I just did regular PAC
    contributions at my target allocation and never acted on signals?"

    Args:
        config: Original backtest config (start/end dates, PAC settings).
        settings: Application settings (assets, target allocation).
        price_data: Same price data used for strategy simulation.
        rng_seed: Optional seed for reproducibility.

    Returns:
        SimulationResult for the benchmark run.
    """
    bench_config = config.model_copy(
        update={
            "strategy": "benchmark",
            "slippage_days": (0, 0),
        }
    )

    simulator = BacktestSimulator(
        config=bench_config,
        settings=settings,
        price_data=price_data,
        signal_registry=SignalRegistry(),
        strategy=_BenchmarkStrategy(_BenchmarkParams()),
        rng_seed=rng_seed,
    )
    return simulator.run()
