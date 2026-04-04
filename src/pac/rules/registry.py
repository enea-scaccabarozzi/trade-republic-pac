from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pac.analysis.deviation import DeviationReport
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.base import SignalRule, _NoParams


class SignalRegistry:
    """Collects signal rules and evaluates them against portfolio state."""

    def __init__(self) -> None:
        self._rules: dict[str, type[SignalRule[Any]]] = {}

    def register(self, rule_cls: type[SignalRule[Any]]) -> None:
        """Register a rule class by its name.

        Args:
            rule_cls: A concrete SignalRule subclass.

        Raises:
            TypeError: If rule_cls is not a SignalRule subclass.
            TypeError: If rule_cls has no params_model (missing Generic type arg).
        """
        if not (isinstance(rule_cls, type) and issubclass(rule_cls, SignalRule)):
            msg = f"{rule_cls} is not a SignalRule subclass"
            raise TypeError(msg)
        if rule_cls.params_model is _NoParams:
            msg = (
                f"{rule_cls.__name__} has no params_model"
                " — did you forget Generic[ParamsT]?"
            )
            raise TypeError(msg)
        instance = rule_cls()
        self._rules[instance.name] = rule_cls

    def evaluate_signal(
        self,
        name: str,
        params_dict: dict[str, Any],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> list[Signal]:
        """Evaluate a single signal by name with raw params dict.

        Validates params_dict against the rule's params_model, then
        calls evaluate() with the typed params instance.

        Args:
            name: Rule name (must be registered).
            params_dict: Raw params from config (validated here).
            report: Deviation analysis.
            snapshot: Current portfolio state.

        Returns:
            List of triggered signals.

        Raises:
            KeyError: If name is not a registered rule.
            ValidationError: If params_dict fails validation.
        """
        rule_cls = self._rules[name]
        params = rule_cls.params_model.model_validate(params_dict)
        rule = rule_cls()
        return rule.evaluate(report, snapshot, params)

    def evaluate_all(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> list[Signal]:
        """Run all registered rules with default params.

        Used by interactive handlers (e.g. /rebalance) that need
        a quick overview of all signals from all rules.

        Args:
            report: Deviation analysis for the current portfolio.
            snapshot: Current portfolio state.

        Returns:
            Flat list of all signals from all rules.
        """
        signals: list[Signal] = []
        for rule_cls in self._rules.values():
            params = rule_cls.params_model()
            rule = rule_cls()
            signals.extend(rule.evaluate(report, snapshot, params))
        return signals

    def get_rule(self, name: str) -> type[SignalRule[Any]]:
        """Look up a registered rule class by name.

        Raises:
            KeyError: If name is not registered.
        """
        return self._rules[name]

    @property
    def rule_names(self) -> list[str]:
        """All registered rule names."""
        return list(self._rules.keys())

    def __iter__(self) -> Iterator[str]:
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, name: str) -> bool:
        return name in self._rules
