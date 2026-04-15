"""Research framework — experiment management and auto-state computation."""

from pac.backtester.research.context import ResearchContext
from pac.backtester.research.events import EventCalendar, MarketEvent
from pac.backtester.research.events_builtin import BUILTIN_CALENDARS
from pac.backtester.research.experiment import ExperimentState, load_experiment
from pac.backtester.research.indicators import (
    CompositeResult,
    IndicatorDef,
    IndicatorRegistry,
    IndicatorResult,
    threshold,
)
from pac.backtester.research.manifest import ExperimentManifest
from pac.backtester.research.models import (
    ComparisonTable,
    EventAnalysisResult,
    EventMetrics,
    MetricBand,
    OOSResult,
    QuantstatsMetrics,
    SweepResult,
    VariantResult,
    WalkForwardResult,
    WFWindow,
)

__all__ = [
    "BUILTIN_CALENDARS",
    "ComparisonTable",
    "CompositeResult",
    "EventAnalysisResult",
    "EventCalendar",
    "EventMetrics",
    "ExperimentManifest",
    "ExperimentState",
    "IndicatorDef",
    "IndicatorRegistry",
    "IndicatorResult",
    "MarketEvent",
    "MetricBand",
    "OOSResult",
    "QuantstatsMetrics",
    "ResearchContext",
    "SweepResult",
    "VariantResult",
    "WFWindow",
    "WalkForwardResult",
    "load_experiment",
    "threshold",
]
