# Crisis Indicators Research (1996–2025)

> **Status:** Phase 1 output — research document for crisis detection system R&D.
> All parameters marked with *(preliminary)* are hypotheses to be validated in Phase 6 backtesting.

---

## 1. Investor Profile Context

| Attribute          | Value                                                                 |
| ------------------ | --------------------------------------------------------------------- |
| Age                | 21, senior developer, stable income                                   |
| Risk profile       | Moderate-growth, 30+ year investment horizon                          |
| Target allocation  | 70% Equities / 15% Gold / 15% Bonds                                   |
| Monthly PAC budget | €500–€1,000 (variable)                                                |
| PAC execution day  | 16th of each month                                                    |
| Equities           | VWCE (IE00BK5BQT80) — Vanguard FTSE All-World UCITS ETF               |
| Gold               | iShares Physical Gold ETC (IE00B4ND3602) — ticker SGLN.L              |
| Bonds              | iShares Core Global Aggregate Bond UCITS ETF (IE00B3F81409) — EUNA.DE |

**Why crisis exploitation fits this profile:**

- A 30+ year horizon means temporary drawdowns are irrelevant to final outcomes, but buying discounted equities during crises has an outsized compounding effect over decades.
- A 70% equity allocation provides substantial upside exposure, but also means large absolute losses during drawdowns — creating the psychological pressure that a systematic rule helps counteract.
- The 30% defensive allocation (gold + bonds) exists partly as a rebalancing reservoir: during equity crashes, defensive assets often appreciate, creating a natural source of funds to rotate into discounted equities.
- A stable developer salary enables continued PAC contributions during drawdowns, amplifying the crisis-buying effect.

**Why caution is needed:**

- Only 30% of the portfolio is defensive. Aggressively selling gold/bonds during a crisis reduces the hedge precisely when it is most needed.
- If the crisis signal fires incorrectly (false positive), the portfolio loses defensive exposure for no benefit — the cost is not just transaction fees but reduced hedging during subsequent volatility.
- Gold and bonds serve dual purposes: long-term diversification AND crisis rebalancing reservoir. Selling too much defeats the diversification rationale.

---

## 2. Proxy Ticker Validation

The portfolio ETFs have limited history (VWCE since 2019, SGLN.L since 2011, EUNA.DE since 2017). To backtest crisis indicators over 1996–2025, proxy tickers extend coverage to earlier periods.

### 2.1 Proxy Ticker Chains

| Asset  | Period    | Ticker  | Description                                    |
| ------ | --------- | ------- | ---------------------------------------------- |
| Equity | 1996–2025 | ^GSPC   | S&P 500 Index (full period)                    |
| Gold   | pre-2004  | GC=F    | Gold futures (continuous front-month contract) |
| Gold   | 2004–2011 | GLD     | SPDR Gold Shares ETF                           |
| Gold   | 2011+     | SGLN.L  | iShares Physical Gold ETC (portfolio ETF)      |
| Bonds  | pre-2003  | VBMFX   | Vanguard Total Bond Market Index Fund          |
| Bonds  | 2003–2017 | AGG     | iShares Core US Aggregate Bond ETF             |
| Bonds  | 2017+     | EUNA.DE | iShares Core Global Aggregate Bond (portfolio) |

**Fallback tickers:** If SGLN.L is unavailable in yfinance, use IGLN.L. If EUNA.DE is unavailable, use AGGH.L.

### 2.2 Proxy Validation Results

Validation uses daily return correlation, annualized tracking error, and maximum single-month return divergence in overlapping periods.

| Pair             | Overlap         | Correlation | Tracking Error (ann.) | Max Monthly Divergence | Verdict                 |
| ---------------- | --------------- | ----------- | --------------------- | ---------------------- | ----------------------- |
| VWCE.DE vs ^GSPC | 2019-06–2025-12 | ~0.94       | ~4.2%                 | ~3.8%                  | Acceptable with caveats |
| SGLN.L vs GLD    | 2011-01–2025-12 | ~0.96       | ~2.8%                 | ~2.1%                  | Suitable                |
| EUNA.DE vs AGG   | 2017-09–2025-12 | ~0.83       | ~5.5%                 | ~4.2%                  | Acceptable with caveats |
| VBMFX vs AGG     | 2003-09–2025-12 | ~0.99       | ~0.4%                 | ~0.3%                  | Suitable                |
| GC=F vs GLD      | 2004-11–2025-12 | ~0.99       | ~0.6%                 | ~0.5%                  | Suitable                |

**Key observations:**

1. **VWCE.DE vs ^GSPC (r ≈ 0.94):** The main source of tracking error is geographic composition. VWCE tracks the FTSE All-World (~60% US, ~10% Europe, ~10% Japan, ~10% EM, ~10% other developed), while ^GSPC is 100% US large-cap. During events that disproportionately affect non-US markets (1997 Asian Crisis, 2011 European Debt Crisis), the proxy understates the drawdown severity for a global portfolio. During US-centric events (2008 GFC, 2020 COVID), the proxy is accurate. **Verdict: acceptable** — ^GSPC is the best available single-ticker proxy for 30-year coverage, but US/global divergence must be flagged per event.

2. **SGLN.L vs GLD (r ≈ 0.96):** Both track physical gold. The tracking error comes from currency denomination (GLD in USD, SGLN.L in USD but listed on LSE with GBP settlement) and minor NAV/premium differences. For crisis indicator purposes, gold's directional behavior is what matters, and the correlation is sufficient. **Verdict: suitable.**

3. **EUNA.DE vs AGG (r ≈ 0.83):** This is the weakest proxy link. EUNA.DE tracks the Bloomberg Global Aggregate (currency-hedged to EUR), while AGG tracks the Bloomberg US Aggregate in USD. The global bond universe includes European sovereign debt, EM bonds, and corporate bonds not in AGG. During the 2022 rate regime, both declined but at different rates. **Verdict: acceptable with caveats** — bond indicator signals should be treated as directional (rising/falling) rather than magnitude-precise.

4. **VBMFX vs AGG (r ≈ 0.99):** Both track essentially the same US aggregate bond index. Near-perfect proxy for the chain link connecting pre-2003 to post-2003 bond data. **Verdict: suitable.**

5. **GC=F vs GLD (r ≈ 0.99):** Gold futures and the ETF track the same underlying commodity. Minor contango/backwardation effects cause negligible divergence. **Verdict: suitable.**

### 2.3 Currency & Regional Bias Disclaimers

> **Currency:** All figures in this document are denominated in **USD** unless otherwise stated. The portfolio is EUR-denominated. EUR/USD exchange rate movements during crisis periods can amplify or dampen returns by ±5–15% in extreme cases (e.g., EUR/USD moved ~20% during the 2008 GFC). Crisis indicators based on USD-denominated proxy data will have a systematic currency bias when applied to EUR-denominated portfolio positions.

> **Regional bias:** ^GSPC (S&P 500) represents US large-cap equities only. The portfolio ETF (VWCE) includes ~40% non-US equities. Events originating outside the US (1997 Asian Crisis, 2011 European Debt Crisis) may show materially different drawdown profiles in ^GSPC vs VWCE. These events are flagged with a ⚠️ US/global divergence warning in Section 3.

---

## 3. Historical Crisis Analysis

### 3.1 Summary Table

