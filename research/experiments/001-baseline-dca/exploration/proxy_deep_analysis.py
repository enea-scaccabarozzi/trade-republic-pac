"""Deep proxy analysis: daily vs weekly vs monthly correlation.

Cross-timezone assets (EUR vs USD close) have artificially low daily
correlation due to trading-hour misalignment. Weekly/monthly returns
wash out this noise and reveal the true tracking relationship.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from pac.backtester.data.models import DataRequest, Interval, PriceSeries
from pac.backtester.data.provider import MarketDataProvider

provider = MarketDataProvider()


def fetch(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch closing prices as pandas Series indexed by date."""
    series = provider.fetch(DataRequest(
        ticker=ticker,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        interval=Interval.DAILY,
    ))
    dates = [b.date for b in series.bars]
    closes = [float(b.close) for b in series.bars]
    return pd.Series(closes, index=pd.DatetimeIndex(dates), name=ticker)


def correlation_at_frequencies(
    s1: pd.Series, s2: pd.Series
) -> dict[str, float | int]:
    """Compute return correlation at daily, weekly, and monthly frequencies."""
    df = pd.DataFrame({s1.name: s1, s2.name: s2}).dropna()
    if len(df) < 10:
        return {"daily": 0.0, "weekly": 0.0, "monthly": 0.0, "overlap_days": 0}

    daily_ret = df.pct_change().dropna()
    daily_corr = daily_ret.corr().iloc[0, 1]

    weekly = df.resample("W-FRI").last().dropna()
    weekly_ret = weekly.pct_change().dropna()
    weekly_corr = weekly_ret.corr().iloc[0, 1] if len(weekly_ret) > 2 else 0.0

    monthly = df.resample("ME").last().dropna()
    monthly_ret = monthly.pct_change().dropna()
    monthly_corr = monthly_ret.corr().iloc[0, 1] if len(monthly_ret) > 2 else 0.0

    daily_vol1 = float(daily_ret.iloc[:, 0].std() * np.sqrt(252))
    daily_vol2 = float(daily_ret.iloc[:, 1].std() * np.sqrt(252))
    vol_ratio = daily_vol1 / daily_vol2 if daily_vol2 > 0 else 0.0

    return {
        "daily_corr": round(float(daily_corr), 4),
        "weekly_corr": round(float(weekly_corr), 4),
        "monthly_corr": round(float(monthly_corr), 4),
        "overlap_days": len(df),
        "vol_1": round(daily_vol1, 4),
        "vol_2": round(daily_vol2, 4),
        "vol_ratio": round(vol_ratio, 2),
    }


def analyze_pair(
    t1: str, t2: str, start: str, end: str, label: str
) -> dict:
    """Analyze a proxy→target pair and print results."""
    s1 = fetch(t1, start, end)
    s2 = fetch(t2, start, end)
    stats = correlation_at_frequencies(s1, s2)

    quality = "GOOD"
    if stats["monthly_corr"] < 0.70:
        quality = "POOR"
    elif stats["monthly_corr"] < 0.90:
        quality = "WARNING"

    print(f"\n{'='*65}")
    print(f"  {t1}  →  {t2}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Overlap:      {stats['overlap_days']} days")
    print(f"  Daily corr:   {stats['daily_corr']:.4f}")
    print(f"  Weekly corr:  {stats['weekly_corr']:.4f}")
    print(f"  Monthly corr: {stats['monthly_corr']:.4f}")
    print(f"  Vol ({t1}):  {stats['vol_1']:.4f}")
    print(f"  Vol ({t2}):  {stats['vol_2']:.4f}")
    print(f"  Vol ratio:    {stats['vol_ratio']:.2f}")
    print(f"  Quality:      {quality} (based on monthly corr)")

    stats["quality"] = quality
    stats["label"] = label
    return stats


