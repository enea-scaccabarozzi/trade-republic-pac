"""Check for MSCI World Total Return variants on yfinance."""

from __future__ import annotations

import yfinance as yf

CANDIDATES = [
    "^990100-USD-STRD",
    "^990100-USD-NETR",
    "^990100-USD-GSTR",
    "^WORLD",
    "URTH",
    "SWDA.L",
]

for t in CANDIDATES:
    data = yf.download(t, start="2001-01-01", end="2010-01-01", progress=False)
    if data.empty:
        print(f"{t:<25} NO DATA")
    else:
        s = data.index[0].date()
        e = data.index[-1].date()
        first = float(data["Close"].iloc[0].item() if hasattr(data["Close"].iloc[0], 'item') else data["Close"].iloc[0])
        last = float(data["Close"].iloc[-1].item() if hasattr(data["Close"].iloc[-1], 'item') else data["Close"].iloc[-1])
        ret = (last / first - 1) * 100
        print(f"{t:<25} {s} -> {e}  first={first:.2f}  last={last:.2f}  cum_ret={ret:+.1f}%")
