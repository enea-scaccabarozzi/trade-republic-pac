from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalSeverity(StrEnum):
    """Severity levels for portfolio signals."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActionType(StrEnum):
    """Possible rebalance actions."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Signal(BaseModel):
    """A triggered portfolio signal."""

    name: str
    severity: SignalSeverity
    message: str
    triggered_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class RebalanceAction(BaseModel):
    """Recommended action to rebalance the portfolio."""

    asset_id: str
    action: ActionType
    reason: str
    current_pct: float
    target_pct: float
