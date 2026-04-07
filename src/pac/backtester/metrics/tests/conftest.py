from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from pac.backtester.engine.simulator import (
    DayResult,
    IterationResult,
    SimulationResult,
)


def _make_day_results(
    values: list[float],
    start: date = date(2024, 1, 2),
) -> list[DayResult]:
    """Build a list of DayResult from float equity values."""
    results: list[DayResult] = []
    current = start
    for v in values:
        # Skip weekends
        while current.weekday() >= 5:
            current += timedelta(days=1)
        results.append(
            DayResult(
                date=current,
                total_value=Decimal(str(v)),
                allocations={
                    "stocks": Decimal("70"),
                    "gold": Decimal("15"),
                    "bonds": Decimal("15"),
                },
                cash=Decimal("0"),
            ),
        )
        current += timedelta(days=1)
    return results


def _make_iteration(
    values: list[float],
    iteration: int = 0,
    start: date = date(2024, 1, 2),
) -> IterationResult:
    """Build an IterationResult with a controlled equity curve."""
    daily = _make_day_results(values, start=start)
    return IterationResult(
        iteration=iteration,
        daily_values=daily,
        trades=[],
        final_value=daily[-1].total_value if daily else Decimal("0"),
    )


@pytest.fixture
def known_returns() -> pd.Series:
    """Hand-crafted return series with positive drift."""
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    # Alternating small gains/losses with positive drift
    vals = []
    for i in range(60):
        if i % 3 == 0:
            vals.append(0.005)
        elif i % 3 == 1:
            vals.append(-0.002)
        else:
            vals.append(0.003)
    return pd.Series(vals, index=dates)


@pytest.fixture
def flat_returns() -> pd.Series:
    """Constant positive daily return — no downside."""
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    return pd.Series([0.001] * 60, index=dates)


@pytest.fixture
def declining_returns() -> pd.Series:
    """Negative daily returns — persistent decline."""
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    return pd.Series([-0.005] * 60, index=dates)


@pytest.fixture
def mock_iteration_result() -> IterationResult:
    """Single iteration with an upward equity curve."""
    # 100 → 105 → 110 → 108 → 112 → 115
    return _make_iteration([100, 105, 110, 108, 112, 115])


@pytest.fixture
def mock_simulation_result() -> SimulationResult:
    """Multiple iterations with slightly different equity curves."""
    from pac.backtester.config import BacktestConfig

    iterations = [
        _make_iteration([100, 105, 110, 108, 112, 115], iteration=0),
        _make_iteration([100, 103, 107, 105, 110, 113], iteration=1),
        _make_iteration([100, 106, 112, 110, 114, 118], iteration=2),
    ]
    config = BacktestConfig(
        strategy="test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        monte_carlo_iterations=3,
        metrics=["sharpe", "max_drawdown", "cagr"],
        benchmark=True,
    )
    return SimulationResult(config=config, iterations=iterations)
