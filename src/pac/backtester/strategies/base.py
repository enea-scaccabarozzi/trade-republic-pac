from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, get_args

from pydantic import BaseModel

from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal

if TYPE_CHECKING:
    from pac.analysis.deviation import DeviationReport
    from pac.backtester.engine.actions import Action, PacAdjustment

ParamsT = TypeVar("ParamsT", bound=BaseModel)

__all__ = ["BacktestStrategy", "ParamsT", "_NoStrategyParams"]


class _NoStrategyParams(BaseModel):
    """Sentinel default for params_model — satisfies mypy strict mode."""


class BacktestStrategy(ABC, Generic[ParamsT]):
    """Base class for backtest strategies.

    Subclass with a concrete Params type:
        class MyStrategy(BacktestStrategy[MyParams]): ...

    The framework auto-extracts ``params_model`` from the Generic type arg
    via ``__init_subclass__``. Never set params_model manually.

    Strategies are **stateful** — unlike SignalRule, they store params
    on self and can track decisions across time steps within a single
    Monte Carlo iteration.
    """

    params_model: ClassVar[type[BaseModel]] = _NoStrategyParams
    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", []):
            origin = getattr(base, "__origin__", None)
            if origin is BacktestStrategy:
                args = get_args(base)
                if (
                    args
                    and isinstance(args[0], type)
                    and issubclass(args[0], BaseModel)
                ):
                    cls.params_model = args[0]
                    break
        # Validate that concrete subclasses define name as a str class attribute
        if not getattr(cls, "__abstractmethods__", frozenset()) and not isinstance(
            cls.__dict__.get("name"), str
        ):
            msg = (
                f"{cls.__name__} must define 'name' as a str class attribute"
            )
            raise TypeError(msg)

    def __init__(self, params: ParamsT) -> None:
        """Initialize with validated strategy params.

        Args:
            params: Typed params instance validated by Pydantic.
        """
        self._params = params

    @abstractmethod
    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        """Translate triggered signals into concrete actions.

        Called on every trading day that produces at least one signal.
        The strategy decides which (if any) actions to take.

        Args:
            signals: Signals from all evaluated rules for this day.
            snapshot: Current portfolio state.
            report: Deviation analysis for the current portfolio.
            current_date: The trading day being processed.

        Returns:
            List of actions to queue (may be empty).
        """
        ...

    def on_pac_date(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
        current_pac_volumes: dict[str, Decimal],
    ) -> PacAdjustment | None:
        """Optional hook: dynamically adjust PAC volumes on execution dates.

        Called on PAC dates (2nd/16th) *before* the PAC execution.
        Return a PacAdjustment to change volumes, or None to keep current.

        Args:
            snapshot: Current portfolio state.
            report: Deviation analysis for the current portfolio.
            current_date: The PAC execution date.
            current_pac_volumes: Current PAC volumes per asset
                (strategies can use this for incremental adjustments).

        Default: None (maintain current PAC allocation).
        """
        return None