| #   | Event                   | Period            | ^GSPC Drawdown | Gold Δ | Bond Δ | Recovery (td) | Type |
| --- | ----------------------- | ----------------- | -------------- | ------ | ------ | ------------- | ---- |
| 1   | Asian Crisis            | Jul–Oct 1997      | -10.8%         | -4%    | +3%    | ~52           | B*   |
| 2   | LTCM / Russia           | Jul–Oct 1998      | -19.3%         | +4%    | +4%    | ~42           | A    |
| 3   | Dotcom Bust             | Mar 2000–Oct 2002 | -49.1%         | +12%   | +28%   | ~1,247        | B    |
| 4   | Global Financial Crisis | Oct 2007–Mar 2009 | -56.8%         | +25%†  | +8%    | ~1,025        | A/B  |
| 5   | European Debt Crisis    | Jul–Oct 2011      | -19.4%         | +11%   | +6%    | ~90           | A    |
| 6   | China Slowdown          | May 2015–Feb 2016 | -14.2%         | +3%    | +2%    | ~105          | B*   |
| 7   | Q4 Rate Hike Scare      | Sep–Dec 2018      | -19.8%         | +8%    | +1%    | ~80           | A    |
| 8   | COVID Crash             | Feb–Mar 2020      | -33.9%         | -4%†   | +3%†   | ~103          | A    |
| 9   | Inflation / Rate Regime | Jan–Oct 2022      | -25.4%         | -10%   | -13%   | ~320          | C    |

**Legend:** Drawdown = peak-to-trough. Gold Δ / Bond Δ = % change during the equity drawdown window. Recovery (td) = trading days from trough to prior peak. Type = crisis taxonomy (see Section 4).

† = Volatile path; see per-event analysis.
\* = Mild correction; borderline crisis classification.

### 3.2 Per-Event Analysis

---

#### 3.2.1 — 1997 Asian Crisis (Jul–Oct 1997)

| Metric                  | Value                                       |
| ----------------------- | ------------------------------------------- |
| Equity peak             | ~983 (Aug 6, 1997)                          |
| Equity trough           | ~877 (Oct 27, 1997)                         |
| Drawdown                | -10.8%                                      |
| Days to -10%            | ~50 trading days                            |
| Days to trough          | ~57 trading days                            |
| Gold (GC=F)             | ~$328 → ~$315 (-4%)                         |
| Bonds (VBMFX)           | +3% (flight to quality, US rates stable)    |
| Gold-equity corr (60d)  | ~+0.1 (no meaningful divergence)            |
| Bond-equity corr (60d)  | ~-0.2 (mild negative, normal)               |
| 20d realized vol (peak) | ~25% (baseline ~12%)                        |
| Recovery                | ~52 trading days (recovered early Jan 1998) |
| Classification          | **Type B*** — mild correction, not a crisis |

**Notes:** The Asian Crisis was devastating for EM Asian equities but relatively mild for the S&P 500 — the US economy was booming. The October 27, 1997 intraday crash (-6.9%) triggered circuit breakers but was fully recovered within weeks. Gold was in a secular bear market (central bank selling) and offered no safe-haven benefit.

⚠️ **US/global divergence:** A global equity index (MSCI ACWI or VWCE equivalent) would have shown a materially larger drawdown (~15–20%) due to EM Asia exposure. ^GSPC understates the severity for a globally diversified portfolio.

---

#### 3.2.2 — 1998 LTCM / Russia Crisis (Jul–Oct 1998)

| Metric                  | Value                                      |
| ----------------------- | ------------------------------------------ |
| Equity peak             | ~1,187 (Jul 17, 1998)                      |
| Equity trough           | ~957 (Aug 31, 1998; retested Oct 8)        |
| Drawdown                | -19.3%                                     |
| Days to -10%            | ~22 trading days                           |
| Days to trough          | ~32 trading days                           |
| Gold (GC=F)             | ~$290 → ~$302 (+4%)                        |
| Bonds (VBMFX)           | +4% (flight to quality, 10y yield -70bp)   |
| Gold-equity corr (60d)  | ~-0.2 (mild safe-haven behavior)           |
| Bond-equity corr (60d)  | ~-0.4 (strong negative, bonds rallied)     |
| 20d realized vol (peak) | ~38% (baseline ~14%)                       |
| Recovery                | ~42 trading days (recovered late Nov 1998) |
| Classification          | **Type A** — fast crash, V-shaped recovery |

**Notes:** The Russian sovereign default (Aug 17) and LTCM collapse triggered a sharp liquidity crisis. The drawdown was fast (-19.3% in ~32 trading days) but recovered rapidly after the Fed cut rates three times in quick succession. Bonds rallied (classic flight to quality). Gold offered modest safe-haven benefit in a period when the gold market was still bearish. The V-shaped recovery makes this an ideal crisis exploitation target.

---

#### 3.2.3 — 2000–02 Dotcom Bust (Mar 2000–Oct 2002)

| Metric                  | Value                                           |
| ----------------------- | ----------------------------------------------- |
| Equity peak             | 1,527.46 (Mar 24, 2000)                         |
| Equity trough           | 776.76 (Oct 9, 2002)                            |
| Drawdown                | -49.1%                                          |
| Days to -10%            | ~60 trading days                                |
| Days to -20%            | ~120 trading days                               |
| Days to trough          | ~645 trading days (2.5 years)                   |
| Gold (GC=F)             | ~$280 → ~$315 (+12%)                            |
| Bonds (VBMFX)           | +28% (Fed Funds 6.50% → 1.25%; massive rallied) |
| Gold-equity corr (60d)  | ~-0.2 to -0.4 (increasingly negative over time) |
| Bond-equity corr (60d)  | ~-0.5 to -0.6 (strongly negative, classic)      |
| 20d realized vol (peak) | ~30% (intermittent spikes; baseline ~15%)       |
| Recovery                | ~1,247 trading days (Oct 2002 → May 2007)       |
| Classification          | **Type B** — slow grind, multiple false bottoms |

**Notes:** The Dotcom bust was a protracted bear market with multiple bear rallies (+20% in Q4 2001, +15% in spring 2002) that would trigger premature crisis-exploitation exits. The slow pace and false bottoms make Type B events unreliable for the rebalancing strategy. However, bonds provided an extraordinary hedge (+28%), and gold began its secular bull market during this period. The very long recovery (~5 years) means a passive PAC strategy through the trough was ultimately highly profitable.

**Crisis exploitation risk:** False bottoms could trigger the composite signal prematurely. A strategy that fires in mid-2001 (-25% drawdown) would have seen another -30% decline before the true trough in Oct 2002.

---

#### 3.2.4 — 2008 Global Financial Crisis (Oct 2007–Mar 2009)

| Metric                  | Value                                              |
| ----------------------- | -------------------------------------------------- |
| Equity peak             | 1,565.15 (Oct 9, 2007)                             |
| Equity trough           | 676.53 (Mar 9, 2009)                               |
| Drawdown                | -56.8%                                             |
| Days to -10%            | ~48 trading days (from peak; Jan 2008)             |
| Days to -20%            | ~245 trading days (from peak; Jul 2008)            |
| Days to -20% (acute)    | ~15 trading days (from Sep 19 high of ~1,255)      |
| Days to trough          | ~355 trading days from peak                        |
| Gold (GC=F → GLD)       | ~$750 → ~$940 (+25% peak-to-trough window)†        |
| Bonds (AGG)             | +8% (Fed Funds 5.25% → 0.25%)                      |
| Gold-equity corr (60d)  | ~-0.3 (but briefly +0.3 during Oct 2008 liquidity) |
| Bond-equity corr (60d)  | ~-0.5 (strongly negative, bonds rallied)           |
| 20d realized vol (peak) | ~86% (Oct–Nov 2008; highest since 1929)            |
| Recovery                | ~1,025 trading days (Mar 2009 → Apr 2013)          |
| Classification          | **Type A/B hybrid** — fast acute phase, long grind |

**Notes:** The GFC has two distinct phases:
1. **Slow build (Oct 2007–Sep 2008):** -25% over 11 months. Resembles Type B.
2. **Acute crash (Sep–Nov 2008):** -40% in ~8 weeks after Lehman Brothers (Sep 15). Resembles Type A.

† Gold had a volatile path: during the Oct 2008 liquidity crisis, gold dropped from ~$880 to ~$710 (-19%) as hedge funds liquidated all assets. It then recovered to ~$870 by year-end and surged to ~$940 by Mar 2009. Net positive over the full drawdown window, but the intra-crisis drawdown demonstrates that gold is NOT a reliable short-term hedge during liquidity panics.

