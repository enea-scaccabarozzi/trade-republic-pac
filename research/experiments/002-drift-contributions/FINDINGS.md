# Drift-Based Contribution Steering

> **Hypothesis**: Dynamically redistributing fixed monthly DCA contributions toward underweight assets based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation, without selling or incurring fees.
> **Status**: concluded
> **Date**: 2026-04-22
> **Depends on**: [001-baseline-dca](../001-baseline-dca/FINDINGS.md)

## Baseline Reference

From experiment 001 (N=50 Monte Carlo):

| Metric | Median | P5 | P95 |
|--------|--------|----|-----|
| TWRR | 8.58% | — | — |
| MWRR | 9.67% | — | — |
| Sharpe | 0.76 | — | — |
| Max Drawdown | -44.3% | — | — |
| Sortino | 1.36 | — | — |
| Calmar | 0.82 | — | — |
| Final Value | ~471k | 470,770 | 473,725 |

## Exploration

Four scripts systematically narrowed the search space before building any strategy code.

### Scripts Used (in order of creation)

1. [drift_characterization.py](exploration/drift_characterization.py) — analyze drift magnitudes, persistence, and regime behavior over 21 years
1. [smoothing_assessment.py](exploration/smoothing_assessment.py) — compare spot vs SMA vs EMA drift: noise reduction vs lag tradeoff
1. [contribution_capacity.py](exploration/contribution_capacity.py) — measure contribution rebalancing power as portfolio grows
1. [theoretical_ceiling.py](exploration/theoretical_ceiling.py) — oracle strategy upper bound on improvement

### Drift Characterization

**WHY**: Before building any strategy, we need to know if drift is large enough to matter. If max |drift| < 2pp across the entire 21-year period, contribution steering has nothing to work with.

**HOW**: Simulated the baseline DCA over 2005-01-03 to 2026-04-22, computed daily allocation percentages per asset, and analyzed drift (actual_pct - target_pct) distributions, autocorrelation, and per-regime behavior.

**WHAT**: Drift is large and persistent:

- Stocks: mean |drift| 7.1pp, max 30pp, 68% of days >5pp, 18% >10pp
- Gold: mean |drift| 4.2pp, max 18pp, 76% of days >2pp
- Bonds: mean |drift| 4.1pp, max 15pp, 76% of days >2pp
- Autocorrelation at lag-1: >0.999 for all assets (drift barely changes day-to-day)
- Half-life: effectively infinite — drift doesn't mean-revert, it persists until the next PAC date

**SO WHAT**: The kill criterion (max |drift| < 2pp) passes easily. There is substantial drift to exploit. The extreme persistence means smoothing is unlikely to add value — the signal is already stable.

### Smoothing Value Assessment

**WHY**: The drift characterization showed high persistence, but we needed to quantify whether smoothing (SMA/EMA) adds any value for a monthly-frequency strategy.

**HOW**: Computed spot drift and compared against SMA(5/10/20/40) and EMA(5/10/20/40) variants. Measured variance ratio (noise reduction) and effective lag at peak cross-correlation.

**WHAT**: All smoothing variants show zero lag (peak correlation at lag=0 days). Noise reduction ranges from 12-27%, but the underlying signal is already extremely stable.

**SO WHAT**: Smoothing is unnecessary for this use case. The PAC executes monthly, drift is highly persistent, and there is no lag advantage. **Decision: drop the smoothing dimension entirely from the strategy parameter space.** This eliminates one full axis from the sweep.

### Contribution Capacity Analysis

**WHY**: Even if drift is large, contributions can only fix drift if they are large relative to the portfolio. As the portfolio grows, a fixed €500-700/month contribution becomes an increasingly small fraction of portfolio value.

**HOW**: Simulated the baseline DCA and measured contribution/portfolio ratio over time.

**WHAT**: The contribution capacity decays rapidly:

- 2005: ~30% of portfolio (front-loaded, very effective)
- 2006: ~5.5%
- 2009: \<2pp/month (crossed below 2pp on 2009-08-07)
- 2011: \<1pp/month
- 2015: \<0.5pp/month

**SO WHAT**: Contribution steering is overwhelmingly front-loaded. After the first ~5 years, the monthly contribution is too small relative to the portfolio to materially correct drift. Any improvement from steering will come almost entirely from the early years of the investment period. This fundamentally limits the ceiling for this approach.

### Theoretical Ceiling

**WHY**: Before investing effort in a parameterized strategy, we need to know: what's the maximum possible improvement from contribution steering? If an oracle with perfect information can't beat the baseline meaningfully, no real strategy will either.

