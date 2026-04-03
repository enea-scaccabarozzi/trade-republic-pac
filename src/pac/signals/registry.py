from __future__ import annotations

from collections.abc import Iterator

from pac.analysis.deviation import DeviationReport
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.signals.base import SignalRule


class SignalRegistry:
    """Collects signal rules and evaluates them against portfolio state."""

    def __init__(self) -> None:
        self._rules: list[SignalRule] = []

    def register(self, rule: SignalRule) -> None:
        """Add a signal rule to the registry.

        Args:
            rule: A SignalRule-conforming instance.

        Raises:
            TypeError: If rule does not conform to SignalRule protocol.
        """
        # isinstance provides a runtime safety net at the registration boundary;
        # mypy gives the real structural conformance guarantee at type-check time.
        if not isinstance(rule, SignalRule):
            msg = f"{type(rule).__name__} does not implement SignalRule"
            raise TypeError(msg)
        self._rules.append(rule)

    def evaluate_all(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        settings: Settings,
    ) -> list[Signal]:
        """Run all registered rules and return merged signals.

        Args:
            report: Deviation analysis for the current portfolio.
            snapshot: Current portfolio state.
            settings: Application settings.

        Returns:
            Flat list of all signals from all rules.
        """
        signals: list[Signal] = []
        for rule in self._rules:
            signals.extend(rule.evaluate(report, snapshot, settings))
        return signals

    def __iter__(self) -> Iterator[SignalRule]:
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)
