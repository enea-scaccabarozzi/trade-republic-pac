"""Data models for compare/sweep results."""

from __future__ import annotations

__all__ = [
    "ComparisonTable",
    "EventAnalysisResult",
    "EventMetrics",
    "MetricBand",
    "OOSResult",
    "QuantstatsMetrics",
    "SweepResult",
    "VariantResult",
    "WFWindow",
    "WalkForwardResult",
]

from datetime import date as date_type
from typing import Any

from pydantic import BaseModel


class VariantResult(BaseModel, frozen=True):
    """One row in a comparison table — a strategy+params combo with its metrics."""

    label: str
    strategy: str
    params: dict[str, Any]
    final_value: float
    metrics: dict[str, float]


class ComparisonTable(BaseModel, frozen=True):
    """Side-by-side comparison of multiple strategy variants."""

    variants: list[VariantResult]
    metric_names: list[str]

    def to_dict(self) -> dict[str, dict[str, float]]:
        """Pivot to {label: {metric: value}} for easy tabular display."""
        return {
            v.label: {**v.metrics, "final_value": v.final_value} for v in self.variants
        }


class SweepResult(BaseModel, frozen=True):
    """Result of a parameter grid sweep — one VariantResult per grid point."""

    strategy: str
    param_grid: dict[str, list[Any]]
    results: list[VariantResult]
    metric_names: list[str]

    @property
    def best(self) -> VariantResult:
        """Return the variant with the highest first metric."""
        primary = self.metric_names[0]
        return max(
            self.results,
            key=lambda v: v.metrics.get(primary, float("-inf")),
        )


# ── OOS result models ─────────────────────────────────────


class OOSResult(BaseModel, frozen=True):
    """Result of a temporal holdout (split at a date)."""

    split_date: date_type
    in_sample_metrics: dict[str, float]
    out_of_sample_metrics: dict[str, float]
    in_sample_final_value: float
    out_of_sample_final_value: float
    degradation_ratio: float


class WFWindow(BaseModel, frozen=True):
    """A single walk-forward window."""

    window_index: int
    is_start: date_type
    is_end: date_type
    oos_start: date_type
    oos_end: date_type
    is_metrics: dict[str, float]
    oos_metrics: dict[str, float]


class WalkForwardResult(BaseModel, frozen=True):
    """Result of expanding walk-forward validation."""

    windows: list[WFWindow]
    strategy: str
    params: dict[str, Any]
    metric_names: list[str]
    stability_score: float
    consistent_windows: int


class EventMetrics(BaseModel, frozen=True):
    """Per-event performance from evaluate_events()."""

    event_name: str | None
    event_start: date_type
    event_end: date_type
    event_tags: list[str]
    metrics_during_event: dict[str, float]
    event_return: float


class EventAnalysisResult(BaseModel, frozen=True):
    """Result of event-based evaluation."""

    calendar_name: str
    strategy: str
    params: dict[str, Any]
    metric_names: list[str]
    per_event: list[EventMetrics]
    mean_event_return: float
    generalization_score: float


class MetricBand(BaseModel, frozen=True):
    """P5/median/P95 band for a single metric across MC iterations."""

    p5: float
    median: float
    p95: float


class QuantstatsMetrics(BaseModel, frozen=True):
    """Result of quantstats() — either single-iteration or MC-aggregated.

    ``metrics`` values are ``float`` for single ``IterationResult`` input,
    ``MetricBand`` for ``SimulationResult`` (MC) input.
    """

    metrics: dict[str, float | MetricBand]