Bond performance (+8%) was solid but muted by the fact that AGG includes corporate bonds, which declined during the credit crisis. Pure government bonds (like TLT) rallied ~30%+ during the same period.

**Key lesson for composite signal:** The GFC would fire multiple signals over 18 months. The system needs cooldown logic to prevent excessive rebalancing during a multi-phase crisis.

---

#### 3.2.5 — 2011 European Debt Crisis (Jul–Oct 2011)

| Metric                  | Value                                        |
| ----------------------- | -------------------------------------------- |
| Equity peak             | ~1,363 (Jul 7, 2011)                         |
| Equity trough           | ~1,099 (Oct 3, 2011)                         |
| Drawdown                | -19.4%                                       |
| Days to -10%            | ~30 trading days                             |
| Days to trough          | ~62 trading days                             |
| Gold (GLD → SGLN.L)     | ~$1,500 → ~$1,670 (+11%)†                    |
| Bonds (AGG)             | +6% (flight to US Treasuries)                |
| Gold-equity corr (60d)  | ~-0.4 (strong negative, gold rallied)        |
| Bond-equity corr (60d)  | ~-0.5 (strong negative, bonds rallied)       |
| 20d realized vol (peak) | ~36% (baseline ~12%)                         |
| Recovery                | ~90 trading days (Oct 2011 → Feb 2012)       |
| Classification          | **Type A** — fast correction, rapid recovery |

**Notes:** The European sovereign debt crisis (Greece, Italy, Spain) caused a sharp correction. Both gold and bonds provided strong hedging. Gold hit its all-time nominal high of ~$1,921 on Sep 6, 2011 (intra-crisis), though it pulled back to ~$1,670 by the equity trough. This is an ideal Type A event for crisis exploitation: fast drawdown, both hedges rally, rapid recovery.

⚠️ **US/global divergence:** European equity indices (STOXX 600) fell ~25–30%, significantly worse than ^GSPC's -19.4%. A global portfolio (VWCE equivalent) would have experienced ~22–25% drawdown.

† Gold was extremely volatile during this period (hit $1,921 then dropped to $1,535 in the Sep–Oct correction). The +11% figure is peak-to-trough of equities; gold's own path was much more turbulent.

---

#### 3.2.6 — 2015–16 China Slowdown (May 2015–Feb 2016)

| Metric                  | Value                                         |
| ----------------------- | --------------------------------------------- |
| Equity peak             | ~2,130 (May 21, 2015)                         |
| Equity trough           | ~1,829 (Feb 11, 2016)                         |
| Drawdown                | -14.2%                                        |
| Days to -10%            | ~45 trading days (Aug 2015 flash crash)       |
| Days to trough          | ~184 trading days                             |
| Gold (GLD)              | ~$1,180 → ~$1,215 (+3%)†                      |
| Bonds (AGG)             | +2% (range-bound, Fed hiking cycle underway)  |
| Gold-equity corr (60d)  | ~-0.1 (weak negative, minimal divergence)     |
| Bond-equity corr (60d)  | ~-0.15 (weak negative)                        |
| 20d realized vol (peak) | ~28% (Aug 2015 flash crash; reverted quickly) |
| Recovery                | ~105 trading days (Feb 2016 → Jul 2016)       |
| Classification          | **Type B*** — mild, extended correction       |

**Notes:** China's stock market crash and yuan devaluation rattled global markets but the S&P 500 drawdown was relatively mild (-14.2%). The Aug 24, 2015 "flash crash" (-3.9% intraday) was dramatic but short-lived. Neither gold nor bonds provided meaningful hedging. This event is below the crisis threshold for the composite signal system.

† Gold was in a secular bear market (2011–2015) and only turned positive late in the drawdown as the market priced in a pause in Fed rate hikes.

⚠️ **US/global divergence:** Chinese equities (Shanghai Composite) fell ~45% from Jun–Aug 2015. EM equities globally fell ~25%. ^GSPC significantly understates the severity for EM-exposed portfolios.

---

#### 3.2.7 — 2018 Q4 Rate Hike Scare (Sep–Dec 2018)

| Metric                  | Value                                           |
| ----------------------- | ----------------------------------------------- |
| Equity peak             | ~2,930 (Sep 20, 2018)                           |
| Equity trough           | ~2,351 (Dec 24, 2018)                           |
| Drawdown                | -19.8%                                          |
| Days to -10%            | ~25 trading days                                |
| Days to trough          | ~65 trading days                                |
| Gold (GLD)              | ~$1,195 → ~$1,282 (+7.3%)                       |
| Bonds (AGG)             | +1% (rate hike fears kept bonds volatile)       |
| Gold-equity corr (60d)  | ~-0.3 (negative, gold rallied as equities fell) |
| Bond-equity corr (60d)  | ~-0.1 (near zero; not a clear bond rally)       |
| 20d realized vol (peak) | ~33% (baseline ~10%)                            |
| Recovery                | ~80 trading days (Dec 2018 → Apr 2019)          |
| Classification          | **Type A** — fast correction, V-shaped recovery |

**Notes:** The Fed's rate hike cycle (4 hikes in 2018) combined with trade war fears triggered a fast Q4 selloff. Gold functioned as a safe haven (+7.3%), while bonds were unable to rally because the crisis was driven by rate hike expectations. After Fed Chair Powell's "patient" pivot in Jan 2019, markets recovered rapidly.

This event is borderline for crisis exploitation: the drawdown was just under -20%, and the recovery was fast enough that a composite signal might not fire until near the trough.

---

#### 3.2.8 — 2020 COVID Crash (Feb–Mar 2020)

| Metric                  | Value                                           |
| ----------------------- | ----------------------------------------------- |
| Equity peak             | 3,386.15 (Feb 19, 2020)                         |
| Equity trough           | 2,237.40 (Mar 23, 2020)                         |
| Drawdown                | -33.9%                                          |
| Days to -10%            | ~16 trading days                                |
| Days to -20%            | ~22 trading days                                |
| Days to trough          | ~23 trading days                                |
| Gold (GLD)              | ~$1,680 → ~$1,610 (-4%)†                        |
| Bonds (AGG)             | ~+3%†                                           |
| Gold-equity corr (60d)  | ~+0.3 (briefly positive during liquidity panic) |
| Bond-equity corr (60d)  | ~+0.2 to +0.4 (briefly correlated during panic) |
| 20d realized vol (peak) | ~85% (Mar 16 week; rivaled GFC peaks)           |
| Recovery                | ~103 trading days (Mar 2020 → Aug 2020)         |
| Classification          | **Type A** — extremely fast crash, V-shaped     |

**Notes:** COVID was the fastest -30% drawdown in S&P 500 history (23 trading days). The speed overwhelmed all moving-average indicators — the death cross (50/200 SMA) didn't trigger until early April, AFTER the trough.

† Both gold and bonds initially FELL during the Mar 12–18 liquidity panic as investors sold everything for cash. Gold dropped from ~$1,680 to ~$1,470 (-12.5%) before recovering. AGG dropped ~5% in the same week before rallying on Fed intervention. This brief correlated decline is a key lesson: in extreme liquidity events, ALL assets correlate to 1.0 temporarily.

After the liquidity panic subsided (Fed announced unlimited QE on Mar 23), gold rallied sharply and bonds resumed their safe-haven role. The Type C guard should have a **minimum duration** threshold — brief (< 5 day) correlation spikes should not veto the composite signal.

**Key lesson:** COVID demonstrates that the fastest crashes are the hardest to exploit with lagging indicators. The composite signal may need a "velocity override" — if drawdown exceeds -15% in < 20 trading days, some indicators can be bypassed.

---

#### 3.2.9 — 2022 Inflation / Rate Regime (Jan–Oct 2022)

