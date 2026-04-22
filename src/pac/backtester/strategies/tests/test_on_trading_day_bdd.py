from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel
from pytest_bdd import given, scenarios, then, when

from pac.analysis.deviation import DeviationReport, DeviationResult
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.tests.conftest import SimpleParams, SimpleStrategy
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity

scenarios("../features/on_trading_day.feature")


class _ObservationRecord(BaseModel, frozen=True):
    current_date: date
    allocations: dict[str, Decimal]
    deviations: dict[str, Decimal]


class _ObserverParams(BaseModel, frozen=True):
    pass


class _ObserverStrategy(BacktestStrategy[_ObserverParams]):
    """Test strategy that records every on_trading_day call."""

    name: ClassVar[str] = "observer_test"

    def __init__(self, params: _ObserverParams) -> None:
        super().__init__(params)
        self._observations: list[_ObservationRecord] = []

    def reset(self) -> None:
        super().reset()
        self._observations = []

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
        asset_ids = [p.asset_id for p in snapshot.positions]
        allocs = snapshot.allocations(asset_ids)
        self._observations.append(
            _ObservationRecord(
                current_date=current_date,
                allocations={aid: allocs[aid].actual_pct for aid in asset_ids},
                deviations={
                    aid: report.deviations[aid].deviation_pct
                    for aid in report.deviations
                },
            ),
        )

    @property
    def observations(self) -> list[_ObservationRecord]:
        return list(self._observations)


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _make_snapshot(
    stocks_value: Decimal = Decimal("7000"),
    bonds_value: Decimal = Decimal("3000"),
    cash: Decimal = Decimal("0"),
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal("100"),
                price=stocks_value / Decimal("100"),
                market_value=stocks_value,
                asset_id="stocks",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal("100"),
                price=bonds_value / Decimal("100"),
                market_value=bonds_value,
                asset_id="bonds",
            ),
        ],
        cash=cash,
        timestamp=datetime(2024, 1, 15),
    )


def _make_report(
    stocks_dev: Decimal = Decimal("0"),
    bonds_dev: Decimal = Decimal("0"),
) -> DeviationReport:
    return DeviationReport(
        deviations={
            "stocks": DeviationResult(
                asset_id="stocks",
                name="Stocks ETF",
                actual_pct=Decimal("70") + stocks_dev,
                target_pct=Decimal("70"),
                deviation_pct=stocks_dev,
                abs_deviation_pct=abs(stocks_dev),
                severity=SignalSeverity.INFO,
            ),
            "bonds": DeviationResult(
                asset_id="bonds",
                name="Bond ETF",
                actual_pct=Decimal("30") + bonds_dev,
                target_pct=Decimal("30"),
                deviation_pct=bonds_dev,
                abs_deviation_pct=abs(bonds_dev),
                severity=SignalSeverity.INFO,
            ),
        },
        max_severity=SignalSeverity.INFO,
        timestamp=datetime(2024, 1, 15),
    )


# -- Given steps ----------------------------------------------------------


@given("a strategy that records daily portfolio observations")
def _strategy_that_records(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = _ObserverStrategy(_ObserverParams())


@given("a simulation spanning 5 trading days")
def _sim_5_days(ctx: dict[str, Any]) -> None:
    ctx["trading_days"] = [date(2024, 1, d) for d in range(15, 20)]
    ctx["snapshot"] = _make_snapshot()
    ctx["report"] = _make_report()


@given("a simulation with a portfolio holding stocks and bonds")
def _sim_with_portfolio(ctx: dict[str, Any]) -> None:
    ctx["trading_days"] = [date(2024, 1, 15)]
    ctx["snapshot"] = _make_snapshot(
        stocks_value=Decimal("7000"),
        bonds_value=Decimal("3000"),
    )
    ctx["report"] = _make_report(
        stocks_dev=Decimal("0"),
        bonds_dev=Decimal("0"),
    )


@given(
    "a completed simulation iteration with accumulated observations",
)
def _completed_iteration(ctx: dict[str, Any]) -> None:
    strategy: _ObserverStrategy = ctx["strategy"]
    snapshot = _make_snapshot()
    report = _make_report()
    for d in [date(2024, 1, 15), date(2024, 1, 16)]:
        strategy.on_trading_day(snapshot, report, d)
    assert len(strategy.observations) == 2
    ctx["snapshot"] = snapshot
    ctx["report"] = report


@given("a strategy with default on_trading_day")
def _default_strategy(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = SimpleStrategy(SimpleParams())


# -- When steps -----------------------------------------------------------


@when("the simulation completes")
def _simulation_completes(ctx: dict[str, Any]) -> None:
    strategy: _ObserverStrategy = ctx["strategy"]
    snapshot = ctx["snapshot"]
    report = ctx["report"]
    for d in ctx["trading_days"]:
        strategy.on_trading_day(snapshot, report, d)


@when("a new iteration begins")
def _new_iteration(ctx: dict[str, Any]) -> None:
    ctx["strategy"].reset()


@when("on_trading_day is called with a portfolio snapshot")
def _call_default_on_trading_day(ctx: dict[str, Any]) -> None:
    strategy = ctx["strategy"]
    snapshot = _make_snapshot()
    report = _make_report()
    strategy.on_trading_day(snapshot, report, date(2024, 1, 15))
    ctx["call_completed"] = True


# -- Then steps -----------------------------------------------------------


@then("the strategy recorded 5 daily observations")
def _recorded_5(ctx: dict[str, Any]) -> None:
    assert len(ctx["strategy"].observations) == 5


@then("each observation includes allocation percentages for all assets")
def _obs_has_allocations(ctx: dict[str, Any]) -> None:
    for obs in ctx["strategy"].observations:
        assert "stocks" in obs.allocations
        assert "bonds" in obs.allocations
        assert all(v >= 0 for v in obs.allocations.values())


@then(
    "each observation includes signed deviation from target for each asset",
)
def _obs_has_deviations(ctx: dict[str, Any]) -> None:
    for obs in ctx["strategy"].observations:
        assert "stocks" in obs.deviations
        assert "bonds" in obs.deviations


@then("the observations are ordered by date")
def _obs_ordered(ctx: dict[str, Any]) -> None:
    dates = [obs.current_date for obs in ctx["strategy"].observations]
    assert dates == sorted(dates)


@then("no prior observations remain")
def _obs_empty(ctx: dict[str, Any]) -> None:
    assert len(ctx["strategy"].observations) == 0


@then("no error is raised and no state changes")
def _no_error(ctx: dict[str, Any]) -> None:
    assert ctx["call_completed"] is True
