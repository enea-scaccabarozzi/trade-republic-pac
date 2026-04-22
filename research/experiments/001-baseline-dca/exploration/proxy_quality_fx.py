"""Proxy quality analysis WITH FX conversion to EUR.

All series are converted to EUR before comparison, matching how the
backtester's fetch_with_proxy() actually processes proxy chains.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from pac.backtester.data.models import DataRequest, Interval, PriceSeries
from pac.backtester.data.provider import MarketDataProvider
from pac.backtester.data.fx import convert_to_eur
from pac.backtester.data.proxy_quality import assess_proxy_quality


provider = MarketDataProvider()


def fetch(ticker: str, start: str, end: str) -> PriceSeries:
    return provider.fetch(DataRequest(
        ticker=ticker,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        interval=Interval.DAILY,
    ))


def fetch_eur(ticker: str, start: str, end: str, currency: str) -> PriceSeries:
    """Fetch and convert to EUR."""
    series = fetch(ticker, start, end)
    if currency == "EUR":
        return series
    return convert_to_eur(series, currency, provider.fetch)


def print_report(report, note: str = "") -> dict:
    print(f"\n{'='*60}")
    print(f"  {report.proxy_ticker}  →  {report.target_ticker}")
    if note:
        print(f"  ({note})")
    print(f"{'='*60}")
    print(f"  Overlap days:  {report.overlap_days}")
    print(f"  Correlation:   {report.correlation:.4f}")
    print(f"  Proxy vol:     {report.proxy_vol:.4f}")
    print(f"  Target vol:    {report.target_vol:.4f}")
    print(f"  Vol ratio:     {report.vol_ratio:.2f}")
    print(f"  Quality:       {report.quality.upper()}")
    if report.issues:
        for issue in report.issues:
            print(f"  ! {issue}")
    else:
        print(f"  No issues")
    return asdict(report)


def main():
    results = {}

    # ================================================================
    # STOCKS: ^990100-USD-STRD (USD) → IWDA.AS (EUR) → VWCE.DE (EUR)
    # ================================================================
    print("\n" + "#" * 60)
    print("# STOCKS — all converted to EUR")
    print("#" * 60)

    # Handoff 1: MSCI World USD → IWDA.AS EUR (around 2009-09-24)
    msci = fetch_eur("^990100-USD-STRD", "2009-09-01", "2012-09-30", "USD")
    iwda = fetch_eur("IWDA.AS", "2009-09-01", "2012-09-30", "EUR")
    r = assess_proxy_quality(msci, iwda)
    results["stocks_h1_msci_world_to_iwda"] = print_report(
        r, "MSCI World USD→EUR vs IWDA.AS EUR, 3yr overlap"
    )

    # Handoff 2: IWDA.AS → VWCE.DE (around 2019-07-28)
    iwda2 = fetch_eur("IWDA.AS", "2019-07-01", "2022-07-31", "EUR")
    vwce = fetch_eur("VWCE.DE", "2019-07-01", "2022-07-31", "EUR")
    r = assess_proxy_quality(iwda2, vwce)
    results["stocks_h2_iwda_to_vwce"] = print_report(
        r, "IWDA.AS EUR vs VWCE.DE EUR, 3yr overlap"
    )

    # Alternative: VHGEX USD → IWDA.AS EUR
    vhgex = fetch_eur("VHGEX", "2009-09-01", "2012-09-30", "USD")
    r = assess_proxy_quality(vhgex, iwda)
    results["stocks_alt_vhgex_to_iwda"] = print_report(
        r, "VHGEX USD→EUR vs IWDA.AS EUR, 3yr overlap"
    )

    # Longer overlap: MSCI World vs IWDA.AS (full available overlap)
    msci_long = fetch_eur("^990100-USD-STRD", "2009-09-25", "2019-07-28", "USD")
    iwda_long = fetch_eur("IWDA.AS", "2009-09-25", "2019-07-28", "EUR")
    r = assess_proxy_quality(msci_long, iwda_long)
    results["stocks_h1_msci_world_to_iwda_FULL"] = print_report(
        r, "MSCI World USD→EUR vs IWDA.AS EUR, FULL 10yr overlap"
    )

    # ================================================================
    # GOLD: GC=F (USD) → SGLN.L (GBP)
    # ================================================================
    print("\n" + "#" * 60)
    print("# GOLD — all converted to EUR")
    print("#" * 60)

    gc = fetch_eur("GC=F", "2011-04-01", "2014-04-30", "USD")
    sgln = fetch_eur("SGLN.L", "2011-04-01", "2014-04-30", "GBP")
    r = assess_proxy_quality(gc, sgln)
    results["gold_h1_gcf_to_sgln"] = print_report(
        r, "GC=F USD→EUR vs SGLN.L GBP→EUR, 3yr overlap"
    )

    # Longer overlap
    gc_long = fetch_eur("GC=F", "2011-04-08", "2026-04-21", "USD")
    sgln_long = fetch_eur("SGLN.L", "2011-04-08", "2026-04-21", "GBP")
    r = assess_proxy_quality(gc_long, sgln_long)
    results["gold_h1_gcf_to_sgln_FULL"] = print_report(
        r, "GC=F USD→EUR vs SGLN.L GBP→EUR, FULL 15yr overlap"
    )

    # Alternative: GLD USD → SGLN.L GBP (GLD is an ETF, not futures)
    gld = fetch_eur("GLD", "2011-04-01", "2014-04-30", "USD")
    r = assess_proxy_quality(gld, sgln)
    results["gold_alt_gld_to_sgln"] = print_report(
        r, "GLD USD→EUR vs SGLN.L GBP→EUR, 3yr overlap"
    )

    # ================================================================
    # BONDS: VBMFX (USD) → AGG (USD)
    # ================================================================
    print("\n" + "#" * 60)
    print("# BONDS — all converted to EUR")
    print("#" * 60)

    vbmfx = fetch_eur("VBMFX", "2003-09-01", "2006-09-30", "USD")
    agg = fetch_eur("AGG", "2003-09-01", "2006-09-30", "USD")
    r = assess_proxy_quality(vbmfx, agg)
    results["bonds_h1_vbmfx_to_agg"] = print_report(
        r, "VBMFX USD→EUR vs AGG USD→EUR, 3yr overlap"
    )

    # Longer overlap
    vbmfx_long = fetch_eur("VBMFX", "2003-09-29", "2026-04-21", "USD")
    agg_long = fetch_eur("AGG", "2003-09-29", "2026-04-21", "USD")
    r = assess_proxy_quality(vbmfx_long, agg_long)
    results["bonds_h1_vbmfx_to_agg_FULL"] = print_report(
        r, "VBMFX USD→EUR vs AGG USD→EUR, FULL 22yr overlap"
    )

    # Same-currency check (no FX conversion) to isolate FX effect
    print("\n" + "#" * 60)
    print("# BONDS — same currency (USD, no FX)")
    print("#" * 60)

    vbmfx_usd = fetch("VBMFX", "2003-09-01", "2006-09-30")
    agg_usd = fetch("AGG", "2003-09-01", "2006-09-30")
    r = assess_proxy_quality(vbmfx_usd, agg_usd)
    results["bonds_h1_vbmfx_to_agg_SAME_CCY"] = print_report(
        r, "VBMFX vs AGG, both raw USD (no FX), 3yr overlap"
    )

    # --- Save ---
    output = Path(__file__).resolve().parents[1] / "results" / "proxy_quality_fx.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