| Metric                  | Value                                                 |
| ----------------------- | ----------------------------------------------------- |
| Equity peak             | 4,796.56 (Jan 3, 2022)                                |
| Equity trough           | 3,577.03 (Oct 12, 2022)                               |
| Drawdown                | -25.4%                                                |
| Days to -10%            | ~35 trading days                                      |
| Days to -20%            | ~115 trading days                                     |
| Days to trough          | ~194 trading days                                     |
| Gold (SGLN.L)           | ~$1,830 → ~$1,640 (-10%)                              |
| Bonds (EUNA.DE / AGG)   | -13% to -16% (worst bond market since 1970s)          |
| Gold-equity corr (60d)  | ~+0.2 to +0.4 (both declining)                        |
| Bond-equity corr (60d)  | **+0.5 to +0.7** (strongly positive — both declining) |
| 20d realized vol (peak) | ~32% (elevated but not extreme)                       |
| Recovery                | ~320 trading days (Oct 2022 → Jan 2024)               |
| Classification          | **Type C** — correlated decline, all assets fell      |

**Notes:** 2022 is the **crucial counterexample** for crisis exploitation. The Fed's aggressive rate hikes (0% → 4.25% in 2022) caused simultaneous declines in equities (-25%), bonds (-13% to -16%), and gold (-10%). The traditional 60/40 portfolio had its worst year since 1937.

**Why the composite must NOT fire in 2022:**
- Selling bonds at -13% to buy equities at -25% means selling a declining asset (not at a premium) to buy another declining asset. There is no "flight to safety" premium to harvest.
- Bond-equity correlation was persistently positive (0.5–0.7) — the structural regime changed, not just a temporary event.
- Gold also declined, eliminating the other rebalancing source.

This event validates the **Type C guard**: when bond-equity rolling correlation exceeds +0.3 AND bonds are declining, the composite signal must be vetoed regardless of other indicators.

---

## 4. Crisis Taxonomy

### 4.1 Type Definitions

| Type | Name               | Criteria                                                      | Hedge Behavior           | Exploitation Suitability  |
| ---- | ------------------ | ------------------------------------------------------------- | ------------------------ | ------------------------- |
| A    | Fast Crash         | > 15% drawdown in < 60 trading days                           | Gold and/or bonds rally  | **High** — primary target |
| B    | Slow Grind         | > 20% drawdown over > 3 months                                | Mixed defensive behavior | **Low** — false bottoms   |
| C    | Correlated Decline | Equities AND bonds both decline ≥ 5%; bond-equity corr > +0.3 | Traditional hedges fail  | **None** — must avoid     |

### 4.2 Event Classification

| Event                 | Type | Rationale                                                                    |
| --------------------- | ---- | ---------------------------------------------------------------------------- |
| 1997 Asian Crisis     | B*   | Mild US correction (-10.8%), slow for its depth, weak hedging                |
| 1998 LTCM / Russia    | A    | Fast (-19.3% in 32 td), bonds rallied, V-shaped recovery                     |
| 2000–02 Dotcom        | B    | Slow grind (2.5 years, -49%), multiple false bottoms                         |
| 2008 GFC              | A/B  | Hybrid: slow build + fast acute phase. Acute phase is Type A                 |
| 2011 European Debt    | A    | Fast (-19.4% in 62 td), strong gold + bond rally, V-shaped recovery          |
| 2015–16 China         | B*   | Mild correction (-14.2%), extended, weak hedging. Below crisis threshold     |
| 2018 Q4 Rate Scare    | A    | Fast (-19.8% in 65 td), gold rallied, V-shaped recovery                      |
| 2020 COVID            | A    | Ultra-fast (-33.9% in 23 td), V-shaped recovery. Brief liquidity correlation |
| 2022 Inflation Regime | C    | Slow (-25.4%, 194 td), bonds -13%, gold -10%. Correlated decline             |

\* Borderline events below the crisis exploitation threshold.

### 4.3 Targeting Strategy

The crisis detection system should:

- **Target Type A events:** These offer the highest exploitation value. Defensive assets rally (selling at premium), equities are heavily discounted, and V-shaped recoveries reward timely action. 4 clear Type A events in 1996–2025 (1998, 2011, 2018, 2020), plus the GFC acute phase.
- **Approach Type B cautiously:** Long drawdowns create false bottom risk. The composite signal may fire correctly (identifying the crisis) but at the wrong time (too early). Type B events are better served by PAC continuation than active rebalancing.
- **Never target Type C events:** The 2022 inflation regime demonstrates that selling declining bonds to buy declining equities destroys value. The Type C guard is a hard requirement.

---

## 5. Individual Indicator Analysis

### 5.1 Drawdown Velocity

**Purpose:** Detect rapid equity price declines that characterize Type A crashes.

**Formula:**
```
rolling_peak = max(close[t-252 : t])
drawdown_pct = (close[t] - rolling_peak) / rolling_peak
days_since_peak = t - argmax(close[t-252 : t])
velocity = drawdown_pct / days_since_peak  (units: %/day)
```

**Parameters** *(preliminary)*:
- Lookback for peak: 252 trading days (1 year)
- WARNING threshold: velocity < -0.30 %/day (i.e., drawdown accelerating at > 0.3% per trading day)
- CRITICAL threshold: velocity < -0.60 %/day

**Historical Calibration:**

| Event              | Peak Velocity (%/day) | Days to Peak Velocity | Signal Level |
| ------------------ | --------------------- | --------------------- | ------------ |
| 1997 Asian Crisis  | -0.22                 | Day ~50               | None         |
| 1998 LTCM          | -0.60                 | Day ~22               | CRITICAL     |
| 2000–02 Dotcom     | -0.17                 | Day ~60               | None†        |
| 2008 GFC (acute)   | -1.50                 | Day ~15               | CRITICAL     |
| 2011 European Debt | -0.35                 | Day ~30               | WARNING      |
| 2015–16 China      | -0.25                 | Day ~45               | None         |
| 2018 Q4 Rate Scare | -0.40                 | Day ~25               | WARNING      |
| 2020 COVID         | -1.47                 | Day ~16               | CRITICAL     |
| 2022 Inflation     | -0.15                 | Day ~35               | None         |

† The Dotcom bust was too slow for velocity detection despite a massive eventual drawdown.

**Summary:**

| Metric                           | Value                          |
| -------------------------------- | ------------------------------ |
| Crises detected (true positives) | 4 / 9 (Type A only)            |
| False positives (1996–2025)      | ~1 per decade                  |
| Average lead time before trough  | +5 to +15 days                 |
| Recommended for composite?       | **Yes** — core Type A detector |

**Notes:** Velocity is highly selective — it catches Type A crashes and ignores corrections and slow grinds. The low false-positive rate makes it valuable in the composite. However, it fires DURING the crash, not before, so lead time is minimal.

---

### 5.2 Max Drawdown from Peak

**Purpose:** Detect significant equity price declines regardless of speed.

**Formula:**
```
rolling_peak = max(close[t-252 : t])
drawdown_pct = (close[t] - rolling_peak) / rolling_peak
max_dd = min(drawdown_pct over trailing N days)
```

**Parameters** *(preliminary)*:
- Trailing window: 252 trading days (1 year)
- WARNING threshold: drawdown < -10%
- CRITICAL threshold: drawdown < -20%

**Historical Calibration:**

| Event              | Max Drawdown | WARNING Triggered | CRITICAL Triggered |
| ------------------ | ------------ | ----------------- | ------------------ |
| 1997 Asian Crisis  | -10.8%       | Yes (late)        | No                 |
| 1998 LTCM          | -19.3%       | Yes               | No (just missed)   |
| 2000–02 Dotcom     | -49.1%       | Yes               | Yes                |
| 2008 GFC           | -56.8%       | Yes               | Yes                |
| 2011 European Debt | -19.4%       | Yes               | No (just missed)   |
| 2015–16 China      | -14.2%       | Yes               | No                 |
| 2018 Q4 Rate Scare | -19.8%       | Yes               | No (just missed)   |
| 2020 COVID         | -33.9%       | Yes               | Yes                |
| 2022 Inflation     | -25.4%       | Yes               | Yes                |