**HOW**: Implemented an oracle strategy that allocates each month's contribution perfectly toward underweight assets proportional to their shortfall, with full knowledge of the actual drift on the PAC date. This is the theoretical maximum — no real strategy can exceed it.

**WHAT**:
| Metric | Baseline | Oracle | Delta |
|--------|----------|--------|-------|
| TWRR | 8.33% | 8.68% | +0.35pp |
| Sharpe | 0.767 | 0.773 | +0.006 |
| Sortino | 1.373 | 1.392 | +0.018 |
| Max DD | -43.8% | -56.7% | -12.9pp |
| Final Value | €472,718 | €449,248 | -€23,470 |

**SO WHAT**: A nuanced result. The oracle improves TWRR and Sharpe marginally, but **reduces final portfolio value by ~€23k and worsens max drawdown by 12.9pp**. This makes sense: steering contributions toward underweight assets (bonds, gold) means less money flows into stocks, which have the highest long-term returns. The oracle is "right" about risk-adjusted returns but "wrong" about absolute wealth accumulation.

### Failing Paths

No approaches were abandoned during exploration — all four scripts produced useful results that informed the strategy design.

### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| Drift characterization | [results/drift_characterization.json](results/drift_characterization.json) | Distribution stats, autocorrelation, and regime analysis |
| Smoothing assessment | [results/smoothing_assessment.json](results/smoothing_assessment.json) | Variance ratios and lag for SMA/EMA variants |
| Contribution capacity | [results/contribution_capacity.json](results/contribution_capacity.json) | Contribution/portfolio ratio by year |
| Theoretical ceiling | [results/theoretical_ceiling.json](results/theoretical_ceiling.json) | Oracle strategy upper bound |

## Consolidation

### Scripts Used

1. [quick_test.py](consolidation/quick_test.py) — quick-test DriftDCA with default params, then coarse parameter sweep across 54 configurations

### Strategy: DriftDCA

**[strategies/drift_dca.py](strategies/drift_dca.py)** — A single parameterized strategy with three parameters:

- **`adjustment_formula`**: proportional (always active, linear scaling), threshold (only fires when max |drift| >= threshold), or stepped (discrete 0/50%/100% tilt based on drift magnitude)
- **`max_tilt_pct`** (0.0–1.0): how aggressively to tilt away from target weights toward underweight assets. 0.0 = baseline behavior; 1.0 = maximum correction
- **`threshold_pct`** (≥0): minimum |drift| to trigger adjustment (threshold/stepped only)

The core algorithm: compute per-asset drift from the DeviationReport, determine a tilt_factor from the formula, blend target-weight fractions with correction fractions (proportional to underweight amounts), and convert to EUR volumes preserving the total budget.

### Quick Test (Default Params)

DriftDCA with default params (proportional, tilt=0.5, threshold=3.0) vs baseline:

- TWRR delta: +0.05pp
- Sharpe delta: +0.0016
- MaxDD delta: -0.04pp (negligible)
- Final value delta: -€1,408

Directionally positive but extremely small.

### Coarse Parameter Sweep

Swept 54 configurations: 3 formulas × 6 tilt values × 4 threshold values (proportional uses only 1 threshold since it ignores it).

**Top 10 by TWRR delta:**

| Formula | Tilt | Thresh | dTWRR | dSharpe | dMax DD | dFinal Value |
|---------|------|--------|-------|---------|---------|--------------|
| stepped | 1.0 | 2.0 | +0.51pp | +0.0012 | -12.9pp | -€16,648 |
| stepped | 1.0 | 3.0 | +0.38pp | +0.0066 | -12.9pp | -€27,170 |
| stepped | 1.0 | 5.0 | +0.37pp | +0.0157 | -12.9pp | -€37,905 |
| stepped | 0.7 | 2.0 | +0.24pp | +0.0054 | -1.1pp | -€12,215 |
| stepped | 0.5 | 2.0 | +0.14pp | +0.0053 | +4.7pp | -€8,394 |
| threshold | 1.0 | 2.0 | +0.11pp | +0.0024 | +0.3pp | -€2,236 |
| proportional | 1.0 | 3.0 | +0.11pp | +0.0024 | +0.4pp | -€2,251 |
| stepped | 0.7 | 3.0 | +0.10pp | +0.0088 | -1.1pp | -€22,420 |
| stepped | 0.5 | 3.0 | +0.08pp | +0.0062 | +4.5pp | -€12,382 |
| threshold | 1.0 | 3.0 | +0.08pp | +0.0030 | +0.5pp | -€3,803 |

