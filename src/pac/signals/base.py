from __future__ import annotations

from typing import Protocol, runtime_checkable

from pac.analysis.deviation import DeviationReport
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


@runtime_checkable
class SignalRule(Protocol):
    """Protocol for signal rules.

    Each rule evaluates portfolio state and returns zero or more signals.
    Rules are stateless — configuration comes from Settings.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this rule."""
        ...

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        settings: Settings,
    ) -> list[Signal]:
        """Evaluate portfolio state and return triggered signals.

        Args:
            report: Deviation analysis for the current portfolio.
            snapshot: Current portfolio state with positions and allocations.
            settings: Application settings with thresholds and targets.

        Returns:
            List of signals triggered by this rule. Empty if no alerts.
        """
        ...
