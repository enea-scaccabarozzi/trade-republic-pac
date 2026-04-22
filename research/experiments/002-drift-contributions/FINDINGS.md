# Drift-Based Contribution Steering

> **Hypothesis**: Dynamically redistributing fixed monthly DCA contributions toward underweight assets based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation, without selling or incurring fees.
> **Status**: consolidating
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
2. [smoothing_assessment.py](exploration/smoothing_assessment.py) — compare spot vs SMA vs EMA drift: noise reduction vs lag tradeoff
3. [contribution_capacity.py](exploration/contribution_capacity.py) — measure contribution rebalancing power as portfolio grows
4. [theoretical_ceiling.py](exploration/theoretical_ceiling.py) — oracle strategy upper bound on improvement

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
- 2009: <2pp/month (crossed below 2pp on 2009-08-07)
- 2011: <1pp/month
- 2015: <0.5pp/month

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

2. **Stepped formula dominates TWRR improvement** but at severe drawdown cost. The best stepped configs reach the oracle ceiling (~0.5pp) but with -12.9pp worse max drawdown and -€16k to -€38k less wealth.

3. **Proportional formula is the safest** — consistent small gains with minimal side effects. At tilt=0.5: +0.05pp TWRR, +0.0016 Sharpe, only -€1,408 and no meaningful drawdown change.

4. **Higher tilt always costs more in final value.** The relationship is monotonic: more aggressive steering = more money diverted from stocks = lower terminal wealth.

5. **Threshold parameter matters for stepped formula** — low thresholds (2.0) allow the stepped formula to fire more often, capturing more drift correction. High thresholds (8.0) make it fire rarely, and the discrete jumps cause erratic behavior (several bottom-ranked configs are stepped with high thresholds).

6. **Sharpe improvement is more consistent** across configurations. Even configs that lose on TWRR often gain on Sharpe, suggesting the risk reduction is real even when return improvement is negligible.

### Candidate Selection for Validation

Given the fundamental tension between TWRR/Sharpe and final value, three candidates represent the Pareto frontier:

1. **Conservative**: proportional, tilt=0.3 — +0.03pp TWRR, -€975 final value, nearly unchanged risk
2. **Moderate**: proportional, tilt=1.0 — +0.11pp TWRR, -€2,251 final value, +0.4pp better drawdown
3. **Aggressive**: stepped, tilt=0.5, thresh=2.0 — +0.14pp TWRR, -€8,394 final value, +4.7pp better drawdown

### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| DriftDCA strategy | [strategies/drift_dca.py](strategies/drift_dca.py) | Parameterized strategy with 3 formulas |
| Consolidation sweep | [consolidation/quick_test.py](consolidation/quick_test.py) | Quick-test + 54-config parameter sweep |
| Sweep results | [results/consolidation_sweep.json](results/consolidation_sweep.json) | Full metrics for all configurations |