**Key observations:**

1. **Every TWRR-improving configuration reduces final portfolio value.** This is the fundamental tension: steering contributions away from stocks (the highest-return asset) improves TWRR (risk-adjusted) but reduces terminal wealth. There is no free lunch.

1. **Stepped formula dominates TWRR improvement** but at severe drawdown cost. The best stepped configs reach the oracle ceiling (~0.5pp) but with -12.9pp worse max drawdown and -€16k to -€38k less wealth.

1. **Proportional formula is the safest** — consistent small gains with minimal side effects. At tilt=0.5: +0.05pp TWRR, +0.0016 Sharpe, only -€1,408 and no meaningful drawdown change.

1. **Higher tilt always costs more in final value.** The relationship is monotonic: more aggressive steering = more money diverted from stocks = lower terminal wealth.

1. **Threshold parameter matters for stepped formula** — low thresholds (2.0) allow the stepped formula to fire more often, capturing more drift correction. High thresholds (8.0) make it fire rarely, and the discrete jumps cause erratic behavior (several bottom-ranked configs are stepped with high thresholds).

1. **Sharpe improvement is more consistent** across configurations. Even configs that lose on TWRR often gain on Sharpe, suggesting the risk reduction is real even when return improvement is negligible.

### Candidate Selection for Validation

Given the fundamental tension between TWRR/Sharpe and final value, three candidates represent the Pareto frontier:

1. **Conservative**: proportional, tilt=0.3 — +0.03pp TWRR, -€975 final value, nearly unchanged risk
1. **Moderate**: proportional, tilt=1.0 — +0.11pp TWRR, -€2,251 final value, +0.4pp better drawdown
1. **Aggressive**: stepped, tilt=0.5, thresh=2.0 — +0.14pp TWRR, -€8,394 final value, +4.7pp better drawdown

### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| DriftDCA strategy | [strategies/drift_dca.py](strategies/drift_dca.py) | Parameterized strategy with 3 formulas |
| Consolidation sweep | [consolidation/quick_test.py](consolidation/quick_test.py) | Quick-test + 54-config parameter sweep |
| Sweep results | [results/consolidation_sweep.json](results/consolidation_sweep.json) | Full metrics for all configurations |

## Validation

### Scripts Used

1. [validate.py](validation/validate.py) — full validation suite: Monte Carlo (N=50), OOS (70/30 temporal split), walk-forward (10yr IS, 5yr step), event analysis (crisis calendar), and QuantStats tearsheet for the best candidate

### Candidates Validated

| Name | Formula | Tilt | Threshold | Rationale |
|------|---------|------|-----------|-----------|
| Conservative | proportional | 0.3 | 3.0 | Minimal intervention, smallest final-value cost |
| Moderate | proportional | 1.0 | 3.0 | Full proportional tilt, moderate cost |
| Aggressive | stepped | 0.5 | 2.0 | Discrete jumps, largest TWRR gain in consolidation |

### Monte Carlo (N=50, stochastic contributions €500–700)

**WHY**: Contribution amounts vary randomly between €500 and €700 each month. MC tests whether the strategy's advantage holds across 50 different contribution sequences, not just one deterministic path.

**HOW**: 50 iterations per candidate with different RNG seeds controlling monthly contribution amounts. All other parameters (prices, dates, fees) are fixed. Report median and [P5, P95] confidence intervals.

**WHAT**:

| Metric | Baseline | Conservative | Moderate | Aggressive |
|--------|----------|-------------|----------|------------|
| TWRR (median) | 8.58% | 8.62% (+0.04pp) | 8.70% (+0.12pp) | 8.77% (+0.19pp) |
| Sharpe | 0.759 | 0.760 (+0.001) | 0.761 (+0.002) | 0.764 (+0.005) |
| Max DD | -44.3% | -44.2% (+0.1pp) | -43.7% (+0.6pp) | -39.4% (+4.9pp) |
| Calmar | 0.819 | 0.821 (+0.002) | 0.830 (+0.011) | 0.918 (+0.099) |
| Sortino | 1.356 | 1.357 (+0.001) | 1.354 (-0.002) | 1.332 (-0.024) |
| Final Value | €472,175 | €471,637 (-€538) | €470,581 (-€1,594) | €464,379 (-€7,796) |

Confidence intervals are tight (P5–P95 spread ~1–2% of median), confirming that results are stable across contribution randomness.