def main():
    results = {}

    # ================================================================
    # STOCKS
    # ================================================================
    print("\n" + "#" * 65)
    print("# STOCKS PROXY CHAIN ANALYSIS")
    print("# Target: VWCE.DE (FTSE All-World, EUR)")
    print("#" * 65)

    # Same-currency checks first (no FX noise)
    results["stocks_msci_raw_vs_iwda"] = analyze_pair(
        "^990100-USD-STRD", "IWDA.AS",
        "2009-09-25", "2019-07-28",
        "MSCI World (USD) vs IWDA.AS (EUR) — cross-ccy, 10yr"
    )

    results["stocks_iwda_vs_vwce"] = analyze_pair(
        "IWDA.AS", "VWCE.DE",
        "2019-07-29", "2026-04-21",
        "IWDA.AS (EUR) vs VWCE.DE (EUR) — same-ccy, full overlap"
    )

    results["stocks_vhgex_vs_iwda"] = analyze_pair(
        "VHGEX", "IWDA.AS",
        "2009-09-25", "2019-07-28",
        "VHGEX (USD, active) vs IWDA.AS (EUR) — cross-ccy, 10yr"
    )

    # Compare alternatives for pre-2009 proxy
    results["stocks_msci_vs_spy"] = analyze_pair(
        "^990100-USD-STRD", "SPY",
        "2001-01-01", "2009-09-24",
        "MSCI World (USD) vs SPY (USD) — same-ccy baseline"
    )

    results["stocks_vhgex_vs_msci"] = analyze_pair(
        "VHGEX", "^990100-USD-STRD",
        "2001-01-01", "2009-09-24",
        "VHGEX (USD) vs MSCI World (USD) — same-ccy, pre-2009"
    )

    # ================================================================
    # GOLD
    # ================================================================
    print("\n" + "#" * 65)
    print("# GOLD PROXY CHAIN ANALYSIS")
    print("# Target: SGLN.L (iShares Physical Gold, GBP)")
    print("#" * 65)

    results["gold_gcf_vs_sgln"] = analyze_pair(
        "GC=F", "SGLN.L",
        "2011-04-08", "2026-04-21",
        "GC=F (USD) vs SGLN.L (GBP) — cross-ccy, full overlap"
    )

    results["gold_gld_vs_sgln"] = analyze_pair(
        "GLD", "SGLN.L",
        "2011-04-08", "2026-04-21",
        "GLD (USD) vs SGLN.L (GBP) — cross-ccy, full overlap"
    )

    results["gold_gcf_vs_gld"] = analyze_pair(
        "GC=F", "GLD",
        "2004-11-18", "2026-04-21",
        "GC=F (USD) vs GLD (USD) — same-ccy baseline"
    )

    # ================================================================
    # BONDS
    # ================================================================
    print("\n" + "#" * 65)
    print("# BONDS PROXY CHAIN ANALYSIS")
    print("# Target: AGG (iShares US Aggregate Bond, USD)")
    print("#" * 65)

    results["bonds_vbmfx_vs_agg_sameccy"] = analyze_pair(
        "VBMFX", "AGG",
        "2003-09-29", "2026-04-21",
        "VBMFX (USD) vs AGG (USD) — same-ccy, full overlap"
    )

    results["bonds_vbmfx_vs_agg_3yr"] = analyze_pair(
        "VBMFX", "AGG",
        "2003-09-29", "2006-09-30",
        "VBMFX (USD) vs AGG (USD) — same-ccy, 3yr around handoff"
    )

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n\n" + "=" * 65)
    print("SUMMARY TABLE")
    print("=" * 65)
    print(f"{'Pair':<40} {'Daily':>7} {'Weekly':>7} {'Month':>7} {'Quality'}")
    print("-" * 75)
    for key, data in results.items():
        label = key.replace("_", " ")[:39]
        d = data["daily_corr"]
        w = data["weekly_corr"]
        m = data["monthly_corr"]
        q = data["quality"]
        print(f"{label:<40} {d:>7.4f} {w:>7.4f} {m:>7.4f} {q}")

    # Save
    output = Path(__file__).resolve().parents[1] / "results" / "proxy_deep_analysis.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    main()
