"""Pure indicator helper functions for crisis detection rules.

No rule logic or signal emission — just math on PriceSeries data.
Each compute function validates minimum data requirements and raises
ValueError if insufficient bars are available; calling rules catch
this and return an empty signal list (graceful degradation).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt

from pac.models.market_data import PriceSeries

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawdownResult:
    """Result of drawdown + velocity calculation."""

    drawdown_pct: float
    """Negative during drawdowns (e.g., -0.15 = -15%)."""
    days_since_peak: int
    """Trading days from rolling peak to current."""
    velocity: float
    """drawdown_pct / days_since_peak (%/day), negative."""
    rolling_peak: float
    """The peak close price in the lookback window."""


@dataclass(frozen=True)
class DivergenceResult:
    """Result of gold-equity divergence calculation."""

    gold_return: float
    """N-day gold return."""
    equity_return: float
    """N-day equity return."""
    divergence: float
    """gold_return - equity_return."""


@dataclass(frozen=True)
class VolatilityRegimeResult:
    """Result of volatility regime calculation."""

    short_vol: float
    """Annualized short-window vol."""
    long_vol: float
    """Annualized long-window vol."""
    vol_ratio: float
    """short_vol / long_vol."""


@dataclass(frozen=True)
class CorrelationResult:
    """Result of bond-equity rolling correlation."""

    correlation: float
    """Pearson correlation of daily returns."""
    bond_declining: bool
    """True if bonds are lower than N days ago."""
    days_above_threshold: int
    """Consecutive days corr > veto_threshold."""


@dataclass(frozen=True)
class RelativeStrengthResult:
    """Result of gold/equity relative strength calculation."""

    rs_current: float
    """Current gold/equity price ratio."""
    rs_ma: float
    """MA of the ratio (e.g., 120-day)."""
    breakout_pct: float
    """(rs_current / rs_ma - 1) * 100."""


@dataclass(frozen=True)
class DeathCrossResult:
    """Result of death cross (SMA crossover) check."""

    sma_short: float
    """Current short SMA (e.g., 50-day)."""
    sma_long: float
    """Current long SMA (e.g., 200-day)."""
    bearish_regime: bool
    """sma_short < sma_long."""
    cross_event: bool
    """Crossover happened on the current bar."""


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def closes_as_floats(series: PriceSeries) -> list[float]:
    """Extract close prices as float list."""
    return [float(bar.close) for bar in series.bars]


def daily_returns(closes: list[float]) -> list[float]:
    """Compute simple daily returns: (p[i] - p[i-1]) / p[i-1].

    Skips any bar where p[i-1] == 0.0 to avoid ZeroDivisionError.
    """
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] != 0.0
    ]


def daily_log_returns(closes: list[float]) -> list[float]:
    """Compute log daily returns: ln(p[i] / p[i-1]).

    Skips any bar where p[i-1] <= 0.0.
    """
    return [
        log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0.0
    ]


def rolling_mean(values: list[float], window: int) -> float:
    """Mean of the last *window* values."""
    if window < 1:
        msg = f"rolling_mean requires window >= 1, got {window}"
        raise ValueError(msg)
    subset = values[-window:]
    if len(subset) < window:
        msg = f"Not enough values ({len(subset)}) for window={window}"
        raise ValueError(msg)
    return sum(subset) / window


def rolling_std(values: list[float], window: int) -> float:
    """Sample standard deviation of the last *window* values.

    Requires window >= 2 (sample std needs n-1 denominator).
    Raises ValueError if window < 2 or len(values) < window.
    """
    if window < 2:
        msg = f"rolling_std requires window >= 2, got {window}"
        raise ValueError(msg)
    subset = values[-window:]
    if len(subset) < window:
        msg = f"Not enough values ({len(subset)}) for window={window}"
        raise ValueError(msg)
    mean = sum(subset) / len(subset)
    variance = sum((x - mean) ** 2 for x in subset) / (len(subset) - 1)
    return sqrt(variance)


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient between two equal-length series.

    Returns None if either series has zero variance.
    """
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / (n - 1)
    std_x = sqrt(sum((x - mean_x) ** 2 for x in xs) / (n - 1))
    std_y = sqrt(sum((y - mean_y) ** 2 for y in ys) / (n - 1))
    if std_x == 0.0 or std_y == 0.0:
        return None
    return cov / (std_x * std_y)


# ---------------------------------------------------------------------------
# Compute functions
# ---------------------------------------------------------------------------