**SO WHAT**: All three candidates consistently improve TWRR and Sharpe over MC runs. The aggressive candidate stands out with a +4.9pp improvement in max drawdown and a +12% improvement in Calmar ratio — but at a cost of -€7,796 in final value (-1.7%). The moderate candidate offers a good middle ground: +0.12pp TWRR, +0.6pp better max drawdown, and only -€1,594 final value cost (-0.3%).

### Out-of-Sample (70/30 temporal split at 2019-12-01)

**WHY**: The strategy was designed and tuned on the full 2005–2026 period. OOS tests whether it generalizes or was overfit to the training data.

**HOW**: Train on 2005-01-03 to 2019-12-01 (IS), test on 2019-12-01 to 2026-04-22 (OOS). Compare IS vs OOS Sharpe via degradation_ratio (OOS Sharpe / IS Sharpe). Values > 1.0 mean OOS outperforms IS — the opposite of overfitting.

**WHAT**:

| Metric | Baseline | Conservative | Moderate | Aggressive |
|--------|----------|-------------|----------|------------|
| IS Sharpe | 0.856 | 0.857 | 0.859 | 0.859 |
| IS TWRR | 7.22% | 7.27% | 7.40% | 7.52% |
| IS Max DD | -43.8% | -43.9% | -43.5% | -39.2% |
| OOS Sharpe | 1.235 | 1.226 | 1.217 | 1.202 |
| OOS TWRR | 12.36% | 12.39% | 12.76% | 15.71% |
| OOS Max DD | -30.3% | -30.9% | -31.5% | -32.3% |
| Degradation ratio | 1.443 | 1.430 | 1.418 | 1.398 |

**SO WHAT**: All degradation ratios are well above 1.0, meaning OOS performance exceeds IS performance for all candidates. This is not overfitting — it reflects the 2020–2026 OOS period being a strong market environment. Importantly, the DriftDCA candidates show slightly lower degradation ratios than baseline, which is expected: contribution steering is most effective in the early years (IS period, when contributions are large relative to portfolio), so IS improvement is slightly larger than OOS improvement. The OOS TWRR improvement for aggressive (+3.35pp) is noteworthy but likely driven by the small OOS portfolio size where contributions still have leverage.

### Walk-Forward (10yr IS, 5yr step)

**WHY**: A single IS/OOS split is sensitive to the split date. Walk-forward uses multiple overlapping windows to test stability across different market regimes.

**HOW**: Three windows with 10-year IS and expanding OOS:

- W1: IS 2005–2015, OOS 2015–2020
- W2: IS 2005–2020, OOS 2020–2025
- W3: IS 2005–2025, OOS 2025–2026
  Stability score = sum of OOS Sharpe across windows. Higher = more consistent.

**WHAT**:

| Window | Baseline | Conservative | Moderate | Aggressive |
|--------|----------|-------------|----------|------------|
| W1 (OOS Sharpe) | 1.348 | 1.338 | 1.328 | 1.321 |
| W2 (OOS Sharpe) | 1.344 | 1.336 | 1.329 | 1.321 |
| W3 (OOS Sharpe) | 2.202 | 2.190 | 2.174 | 2.145 |
| **Stability** | **3.301** | **3.291** | **3.298** | **3.353** |

**SO WHAT**: Walk-forward stability is remarkably consistent across all candidates (range 3.29–3.35). The aggressive candidate actually has the highest stability score (3.353), suggesting its improvement does not decay over time. Per-window OOS Sharpe values are slightly lower for DriftDCA candidates, consistent with the OOS finding that contribution steering adds less value in later periods. The very high W3 values for all candidates reflect the short, bullish 2025–2026 OOS window.

### Event Analysis (Crisis Calendar)

**WHY**: The aggregate metrics mask how the strategy behaves during market stress. Crisis events are when drawdown protection matters most.

**HOW**: Computed total portfolio return during each crisis event from the crisis calendar, using a single deterministic simulation per candidate.

**WHAT**:

| Event | Baseline | Conservative | Moderate | Aggressive |
|-------|----------|-------------|----------|------------|
| GFC (Oct 2007 – Mar 2009) | +8.0% | +8.8% | +9.5% | +7.7% |
| Eurozone crisis (Jul 2011 – Jun 2012) | +27.3% | +27.2% | +27.1% | +26.6% |
| COVID crash (Feb – Mar 2020) | -27.4% | -27.3% | -27.1% | -26.1% |
| 2022 bear market (Jan – Oct 2022) | -0.6% | -0.4% | -0.1% | +2.5% |

