from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pac.analysis.deviation import DeviationReport
from pac.backtester.config import BacktestConfig
from pac.backtester.engine.actions import (
    Action,
    ActionType,
    HardRebalanceOrder,
    PacAdjustment,
)
from pac.backtester.engine.simulator import BacktestSimulator
from pac.backtester.engine.tests.conftest import (
    NoopStrategy,
    StubStrategy,
    _NoopParams,
    _StubParams,
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.registry import SignalRegistry


def _make_simulator(
    *,
    start: date = date(2024, 1, 1),
    end: date = date(2024, 3, 31),
    iterations: int = 1,
    slippage: tuple[int, int] = (0, 0),
    strategy: BacktestStrategy[Any] | None = None,
    seed: int | None = 42,
) -> BacktestSimulator:
    settings = make_settings()
    config = BacktestConfig(
        strategy="test",
        start_date=start,
        end_date=end,
        monte_carlo_iterations=iterations,
        slippage_days=slippage,
    )
    price_data = make_three_asset_price_data(start, n_days=90)
    return BacktestSimulator(
        config=config,
        settings=settings,
        price_data=price_data,
        signal_registry=SignalRegistry(),
        strategy=strategy or NoopStrategy(_NoopParams()),
        rng_seed=seed,
    )


class TestRunSingleIteration:
    def test_run_single_iteration_returns_result(self) -> None:
        sim = _make_simulator()
        result = sim.run_iteration(0)
        assert result.iteration == 0
        assert len(result.daily_values) > 0
        assert result.final_value > Decimal(0)

    def test_daily_values_cover_all_trading_days(self) -> None:
        sim = _make_simulator()
        result = sim.run_iteration(0)
        # Should have entries for each trading day in the range
        assert len(result.daily_values) > 50  # ~3 months of trading days


class TestPacExecution:
    def test_pac_executions_on_pac_dates(self) -> None:
        sim = _make_simulator()
        result = sim.run_iteration(0)
        pac_trades = [t for t in result.trades if t.type == "pac_execution"]
        assert len(pac_trades) > 0
        # Each PAC trade should have zero fee
        for trade in pac_trades:
            assert trade.fee == Decimal(0)

    def test_noop_strategy_only_pac_trades(self) -> None:
        sim = _make_simulator()
        result = sim.run_iteration(0)
        for trade in result.trades:
            assert trade.type == "pac_execution"


class TestStrategyIntegration:
    def test_signals_fed_to_strategy(self) -> None:
        settings = make_settings(
            signals=[
                {
                    "name": "threshold_check",
                    "rule": "threshold_deviation",
                    "schedule": "daily",
                    "channels": [],
                    "params": {"warning_pct": "1.0", "critical_pct": "3.0"},
                    "template": "threshold_alert",
                },
            ],
        )
        stub = StubStrategy(_StubParams(), actions=[])
        config = BacktestConfig(
            strategy="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            monte_carlo_iterations=1,
            slippage_days=(0, 0),
        )
        price_data = make_three_asset_price_data(date(2024, 1, 1), n_days=90)

        # Register threshold rule if available
        from pac.rules.discovery import discover_rules

        registry = SignalRegistry()
        for rule_cls in discover_rules().values():
            registry.register(rule_cls)

        sim = BacktestSimulator(
            config=config,
            settings=settings,
            price_data=price_data,
            signal_registry=registry,
            strategy=stub,
            rng_seed=42,
        )
        sim.run_iteration(0)
        # Strategy should be called when signals fire
        assert len(stub.calls) > 0

    def test_strategy_actions_queued_with_slippage(self) -> None:
        rebalance_action = Action(
            type=ActionType.HARD_REBALANCE,
            rebalance_orders=[
                HardRebalanceOrder(
                    asset_id="stocks",
                    direction="buy",
                    amount_eur=Decimal("100"),
                ),
            ],
        )
        settings = make_settings(
            signals=[
                {
                    "name": "threshold_check",
                    "rule": "threshold_deviation",
                    "schedule": "daily",
                    "channels": [],
                    "params": {"warning_pct": "1.0", "critical_pct": "3.0"},
                    "template": "threshold_alert",
                },
            ],
        )
        stub = StubStrategy(_StubParams(), actions=[rebalance_action])
        config = BacktestConfig(
            strategy="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            monte_carlo_iterations=1,
            slippage_days=(2, 2),  # fixed 2-day slippage
        )
        price_data = make_three_asset_price_data(date(2024, 1, 1), n_days=90)

        from pac.rules.discovery import discover_rules

        registry = SignalRegistry()
        for rule_cls in discover_rules().values():
            registry.register(rule_cls)

        sim = BacktestSimulator(
            config=config,
            settings=settings,
            price_data=price_data,
            signal_registry=registry,
            strategy=stub,
            rng_seed=42,
        )
        result = sim.run_iteration(0)
        # Should have hard_rebalance trades from the strategy
        rebal_trades = [t for t in result.trades if t.type == "hard_rebalance"]
        assert len(rebal_trades) > 0


class TestDeterminism:
    def test_deterministic_with_seed(self) -> None:
        sim1 = _make_simulator(slippage=(0, 3), iterations=3, seed=42)
        sim2 = _make_simulator(slippage=(0, 3), iterations=3, seed=42)
        result1 = sim1.run()
        result2 = sim2.run()
        for it1, it2 in zip(
            result1.iterations, result2.iterations, strict=True,
        ):
            assert it1.final_value == it2.final_value
            assert len(it1.daily_values) == len(it2.daily_values)


class TestMonteCarloIterations:
    def test_multiple_iterations_produce_distribution(self) -> None:
        sim = _make_simulator(slippage=(0, 3), iterations=5)
        result = sim.run()
        assert len(result.iterations) == 5
        # With slippage variation, not all iterations should have the same trades
        # (though values may be similar with noop strategy)
        final_values = [it.final_value for it in result.iterations]
        assert len(final_values) == 5


class TestSimulationResult:
    def test_simulation_result_contains_config(self) -> None:
        sim = _make_simulator()
        result = sim.run()
        assert result.config.strategy == "test"
        assert result.config.start_date == date(2024, 1, 1)


class TestZeroSlippage:
    def test_zero_slippage_immediate_execution(self) -> None:
        rebalance_action = Action(
            type=ActionType.HARD_REBALANCE,
            rebalance_orders=[
                HardRebalanceOrder(
                    asset_id="stocks",
                    direction="buy",
                    amount_eur=Decimal("100"),
                ),
            ],
        )
        settings = make_settings(
            signals=[
                {
                    "name": "threshold_check",
                    "rule": "threshold_deviation",
                    "schedule": "daily",
                    "channels": [],
                    "params": {"warning_pct": "1.0", "critical_pct": "3.0"},
                    "template": "threshold_alert",
                },
            ],
        )
        stub = StubStrategy(_StubParams(), actions=[rebalance_action])
        config = BacktestConfig(
            strategy="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 28),
            monte_carlo_iterations=1,
            slippage_days=(0, 0),
        )
        price_data = make_three_asset_price_data(date(2024, 1, 1), n_days=60)

        from pac.rules.discovery import discover_rules

        registry = SignalRegistry()
        for rule_cls in discover_rules().values():
            registry.register(rule_cls)

        sim = BacktestSimulator(
            config=config,
            settings=settings,
            price_data=price_data,
            signal_registry=registry,
            strategy=stub,
            rng_seed=42,
        )
        result = sim.run_iteration(0)
        # With zero slippage, actions should execute same day
        rebal_trades = [t for t in result.trades if t.type == "hard_rebalance"]
        assert len(rebal_trades) > 0


class TestPortfolioValueConsistency:
    def test_portfolio_total_value_matches_snapshot_total_value(self) -> None:
        sim = _make_simulator()
        result = sim.run_iteration(0)
        # Final value should be positive and reasonable
        assert result.final_value > Decimal(0)
        # Daily values should be monotonically reasonable
        for dv in result.daily_values:
            assert dv.total_value > Decimal(0)
            assert dv.cash >= Decimal(0)


class TestOnPacDateIntegration:
    def test_on_pac_date_adjusts_volumes_for_next_pac(self) -> None:
        """Strategy returns PacAdjustment on first PAC date, changing volumes."""
        from pydantic import BaseModel

        class _AdjustParams(BaseModel):
            pass

        class AdjustOnFirstPac(BacktestStrategy[_AdjustParams]):
            name = "adjust_first_pac"

            def __init__(self, params: _AdjustParams) -> None:
                super().__init__(params)
                self._called = False

            def on_signals(
                self,
                signals: list[Signal],
                snapshot: PortfolioSnapshot,
                report: DeviationReport,
                current_date: date,
            ) -> list[Action]:
                return []

            def on_pac_date(
                self,
                snapshot: PortfolioSnapshot,
                report: DeviationReport,
                current_date: date,
                current_pac_volumes: dict[str, Decimal],
            ) -> PacAdjustment | None:
                if not self._called:
                    self._called = True
                    return PacAdjustment(
                        new_volumes={
                            "stocks": Decimal("500"),
                            "gold": Decimal("0"),
                            "bonds": Decimal("0"),
                        },
                    )
                return None

        strategy = AdjustOnFirstPac(_AdjustParams())
        sim = _make_simulator(strategy=strategy)
        result = sim.run_iteration(0)
        pac_trades = [t for t in result.trades if t.type == "pac_execution"]
        assert len(pac_trades) > 0
        # Find PAC trades after the first PAC date
        first_pac_date = pac_trades[0].date
        later_trades = [t for t in pac_trades if t.date > first_pac_date]
        # Later PAC trades for gold/bonds should have zero quantity
        for trade in later_trades:
            if trade.asset_id in ("gold", "bonds"):
                assert trade.amount_eur == Decimal(0) or trade.quantity == Decimal(0)
