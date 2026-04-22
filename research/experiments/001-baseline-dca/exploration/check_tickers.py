"""Quick check: which tickers have data on yfinance and from when?"""

from __future__ import annotations

import yfinance as yf
from datetime import date

CANDIDATES = {
    # Stocks — primary + proxy candidates
    "VWCE.DE": "Vanguard FTSE All-World UCITS (EUR) — PRIMARY",
    "IWDA.AS": "iShares MSCI World UCITS (EUR)",
    "^990100-USD-STRD": "MSCI World Index (USD)",
    "VHGEX": "Vanguard Global Equity Fund (USD, active)",
    "ACWI": "iShares MSCI ACWI ETF (USD)",
    "VT": "Vanguard Total World Stock ETF (USD)",
    "EFA": "iShares MSCI EAFE (USD, ex-US/Canada)",
    "SPY": "S&P 500 ETF (USD, US-only baseline)",
    "VGTSX": "Vanguard Total Intl Stock Index (USD, ex-US)",
    # Gold — primary + proxy candidates
    "SGLN.L": "iShares Physical Gold ETC (GBP) — PRIMARY",
    "GC=F": "Gold Futures (USD)",
    "GLD": "SPDR Gold Shares ETF (USD)",
    "IAU": "iShares Gold Trust (USD)",
    # Bonds — primary + proxy candidates
    "AGG": "iShares Core US Aggregate Bond (USD) — PRIMARY",
    "VBMFX": "Vanguard Total Bond Market Index (USD)",
    "BND": "Vanguard Total Bond Market ETF (USD)",
    "FBIDX": "Fidelity US Bond Index (USD)",
}

print(f"{'Ticker':<25} {'Start':<12} {'End':<12} {'Days':>6}  Description")
print("-" * 100)

for ticker, desc in CANDIDATES.items():
    try:
        data = yf.download(ticker, start="1990-01-01", end="2026-04-22", progress=False)
        if data.empty:
            print(f"{ticker:<25} {'NO DATA':<12} {'':<12} {'':>6}  {desc}")
        else:
            start = data.index[0].date()
            end = data.index[-1].date()
            days = len(data)
            print(f"{ticker:<25} {str(start):<12} {str(end):<12} {days:>6}  {desc}")
    except Exception as e:
        print(f"{ticker:<25} {'ERROR':<12} {str(e)[:50]:<50}  {desc}")
