> **Note:** This analysis template was superseded by the full research paper at
> [research/papers/crisis-strategy/paper.md](../research/papers/crisis-strategy/paper.md).
> The tables below were not populated; all findings are in the paper.

# Crisis Exploitation Backtest Analysis

> Generated from `scripts/run_backtest_validation.py` runs.
> Date: YYYY-MM-DD

## Configuration

- **Config file:** `backtest/pac-backtest.yaml`
- **Proxy tickers:** ^GSPC (equity), GC=F→SGLN.L (gold), VBMFX→AGG (bonds)
- **Period:** 1996-01-02 to 2025-12-31
- **Monthly contribution:** €500
- **Initial cash:** €10,000
- **PAC day:** 16th

## A/B Comparison: Baseline vs Crisis-Aware

### Full Period (1996–2025)

| Metric        | Baseline (pac_alignment) | Crisis-Aware (crisis_exploit) | Delta |
| ------------- | ------------------------ | ----------------------------- | ----- |
| CAGR (med)    |                          |                               |       |
| Sortino (med) |                          |                               |       |
| Sharpe (med)  |                          |                               |       |
| Max DD (med)  |                          |                               |       |
| Volatility    |                          |                               |       |
| Final Value   |                          |                               |       |

### Sub-Period: Pre-2010 (1996–2009)

| Metric        | Baseline | Crisis-Aware | Delta |
| ------------- | -------- | ------------ | ----- |
| CAGR (med)    |          |              |       |
| Sortino (med) |          |              |       |
| Max DD (med)  |          |              |       |
| Final Value   |          |              |       |

### Sub-Period: Post-2010 (2010–2025)

| Metric        | Baseline | Crisis-Aware | Delta |
| ------------- | -------- | ------------ | ----- |
| CAGR (med)    |          |              |       |
| Sortino (med) |          |              |       |
| Max DD (med)  |          |              |       |
| Final Value   |          |              |       |

## Sensitivity Analysis

### Sell Fraction (sell_fraction_critical)

| sell_fraction_critical | CAGR (med) | Sortino | Max DD |
| ---------------------- | ---------- | ------- | ------ |
| 0.25                   |            |         |        |
| 0.50 (default)         |            |         |        |
| 0.75                   |            |         |        |

### Cooldown Days

| cooldown_days | CAGR (med) | Sortino | Trade Count |
| ------------- | ---------- | ------- | ----------- |
| 30            |            |         |             |
| 60            |            |         |             |
| 90 (default)  |            |         |             |
| 120           |            |         |             |
| 180           |            |         |             |

### Min Severity

| min_severity       | CAGR (med) | Sortino | Trade Count |
| ------------------ | ---------- | ------- | ----------- |
| WARNING            |            |         |             |
| CRITICAL (default) |            |         |             |

## Assumption Validation

### [A08] Composite fires 2–5 times per decade

- Expected: 6 fires in 28 years (~2.1/decade)
- Observed: ___ fires in the full-period backtest
- **PASS / FAIL**

### [A09] Composite does NOT fire during 2022

- Observed: ___
- **PASS / FAIL**

### [A10] Composite fires during COVID despite brief correlation spike

- Observed: ___
- **PASS / FAIL**

### [A11] Crisis exploitation improves terminal value by ≥1% per event

- Observed delta (full period): ___
- Events in period: ___
- Per-event improvement: ___
- **PASS / FAIL**

## Recommended Parameters

Based on the analysis above, the recommended parameter values are:

| Parameter              | Default  | Recommended | Rationale |
| ---------------------- | -------- | ----------- | --------- |
| sell_fraction_critical | 0.50     |             |           |
| sell_fraction_warning  | 0.25     |             |           |
| cooldown_days          | 90       |             |           |
| min_severity           | CRITICAL |             |           |
| min_active_indicators  | 3        |             |           |
| min_gold_pct           | 5.0      |             |           |
| min_bonds_pct          | 5.0      |             |           |

## Observations & Notes

- (Fill in observations after running backtests)