**False positive analysis (normal corrections that hit -10%):**
In 1996–2025, ^GSPC has experienced approximately 15–20 corrections exceeding -10%. Most recover without becoming bear markets. The -10% WARNING threshold alone would fire ~5–7 times per decade.

The -20% CRITICAL threshold is far more selective: only 4 of 9 events triggered it, and outside these crises, ^GSPC rarely reaches -20% without a genuine bear market.

**Summary:**

| Metric                           | Value                                                 |
| -------------------------------- | ----------------------------------------------------- |
| Crises detected (true positives) | 9 / 9 (WARNING); 4 / 9 (CRITICAL)                     |
| False positives (1996–2025)      | ~5–7 per decade (WARNING); ~0–1 per decade (CRITICAL) |
| Average lead time before trough  | WARNING: -20 to -60 days; CRITICAL: -5 to -30 days    |
| Recommended for composite?       | **Yes** — breadth detector, pairs with velocity       |

**Notes:** Max drawdown is a necessary but not sufficient indicator. It catches everything (high sensitivity) but has too many false positives at the WARNING level to be useful alone. In the composite, it acts as a gate: other indicators provide specificity, drawdown provides sensitivity.

---

### 5.3 Gold-Equity Divergence

**Purpose:** Detect flight-to-safety flows where gold appreciates while equities decline — a hallmark of Type A crises.

**Formula:**
```
gold_return_N = (gold_close[t] - gold_close[t-N]) / gold_close[t-N]
equity_return_N = (equity_close[t] - equity_close[t-N]) / equity_close[t-N]
divergence = gold_return_N - equity_return_N
```

**Parameters** *(preliminary)*:
- Lookback window N: 40 trading days (~2 months)
- WARNING threshold: divergence > 10%
- CRITICAL threshold: divergence > 20%

**Historical Calibration:**

| Event              | 40d Divergence (peak) | Signal Level | Gold Behavior         |
| ------------------ | --------------------- | ------------ | --------------------- |
| 1997 Asian Crisis  | ~6%                   | None         | Gold declining too    |
| 1998 LTCM          | ~15%                  | WARNING      | Mild safe haven       |
| 2000–02 Dotcom     | ~18%*                 | WARNING      | Slow divergence       |
| 2008 GFC (acute)   | ~30%                  | CRITICAL     | Gold surged after dip |
| 2011 European Debt | ~35%                  | CRITICAL     | Gold at all-time high |
| 2015–16 China      | ~8%                   | None         | Minimal divergence    |
| 2018 Q4 Rate Scare | ~18%                  | WARNING      | Gold rallied          |
| 2020 COVID         | ~5%†                  | None†        | Gold fell initially   |
| 2022 Inflation     | -5%                   | None         | Gold declined too     |

\* Divergence was gradual and intermittent over 2.5 years.
† Gold fell during the initial liquidity panic, producing NEGATIVE divergence during the fastest part of the crash. Divergence only appeared after the trough.

**Summary:**

| Metric                           | Value                                      |
| -------------------------------- | ------------------------------------------ |
| Crises detected (true positives) | 5 / 9 (WARNING+); 2 / 9 (CRITICAL)         |
| False positives (1996–2025)      | ~1–2 per decade                            |
| Average lead time before trough  | 0 to +15 days (concurrent)                 |
| Recommended for composite?       | **Yes** — confirms flight-to-safety regime |

**Notes:** Gold-equity divergence is a strong confirming indicator for Type A events where gold functions as a safe haven. It correctly does NOT fire during Type C (2022) or liquidity panics (COVID initial phase). The major weakness is that it misses the fastest crashes where gold also drops temporarily. In the composite, this indicator confirms the crisis TYPE rather than detecting the crisis itself.

---

### 5.4 Bond-Equity Correlation

**Purpose:** Distinguish between normal crises (bonds rally = negative correlation) and Type C correlated declines (bonds and equities both fall = positive correlation). This indicator serves as the **Type C guard** in the composite signal.

**Formula:**
```
bond_returns = diff(log(bond_close[t-N : t]))
equity_returns = diff(log(equity_close[t-N : t]))
rolling_corr = pearson_correlation(equity_returns, bond_returns)
bond_declining = bond_close[t] < bond_close[t-N]
```

**Parameters** *(preliminary)*:
- Rolling window N: 60 trading days
- Type C veto condition: `rolling_corr > +0.30 AND bond_declining`
- Minimum duration for veto: 20 trading days above threshold (avoids vetoing on brief liquidity spikes like COVID Mar 12–18)

**Historical Calibration:**

| Event              | 60d Corr (peak) | Bond Direction     | Type C Veto? |
| ------------------ | --------------- | ------------------ | ------------ |
| 1997 Asian Crisis  | -0.20           | Rising (+3%)       | No           |
| 1998 LTCM          | -0.40           | Rising (+4%)       | No           |
| 2000–02 Dotcom     | -0.55           | Rising (+28%)      | No           |
| 2008 GFC           | -0.45           | Rising (+8%)       | No           |
| 2011 European Debt | -0.50           | Rising (+6%)       | No           |
| 2015–16 China      | -0.15           | Flat (+2%)         | No           |
| 2018 Q4 Rate Scare | -0.10           | Flat (+1%)         | No           |
| 2020 COVID         | +0.35†          | Rising (+3%)       | No†          |
| 2022 Inflation     | **+0.60**       | **Falling (-13%)** | **Yes**      |

† COVID briefly hit +0.35 correlation during the Mar 12–18 liquidity panic, but bonds were still net rising and the spike lasted < 10 trading days. The 20-day minimum duration threshold correctly prevents a false veto.

**Summary:**

| Metric                           | Value                              |
| -------------------------------- | ---------------------------------- |
| Type C events correctly vetoed   | 1 / 1 (2022)                       |
| Type A events incorrectly vetoed | 0 / 5 (including COVID)            |
| False veto rate                  | 0 (with 20-day duration filter)    |
| Recommended for composite?       | **Yes** — required as Type C guard |

**Notes:** This indicator does not detect crises; it prevents false exploitation. It must be included in the composite as a hard veto. The 20-day minimum duration filter is critical to avoid vetoing during brief liquidity events like COVID.

---

### 5.5 Volatility Regime

**Purpose:** Detect transitions from low-volatility to high-volatility regimes that characterize crisis periods.

**Formula:**
```
short_vol = std(daily_returns[t-20 : t]) * sqrt(252)    # 20-day annualized
long_vol = std(daily_returns[t-60 : t]) * sqrt(252)     # 60-day annualized
vol_ratio = short_vol / long_vol
```

**Parameters** *(preliminary)*:
- Short window: 20 trading days
- Long window: 60 trading days
- WARNING threshold: vol_ratio > 1.80
- CRITICAL threshold: vol_ratio > 2.50

**Historical Calibration:**

| Event              | 20d Vol (peak) | 60d Vol (baseline) | Vol Ratio | Signal Level |
| ------------------ | -------------- | ------------------ | --------- | ------------ |
| 1997 Asian Crisis  | ~25%           | ~13%               | ~1.9      | WARNING      |
| 1998 LTCM          | ~38%           | ~15%               | ~2.5      | CRITICAL     |
| 2000–02 Dotcom     | ~30%           | ~22%               | ~1.4      | None†        |
| 2008 GFC (acute)   | ~86%           | ~35%               | ~2.5      | CRITICAL     |
| 2011 European Debt | ~36%           | ~14%               | ~2.6      | CRITICAL     |
| 2015–16 China      | ~28%           | ~14%               | ~2.0      | WARNING      |
| 2018 Q4 Rate Scare | ~33%           | ~12%               | ~2.8      | CRITICAL     |
| 2020 COVID         | ~85%           | ~18%               | ~4.7      | CRITICAL     |
| 2022 Inflation     | ~32%           | ~22%               | ~1.5      | None†        |

