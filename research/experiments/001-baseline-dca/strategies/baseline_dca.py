"""Baseline DCA strategy: pure static allocation, no signal response.

Invests at fixed 70/15/15 target weights on each PAC date. Never
rebalances, never adjusts volumes in response to signals. This is
the simplest possible DCA strategy, serving as the benchmark for all
future experiments.
"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class BaselineDCAParams(BaseModel, frozen=True):
    """No tunable parameters — pure static DCA."""


class BaselineDCA(BacktestStrategy[BaselineDCAParams]):
    """Do nothing beyond the default PAC execution.

    - on_signals: returns empty (ignores all signals)
    - on_pac_date: returns None (keeps initial target-proportional volumes)

    The simulator's built-in PAC execution handles buying at target weights.
    """

    name: ClassVar[str] = "baseline_dca"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []
