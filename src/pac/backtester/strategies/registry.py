from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pac.backtester.strategies.base import BacktestStrategy, _NoStrategyParams


class StrategyRegistry:
    """Collects strategy classes and instantiates them with typed params."""

    def __init__(self) -> None:
        self._strategies: dict[str, type[BacktestStrategy[Any]]] = {}

    def register(self, strategy_cls: type[BacktestStrategy[Any]]) -> None:
        """Register a strategy class by its name.

        Raises:
            TypeError: If strategy_cls is not a BacktestStrategy subclass.
            TypeError: If strategy_cls has no params_model.
        """
        if not (
            isinstance(strategy_cls, type)
            and issubclass(strategy_cls, BacktestStrategy)
        ):
            msg = f"{strategy_cls} is not a BacktestStrategy subclass"
            raise TypeError(msg)
        if strategy_cls.params_model is _NoStrategyParams:
            msg = (
                f"{strategy_cls.__name__} has no params_model"
                " — did you forget Generic[ParamsT]?"
            )
            raise TypeError(msg)
        # Read name directly from class attribute — no instantiation needed
        self._strategies[strategy_cls.name] = strategy_cls

    def instantiate(
        self,
        name: str,
        params_dict: dict[str, Any] | None = None,
    ) -> BacktestStrategy[Any]:
        """Create a strategy instance with validated params.

        Args:
            name: Strategy name (must be registered).
            params_dict: Raw params from config. If None, uses defaults.

        Returns:
            A new strategy instance with typed params.

        Raises:
            KeyError: If name is not registered.
            ValidationError: If params_dict fails validation.
        """
        strategy_cls = self._strategies[name]
        params = strategy_cls.params_model.model_validate(params_dict or {})
        return strategy_cls(params)

    def get_strategy_class(self, name: str) -> type[BacktestStrategy[Any]]:
        """Look up a registered strategy class by name."""
        return self._strategies[name]

    @property
    def strategy_names(self) -> list[str]:
        """All registered strategy names."""
        return list(self._strategies.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._strategies

    def __iter__(self) -> Iterator[str]:
        return iter(self._strategies)

    def __len__(self) -> int:
        return len(self._strategies)
