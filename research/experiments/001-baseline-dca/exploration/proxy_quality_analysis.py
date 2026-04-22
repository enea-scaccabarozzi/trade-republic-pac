"""Proxy quality analysis for all 3 asset chains.

Proposed chains:
  Stocks: ^990100-USD-STRD (USD) → IWDA.AS (EUR) → VWCE.DE (EUR)
  Gold:   GC=F (USD) → SGLN.L (GBP)
  Bonds:  VBMFX (USD) → AGG (USD)

Also tests VHGEX as alternative stock proxy vs ^990100-USD-STRD.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.data.provider import MarketDataProvider, DataRequest
from pac.backtester.data.proxy_quality import assess_proxy_quality


def fetch(ticker: str, start: str, end: str) -> PriceSeries:
    provider = MarketDataProvider()
    return provider.fetch(DataRequest(
        ticker=ticker,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        interval=Interval.DAILY,
    ))


def print_report(report) -> dict:
    print(f"\n{'='*60}")
    print(f"  {report.proxy_ticker}  →  {report.target_ticker}")
    print(f"{'='*60}")
    print(f"  Overlap days:  {report.overlap_days}")
    print(f"  Correlation:   {report.correlation:.4f}")
    print(f"  Proxy vol:     {report.proxy_vol:.4f}")
    print(f"  Target vol:    {report.target_vol:.4f}")
    print(f"  Vol ratio:     {report.vol_ratio:.2f}")
    print(f"  Quality:       {report.quality.upper()}")
    if report.issues:
        for issue in report.issues:
            print(f"  ⚠ {issue}")
    return asdict(report)


def main():
    results = []

    # --- STOCKS ---
    print("\n" + "#" * 60)
    print("# STOCKS PROXY CHAIN")
    print("#" * 60)

    # Handoff 1: ^990100-USD-STRD → IWDA.AS (around 2009-09-24)
    # Overlap: both must have data in the same period
    # IWDA.AS starts 2009-09-25, so overlap with MSCI World starts there
    msci_world = fetch("^990100-USD-STRD", "2009-09-01", "2012-09-30")
    iwda = fetch("IWDA.AS", "2009-09-01", "2012-09-30")
    r = assess_proxy_quality(msci_world, iwda)
    results.append(("stocks_msci_world_to_iwda", print_report(r)))

    # Handoff 2: IWDA.AS → VWCE.DE (around 2019-07-28)
    iwda2 = fetch("IWDA.AS", "2019-07-01", "2022-07-31")
    vwce = fetch("VWCE.DE", "2019-07-01", "2022-07-31")
    r = assess_proxy_quality(iwda2, vwce)
    results.append(("stocks_iwda_to_vwce", print_report(r)))

    # Alternative: VHGEX → IWDA.AS
    vhgex = fetch("VHGEX", "2009-09-01", "2012-09-30")
    r = assess_proxy_quality(vhgex, iwda)
    results.append(("stocks_vhgex_to_iwda", print_report(r)))

    # Full overlap comparison: VHGEX vs ^990100-USD-STRD (2001-2009)
    msci_long = fetch("^990100-USD-STRD", "2001-01-01", "2009-09-24")
    vhgex_long = fetch("VHGEX", "2001-01-01", "2009-09-24")
    r = assess_proxy_quality(msci_long, vhgex_long)
    results.append(("stocks_msci_vs_vhgex_2001_2009", print_report(r)))

    # --- GOLD ---
    print("\n" + "#" * 60)
    print("# GOLD PROXY CHAIN")
    print("#" * 60)

    # GC=F → SGLN.L (around 2011-04-07)
    gc = fetch("GC=F", "2011-04-01", "2014-04-30")
    sgln = fetch("SGLN.L", "2011-04-01", "2014-04-30")
    r = assess_proxy_quality(gc, sgln)
    results.append(("gold_gcf_to_sgln", print_report(r)))

    # --- BONDS ---
    print("\n" + "#" * 60)
    print("# BONDS PROXY CHAIN")
    print("#" * 60)

    # VBMFX → AGG (around 2003-09-21)
    vbmfx = fetch("VBMFX", "2003-09-01", "2006-09-30")
    agg = fetch("AGG", "2003-09-01", "2006-09-30")
    r = assess_proxy_quality(vbmfx, agg)
    results.append(("bonds_vbmfx_to_agg", print_report(r)))

    # --- SAVE RESULTS ---
    output = Path(__file__).resolve().parents[1] / "results" / "proxy_quality.json"
    output.parent.mkdir(exist_ok=True)
    serializable = {}
    for name, data in results:
        serializable[name] = data
    output.write_text(json.dumps(serializable, indent=2, default=str))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
