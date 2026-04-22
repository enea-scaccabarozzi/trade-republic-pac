# Drift-Based Contribution Steering

> **Hypothesis**: Dynamically redistributing fixed monthly DCA contributions toward underweight assets based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation, without selling or incurring fees.
> **Status**: exploring
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

### Scripts Used (in order of creation)

1. [drift_characterization.py](exploration/drift_characterization.py) — analyze drift magnitudes, persistence, and regime behavior over 21 years
2. [smoothing_assessment.py](exploration/smoothing_assessment.py) — compare spot vs SMA vs EMA drift: noise reduction vs lag tradeoff
3. [contribution_capacity.py](exploration/contribution_capacity.py) — measure contribution rebalancing power as portfolio grows
4. [theoretical_ceiling.py](exploration/theoretical_ceiling.py) — oracle strategy upper bound on improvement

### Drift Characterization

*(To be filled after running drift_characterization.py)*

### Smoothing Value Assessment

*(To be filled after running smoothing_assessment.py)*

### Contribution Capacity Analysis

*(To be filled after running contribution_capacity.py)*

### Theoretical Ceiling

*(To be filled after running theoretical_ceiling.py)*

### Failing Paths

*(Document any approaches tried and abandoned)*

### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| *(To be filled)* | | |
