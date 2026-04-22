"""Verify auto_adjust=True provides total return for VHGEX vs price-only for index."""

from __future__ import annotations

import yfinance as yf

tickers = {
    "^990100-USD-STRD": "MSCI World (price-return index)",
    "VHGEX": "Vanguard Global Equity (mutual fund, auto_adjust=True)",
    "SPY": "S&P 500 ETF (distributing, auto_adjust=True)",
}

print("2001-01-02 to 2009-09-24 cumulative returns:")
print(f"{'Ticker':<25} {'Type':<55} {'CumRet':>8}")
print("-" * 95)

for t, desc in tickers.items():
    tk = yf.Ticker(t)
    df = tk.history(start="2001-01-02", end="2009-09-25", auto_adjust=True)
    if df.empty:
        print(f"{t:<25} {desc:<55} NO DATA")
        continue
    first = float(df["Close"].iloc[0])
    last = float(df["Close"].iloc[-1])
    ret = (last / first - 1) * 100
    print(f"{t:<25} {desc:<55} {ret:>+7.1f}%")

print()
print("If auto_adjust works, VHGEX and SPY should show HIGHER returns")
print("than ^990100-USD-STRD (which is price-only, no dividends).")
print()
print("Expected: MSCI World price ~= -3%, with dividends ~= +15%")
print("SPY with dividends should show better than SPY price-only")