def compute_drawdown(
    equity_series: PriceSeries,
    lookback_bars: int = 252,
) -> DrawdownResult:
    """Compute equity drawdown from rolling peak and velocity.

    Formula (research doc Section 5.1 + 5.2):
        rolling_peak = max(close[t-lookback : t])
        drawdown_pct = (close[t] - rolling_peak) / rolling_peak
        days_since_peak = t - argmax(close[t-lookback : t])
        velocity = drawdown_pct / days_since_peak  (%/day)
    """
    closes = closes_as_floats(equity_series)
    if len(closes) < 2:
        msg = f"Need at least 2 bars, got {len(closes)}"
        raise ValueError(msg)

    window = closes[-lookback_bars:]
    peak = max(window)
    peak_idx = len(window) - 1 - window[::-1].index(peak)
    current = closes[-1]

    drawdown_pct = (current - peak) / peak if peak != 0.0 else 0.0
    days_since_peak = len(window) - 1 - peak_idx
    velocity = drawdown_pct / days_since_peak if days_since_peak > 0 else 0.0

    return DrawdownResult(
        drawdown_pct=drawdown_pct,
        days_since_peak=days_since_peak,
        velocity=velocity,
        rolling_peak=peak,
    )


def compute_divergence(
    gold_series: PriceSeries,
    equity_series: PriceSeries,
    lookback_bars: int = 40,
) -> DivergenceResult:
    """Compute gold-equity return divergence.

    Formula (research doc Section 5.3):
        gold_return_N = (gold[-1] - gold[-N]) / gold[-N]
        equity_return_N = (equity[-1] - equity[-N]) / equity[-N]
        divergence = gold_return_N - equity_return_N
    """
    gold_closes = closes_as_floats(gold_series)
    equity_closes = closes_as_floats(equity_series)

    if len(gold_closes) < lookback_bars + 1:
        msg = (
            f"Gold series needs at least {lookback_bars + 1} bars, "
            f"got {len(gold_closes)}"
        )
        raise ValueError(msg)
    if len(equity_closes) < lookback_bars + 1:
        msg = (
            f"Equity series needs at least {lookback_bars + 1} bars, "
            f"got {len(equity_closes)}"
        )
        raise ValueError(msg)

    gold_start = gold_closes[-(lookback_bars + 1)]
    equity_start = equity_closes[-(lookback_bars + 1)]

    if gold_start == 0.0 or equity_start == 0.0:
        msg = "Zero start price — cannot compute returns"
        raise ValueError(msg)

    gold_return = (gold_closes[-1] - gold_start) / gold_start
    equity_return = (equity_closes[-1] - equity_start) / equity_start

    return DivergenceResult(
        gold_return=gold_return,
        equity_return=equity_return,
        divergence=gold_return - equity_return,
    )


def compute_volatility_regime(
    equity_series: PriceSeries,
    short_window: int = 20,
    long_window: int = 60,
) -> VolatilityRegimeResult:
    """Compute volatility regime (short vol / long vol ratio).

    Formula (research doc Section 5.5):
        short_vol = std(daily_returns[-short_window:]) * sqrt(252)
        long_vol = std(daily_returns[-long_window:]) * sqrt(252)
        vol_ratio = short_vol / long_vol
    """
    closes = closes_as_floats(equity_series)
    rets = daily_returns(closes)

    # Need at least long_window returns
    if len(rets) < long_window:
        msg = f"Need at least {long_window} daily returns, got {len(rets)}"
        raise ValueError(msg)

    annualize = sqrt(252)
    short_vol = rolling_std(rets, short_window) * annualize
    long_vol = rolling_std(rets, long_window) * annualize

    if long_vol == 0.0:
        msg = "Long-term volatility is zero — cannot compute ratio"
        raise ValueError(msg)

    return VolatilityRegimeResult(
        short_vol=short_vol,
        long_vol=long_vol,
        vol_ratio=short_vol / long_vol,
    )


