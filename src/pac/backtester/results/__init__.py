"""Results persistence — frontend-agnostic JSON sidecar format."""

from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore

__all__ = [
    "ResultStore",
    "RunResult",
    "build_run_result",
]
