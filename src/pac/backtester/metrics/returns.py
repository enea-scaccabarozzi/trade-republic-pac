from __future__ import annotations

import pandas as pd

from pac.backtester.engine.simulator import IterationResult


def equity_to_returns(iteration: IterationResult) -> pd.Series:
    """Convert an iteration's equity curve to a daily return series.

    Takes daily_values from IterationResult, builds a pd.Series indexed
    by date with total_value as values, then computes pct_change().

    The first day is dropped (NaN from pct_change).

    Args:
        iteration: A single MC iteration result.

    Returns:
        pd.Series of daily percentage returns, float-typed,
        indexed by datetime. Returns empty Series if < 2 data points.
    """
    if len(iteration.daily_values) < 2:
        return pd.Series(dtype=float)

    values = [float(dv.total_value) for dv in iteration.daily_values]
    dates = pd.DatetimeIndex([dv.date for dv in iteration.daily_values])
    equity = pd.Series(values, index=dates)
    returns: pd.Series[float] = equity.pct_change().dropna()
    return returns
