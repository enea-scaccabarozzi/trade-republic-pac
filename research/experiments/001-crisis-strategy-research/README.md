# 001: Crisis Strategy Research

**Status:** Completed (retroactive backfill from Task 010)

## Summary

Iterative hypothesis-driven research across 9 hypotheses, validating whether
a rule-based crisis detection system can generate alpha for a PAC portfolio.

**Key finding:** Cash flow manipulation (PAC tilt 100/0/0 during crisis + 120d
recovery) is the dominant alpha source (~78%). Hard rebalancing at extreme
drawdowns (≤ −20%) adds marginal alpha (~22%) through only 4 trades in 20 years.

## Published Paper

See [research/papers/crisis-strategy/paper.md](../../papers/crisis-strategy/paper.md)

## Task History

This experiment was conducted as Task 010 before the research framework existed.
Original scripts were not preserved (they lived in `/tmp/`). The experiment is
backfilled here for completeness and dashboard discoverability.

Full task record: `.tasks/010-cycle-strategy-research/task.md`

## Strategy

The winning strategy (`crisis_exploit`) implements two mechanisms:
1. **PAC Tilt** — redirect contributions from 70/15/15 to 100/0/0 during crisis + 120d recovery
2. **Hard Rebalance** — sell gold overweight → buy equities when drawdown ≤ −20% (90d cooldown)

Parameters: see Table 5 in the paper.
