from __future__ import annotations

import pandas as pd

from pac.backtester.engine.simulator import IterationResult


def equity_to_returns(iteration: IterationResult) -> pd.Series:
    """Convert an iteration's equity curve to a daily return series.

    Takes daily_values from IterationResult, builds a pd.Series indexed
    by date with total_value as values, then computes pct_change().

    Leading zeros (e.g. when initial_cash=0 and contributions haven't
    arrived yet) are stripped before computing returns to avoid division-
    by-zero producing infinite values.

    The first day after the leading-zero strip is dropped (NaN from
    pct_change), so a single non-zero value produces an empty Series.

    Args:
        iteration: A single MC iteration result.

    Returns:
        pd.Series of daily percentage returns, float-typed,
        indexed by datetime. Returns empty Series if < 2 data points
        or if all values are zero.
    """
    if len(iteration.daily_values) < 2:
        return pd.Series(dtype=float)

    values = [float(dv.total_value) for dv in iteration.daily_values]
    dates = pd.DatetimeIndex([dv.date for dv in iteration.daily_values])
    equity = pd.Series(values, index=dates)

    # Skip leading zeros (initial_cash=0 before first contribution)
    first_nonzero = equity.ne(0).idxmax()
    if equity.loc[first_nonzero] == 0:
        return pd.Series(dtype=float)  # all zeros
    equity = equity.loc[first_nonzero:]

    returns: pd.Series[float] = equity.pct_change().dropna()
    return returns