def compute_correlation(
    bond_series: PriceSeries,
    equity_series: PriceSeries,
    window: int = 60,
    veto_threshold: float = 0.30,
) -> CorrelationResult:
    """Compute rolling bond-equity correlation for Type C guard.

    Formula (research doc Section 5.4):
        bond_returns = log_returns(bond_close[-window:])
        equity_returns = log_returns(equity_close[-window:])
        correlation = pearson(equity_returns, bond_returns)
        bond_declining = bond_close[-1] < bond_close[-window]
    """
    bond_closes = closes_as_floats(bond_series)
    equity_closes = closes_as_floats(equity_series)

    min_bars = window + 1
    if len(bond_closes) < min_bars:
        msg = f"Bond series needs at least {min_bars} bars, got {len(bond_closes)}"
        raise ValueError(msg)
    if len(equity_closes) < min_bars:
        msg = f"Equity series needs at least {min_bars} bars, got {len(equity_closes)}"
        raise ValueError(msg)

    bond_log_rets = daily_log_returns(bond_closes)
    equity_log_rets = daily_log_returns(equity_closes)

    # Use last window returns
    bond_window = bond_log_rets[-window:]
    equity_window = equity_log_rets[-window:]

    n = min(len(bond_window), len(equity_window))
    corr = pearson_correlation(bond_window[-n:], equity_window[-n:])
    correlation = corr if corr is not None else 0.0

    bond_declining = bond_closes[-1] < bond_closes[-window]

    # Count consecutive days above threshold by sliding sub-windows
    # Walk backwards from end until correlation of a sub-window drops below
    days_above = 0
    sub_size = min(window, 20)
    if len(bond_log_rets) >= sub_size and len(equity_log_rets) >= sub_size:
        for offset in range(len(bond_log_rets) - sub_size, -1, -1):
            b_sub = bond_log_rets[offset : offset + sub_size]
            e_sub = equity_log_rets[offset : offset + sub_size]
            sub_corr = pearson_correlation(b_sub, e_sub)
            if sub_corr is not None and sub_corr > veto_threshold:
                days_above += 1
            else:
                break

    return CorrelationResult(
        correlation=correlation,
        bond_declining=bond_declining,
        days_above_threshold=days_above,
    )


def compute_relative_strength(
    gold_series: PriceSeries,
    equity_series: PriceSeries,
    ma_window: int = 120,
) -> RelativeStrengthResult:
    """Compute gold/equity relative strength ratio with MA breakout.

    Formula (research doc Section 5.7):
        RS = gold_close[t] / equity_close[t]
        RS_MA = mean(RS[t-ma_window : t])
        breakout_pct = (RS / RS_MA - 1) * 100
    """
    gold_closes = closes_as_floats(gold_series)
    equity_closes = closes_as_floats(equity_series)

    if len(gold_closes) < ma_window or len(equity_closes) < ma_window:
        msg = (
            f"Need at least {ma_window} bars for RS MA, "
            f"got gold={len(gold_closes)}, equity={len(equity_closes)}"
        )
        raise ValueError(msg)

    # Compute RS ratio for the last ma_window bars
    n = min(len(gold_closes), len(equity_closes))
    rs_values: list[float] = []
    for i in range(n):
        eq = equity_closes[i]
        if eq != 0.0:
            rs_values.append(gold_closes[i] / eq)

    if len(rs_values) < ma_window:
        msg = f"Not enough valid RS values ({len(rs_values)}) for ma_window={ma_window}"
        raise ValueError(msg)

    rs_current = rs_values[-1]
    rs_ma = rolling_mean(rs_values, ma_window)
    breakout_pct = (rs_current / rs_ma - 1) * 100 if rs_ma != 0.0 else 0.0

    return RelativeStrengthResult(
        rs_current=rs_current,
        rs_ma=rs_ma,
        breakout_pct=breakout_pct,
    )


def compute_death_cross(
    equity_series: PriceSeries,
    short_window: int = 50,
    long_window: int = 200,
) -> DeathCrossResult:
    """Compute death cross (short SMA < long SMA crossover).

    Formula (research doc Section 5.6):
        sma_short = mean(close[-short_window:])
        sma_long = mean(close[-long_window:])
        bearish_regime = sma_short < sma_long
        cross_event = sma_short < sma_long AND prev_sma_short >= prev_sma_long
    """
    closes = closes_as_floats(equity_series)

    if len(closes) < long_window + 1:
        msg = f"Need at least {long_window + 1} bars for death cross, got {len(closes)}"
        raise ValueError(msg)

    # Current SMAs
    sma_short = sum(closes[-short_window:]) / short_window
    sma_long = sum(closes[-long_window:]) / long_window

    # Previous day SMAs (shift window back by 1)
    prev_short = sum(closes[-(short_window + 1) : -1]) / short_window
    prev_long = sum(closes[-(long_window + 1) : -1]) / long_window

    bearish_regime = sma_short < sma_long
    cross_event = sma_short < sma_long and prev_short >= prev_long

    return DeathCrossResult(
        sma_short=sma_short,
        sma_long=sma_long,
        bearish_regime=bearish_regime,
        cross_event=cross_event,
    )
