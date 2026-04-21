# Analysis

Portfolio deviation calculation and PAC redistribution planning. Pure computation with no side effects or I/O.

## Architectural Role

| Aspect      | Details                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | [`models`](../models/) (`PortfolioSnapshot`, `SignalSeverity`), [`config`](../config/) (`Settings`)                       |
| Consumed by | [`rules`](../rules/) (`evaluate()` calls `calculate_deviations`), [`orchestrator`](../orchestrator/) (`compute_pac_plan`) |
| Boundary    | Deviation math, severity classification, projection-based PAC distribution                                                |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Core portfolio and signal types used as function inputs and outputs | `PortfolioSnapshot`, `SignalSeverity` |
| `config` | `pac.config` | Application settings required to extract target allocations and asset metadata | `Settings` |

## Key Components

| Component                  | File           | Description                                                             |
| -------------------------- | -------------- | ----------------------------------------------------------------------- |
| `calculate_deviations()`   | `deviation.py` | Per-asset deviation from target allocation with severity classification |
| `DeviationResult`          | `deviation.py` | Single-asset deviation data (actual vs target pct, severity)            |
| `DeviationReport`          | `deviation.py` | Aggregated deviation results with worst-case severity                   |
| `classify_severity()`      | `deviation.py` | Maps absolute deviation to `INFO` / `WARNING` / `CRITICAL`              |
| `get_target_allocations()` | `deviation.py` | Extracts asset ID → target pct mapping from `Settings`                  |
| `compute_pac_plan()`       | `rebalance.py` | Projection-based PAC distribution toward target allocation              |
| `calculate_pac_plan()`     | `rebalance.py` | Convenience wrapper combining settings extraction + computation         |
| `PacAllocation`            | `rebalance.py` | Computed PAC amount for a single asset                                  |
| `PacPlan`                  | `rebalance.py` | Aggregated PAC allocations for the month                                |

## Configuration

Deviation thresholds (`warning_pct`, `critical_pct`) are passed as function parameters, not read from config directly. Signal rules set these thresholds via their params model and pass them through.

PAC budget defaults to `Decimal("500.00")` in `calculate_pac_plan()` but can be overridden via `total_budget`.

## Usage

```python
from decimal import Decimal
from pac.analysis import calculate_deviations, compute_pac_plan

# Deviation analysis — returns per-asset severity classification
report = calculate_deviations(snapshot, settings, warning_pct=Decimal("3.0"))
report.max_severity   # worst-case severity across all assets
report.deviations     # {asset_id: DeviationResult}

# PAC redistribution — projects post-investment portfolio and allocates shortfall
plan = compute_pac_plan(
    snapshot,
    targets=settings.target_allocations,
    asset_names={a.id: a.name for a in settings.assets},
    total_budget=Decimal("500.00"),
)
plan.allocations  # {asset_id: PacAllocation}
```

### Design Notes

**Cash in the denominator:** `calculate_deviations` includes cash in `total_value`. When cash > 0, `actual_pct` values sum to less than 100%, correctly signalling underinvestment.

**Projection-based rebalancing:** `compute_pac_plan` projects what the portfolio would look like after investing the full budget, then allocates new money proportionally to each asset's shortfall from its target. Overweight assets receive zero. Penny remainders are absorbed into the largest allocation.

## Commands

```bash
just test -k test_deviation    # deviation calculation tests
just test -k test_rebalance    # PAC redistribution tests
```

## See Also

- [Models](../models/) — `PortfolioSnapshot`, `SignalSeverity` used as inputs
- [Rules](../rules/) — rules call `calculate_deviations` in `evaluate()`
- [Orchestrator](../orchestrator/) — calls `compute_pac_plan` for PAC plan signals
- [Testing Philosophy](../../../docs/testing.md) — analysis uses unit tests (pure math), not BDD
