from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.registry import StrategyRegistry
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class _RegParams(BaseModel):
    multiplier: float = 1.0


class _RegStrategy(BacktestStrategy[_RegParams]):
    name = "reg_test"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


class _StrictParams(BaseModel):
    required_field: str


class _StrictStrategy(BacktestStrategy[_StrictParams]):
    name = "strict_test"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


class TestRegisterConcreteStrategy:
    def test_register_concrete_strategy(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        assert "reg_test" in registry
        assert registry.get_strategy_class("reg_test") is _RegStrategy

    def test_register_rejects_non_subclass(self) -> None:
        registry = StrategyRegistry()
        with pytest.raises(TypeError, match="not a BacktestStrategy subclass"):
            registry.register(str)  # type: ignore[arg-type]

    def test_register_rejects_missing_params_model(self) -> None:
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

        registry = StrategyRegistry()
        with pytest.raises(TypeError, match="has no params_model"):
            registry.register(_NoGeneric)

    def test_register_reads_name_without_instantiation(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        assert _RegStrategy.name == "reg_test"
        assert "reg_test" in registry


class TestInstantiate:
    def test_instantiate_with_defaults(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        instance = registry.instantiate("reg_test")
        assert isinstance(instance, _RegStrategy)
        assert instance._params.multiplier == 1.0

    def test_instantiate_with_custom_params(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        instance = registry.instantiate("reg_test", {"multiplier": 2.5})
        assert instance._params.multiplier == 2.5

    def test_instantiate_unknown_name_raises_key_error(self) -> None:
        registry = StrategyRegistry()
        with pytest.raises(KeyError):
            registry.instantiate("unknown")

    def test_instantiate_invalid_params_raises_validation_error(self) -> None:
        registry = StrategyRegistry()
        registry.register(_StrictStrategy)
        with pytest.raises(ValidationError):
            registry.instantiate("strict_test", {})


class TestContainerMethods:
    def test_contains(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        assert "reg_test" in registry
        assert "nonexistent" not in registry

    def test_len(self) -> None:
        registry = StrategyRegistry()
        assert len(registry) == 0
        registry.register(_RegStrategy)
        assert len(registry) == 1

    def test_iter(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        assert list(registry) == ["reg_test"]

    def test_strategy_names_property(self) -> None:
        registry = StrategyRegistry()
        registry.register(_RegStrategy)
        assert registry.strategy_names == ["reg_test"]