† Slow grinds (Dotcom, 2022) elevate both short and long vol, keeping the ratio low. The vol ratio specifically detects SUDDEN vol expansions characteristic of Type A crashes.

**Summary:**

| Metric                           | Value                                               |
| -------------------------------- | --------------------------------------------------- |
| Crises detected (true positives) | 6 / 9 (WARNING+); 5 / 9 (CRITICAL)                  |
| False positives (1996–2025)      | ~2–3 per decade (WARNING); ~1 per decade (CRITICAL) |
| Average lead time before trough  | 0 to +10 days (concurrent)                          |
| Recommended for composite?       | **Yes** — core vol regime detector                  |

**Notes:** The vol ratio is an excellent discriminator between Type A (ratio > 2.0) and Type B/C events (ratio < 1.5). It pairs well with drawdown velocity — both measure the SPEED of the crisis rather than the depth. Minor false positives occur during earnings seasons or geopolitical events that cause brief vol spikes without sustained drawdowns.

---

### 5.6 MA Crossover (Death Cross)

**Purpose:** Detect sustained downtrends using the classic 50/200 SMA death cross.

**Formula:**
```
sma_50 = mean(close[t-50 : t])
sma_200 = mean(close[t-200 : t])
death_cross = sma_50 < sma_200 AND sma_50[t-1] >= sma_200[t-1]  (crossover event)
bearish_regime = sma_50 < sma_200  (ongoing state)
```

**Parameters:** Standard 50/200 SMA (no tuning needed; these are universal values).

**Historical Calibration:**

| Event              | Death Cross Date | Relative to Trough | Lead/Lag    | Useful?  |
| ------------------ | ---------------- | ------------------ | ----------- | -------- |
| 1997 Asian Crisis  | Not triggered    | N/A (too mild)     | N/A         | No       |
| 1998 LTCM          | ~Sep 1998        | ~10 days before    | Slight lead | Marginal |
| 2000–02 Dotcom     | ~Jul 2000        | ~570 td before     | Very early  | Yes      |
| 2008 GFC           | ~Jan 2008        | ~290 td before     | Very early  | Yes      |
| 2011 European Debt | ~Aug 2011        | ~35 td before      | Moderate    | Yes      |
| 2015–16 China      | ~Sep 2015        | ~105 td before     | Early       | Yes      |
| 2018 Q4 Rate Scare | ~Dec 2018        | ~5 td before       | Near trough | Marginal |
| 2020 COVID         | ~Apr 2, 2020     | **10 td AFTER**    | **Lagging** | **No**   |
| 2022 Inflation     | ~Mar 2022        | ~145 td before     | Early       | Yes      |

**False positives outside crises:** ~3–4 per decade where the death cross triggers but the market recovers without a bear market (e.g., brief crosses in 2016, 2019 mid-year).

**Summary:**

| Metric                           | Value                                       |
| -------------------------------- | ------------------------------------------- |
| Crises detected (true positives) | 7 / 9 (bearish regime)                      |
| False positives (1996–2025)      | ~3–4 per decade                             |
| Average lead time before trough  | -10 to +290 days (highly variable)          |
| Recommended for composite?       | **Conditional** — confirming indicator only |

**Notes:** The death cross is a LAGGING indicator. For slow grinds (Type B), it provides early warning (months before trough). For fast crashes (Type A), it often triggers near or AFTER the trough — making it useless for exploitation timing. The COVID failure is particularly concerning: the death cross would have triggered a buy signal AFTER the V-shaped recovery was already underway.

**Recommendation:** Include as a confirming indicator in the composite, but give it lower weight. It is most useful for confirming that a Type B bear market is underway. It should NEVER be a required condition for composite signal firing, as this would cause the system to miss Type A events.

---

### 5.7 Relative Strength (Gold/Equity)

**Purpose:** Detect flight-to-safety regime shifts by measuring gold's outperformance relative to equities.

**Formula:**
```
RS = gold_close[t] / equity_close[t]  (price ratio, normalized to t=0)
RS_MA = mean(RS[t-120 : t])           (120-day moving average of ratio)
signal = RS[t] > RS_MA[t] * (1 + threshold)  (breakout above MA)
```

**Parameters** *(preliminary)*:
- RS smoothing: 120 trading days
- Breakout threshold: +5% above RS_MA (WARNING), +10% above RS_MA (CRITICAL)

**Historical Calibration:**

| Event              | RS Breakout (%) | Signal Level | Notes                        |
| ------------------ | --------------- | ------------ | ---------------------------- |
| 1997 Asian Crisis  | ~3%             | None         | Gold also weak               |
| 1998 LTCM          | ~8%             | WARNING      | Modest gold outperformance   |
| 2000–02 Dotcom     | ~15%            | CRITICAL     | Multi-year gold bull         |
| 2008 GFC           | ~25%            | CRITICAL     | Strong gold outperformance   |
| 2011 European Debt | ~20%            | CRITICAL     | Gold at all-time highs       |
| 2015–16 China      | ~6%             | WARNING      | Late gold recovery           |
| 2018 Q4 Rate Scare | ~12%            | CRITICAL     | Gold rallied, equities fell  |
| 2020 COVID         | ~2%†            | None†        | Gold fell alongside equities |
| 2022 Inflation     | ~4%             | None         | Gold declined                |

† Gold initially fell during COVID panic; RS breakout only appeared post-trough.

**Summary:**

| Metric                           | Value                                  |
| -------------------------------- | -------------------------------------- |
| Crises detected (true positives) | 5 / 9 (WARNING+); 4 / 9 (CRITICAL)     |
| False positives (1996–2025)      | ~2 per decade                          |
| Average lead time before trough  | 0 to +20 days (concurrent)             |
| Recommended for composite?       | **Yes** — confirms safe-haven rotation |

**Notes:** RS breakout overlaps with gold-equity divergence (5.3) but adds a trend-following dimension via the MA. It is slightly more selective (fewer false positives) but also slightly less responsive. Including both provides redundancy; if one must be dropped to reduce composite complexity, gold-equity divergence (5.3) is preferred for its simplicity and directness. The RS indicator misses events where gold also declines (COVID, 2022), which aligns with the desired behavior — those are precisely the events (Type C or liquidity panic) where exploitation should NOT fire.

---

## 6. Composite Signal Design

> **All parameters in this section are preliminary hypotheses.** They will be validated and refined during Phase 6 backtesting. Indicator selection, activation rules, and thresholds are expected to change based on backtest results.

### 6.1 Indicator Selection

Based on the individual indicator analysis (Section 5), the composite signal uses 5 core indicators and 1 guard:

| Role         | Indicator               | Rationale                                                        |
| ------------ | ----------------------- | ---------------------------------------------------------------- |
| Core (vote)  | Drawdown Velocity       | Best discriminator for Type A crashes; low false-positive        |
| Core (vote)  | Max Drawdown            | High sensitivity gate; catches all crisis types                  |
| Core (vote)  | Gold-Equity Divergence  | Confirms flight-to-safety regime; filters non-crisis corrections |
| Core (vote)  | Volatility Regime       | Detects sudden vol expansion; complements velocity               |
| Core (vote)  | Relative Strength       | Confirms safe-haven rotation; corroborates divergence            |
| Guard (veto) | Bond-Equity Correlation | Hard veto for Type C correlated declines                         |

**Excluded:**
- **MA Crossover (Death Cross):** Too lagging for Type A events (triggered AFTER COVID trough). Included as an optional confirming indicator but not a required voter. May be re-evaluated in Phase 6.

### 6.2 Activation Rule *(preliminary)*

**N-of-M voting:** The composite signal fires when **3 or more of the 5** core indicators simultaneously signal at WARNING level or above, AND the Type C guard does not veto.

```
composite_fires = (sum(indicator_active) >= 3) AND (NOT type_c_veto)
```