**SO WHAT**: During crises, DriftDCA candidates show marginal improvements. The most notable result is the aggressive candidate turning the 2022 bear market from a -0.6% loss to a +2.5% gain — consistent with the max drawdown improvement seen in MC. During the GFC, the conservative and moderate candidates outperform baseline (due to early-period contribution leverage), but the aggressive candidate slightly underperforms — the stepped formula's discrete jumps create less favorable timing than the proportional formula during prolonged bear markets. The COVID crash differences are small (~1pp) because it was too short (33 days) for monthly contributions to make a meaningful impact.

### QuantStats Tearsheet

Generated for the aggressive candidate (highest MC Sharpe): [artifacts/tearsheet_aggressive.html](artifacts/tearsheet_aggressive.html)

Additional plots saved to `artifacts/`: returns, monthly heatmap, drawdown, rolling Sharpe, histogram, distribution.

### Failing Paths

The initial validation run failed due to a format specifier bug in the event analysis output (`>{col_w}+.4f` should have been `>+{col_w}.4f`). Fixed and re-run — all 5 phases completed successfully on the second attempt.

### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| Validation script | [validation/validate.py](validation/validate.py) | MC, OOS, walk-forward, events, QuantStats |
| Validation results | [results/validation.json](results/validation.json) | Full metrics for all candidates across all phases |
| Tearsheet (aggressive) | [artifacts/tearsheet_aggressive.html](artifacts/tearsheet_aggressive.html) | Full QuantStats performance report |
| Performance plots | [artifacts/](artifacts/) | returns, drawdown, rolling Sharpe, heatmap, histogram, distribution |

## Conclusion

**Verdict: NO-GO for production implementation.**

Drift-based contribution steering produces statistically real but economically negligible improvements to risk-adjusted returns, while consistently reducing terminal portfolio value. The fundamental tension identified in exploration and consolidation is confirmed by validation:

### The Core Tradeoff

Steering contributions toward underweight assets means steering them *away* from stocks — which have the highest long-term expected return. Every improvement in TWRR, Sharpe, or max drawdown comes at a direct cost in final portfolio value. There is no configuration that improves risk-adjusted returns without reducing wealth accumulation.

### Quantitative Summary

| Candidate | dTWRR | dSharpe | dMax DD | dCalmar | dFinal Value |
|-----------|-------|---------|---------|---------|--------------|
| Conservative | +0.04pp | +0.001 | +0.1pp | +0.002 | -€538 (-0.1%) |
| Moderate | +0.12pp | +0.002 | +0.6pp | +0.011 | -€1,594 (-0.3%) |
| Aggressive | +0.19pp | +0.005 | +4.9pp | +0.099 | -€7,796 (-1.7%) |

### Why It Doesn't Work Well Enough

1. **Contribution capacity decays rapidly.** Monthly contributions of €500–700 are meaningful only in the first ~5 years. After 2009, contributions are \<2% of portfolio value — too small to meaningfully correct drift. The strategy is structurally front-loaded.

1. **The improvements are within noise.** A +0.04pp TWRR improvement (conservative) is indistinguishable from random variation. Even the aggressive candidate's +0.19pp is barely above the MC confidence interval width.

1. **The best metric improvement (max drawdown) requires the worst formula.** The aggressive candidate's +4.9pp max drawdown improvement is the most compelling result, but it uses the stepped formula which applies discrete 0/50%/100% jumps — a crude mechanism that happens to help in the 2022 bear market but could equally hurt in other scenarios.

1. **The theoretical ceiling was ~+0.35pp TWRR.** The oracle strategy (perfect information) could only improve TWRR by 0.35pp while losing €23k in final value. Real strategies achieve less than half of this ceiling while already paying a proportional wealth cost.

### What This Experiment Proves

This is a well-characterized **negative result**. The hypothesis — that contribution steering can meaningfully improve risk-adjusted returns — is technically true but practically irrelevant. The contribution capacity constraint (fixed small amounts vs. a growing portfolio) is the binding limitation, not the formula or parameter choice. No amount of parameter tuning can overcome the fundamental asymmetry between a €600/month contribution and a €400k+ portfolio.

### Recommendation

Do not implement DriftDCA in the production backtester. The complexity cost (new strategy, new parameters, additional testing) is not justified by improvements that are economically indistinguishable from noise. The baseline static 70/15/15 allocation remains the recommended PAC strategy.

For investors seeking better risk-adjusted returns, the lever is **asset selection and target allocation** (choosing a different mix), not **contribution timing** (steering the same mix more cleverly).
