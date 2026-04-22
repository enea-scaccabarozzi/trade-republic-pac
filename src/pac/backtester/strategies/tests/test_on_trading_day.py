from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

_NOW = datetime(2024, 1, 1)


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[],
        cash=Decimal("0"),
        timestamp=_NOW,
    )


def _empty_report() -> DeviationReport:
    return DeviationReport(
        deviations={},
        max_severity=SignalSeverity.INFO,
        timestamp=_NOW,
    )


class _CounterParams(BaseModel, frozen=True):
    pass


class _CounterStrategy(BacktestStrategy[_CounterParams]):
    """Strategy that counts on_trading_day calls."""

    name = "counter_test"

    def __init__(self, params: _CounterParams) -> None:
        super().__init__(params)
        self.day_count = 0

    def reset(self) -> None:
        super().reset()
        self.day_count = 0

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []

    def on_trading_day(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> None:
        self.day_count += 1


class TestOnTradingDayDefault:
    def test_default_returns_none(self) -> None:
        from pac.backtester.strategies.tests.conftest import (
            SimpleParams,
            SimpleStrategy,
        )

        strategy = SimpleStrategy(SimpleParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 15),
        )
        assert strategy.drain_events() == []

    def test_default_does_not_affect_event_buffer(self) -> None:
        from pac.backtester.strategies.tests.conftest import (
            SimpleParams,
            SimpleStrategy,
        )

        strategy = SimpleStrategy(SimpleParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 15),
        )
        assert strategy.drain_events() == []


class TestOnTradingDayStateful:
    def test_accumulates_across_days(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        for i in range(10):
            strategy.on_trading_day(
                _empty_snapshot(),
                _empty_report(),
                date(2024, 1, i + 1),
            )
        assert strategy.day_count == 10

    def test_reset_clears_subclass_state(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 1),
        )
        assert strategy.day_count == 1
        strategy.reset()
        assert strategy.day_count == 0

    def test_empty_portfolio_on_first_day(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 1),
        )
        assert strategy.day_count == 1