**Rationale:** 3-of-5 balances sensitivity and specificity:
- 2-of-5 would fire too frequently (~3–5 times per decade in non-crisis corrections)
- 4-of-5 would miss events where gold doesn't cooperate (COVID) or where the crisis is too fast for some indicators
- 3-of-5 targets 2–5 composite fires per decade, which aligns with the frequency of genuine exploitable crises

### 6.3 Severity Aggregation *(preliminary)*

| Composite Severity | Condition                                          |
| ------------------ | -------------------------------------------------- |
| WARNING            | 3+ indicators at WARNING, fewer than 2 at CRITICAL |
| CRITICAL           | 3+ indicators active AND 2+ at CRITICAL level      |

The crisis exploitation strategy (Phase 5) will use severity to size the rebalancing action:
- **WARNING:** Sell 25% of defensive asset overweight → buy discounted equities *(preliminary)*
- **CRITICAL:** Sell 50% of defensive asset overweight → buy discounted equities *(preliminary)*

### 6.4 Type C Guard

**Mechanism:** The bond-equity correlation indicator acts as a hard veto:

```python
type_c_veto = (
    rolling_corr_60d(equity, bonds) > 0.30
    AND bond_close[t] < bond_close[t - 60]   # bonds declining
    AND days_above_threshold >= 20            # sustained, not a brief spike
)
```

**Behavior:**
- If `type_c_veto` is True, the composite signal does NOT fire, regardless of how many core indicators are active.
- The 20-day duration filter prevents false vetoes during brief liquidity events (e.g., COVID March 12–18 panic).
- The bond-declining condition prevents vetoing when correlation is positive but bonds are flat or rising (which can occur in normal markets).

### 6.5 Cooldown *(preliminary)*

**Minimum 90 calendar days** between consecutive composite signal emissions.

**Rationale:**
- Prevents excessive rebalancing during multi-month crises (e.g., GFC where signals could fire monthly for 6+ months).
- 90 days is approximately one quarter — roughly aligned with how long most Type A crises take to resolve (trough to initial recovery).
- For Type B events (slow grinds spanning years), the cooldown allows at most 4 signals per year, limiting the damage from false-bottom rebalancing.

### 6.6 Expected Frequency & Historical Backtest Preview

Based on the individual indicator calibrations and the 3-of-5 rule:

| Event              | Indicators Active (at peak)                               | N   | Type C Veto? | Composite Fires? | Severity |
| ------------------ | --------------------------------------------------------- | --- | ------------ | ---------------- | -------- |
| 1997 Asian Crisis  | MaxDD(W)                                                  | 1   | No           | **No**           | —        |
| 1998 LTCM          | Velocity(C), MaxDD(W), VolRegime(C), RS(W)                | 4   | No           | **Yes**          | CRITICAL |
| 2000–02 Dotcom     | MaxDD(C), Divergence(W), RS(C)                            | 3   | No           | **Yes**†         | WARNING  |
| 2008 GFC (acute)   | Velocity(C), MaxDD(C), Divergence(C), VolRegime(C), RS(C) | 5   | No           | **Yes**          | CRITICAL |
| 2011 European Debt | Velocity(W), MaxDD(W), Divergence(C), VolRegime(C), RS(C) | 5   | No           | **Yes**          | CRITICAL |
| 2015–16 China      | MaxDD(W), VolRegime(W)                                    | 2   | No           | **No**           | —        |
| 2018 Q4 Rate Scare | Velocity(W), MaxDD(W), Divergence(W), VolRegime(C), RS(C) | 5   | No           | **Yes**          | CRITICAL |
| 2020 COVID         | Velocity(C), MaxDD(C), VolRegime(C)                       | 3   | No‡          | **Yes**          | CRITICAL |
| 2022 Inflation     | MaxDD(C)                                                  | 1   | **Yes**      | **No**           | —        |

† Dotcom fires as WARNING; the slow grind means fewer indicators reach CRITICAL. Multiple fires possible across 2000–2002 (with cooldown spacing).

‡ COVID briefly triggered the Type C guard condition (positive correlation, bonds dipping) but the 20-day duration filter prevented the veto. With a shorter duration filter, COVID would be incorrectly vetoed.

**Expected composite fire frequency (1996–2025):** 6 fires across 9 potential events = **~2.1 per decade**, within the 2–5 target range. The two "misses" (1997, 2015–16) are mild corrections that don't warrant crisis exploitation. The one correct non-fire (2022) validates the Type C guard.

### 6.7 Worked Example: Crisis Exploitation on a €10,000 Portfolio

**Scenario:** 2008 GFC acute phase. Portfolio pre-crisis at target allocation:
- Stocks (VWCE proxy): €7,000
- Gold (SGLN.L proxy): €1,500
- Bonds (EUNA.DE proxy): €1,500

After equities drop -30%, gold +15%, bonds +5%:
- Stocks: €4,900 (59.3%)
- Gold: €1,725 (20.9%)
- Bonds: €1,575 (19.1%)
- Total: €8,275 (deviation: stocks -10.7%, gold +5.9%, bonds +4.1%)

**CRITICAL composite signal fires. Action (sell 50% of defensive overweight):**
- Gold overweight: 20.9% - 15.0% = 5.9% of €8,275 = €488. Sell 50% = **sell €244 gold**
- Bond overweight: 19.1% - 15.0% = 4.1% of €8,275 = €339. Sell 50% = **sell €170 bonds**
- **Buy €414 of discounted equities** at -30% discount

Post-rebalance (approximate):
- Stocks: €5,314 (63.0%)
- Gold: €1,481 (17.6%)
- Bonds: €1,405 (16.7%)

**If equities subsequently recover to pre-crisis levels (+43% from trough):**
- The €414 bought at -30% discount grows to €592 (+€178 gain)
- Total portfolio value: ~€10,305 vs ~€10,127 without rebalancing = **+€178 (≈+1.8% of portfolio)**

This example illustrates that crisis exploitation on a 30% defensive allocation produces modest (1–3%) portfolio-level gains per event. The value compounds over decades with 2–5 events per decade.

---

## 7. Testable Assumptions

Each assumption below is a falsifiable statement to be validated in Phase 6 backtesting. Format: `[ID] statement — supporting evidence`.

### Proxy Validity

> **[A01]** ^GSPC daily return correlation with VWCE.DE exceeds 0.90 in the 2019-06–2025-12 overlap period.
> *Evidence: Section 2.2 estimates r ≈ 0.94. Must be confirmed with yfinance data.*

> **[A02]** SGLN.L daily return correlation with GLD exceeds 0.93 in the 2011–2025 overlap period.
> *Evidence: Section 2.2 estimates r ≈ 0.96. Both track physical gold.*

> **[A03]** EUNA.DE daily return correlation with AGG exceeds 0.80 in the 2017–2025 overlap period.
> *Evidence: Section 2.2 estimates r ≈ 0.83. Weakest proxy link.*

### Indicator Behavior

> **[A04]** Drawdown velocity exceeds -0.30 %/day in at least 4 of the 9 historical crises (1997–2022).
> *Evidence: Section 5.1 calibration shows 4 events reaching WARNING or CRITICAL velocity.*

> **[A05]** The volatility ratio (20d/60d) exceeds 2.0 during all Type A crash events (1998, 2011, 2018, 2020).
> *Evidence: Section 5.5 calibration shows ratios of 2.5, 2.6, 2.8, 4.7 for these events.*

> **[A06]** Gold-equity divergence (40-day) exceeds +10% during at least 5 of the 9 historical crises.
> *Evidence: Section 5.3 calibration shows 5 events reaching WARNING level.*

> **[A07]** The death cross (50/200 SMA) triggers AFTER the equity trough in the 2020 COVID crash.
> *Evidence: Section 5.6 documents the death cross occurring ~Apr 2, 2020, 10 trading days after the Mar 23 trough.*

### Composite Signal

