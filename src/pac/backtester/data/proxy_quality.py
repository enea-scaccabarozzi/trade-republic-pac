"""Proxy quality validation during overlap periods."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pac.backtester.data.models import PriceSeries

_MIN_OVERLAP_DAYS = 120  # ~6 months of trading days
_CORRELATION_WARN = 0.90
_CORRELATION_REJECT = 0.70


@dataclass(frozen=True)
class ProxyQualityReport:
    """Quality assessment for a single proxy→target handoff."""

    proxy_ticker: str
    target_ticker: str
    overlap_days: int
    correlation: float
    proxy_vol: float
    target_vol: float
    vol_ratio: float
    quality: str  # "good", "warning", "poor"
    issues: list[str] = field(default_factory=list)


def assess_proxy_quality(
    proxy_series: PriceSeries,
    target_series: PriceSeries,
) -> ProxyQualityReport:
    """Assess proxy quality by computing correlation and vol ratio during overlap.

    Both series should already be FX-converted to the same base currency.
    Uses the overlapping date range between the two series.

    Quality thresholds:
    - correlation >= 0.90 and vol_ratio in [0.7, 1.4] → "good"
    - correlation >= 0.70 → "warning"
    - correlation < 0.70 → "poor"
    """
    proxy_dates = {b.date: b for b in proxy_series.bars}
    target_dates = {b.date: b for b in target_series.bars}
    overlap_dates = sorted(set(proxy_dates) & set(target_dates))

    issues: list[str] = []

    if len(overlap_dates) < 2:
        return ProxyQualityReport(
            proxy_ticker=proxy_series.ticker,
            target_ticker=target_series.ticker,
            overlap_days=len(overlap_dates),
            correlation=0.0,
            proxy_vol=0.0,
            target_vol=0.0,
            vol_ratio=0.0,
            quality="poor",
            issues=["Insufficient overlap data (< 2 days)"],
        )

    if len(overlap_dates) < _MIN_OVERLAP_DAYS:
        issues.append(
            f"Only {len(overlap_dates)} overlap days "
            f"(recommended >= {_MIN_OVERLAP_DAYS})"
        )

    # compute daily returns over overlap
    import numpy as np

    proxy_prices = np.array([float(proxy_dates[d].close) for d in overlap_dates])
    target_prices = np.array([float(target_dates[d].close) for d in overlap_dates])

    valid = (proxy_prices[:-1] > 0) & (target_prices[:-1] > 0)
    proxy_ret = np.diff(proxy_prices) / np.where(
        proxy_prices[:-1] > 0, proxy_prices[:-1], 1.0
    )
    target_ret = np.diff(target_prices) / np.where(
        target_prices[:-1] > 0, target_prices[:-1], 1.0
    )
    proxy_returns = proxy_ret[valid].tolist()
    target_returns = target_ret[valid].tolist()

    n = len(proxy_returns)
    if n < 2:
        return ProxyQualityReport(
            proxy_ticker=proxy_series.ticker,
            target_ticker=target_series.ticker,
            overlap_days=len(overlap_dates),
            correlation=0.0,
            proxy_vol=0.0,
            target_vol=0.0,
            vol_ratio=0.0,
            quality="poor",
            issues=["Insufficient valid returns for analysis"],
        )

    # Pearson correlation (manual — avoids numpy dependency)
    mean_p = sum(proxy_returns) / n
    mean_t = sum(target_returns) / n
    cov = (
        sum(
            (p - mean_p) * (t - mean_t)
            for p, t in zip(proxy_returns, target_returns, strict=False)
        )
        / n
    )
    std_p = (sum((p - mean_p) ** 2 for p in proxy_returns) / n) ** 0.5
    std_t = (sum((t - mean_t) ** 2 for t in target_returns) / n) ** 0.5

    correlation = cov / (std_p * std_t) if std_p > 0 and std_t > 0 else 0.0

    # Annualized volatilities
    proxy_vol = std_p * math.sqrt(252)
    target_vol = std_t * math.sqrt(252)
    vol_ratio = proxy_vol / target_vol if target_vol > 0 else 0.0

    # Quality classification
    quality: str
    if correlation < _CORRELATION_REJECT:
        quality = "poor"
        issues.append(
            f"Correlation {correlation:.3f} < {_CORRELATION_REJECT} (reject threshold)"
        )
    elif correlation < _CORRELATION_WARN:
        quality = "warning"
        issues.append(
            f"Correlation {correlation:.3f} < {_CORRELATION_WARN} (warning threshold)"
        )
    else:
        quality = "good"

    if not (0.7 <= vol_ratio <= 1.4):
        issues.append(
            f"Vol ratio {vol_ratio:.2f} outside [0.7, 1.4] — consider vol scaling"
        )
        if quality == "good":
            quality = "warning"

    return ProxyQualityReport(
        proxy_ticker=proxy_series.ticker,
        target_ticker=target_series.ticker,
        overlap_days=len(overlap_dates),
        correlation=correlation,
        proxy_vol=proxy_vol,
        target_vol=target_vol,
        vol_ratio=vol_ratio,
        quality=quality,
        issues=issues,
    )
