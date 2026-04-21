from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

import pytest

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.actions import ExecutedTrade
from pac.backtester.engine.simulator import DayResult, IterationResult
from pac.backtester.metrics.models import (
    BacktestReport,
    MetricResult,
    MetricSet,
)


def _make_day_results(
    values: Sequence[float],
    start: date = date(2024, 1, 2),
    allocations: dict[str, Decimal] | None = None,
    cash: Decimal = Decimal("0"),
) -> list[DayResult]:
    """Build a list of DayResult from float equity values."""
    if allocations is None:
        allocations = {
            "stocks": Decimal("70"),
            "gold": Decimal("15"),
            "bonds": Decimal("15"),
        }
    results: list[DayResult] = []
    current = start
    for v in values:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        results.append(
            DayResult(
                date=current,
                total_value=Decimal(str(v)),
                allocations=allocations,
                cash=cash,
            ),
        )
        current += timedelta(days=1)
    return results


def _make_iteration(
    values: Sequence[float],
    iteration: int = 0,
    start: date = date(2024, 1, 2),
    trades: list[ExecutedTrade] | None = None,
    allocations: dict[str, Decimal] | None = None,
    cash: Decimal = Decimal("0"),
) -> IterationResult:
    """Build an IterationResult with a controlled equity curve."""
    daily = _make_day_results(
        values,
        start=start,
        allocations=allocations,
        cash=cash,
    )
    return IterationResult(
        iteration=iteration,
        daily_values=daily,
        trades=trades or [],
        final_value=daily[-1].total_value if daily else Decimal("0"),
    )


def _make_pac_trade(
    d: date,
    asset_id: str = "stocks",
    amount: float = 250.0,
    price: float = 100.0,
) -> ExecutedTrade:
    """Build a PAC execution trade."""
    qty = amount / price
    return ExecutedTrade(
        date=d,
        type="pac_execution",
        asset_id=asset_id,
        direction="buy",
        amount_eur=Decimal(str(amount)),
        quantity=Decimal(str(qty)),
        price=Decimal(str(price)),
        fee=Decimal("0"),
    )


def _make_taxed_rebalance_trade(
    d: date,
    asset_id: str = "bonds",
    direction: Literal["buy", "sell"] = "sell",
    amount: float = 100.0,
    price: float = 50.0,
    tax: float = 10.0,
) -> ExecutedTrade:
    """Build a hard rebalance trade with non-zero tax (e.g., a taxed sell)."""
    qty = amount / price
    return ExecutedTrade(
        date=d,
        type="hard_rebalance",
        asset_id=asset_id,
        direction=direction,
        amount_eur=Decimal(str(amount)),
        quantity=Decimal(str(qty)),
        price=Decimal(str(price)),
        fee=Decimal("1.00"),
        tax=Decimal(str(tax)),
        skipped=False,
    )


def _make_rebalance_trade(
    d: date,
    asset_id: str = "bonds",
    direction: Literal["buy", "sell"] = "buy",
    amount: float = 100.0,
    price: float = 50.0,
    skipped: bool = False,
) -> ExecutedTrade:
    """Build a hard rebalance trade."""
    qty = amount / price if not skipped else 0.0
    return ExecutedTrade(
        date=d,
        type="hard_rebalance",
        asset_id=asset_id,
        direction=direction,
        amount_eur=Decimal(str(amount)) if not skipped else Decimal("0"),
        quantity=Decimal(str(qty)),
        price=Decimal(str(price)),
        fee=Decimal("1.00"),
        skipped=skipped,
    )


def _make_config(**overrides: object) -> BacktestConfig:
    """Build a BacktestConfig with test defaults."""
    defaults: dict[str, object] = {
        "strategy": "test_strategy",
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 3, 31),
        "initial_cash": Decimal("10000"),
        "monthly_contribution": Decimal("500"),
        "pac_execution_days": [2, 16],
        "monte_carlo_iterations": 3,
        "metrics": ["sharpe", "max_drawdown", "cagr"],
        "benchmark": True,
        "slippage_days": (0, 3),
    }
    defaults.update(overrides)
    return BacktestConfig.model_validate(defaults)


def _make_metric_set(
    scenario: str = "strategy",
    metric_names: list[str] | None = None,
) -> MetricSet:
    """Build a MetricSet with dummy metric values."""
    if metric_names is None:
        metric_names = ["sharpe", "max_drawdown", "cagr"]
    metrics: dict[str, MetricResult] = {}
    for name in metric_names:
        metrics[name] = MetricResult(
            name=name,
            median=0.5,
            p5=0.3,
            p95=0.7,
            per_iteration=[0.3, 0.5, 0.7],
        )
    return MetricSet(scenario=scenario, metrics=metrics)


@pytest.fixture
def config() -> BacktestConfig:
    return _make_config()


@pytest.fixture
def three_iteration_report() -> BacktestReport:
    """BacktestReport with 3 MC iterations with divergent final values.

    Iteration 0: final_value = 10500 (low)
    Iteration 1: final_value = 11000 (median)
    Iteration 2: final_value = 11800 (high)
    """
    pac_trades = [
        _make_pac_trade(date(2024, 1, 2), "stocks", 175.0),
        _make_pac_trade(date(2024, 1, 2), "gold", 37.5),
        _make_pac_trade(date(2024, 1, 2), "bonds", 37.5),
        _make_pac_trade(date(2024, 1, 16), "stocks", 175.0),
        _make_pac_trade(date(2024, 1, 16), "gold", 37.5),
        _make_pac_trade(date(2024, 1, 16), "bonds", 37.5),
        _make_pac_trade(date(2024, 2, 2), "stocks", 175.0),
        _make_pac_trade(date(2024, 2, 2), "gold", 37.5),
        _make_pac_trade(date(2024, 2, 2), "bonds", 37.5),
        _make_pac_trade(date(2024, 2, 16), "stocks", 175.0),
        _make_pac_trade(date(2024, 2, 16), "gold", 37.5),
        _make_pac_trade(date(2024, 2, 16), "bonds", 37.5),
    ]
    rebalance_trade = _make_rebalance_trade(
        date(2024, 2, 5),
        "bonds",
        "buy",
        100.0,
    )

    trades_iter0 = [*list(pac_trades), rebalance_trade]
    trades_iter1 = [*list(pac_trades), rebalance_trade]
    trades_iter2 = [
        *list(pac_trades),
        rebalance_trade,
        _make_rebalance_trade(date(2024, 2, 20), "gold", "sell", 50.0),
    ]

    values_low = [10000, 10100, 10200, 10300, 10400, 10500]
    values_mid = [10000, 10200, 10500, 10700, 10900, 11000]
    values_high = [10000, 10300, 10700, 11000, 11400, 11800]

    iterations = [
        _make_iteration(values_low, iteration=0, trades=trades_iter0),
        _make_iteration(values_mid, iteration=1, trades=trades_iter1),
        _make_iteration(values_high, iteration=2, trades=trades_iter2),
    ]

    config = _make_config(monte_carlo_iterations=3)
    return BacktestReport(
        strategy=_make_metric_set("strategy"),
        benchmark=_make_metric_set("benchmark"),
        config=config,
        strategy_iterations=iterations,
        benchmark_iterations=None,
    )


@pytest.fixture
def single_iteration_report() -> BacktestReport:
    """BacktestReport with 1 MC iteration. P5=median=P95."""
    pac_trades = [
        _make_pac_trade(date(2024, 1, 2), "stocks", 175.0),
        _make_pac_trade(date(2024, 1, 2), "gold", 37.5),
        _make_pac_trade(date(2024, 1, 2), "bonds", 37.5),
    ]
    values = [10000, 10100, 10200, 10300, 10400, 10500]
    iterations = [
        _make_iteration(values, iteration=0, trades=pac_trades),
    ]
    config = _make_config(monte_carlo_iterations=1)
    return BacktestReport(
        strategy=_make_metric_set("strategy"),
        benchmark=None,
        config=config,
        strategy_iterations=iterations,
        benchmark_iterations=None,
    )


@pytest.fixture
def report_with_benchmark() -> BacktestReport:
    """BacktestReport with both strategy and benchmark MetricSets."""
    values = [10000, 10200, 10500, 10700, 10900, 11000]
    iterations = [_make_iteration(values, iteration=0)]
    config = _make_config(monte_carlo_iterations=1, benchmark=True)
    return BacktestReport(
        strategy=_make_metric_set("strategy"),
        benchmark=_make_metric_set("benchmark"),
        config=config,
        strategy_iterations=iterations,
        benchmark_iterations=None,
    )


@pytest.fixture
def report_without_benchmark() -> BacktestReport:
    """BacktestReport with benchmark=None."""
    values = [10000, 10200, 10500, 10700, 10900, 11000]
    iterations = [_make_iteration(values, iteration=0)]
    config = _make_config(monte_carlo_iterations=1, benchmark=False)
    return BacktestReport(
        strategy=_make_metric_set("strategy"),
        benchmark=None,
        config=config,
        strategy_iterations=iterations,
        benchmark_iterations=None,
    )
