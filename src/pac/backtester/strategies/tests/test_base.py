from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action, PacAdjustment
from pac.backtester.strategies.base import (
    BacktestStrategy,
    _NoStrategyParams,
)
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

_NOW = datetime(2024, 1, 1)


class _MyParams(BaseModel):
    threshold: float = 5.0


class _ValidStrategy(BacktestStrategy[_MyParams]):
    name = "valid"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


class TestInitSubclassExtractsParamsModel:
    def test_init_subclass_extracts_params_model(self) -> None:
        assert _ValidStrategy.params_model is _MyParams

    def test_no_generic_arg_keeps_sentinel(self) -> None:
        class _NoGeneric(BacktestStrategy):  # type: ignore[type-arg]
            name = "no_generic"

            def on_signals(
                self,
                signals: list[Signal],
                snapshot: PortfolioSnapshot,
                report: DeviationReport,
                current_date: date,
            ) -> list[Action]:
                return []

        assert _NoGeneric.params_model is _NoStrategyParams


class TestNameClassVar:
    def test_name_classvar_required(self) -> None:
        with pytest.raises(TypeError, match="must define 'name'"):

            class _MissingName(BacktestStrategy[_MyParams]):
                def on_signals(
                    self,
                    signals: list[Signal],
                    snapshot: PortfolioSnapshot,
                    report: DeviationReport,
                    current_date: date,
                ) -> list[Action]:
                    return []

    def test_name_classvar_read_without_instance(self) -> None:
        assert _ValidStrategy.name == "valid"


class TestParamsStoredOnSelf:
    def test_params_stored_on_self(self) -> None:
        params = _MyParams(threshold=3.0)
        strategy = _ValidStrategy(params)
        assert strategy._params is params
        assert strategy._params.threshold == 3.0


class TestOnPacDateDefault:
    def test_on_pac_date_default_returns_none(self) -> None:
        strategy = _ValidStrategy(_MyParams())
        result = strategy.on_pac_date(
            snapshot=PortfolioSnapshot(
                positions=[],
                cash=Decimal(0),
                timestamp=_NOW,
            ),
            report=DeviationReport(
                deviations={},
                max_severity=SignalSeverity.INFO,
                timestamp=_NOW,
            ),
            current_date=date(2024, 1, 2),
            current_pac_volumes={"stocks": Decimal("350")},
        )
        assert result is None

    def test_on_pac_date_receives_current_volumes(self) -> None:
        received_volumes: dict[str, Decimal] = {}

        class _CaptureVolumes(BacktestStrategy[_MyParams]):
            name = "capture_volumes"

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
                received_volumes.update(current_pac_volumes)
                return None

        strategy = _CaptureVolumes(_MyParams())
        volumes = {"stocks": Decimal("350"), "gold": Decimal("75")}
        strategy.on_pac_date(
            snapshot=PortfolioSnapshot(
                positions=[],
                cash=Decimal(0),
                timestamp=_NOW,
            ),
            report=DeviationReport(
                deviations={},
                max_severity=SignalSeverity.INFO,
                timestamp=_NOW,
            ),
            current_date=date(2024, 1, 2),
            current_pac_volumes=volumes,
        )
        assert received_volumes == volumes


class TestAbstractMethodsCannotInstantiate:
    def test_abstract_methods_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BacktestStrategy(_MyParams())  # type: ignore[abstract]


class TestStrategyIsStateful:
    def test_strategy_is_stateful(self) -> None:
        class _StatefulStrategy(BacktestStrategy[_MyParams]):
            name = "stateful"

            def __init__(self, params: _MyParams) -> None:
                super().__init__(params)
                self.call_count = 0

            def on_signals(
                self,
                signals: list[Signal],
                snapshot: PortfolioSnapshot,
                report: DeviationReport,
                current_date: date,
            ) -> list[Action]:
                self.call_count += 1
                return []

        strategy = _StatefulStrategy(_MyParams())
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal(0),
            timestamp=_NOW,
        )
        report = DeviationReport(
            deviations={},
            max_severity=SignalSeverity.INFO,
            timestamp=_NOW,
        )

        strategy.on_signals([], snapshot, report, date(2024, 1, 1))
        strategy.on_signals([], snapshot, report, date(2024, 1, 2))
        assert strategy.call_count == 2
