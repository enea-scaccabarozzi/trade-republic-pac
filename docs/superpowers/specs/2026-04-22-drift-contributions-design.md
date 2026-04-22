# Experiment 002: Drift-Based Contribution Steering

## Overview

Explore whether dynamically redistributing fixed monthly DCA contributions toward underweight assets (and away from overweight ones) based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation.

**Constraint**: pure redistribution only — the total monthly contribution stays the same (€500-700 uniform). No selling, no fees, no taxes triggered. The only lever is HOW the contribution is split across assets on each PAC date.

**Depends on**: experiment 001-baseline-dca (baseline numbers, proxy chain, config).

## Hypothesis

Dynamically redistributing fixed monthly DCA contributions toward underweight assets based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation, without selling or incurring fees.

## Search Space

The experiment explores three independent dimensions:

### 1. Drift Calculation Method

How to measure allocation drift from target weights.

- **Spot**: use the `DeviationReport` as-is on the PAC date. Simplest, already available via the framework. Sensitive to single-day price moves.
- **SMA (Simple Moving Average)**: track a rolling average of daily allocations over N days, compute drift from that. Reduces noise, introduces lag.
- **EMA (Exponential Moving Average)**: weight recent allocations more heavily. Less lag than SMA for equivalent smoothing.

Smoothing window values to explore: 5, 10, 20, 40 trading days.

### 2. Adjustment Formula

How drift magnitude maps to contribution weight changes.

- **Proportional**: contribution weight shifted linearly with drift magnitude, scaled by `max_tilt_pct`. Simple, continuous, always active.
- **Threshold**: like proportional, but only activates when drift exceeds `threshold_pct`. Avoids unnecessary churn from minor fluctuations.
- **Stepped**: discrete tilt levels (normal / moderate / aggressive) based on drift crossing threshold boundaries.

Threshold values to explore: 1.0%, 2.0%, 3.0%, 5.0%.

### 3. Tilt Aggressiveness

How far contributions can deviate from target weights.

- `max_tilt_pct` ranges from 0.0 (no adjustment, equivalent to baseline) to 1.0 (can allocate 100% of contribution to a single asset).
- Values to sweep: 0.2, 0.4, 0.6, 0.8, 1.0.

## Framework Enhancement: `on_trading_day` Hook

The `BacktestStrategy` ABC needs a new optional hook to support daily observation of portfolio state. Currently strategies can only observe the portfolio on PAC dates (via `on_pac_date`) or when signals fire (via `on_signals`). Strategies that need to compute smoothed drift (SMA/EMA) require daily allocation history.

### Interface

```python
def on_trading_day(
    self,
    snapshot: PortfolioSnapshot,
    report: DeviationReport,
    current_date: date,
) -> None:
    """Optional hook: observe daily portfolio state.

    Called every trading day after snapshot/report computation.
    Use for accumulating state (allocation history, running
    averages). Cannot emit actions — observation only.

    Default: no-op.
    """
```

### Simulator Wiring

In `BacktestSimulator.run_iteration()`, call `self._strategy.on_trading_day(snapshot, report, d)` after step 3 (snapshot + deviation computation) and before step 4 (signal evaluation). This ensures the strategy sees every trading day's state regardless of whether signals fire.

### Testing Requirements

