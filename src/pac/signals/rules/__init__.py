from __future__ import annotations

from pac.signals.registry import SignalRegistry
from pac.signals.rules.cycle import CycleInversionRule
from pac.signals.rules.threshold import ThresholdDeviationRule

__all__ = [
    "CycleInversionRule",
    "ThresholdDeviationRule",
    "create_default_registry",
]


def create_default_registry() -> SignalRegistry:
    """Create a SignalRegistry pre-loaded with all built-in rules."""
    registry = SignalRegistry()
    registry.register(ThresholdDeviationRule())
    registry.register(CycleInversionRule())
    return registry
