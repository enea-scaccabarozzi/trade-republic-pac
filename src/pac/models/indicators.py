"""Shared indicator type definitions used by rules and results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class IndicatorKind(StrEnum):
    """How the indicator should be visualized."""

    CONTINUOUS = "continuous"
    BOOLEAN = "boolean"
    EVENT = "event"
    RATIO = "ratio"


class IndicatorThreshold(BaseModel, frozen=True):
    """A horizontal threshold line on the indicator chart."""

    value: float
    label: str
    color: str = ""
