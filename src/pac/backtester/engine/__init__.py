"""Simulation engine — clock, portfolio state machine, and event loop."""

from pac.backtester.engine.actions import (
    Action,
    ActionType,
    ExecutedTrade,
    HardRebalanceOrder,
    PacAdjustment,
    PendingAction,
)
from pac.backtester.engine.clock import SimulationClock
from pac.backtester.engine.contributions import (
    ContributionConfig,
    ContributionDistribution,
    FixedContribution,
    NormalContribution,
    UniformContribution,
)
from pac.backtester.engine.market_context import BacktestMarketContext
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.engine.simulator import (
    BacktestSimulator,
    DayResult,
    IterationResult,
    SimulationResult,
)
from pac.backtester.engine.tax import (
    AssetTaxMeta,
    ItalianTaxRegime,
    NoTaxRegime,
    TaxRegime,
    TaxResult,
)

__all__ = [
    "Action",
    "ActionType",
    "AssetTaxMeta",
    "BacktestMarketContext",
    "BacktestSimulator",
    "ContributionConfig",
    "ContributionDistribution",
    "DayResult",
    "ExecutedTrade",
    "FixedContribution",
    "HardRebalanceOrder",
    "ItalianTaxRegime",
    "IterationResult",
    "NoTaxRegime",
    "NormalContribution",
    "PacAdjustment",
    "PendingAction",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "SimulationClock",
    "SimulationResult",
    "TaxRegime",
    "TaxResult",
    "UniformContribution",
]
