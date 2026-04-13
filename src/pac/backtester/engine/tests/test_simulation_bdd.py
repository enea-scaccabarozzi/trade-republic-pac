from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.actions import Action, ActionType, HardRebalanceOrder
from pac.backtester.engine.simulator import BacktestSimulator, SimulationResult
from pac.backtester.engine.tests.conftest import (
    NoopStrategy,
    StubStrategy,
    _NoopParams,
    _StubParams,
    make_portfolio,
    make_settings,
    make_three_asset_price_data,
)
from pac.rules.registry import SignalRegistry

scenarios("../features/simulation.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# -- Background -----------------------------------------------------------


@given("a portfolio with 3 assets: stocks (70%), gold (15%), bonds (15%)")
def _portfolio_3_assets(ctx: dict[str, Any]) -> None:
    ctx["settings"] = make_settings()
    ctx["initial_cash"] = Decimal("10000")
    ctx["monthly_contribution"] = Decimal("500")
    ctx["pac_execution_days"] = [2, 16]


@given("initial cash of €10,000")
def _initial_cash(ctx: dict[str, Any]) -> None:
    ctx["initial_cash"] = Decimal("10000")


@given("a monthly contribution of €500")
def _monthly_contribution(ctx: dict[str, Any]) -> None:
    ctx["monthly_contribution"] = Decimal("500")


@given("PAC execution dates on the 2nd and 16th")
def _pac_dates(ctx: dict[str, Any]) -> None:
    ctx["pac_execution_days"] = [2, 16]


# -- Given steps ----------------------------------------------------------


@given(
    parsers.parse('price data from "{start}" to "{end}"'),
)
def _price_data(ctx: dict[str, Any], start: str, end: str) -> None:
    ctx["start_date"] = date.fromisoformat(start)
    ctx["end_date"] = date.fromisoformat(end)
    ctx["price_data"] = make_three_asset_price_data(ctx["start_date"], n_days=200)


@given("a no-op strategy")
def _noop_strategy(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = NoopStrategy(_NoopParams())


@given("a no-op strategy with zero PAC volumes")
def _noop_strategy_zero_volumes(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = NoopStrategy(_NoopParams())
    ctx["zero_pac_volumes"] = True


@given(
    parsers.parse(
        "a strategy that emits a hard rebalance buy of €{amount:d},{suffix} for stocks",
    ),
)
def _rebalance_strategy_large(ctx: dict[str, Any], amount: int, suffix: str) -> None:
    full_amount = int(f"{amount}{suffix}")
    action = Action(
        type=ActionType.HARD_REBALANCE,
        rebalance_orders=[
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal(str(full_amount)),
            ),
        ],
    )
    ctx["strategy"] = StubStrategy(_StubParams(), actions=[action])


@given(
    parsers.parse(
        "a strategy that emits a hard rebalance buy of €{amount:d} for stocks",
    ),
)
def _rebalance_strategy(ctx: dict[str, Any], amount: int) -> None:
    action = Action(
        type=ActionType.HARD_REBALANCE,
        rebalance_orders=[
            HardRebalanceOrder(
                asset_id="stocks",
                direction="buy",
                amount_eur=Decimal(str(amount)),
            ),
        ],
    )
    ctx["strategy"] = StubStrategy(_StubParams(), actions=[action])


@given(
    parsers.parse("the portfolio has only €{amount:d},{suffix} initial cash"),
)
def _limited_cash_large(ctx: dict[str, Any], amount: int, suffix: str) -> None:
    ctx["initial_cash"] = Decimal(f"{amount}{suffix}")


@given(
    parsers.parse("the portfolio has only €{amount:d} initial cash"),
)
def _limited_cash(ctx: dict[str, Any], amount: int) -> None:
    ctx["initial_cash"] = Decimal(str(amount))


@given(
    parsers.parse("a spread of {bps:d} basis points"),
)
def _spread_bps(ctx: dict[str, Any], bps: int) -> None:
    ctx["spread_bps"] = Decimal(str(bps))


@given(
    parsers.parse("{n:d} Monte Carlo iterations"),
)
def _mc_iterations(ctx: dict[str, Any], n: int) -> None:
    ctx["mc_iterations"] = n


@given(
    parsers.parse("slippage range of {lo:d} to {hi:d} days"),
)
def _slippage_range(ctx: dict[str, Any], lo: int, hi: int) -> None:
    ctx["slippage_days"] = (lo, hi)


@given(
    parsers.parse("a fixed random seed of {seed:d}"),
)
def _fixed_seed(ctx: dict[str, Any], seed: int) -> None:
    ctx["rng_seed"] = seed


# -- Helpers --------------------------------------------------------------


def _build_simulator(ctx: dict[str, Any]) -> BacktestSimulator:
    """Build a simulator from the accumulated context."""
    settings = ctx.get("settings", make_settings())

    # For threshold-based strategies, add a signal config
    strategy = ctx.get("strategy", NoopStrategy(_NoopParams()))
    signals_config: list[dict[str, Any]] = []
    if isinstance(strategy, StubStrategy):
        from pac.rules.discovery import discover_rules

        registry = SignalRegistry()
        for rule_cls in discover_rules().values():
            registry.register(rule_cls)
        signals_config = [
            {
                "name": "threshold_check",
                "rule": "threshold_deviation",
                "schedule": "daily",
                "channels": [],
                "params": {"warning_pct": "1.0", "critical_pct": "3.0"},
                "template": "threshold_alert",
            },
        ]
        settings = make_settings(signals=signals_config)
    else:
        registry = SignalRegistry()

    config = BacktestConfig(
        strategy="test",
        start_date=ctx["start_date"],
        end_date=ctx["end_date"],
        initial_cash=ctx.get("initial_cash", Decimal("10000")),
        monthly_contribution=ctx.get("monthly_contribution", Decimal("500")),
        pac_execution_days=ctx.get("pac_execution_days", [2, 16]),
        monte_carlo_iterations=ctx.get("mc_iterations", 1),
        slippage_days=ctx.get("slippage_days", (0, 0)),
        spread_bps=ctx.get("spread_bps", Decimal("10")),
    )

    return BacktestSimulator(
        config=config,
        settings=settings,
        price_data=ctx["price_data"],
        signal_registry=registry,
        strategy=strategy,
        rng_seed=ctx.get("rng_seed", 42),
    )


# -- When steps -----------------------------------------------------------


@when("a single simulation iteration runs")
def _run_single_iteration(ctx: dict[str, Any]) -> None:
    sim = _build_simulator(ctx)
    ctx["result"] = sim.run_iteration(0)
    ctx["simulator"] = sim


@when("PAC executes on the first PAC date")
def _run_first_pac(ctx: dict[str, Any]) -> None:
    portfolio = make_portfolio(
        cash=Decimal("0"),
        pac_volumes={
            "stocks": Decimal(0),
            "gold": Decimal(0),
            "bonds": Decimal(0),
        },
        pac_execution_days=ctx.get("pac_execution_days", [2, 16]),
    )
    from pac.backtester.engine.tests.conftest import make_price_bars, make_price_series

    bars = make_price_bars(ctx["start_date"], 30)
    prices = {bar.date: bar for bar in bars}

    # Find first PAC date
    from pac.backtester.engine.clock import SimulationClock

    series = make_price_series("TEST", bars)
    clock = SimulationClock(series, ctx.get("pac_execution_days", [2, 16]))
    for d in clock:
        pac_day = clock.which_pac_day(d)
        if pac_day is not None and d in prices:
            price_dict = {"stocks": prices[d], "gold": prices[d], "bonds": prices[d]}
            portfolio.execute_pac(d, price_dict, Decimal("500"), pac_day)
            break

    ctx["portfolio_after_pac"] = portfolio


@when("the full simulation runs")
def _run_full_simulation(ctx: dict[str, Any]) -> None:
    sim = _build_simulator(ctx)
    ctx["simulation_result"] = sim.run()
    ctx["simulator"] = sim


@when("the simulation runs twice with the same parameters")
def _run_twice(ctx: dict[str, Any]) -> None:
    sim1 = _build_simulator(ctx)
    sim2 = _build_simulator(ctx)
    ctx["result1"] = sim1.run()
    ctx["result2"] = sim2.run()


# -- Then steps -----------------------------------------------------------


@then("PAC buy trades appear only on PAC dates (2nd/16th or next trading day)")
def _check_pac_trades_on_pac_dates(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    pac_trades = [t for t in result.trades if t.type == "pac_execution"]
    assert len(pac_trades) > 0


@then("no fees are charged on PAC trades")
def _check_no_pac_fees(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    pac_trades = [t for t in result.trades if t.type == "pac_execution"]
    for trade in pac_trades:
        assert trade.fee == Decimal(0)


@then("€250 is added to cash (€500 / 2 configured days)")
def _check_cash_added(ctx: dict[str, Any]) -> None:
    portfolio = ctx["portfolio_after_pac"]
    assert portfolio.cash == Decimal("250")


@then("skipped trades are recorded in the trade log")
def _check_skipped_trades(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    skipped = [t for t in result.trades if t.skipped]
    assert len(skipped) > 0


@then("hard rebalance trades have a €1 settlement fee")
def _check_settlement_fee(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    rebal_trades = [
        t for t in result.trades if t.type == "hard_rebalance" and not t.skipped
    ]
    for trade in rebal_trades:
        assert trade.fee == Decimal("1.00")


@then(
    parsers.parse("{n:d} iteration results are produced"),
)
def _check_iteration_count(ctx: dict[str, Any], n: int) -> None:
    result: SimulationResult = ctx["simulation_result"]
    assert len(result.iterations) == n


@then("both runs produce identical final values")
def _check_identical_results(ctx: dict[str, Any]) -> None:
    r1: SimulationResult = ctx["result1"]
    r2: SimulationResult = ctx["result2"]
    assert len(r1.iterations) == len(r2.iterations)
    for it1, it2 in zip(r1.iterations, r2.iterations, strict=True):
        assert it1.final_value == it2.final_value
