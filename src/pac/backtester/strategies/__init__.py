"""Backtest strategies — ABC, registry, and auto-discovery."""

from pac.backtester.strategies.base import BacktestStrategy, ParamsT
from pac.backtester.strategies.discovery import discover_strategies
from pac.backtester.strategies.registry import StrategyRegistry

__all__ = [
    "BacktestStrategy",
    "ParamsT",
    "StrategyRegistry",
    "discover_strategies",
]
