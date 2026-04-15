"""Results persistence — frontend-agnostic JSON sidecar format."""

from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import (
    ComparisonResult,
    MetricDelta,
    OOSMetadata,
    RunResult,
)
from pac.backtester.results.store import ResultStore

__all__ = [
    "ComparisonResult",
    "MetricDelta",
    "OOSMetadata",
    "ResultStore",
    "RunResult",
    "build_run_result",
]
