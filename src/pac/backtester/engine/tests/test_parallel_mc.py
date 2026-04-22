from __future__ import annotations

from datetime import date

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import (
    BacktestSimulator,
    run_iterations_parallel,
)
from pac.backtester.engine.tests.conftest import (
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.strategies.builtin.pac_alignment import (
    PacAlignmentParams,
    PacAlignmentStrategy,
)
from pac.rules.registry import SignalRegistry


def test_parallel_mc_matches_sequential() -> None:
    """Parallel MC must produce identical results to sequential with same seeds."""
    settings = make_settings()
    price_data = make_three_asset_price_data(date(2024, 1, 1), 60)
    config = BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        monte_carlo_iterations=4,
    )
    registry = SignalRegistry()
    strategy = PacAlignmentStrategy(PacAlignmentParams())

    # Sequential: each iteration gets rng_seed = base_seed + iteration
    seq_results = []
    for i in range(4):
        sim = BacktestSimulator(
            config,
            settings,
            price_data,
            registry,
            strategy,
            rng_seed=42 + i,
        )
        seq_results.append(sim.run_iteration(i))

    # Parallel — worker processes rebuild registry/strategy via discover_strategies()
    par_results = run_iterations_parallel(
        config,
        settings,
        price_data,
        registry,
        strategy,
        seed=42,
        max_workers=2,
    )

    # Final values must match (order by iteration index)
    seq_sorted = sorted(seq_results, key=lambda r: r.iteration)
    par_sorted = sorted(par_results, key=lambda r: r.iteration)
    for s, p in zip(seq_sorted, par_sorted, strict=True):
        assert s.final_value == p.final_value
        assert s.iteration == p.iteration
