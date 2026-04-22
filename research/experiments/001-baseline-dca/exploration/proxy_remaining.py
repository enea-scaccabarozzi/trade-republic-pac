"""Complete the remaining proxy checks that errored out."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from pac.backtester.data.models import DataRequest, Interval
from pac.backtester.data.provider import MarketDataProvider

provider = MarketDataProvider()


def fetch_raw(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch via yfinance directly to avoid PriceBar validation."""
    import yfinance as yf
    data = yf.download(ticker, start=start, end=end, progress=False)
    if data.empty:
        return pd.Series(dtype=float, name=ticker)
    closes = data["Close"].squeeze()
    closes.name = ticker
    return closes


def correlation_at_frequencies(s1: pd.Series, s2: pd.Series) -> dict:
    df = pd.DataFrame({s1.name: s1, s2.name: s2}).dropna()
    if len(df) < 10:
        return {"daily_corr": 0.0, "weekly_corr": 0.0, "monthly_corr": 0.0}

    daily_ret = df.pct_change().dropna()
    daily_corr = daily_ret.corr().iloc[0, 1]

    weekly = df.resample("W-FRI").last().dropna()
    weekly_ret = weekly.pct_change().dropna()
    weekly_corr = weekly_ret.corr().iloc[0, 1] if len(weekly_ret) > 2 else 0.0

    monthly = df.resample("ME").last().dropna()
    monthly_ret = monthly.pct_change().dropna()
    monthly_corr = monthly_ret.corr().iloc[0, 1] if len(monthly_ret) > 2 else 0.0

    v1 = float(daily_ret.iloc[:, 0].std() * np.sqrt(252))
    v2 = float(daily_ret.iloc[:, 1].std() * np.sqrt(252))

    return {
        "daily_corr": round(float(daily_corr), 4),
        "weekly_corr": round(float(weekly_corr), 4),
        "monthly_corr": round(float(monthly_corr), 4),
        "overlap_days": len(df),
        "vol_1": round(v1, 4),
        "vol_2": round(v2, 4),
        "vol_ratio": round(v1 / v2 if v2 > 0 else 0, 2),
    }


def analyze(t1: str, t2: str, start: str, end: str, label: str) -> dict:
    s1 = fetch_raw(t1, start, end)
    s2 = fetch_raw(t2, start, end)
    stats = correlation_at_frequencies(s1, s2)

    quality = "GOOD"
    if stats["monthly_corr"] < 0.70:
        quality = "POOR"
    elif stats["monthly_corr"] < 0.90:
        quality = "WARNING"

    print(f"\n{'='*65}")
    print(f"  {t1}  ->  {t2}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Overlap:      {stats['overlap_days']} days")
    print(f"  Daily corr:   {stats['daily_corr']:.4f}")
    print(f"  Weekly corr:  {stats['weekly_corr']:.4f}")
    print(f"  Monthly corr: {stats['monthly_corr']:.4f}")
    print(f"  Vol ratio:    {stats['vol_ratio']:.2f}")
    print(f"  Quality:      {quality}")

    stats["quality"] = quality
    return stats


def main():
    results = {}

    print("# GOLD — same currency baseline")
    results["gold_gcf_vs_gld_sameccy"] = analyze(
        "GC=F", "GLD", "2004-11-18", "2026-04-21",
        "GC=F (USD) vs GLD (USD) — same-ccy, full overlap"
    )

    print("\n# BONDS — same currency")
    results["bonds_vbmfx_vs_agg_full"] = analyze(
        "VBMFX", "AGG", "2003-09-29", "2026-04-21",
        "VBMFX (USD) vs AGG (USD) — same-ccy, full overlap"
    )

    results["bonds_vbmfx_vs_agg_3yr"] = analyze(
        "VBMFX", "AGG", "2003-09-29", "2006-09-30",
        "VBMFX (USD) vs AGG (USD) — same-ccy, 3yr handoff"
    )

    # Check how early GC=F data starts reliably
    print("\n# GOLD — coverage check")
    gc = fetch_raw("GC=F", "2000-01-01", "2002-12-31")
    if not gc.empty:
        print(f"  GC=F earliest: {gc.index[0].date()}, {len(gc)} bars")
    else:
        print("  GC=F: no data before 2002")

    output = Path(__file__).resolve().parents[1] / "results" / "proxy_remaining.json"
    output.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    main()