- BDD feature file for the observable behavior (hook is called daily, receives correct data, default no-op doesn't break existing strategies)
- Unit tests for edge cases (empty portfolio, first trading day, reset clears accumulated state)
- Verify existing strategies (baseline_dca and any built-in strategies) are unaffected

### Reset Contract

`reset()` must clear any state accumulated via `on_trading_day`. The `DriftDCA` strategy stores allocation history in an internal buffer; `reset()` clears it.

## Exploration Phase

Statistical groundwork to narrow the search space before writing strategy code. Each script answers a foundational question with quantitative evidence. Scripts that produce kill criteria run first.

### Script 1: Drift Characterization

Analyze the 21-year baseline simulation's daily allocation data.

- Distribution of drift magnitudes per asset over the full period
- Autocorrelation analysis and half-life estimation — is drift persistent or mean-reverting?
- Regime analysis — does drift behavior change during crises vs calm markets?
- **Kill criterion**: if drift never exceeds ~2% from target, contribution steering has negligible room to act

### Script 2: Smoothing Value Assessment

Compare spot drift vs SMA(N) vs EMA(alpha) on the historical allocation series.

- Variance ratio of smoothed vs spot drift (noise reduction quantification)
- Lag measurement — how many days behind does the smoothed signal fall?
- Test multiple windows (5, 10, 20, 40 trading days) and EMA decay constants
- **Narrow criterion**: if smoothing adds significant lag but negligible noise reduction, eliminate smoothed methods from consolidation

### Script 3: Contribution Capacity Analysis

How much rebalancing power do contributions actually have at different portfolio sizes?

- Plot `monthly_contribution / portfolio_value` ratio over the 21-year period
- At each portfolio size, compute the maximum drift correction achievable in a single month
- Identify the crossover point where contributions become structurally too small to matter
- This determines whether the strategy's value is front-loaded (early years) or uniform

### Script 4: Theoretical Ceiling

Simulate a "perfect oracle" that always allocates contributions optimally to minimize drift.

- Upper bound on TWRR/Sharpe improvement over baseline
- Sizes the total opportunity — if the oracle barely beats baseline, the experiment's upside is capped

### Adaptive Narrowing

Exploration findings directly shape what enters consolidation. Examples:
- If smoothing shows no value → drop `drift_method` dimension, use spot only
- If contribution capacity dies after year 10 → weight early-period metrics differently
- If drift is always small → the experiment may conclude early with a negative result

## Consolidation Phase

Build a single parameterized `DriftDCA` strategy and sweep the search space that survived exploration.

### Strategy: `DriftDCA`

One `BacktestStrategy` subclass with parameters controlling all dimensions:

```python
class DriftDCAParams(BaseModel, frozen=True):
    drift_method: Literal["spot", "sma", "ema"] = "spot"
    smoothing_window: int = 20
    adjustment_formula: Literal["proportional", "threshold", "stepped"] = "proportional"
    threshold_pct: float = 3.0
    max_tilt_pct: float = 0.5
```

The strategy overrides `on_pac_date()` to compute drift (using daily state accumulated via `on_trading_day` if smoothing is active) and return a `PacAdjustment` with redistributed volumes.

Invalid parameter combinations (e.g., `smoothing_window` when `drift_method=spot`) are ignored gracefully — the parameter is simply unused.

The exact mathematical formulas for each adjustment method will be designed during consolidation, informed by exploration findings (drift magnitudes, capacity ratios). The high-level descriptions above define the intent; the implementation details are part of the research.

### PAC Configuration

`pac_execution_days=[16]` — monthly on the 16th only, matching experiment 001.

### Consolidation Process

The scripts adapt based on exploration findings. The likely progression:

1. Quick-test a single variant against baseline to validate the strategy works
2. `ctx.compare()` a handful of variants to confirm measurable differences
3. Coarse `ctx.sweep()` across the surviving parameter grid
4. Fine sweep in the promising region
5. Freeze 2-3 candidate parameter sets for validation

This is adaptive — exploration findings may reshape the grid, add/remove dimensions, or redirect the investigation entirely.

## Validation Phase

Standard validation toolkit applied to whatever candidates emerge from consolidation:

- Monte Carlo (N=50, with slippage)
- Out-of-sample holdout
- Walk-forward analysis
- Parameter sensitivity (nearby params shouldn't cause sharp degradation)
- QuantStats tearsheet
- Direct comparison against baseline 001 numbers (TWRR, Sharpe, max drawdown)

The specific runs depend on what consolidation produces. The conclusion answers: **does drift-based contribution steering meaningfully improve on static DCA, and if so, under what configuration?**

## Experiment Structure

```
research/experiments/002-drift-contributions/
├── experiment.toml
├── FINDINGS.md
├── exploration/
│   ├── drift_characterization.py
│   ├── smoothing_assessment.py
│   ├── contribution_capacity.py
│   └── theoretical_ceiling.py
├── consolidation/
│   └── (scripts created based on exploration findings)
├── validation/
│   └── (scripts created based on consolidation findings)
├── strategies/
│   └── drift_dca.py
├── configs/
│   └── baseline.yaml
├── results/
├── artifacts/
└── lib/              (if shared logic emerges across phases)
```
