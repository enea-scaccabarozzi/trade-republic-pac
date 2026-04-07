from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class SimpleParams(BaseModel):
    threshold: float = 5.0


class SimpleStrategy(BacktestStrategy[SimpleParams]):
    """Minimal concrete strategy for testing."""

    name = "simple"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []
