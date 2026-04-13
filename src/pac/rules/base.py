from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, get_args

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.models.indicators import IndicatorKind, IndicatorThreshold
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal

if TYPE_CHECKING:
    from pac.market_context import MarketContext

ParamsT = TypeVar("ParamsT", bound=BaseModel)

# Re-export for convenience (used by build_template_data overrides)
__all__ = [
    "IndicatorKind",
    "IndicatorSpec",
    "IndicatorThreshold",
    "IndicatorValues",
    "ParamsT",
    "SignalRule",
    "_NoParams",
]


class _NoParams(BaseModel):
    """Sentinel default for params_model — satisfies mypy strict mode."""


class IndicatorSpec(BaseModel, frozen=True):
    """Declaration of one indicator a rule can produce."""

    key_suffix: str
    display_name: str
    group: str
    kind: IndicatorKind
    unit: str = ""
    thresholds: list[IndicatorThreshold] = []
    companion_suffixes: list[str] = []


class IndicatorValues(BaseModel, frozen=True):
    """Return type for compute_indicators() — map of suffix to value."""

    values: dict[str, float | bool | None]


class SignalRule(ABC, Generic[ParamsT]):
    """Base class for all signal rules.

    Subclass with a concrete Params type:
        class MyRule(SignalRule[MyParams]): ...

    The framework auto-extracts ``params_model`` from the Generic type arg
    via ``__init_subclass__``. Never set params_model manually.
    """

    params_model: ClassVar[type[BaseModel]] = _NoParams

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # __orig_bases__ stores the Generic subscriptions as written in class
        # definition (e.g. SignalRule[ThresholdParams]). We traverse them to
        # extract the concrete ParamsT type arg for automatic params_model
        # resolution — this is how Python's typing module preserves type args
        # that are erased at runtime.
        for base in getattr(cls, "__orig_bases__", []):
            origin = getattr(base, "__origin__", None)
            if origin is SignalRule:
                args = get_args(base)
                if (
                    args
                    and isinstance(args[0], type)
                    and issubclass(args[0], BaseModel)
                ):
                    cls.params_model = args[0]
                    return

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique rule identifier. Must match the ``rule:`` field in config."""
        ...

    @abstractmethod
    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: ParamsT,
        market_ctx: MarketContext | None = None,
    ) -> list[Signal]:
        """Evaluate portfolio state and return triggered signals.

        Args:
            report: Deviation analysis for the current portfolio.
            snapshot: Current portfolio state with positions and allocations.
            params: Validated instance of this rule's Params model.
            market_ctx: Optional market data context for lookback indicators.

        Returns:
            List of signals triggered by this rule. Empty if no alerts.
        """
        ...

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        """Build the template context dict for this rule's template.

        Default: returns {"signal": signals[0]}. Override for
        rule-specific data (deviations, PAC plan, etc.).
        """
        return {"signal": signals[0]}

    @classmethod
    def indicator_specs(cls) -> list[IndicatorSpec]:
        """Declare indicators this rule produces. Default: empty."""
        return []

    def compute_indicators(
        self,
        params: ParamsT,
        market_ctx: MarketContext | None = None,
    ) -> IndicatorValues | None:
        """Compute current indicator values. Default: None."""
        return None