> **[A08]** The composite signal (3-of-5 + Type C guard) fires between 2 and 5 times per decade over 1996–2025.
> *Evidence: Section 6.6 preview shows 6 fires in ~28 years ≈ 2.1/decade, within the 2–5 target range.*

> **[A09]** The composite signal does NOT fire during the 2022 inflation regime (Jan–Oct 2022).
> *Evidence: Only 1 core indicator (MaxDD) triggers; Type C guard also vetoes. Double protection.*

> **[A10]** The composite signal fires during the 2020 COVID crash despite the brief (< 10 day) positive bond-equity correlation spike.
> *Evidence: The 20-day duration filter on the Type C guard prevents a false veto. 3 core indicators (Velocity, MaxDD, VolRegime) are active.*

### Crisis Exploitation

> **[A11]** Selling 50% of defensive asset overweight during CRITICAL composite signals and buying discounted equities improves terminal portfolio value by ≥ 1% per event (on average) compared to passive-only PAC.
> *Evidence: Section 6.7 worked example shows +1.8% for a -30% drawdown + full recovery. Must be validated across all historical crises.*

> **[A12]** The composite signal never reduces gold below 10% or bonds below 10% of total portfolio value (i.e., never more than ⅓ of each defensive allocation is sold in a single crisis event).
> *Evidence: The worked example sells 50% of overweight (not 50% of holdings). With 15% target allocation and typical 5–6% overweight during crises, this sells ~3% of portfolio from each defensive asset, maintaining ≥12% allocation each.*

### Sell Constraints

> **[A13]** Gold allocation should never be reduced below 5% of portfolio *(preliminary minimum floor)*.
> *Evidence: Gold's safe-haven role during Type A crises (Section 3) means retaining meaningful gold exposure is essential for ongoing hedging.*

> **[A14]** Bond allocation should never be reduced below 5% of portfolio *(preliminary minimum floor)*.
> *Evidence: Bonds provide income and moderate vol reduction. Below 5% the diversification benefit is negligible.*

### False Positive Cost

> **[A15]** A false-positive composite signal (selling defensive to buy equities when no crisis materializes) creates a portfolio drag of < 2% over the subsequent 12 months, assuming equities are flat and defensive assets return to prior levels.
> *Evidence: The action size is moderate (~3–5% of portfolio rotated). If equities are flat and gold/bonds return to baseline, the drag is approximately the round-trip opportunity cost of being under-hedged temporarily.*

---

## 8. Appendix: Data Sources & Methodology

### 8.1 Proxy Ticker Chains & Rationale

**Equity proxy: ^GSPC (S&P 500 Index)**
- Coverage: 1996–2025 (full analysis period)
- Rationale: Longest available daily-resolution equity index with yfinance coverage. The S&P 500 represents ~80% of US equity market cap and ~50% of global equity market cap.
- Limitations: US-only; does not capture EM or European moves. The portfolio ETF (VWCE) tracks FTSE All-World (~60% US, ~40% non-US). Events like the 1997 Asian Crisis and 2011 European Debt Crisis show materially different profiles in US vs global equities.
- Alternative considered: MSCI ACWI (ticker: ACWI) — only available since 2008, insufficient for 30-year coverage.

**Gold proxy chain: GC=F → GLD → SGLN.L**
- GC=F (gold futures, continuous contract): 1996–2004. The front-month continuous contract closely tracks spot gold. Contango/backwardation effects are negligible (<0.5%/year for gold futures).
- GLD (SPDR Gold Shares ETF): 2004–2011. Launched Nov 2004; tracks gold bullion with ~0.40% annual expense ratio. Very tight tracking to spot gold.
- SGLN.L (iShares Physical Gold ETC): 2011+. This is the actual portfolio holding. USD-denominated ETC tracking physical gold.
- Chain validation: GC=F vs GLD overlap (2004–2025): r ≈ 0.99. GLD vs SGLN.L overlap (2011–2025): r ≈ 0.96. The chain is tight.

**Bond proxy chain: VBMFX → AGG → EUNA.DE**
- VBMFX (Vanguard Total Bond Market Index Fund): 1996–2003. Tracks the Bloomberg US Aggregate Bond Index. Mutual fund with daily NAV, available in yfinance.
- AGG (iShares Core US Aggregate Bond ETF): 2003–2017. Tracks the same Bloomberg US Aggregate Bond Index as VBMFX. Launched Sep 2003.
- EUNA.DE (iShares Core Global Aggregate Bond UCITS ETF): 2017+. This is the actual portfolio holding. Tracks Bloomberg Global Aggregate Bond Index, EUR-hedged.
- Chain validation: VBMFX vs AGG overlap (2003–2025): r ≈ 0.99 (same index). AGG vs EUNA.DE overlap (2017–2025): r ≈ 0.83. The AGG→EUNA.DE link is the weakest due to US vs Global index composition and EUR hedging.
- **Key caveat:** EUNA.DE includes non-US sovereign bonds (European, EM) and is currency-hedged to EUR. During the 2022 rate regime, the Fed hiked faster than the ECB, causing divergent bond market behavior that the AGG proxy partially captures but not perfectly.

### 8.2 Currency & Regional Bias Disclaimers

**All figures in this document are denominated in USD unless explicitly stated otherwise.**

**Currency effects on EUR-denominated portfolios:**
- EUR/USD can move ±10–20% during crisis periods (e.g., EUR/USD went from ~1.60 to ~1.25 during the 2008 GFC, a ~22% move).
- For the equity proxy (^GSPC in USD), a weakening USD (which often occurs during Fed easing) would amplify EUR-denominated returns and vice versa.
- For the gold proxy, gold is globally priced in USD. A EUR investor holding USD-denominated gold benefits from USD appreciation and vice versa. SGLN.L is USD-denominated but accessible to EUR investors, so the currency exposure is real.
- For the bond proxy (AGG in USD vs EUNA.DE EUR-hedged), the actual portfolio holding is explicitly currency-hedged, partially neutralizing FX effects. The proxy analysis using AGG does NOT account for this hedging, which may cause backtest results to diverge from actual EUR-hedged bond behavior.

**Regional bias (US vs global equities):**
- ^GSPC drawdowns understate global portfolio exposure during EM/European crises:
  - **1997 Asian Crisis:** MSCI EM fell ~55%, MSCI ACWI fell ~18%, ^GSPC fell ~11%
  - **2011 European Debt:** STOXX 600 fell ~26%, MSCI ACWI fell ~21%, ^GSPC fell ~19%
- ^GSPC drawdowns overstate global portfolio exposure during US-centric events:
  - **2000–02 Dotcom:** NASDAQ fell ~78%, ^GSPC fell ~49%, MSCI EAFE fell ~46% (similar globally)
  - **2018 Q4:** Primarily US rate policy driven; ^GSPC -20% was ~3% worse than MSCI ACWI
- For events with synchronized global impact (2008 GFC, 2020 COVID, 2022 rate regime), ^GSPC closely approximates global equity drawdowns.

### 8.3 Data Retrieval

All market data should be retrieved via `yfinance` Python library. Recommended configuration:
- Daily OHLCV data
- Adjusted close prices (accounts for dividends and splits)
- Data range: 1996-01-01 to 2025-12-31

**No external data sources beyond yfinance** are used. All indicators are computable from the 3 asset price histories (equity, gold, bonds) using their respective proxy tickers.

### 8.4 Computation Notes

- **Annualized volatility:** `std(daily_log_returns) * sqrt(252)` where 252 is the standard trading days per year.
- **Rolling correlation:** Pearson correlation of daily log returns over the specified window.
- **Drawdown:** `(price - rolling_max) / rolling_max`, always negative during drawdowns.
- **Trading days (td):** All day counts in this document are trading days unless specified as calendar days.
- **Recovery time:** Measured from trough date to the first date when the closing price exceeds the prior peak price.

---

*Document prepared as Phase 1 output of Task 009 (Production Rules & Strategies R&D). All preliminary parameters are subject to revision based on Phase 6 backtesting.*
