"""Metrics framework — quantstats integration, benchmark, and MC aggregation."""

from pac.backtester.metrics.models import BacktestReport, MetricResult, MetricSet
from pac.backtester.metrics.report import compute_report

__all__ = [
    "BacktestReport",
    "MetricResult",
    "MetricSet",
    "compute_report",
]
