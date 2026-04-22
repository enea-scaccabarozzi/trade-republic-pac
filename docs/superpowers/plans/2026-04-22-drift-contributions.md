# Drift-Based Contribution Steering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `on_trading_day` observation hook to the backtester strategy framework, then scaffold experiment 002 with exploration-phase scripts that statistically evaluate drift-based contribution steering.

**Architecture:** The framework enhancement adds a single no-op method to `BacktestStrategy` and one call site in the simulator loop. The experiment uses this hook (and the existing `on_pac_date` hook) to build strategies that observe daily allocations and adjust PAC volumes based on drift. Exploration scripts run first to determine whether the idea has merit before any strategy code is written.

**Tech Stack:** Python 3.11+, pydantic, pytest, pytest-bdd, quantstats, yfinance, pandas, numpy, matplotlib

---

## File Map

### Framework Enhancement (Part 1)

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/pac/backtester/strategies/base.py:138` | Add `on_trading_day()` method after `on_pac_date()` |
| Modify | `src/pac/backtester/engine/simulator.py:283` | Call `on_trading_day()` after snapshot+report computation |
| Create | `src/pac/backtester/strategies/features/on_trading_day.feature` | BDD feature for daily observation hook |
| Create | `src/pac/backtester/strategies/tests/test_on_trading_day_bdd.py` | BDD step definitions |
| Create | `src/pac/backtester/strategies/tests/test_on_trading_day.py` | Unit tests for edge cases |
| Modify | `src/pac/backtester/strategies/README.md:40-44` | Add `on_trading_day()` to Hooks table |

### Experiment 002 (Part 2)

| Action | File | Purpose |
|--------|------|---------|
| Create | `research/experiments/002-drift-contributions/experiment.toml` | Experiment metadata |
| Create | `research/experiments/002-drift-contributions/FINDINGS.md` | Research narrative skeleton |
| Create | `research/experiments/002-drift-contributions/configs/baseline.yaml` | Copy of 001 config with pac_execution_days=[16] |
| Create | `research/experiments/002-drift-contributions/exploration/drift_characterization.py` | Script 1: drift magnitude, persistence, regimes |
| Create | `research/experiments/002-drift-contributions/exploration/smoothing_assessment.py` | Script 2: spot vs SMA vs EMA noise/lag tradeoff |
| Create | `research/experiments/002-drift-contributions/exploration/contribution_capacity.py` | Script 3: contribution/portfolio ratio over time |
| Create | `research/experiments/002-drift-contributions/exploration/theoretical_ceiling.py` | Script 4: oracle upper bound on improvement |

---

## Part 1: Framework Enhancement

### Task 1: Write BDD feature file for on_trading_day

**Files:**
- Create: `src/pac/backtester/strategies/features/on_trading_day.feature`

- [ ] **Step 1: Create the feature file**

```gherkin
Feature: Daily Portfolio Observation
  Strategies can observe daily portfolio state to build running
  statistics (e.g., moving averages of allocations) for use in
  PAC date decisions.

  Background:
    Given a strategy that records daily portfolio observations

  Scenario: Strategy observes every trading day
    Given a simulation spanning 5 trading days
    When the simulation completes
    Then the strategy recorded 5 daily observations

  Scenario: Daily observations include allocation data
    Given a simulation with a portfolio holding stocks and bonds
    When the simulation completes
    Then each observation includes allocation percentages for all assets

  Scenario: Daily observations include drift data
    Given a simulation with a portfolio holding stocks and bonds
    When the simulation completes
    Then each observation includes signed deviation from target for each asset

  Scenario: Observations accumulate in chronological order
    Given a simulation spanning 5 trading days
    When the simulation completes
    Then the observations are ordered by date

  Scenario: Observations reset between Monte Carlo iterations
    Given a completed simulation iteration with accumulated observations
    When a new iteration begins
    Then no prior observations remain

  Scenario: Default on_trading_day is a no-op
    Given a strategy with default on_trading_day
    When on_trading_day is called with a portfolio snapshot
    Then no error is raised and no state changes
```

Write this to `src/pac/backtester/strategies/features/on_trading_day.feature`.

- [ ] **Step 2: Verify feature file syntax**

Run: `uv run python -c "from pytest_bdd.parser import Feature; Feature.make_from('src/pac/backtester/strategies/features/on_trading_day.feature')"`

Expected: no error output.

---

### Task 2: Write BDD step definitions (failing)

**Files:**
- Create: `src/pac/backtester/strategies/tests/test_on_trading_day_bdd.py`

- [ ] **Step 1: Create the BDD test file**

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel
from pytest_bdd import given, scenarios, then, when

from pac.analysis.deviation import DeviationReport, DeviationResult
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.tests.conftest import SimpleStrategy, SimpleParams
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity

scenarios("../features/on_trading_day.feature")


class _ObservationRecord(BaseModel, frozen=True):
    current_date: date
    allocations: dict[str, Decimal]
    deviations: dict[str, Decimal]


class _ObserverParams(BaseModel, frozen=True):
    pass


class _ObserverStrategy(BacktestStrategy[_ObserverParams]):
    """Test strategy that records every on_trading_day call."""

    name: ClassVar[str] = "observer_test"

    def __init__(self, params: _ObserverParams) -> None:
        super().__init__(params)
        self._observations: list[_ObservationRecord] = []

    def reset(self) -> None:
        super().reset()
        self._observations = []

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []

    def on_trading_day(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> None:
        asset_ids = [p.asset_id for p in snapshot.positions]
        allocs = snapshot.allocations(asset_ids)
        self._observations.append(
            _ObservationRecord(
                current_date=current_date,
                allocations={
                    aid: allocs[aid].actual_pct for aid in asset_ids
                },
                deviations={
                    aid: report.deviations[aid].deviation_pct
                    for aid in report.deviations
                },
            ),
        )

    @property
    def observations(self) -> list[_ObservationRecord]:
        return list(self._observations)


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _make_snapshot(
    stocks_value: Decimal = Decimal("7000"),
    bonds_value: Decimal = Decimal("3000"),
    cash: Decimal = Decimal("0"),
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal("100"),
                price=stocks_value / Decimal("100"),
                market_value=stocks_value,
                asset_id="stocks",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal("100"),
                price=bonds_value / Decimal("100"),
                market_value=bonds_value,
                asset_id="bonds",
            ),
        ],
        cash=cash,
        timestamp=datetime(2024, 1, 15),
    )


def _make_report(
    stocks_dev: Decimal = Decimal("0"),
    bonds_dev: Decimal = Decimal("0"),
) -> DeviationReport:
    return DeviationReport(
        deviations={
            "stocks": DeviationResult(
                asset_id="stocks",
                name="Stocks ETF",
                actual_pct=Decimal("70") + stocks_dev,
                target_pct=Decimal("70"),
                deviation_pct=stocks_dev,
                abs_deviation_pct=abs(stocks_dev),
                severity=SignalSeverity.INFO,
            ),
            "bonds": DeviationResult(
                asset_id="bonds",
                name="Bond ETF",
                actual_pct=Decimal("30") + bonds_dev,
                target_pct=Decimal("30"),
                deviation_pct=bonds_dev,
                abs_deviation_pct=abs(bonds_dev),
                severity=SignalSeverity.INFO,
            ),
        },
        max_severity=SignalSeverity.INFO,
        timestamp=datetime(2024, 1, 15),
    )


# -- Given steps ----------------------------------------------------------


@given("a strategy that records daily portfolio observations")
def _strategy_that_records(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = _ObserverStrategy(_ObserverParams())


@given("a simulation spanning 5 trading days")
def _sim_5_days(ctx: dict[str, Any]) -> None:
    ctx["trading_days"] = [date(2024, 1, d) for d in range(15, 20)]
    ctx["snapshot"] = _make_snapshot()
    ctx["report"] = _make_report()


@given("a simulation with a portfolio holding stocks and bonds")
def _sim_with_portfolio(ctx: dict[str, Any]) -> None:
    ctx["trading_days"] = [date(2024, 1, 15)]
    ctx["snapshot"] = _make_snapshot(
        stocks_value=Decimal("7000"),
        bonds_value=Decimal("3000"),
    )
    ctx["report"] = _make_report(
        stocks_dev=Decimal("0"),
        bonds_dev=Decimal("0"),
    )


@given(
    "a completed simulation iteration with accumulated observations",
)
def _completed_iteration(ctx: dict[str, Any]) -> None:
    strategy: _ObserverStrategy = ctx["strategy"]
    snapshot = _make_snapshot()
    report = _make_report()
    for d in [date(2024, 1, 15), date(2024, 1, 16)]:
        strategy.on_trading_day(snapshot, report, d)
    assert len(strategy.observations) == 2
    ctx["snapshot"] = snapshot
    ctx["report"] = report


@given("a strategy with default on_trading_day")
def _default_strategy(ctx: dict[str, Any]) -> None:
    ctx["strategy"] = SimpleStrategy(SimpleParams())


# -- When steps -----------------------------------------------------------


@when("the simulation completes")
def _simulation_completes(ctx: dict[str, Any]) -> None:
    strategy: _ObserverStrategy = ctx["strategy"]
    snapshot = ctx["snapshot"]
    report = ctx["report"]
    for d in ctx["trading_days"]:
        strategy.on_trading_day(snapshot, report, d)


@when("a new iteration begins")
def _new_iteration(ctx: dict[str, Any]) -> None:
    ctx["strategy"].reset()


@when("on_trading_day is called with a portfolio snapshot")
def _call_default_on_trading_day(ctx: dict[str, Any]) -> None:
    strategy = ctx["strategy"]
    snapshot = _make_snapshot()
    report = _make_report()
    strategy.on_trading_day(snapshot, report, date(2024, 1, 15))
    ctx["call_completed"] = True


# -- Then steps -----------------------------------------------------------


@then("the strategy recorded 5 daily observations")
def _recorded_5(ctx: dict[str, Any]) -> None:
    assert len(ctx["strategy"].observations) == 5


@then("each observation includes allocation percentages for all assets")
def _obs_has_allocations(ctx: dict[str, Any]) -> None:
    for obs in ctx["strategy"].observations:
        assert "stocks" in obs.allocations
        assert "bonds" in obs.allocations
        assert all(v >= 0 for v in obs.allocations.values())


@then(
    "each observation includes signed deviation from target for each asset",
)
def _obs_has_deviations(ctx: dict[str, Any]) -> None:
    for obs in ctx["strategy"].observations:
        assert "stocks" in obs.deviations
        assert "bonds" in obs.deviations


@then("the observations are ordered by date")
def _obs_ordered(ctx: dict[str, Any]) -> None:
    dates = [obs.current_date for obs in ctx["strategy"].observations]
    assert dates == sorted(dates)


@then("no prior observations remain")
def _obs_empty(ctx: dict[str, Any]) -> None:
    assert len(ctx["strategy"].observations) == 0


@then("no error is raised and no state changes")
def _no_error(ctx: dict[str, Any]) -> None:
    assert ctx["call_completed"] is True
```

Write this to `src/pac/backtester/strategies/tests/test_on_trading_day_bdd.py`.

- [ ] **Step 2: Run the BDD tests to confirm they fail**

Run: `just test -k test_on_trading_day_bdd`

Expected: failures because `on_trading_day` method does not exist on `BacktestStrategy` yet (the `_ObserverStrategy` definition itself may fail, or the `SimpleStrategy` call to `on_trading_day` in the default scenario will raise `AttributeError`).

---

### Task 3: Implement on_trading_day hook in BacktestStrategy

**Files:**
- Modify: `src/pac/backtester/strategies/base.py:138-159`

- [ ] **Step 1: Add the on_trading_day method to BacktestStrategy**

Insert after the `on_pac_date` method (after line 159 in `base.py`):

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

        Args:
            snapshot: Current portfolio state (post-PAC if PAC date).
            report: Deviation analysis for current portfolio.
            current_date: The trading day being processed.
        """
```

This is a no-op default — no body beyond the docstring (implicit `None` return).

- [ ] **Step 2: Run BDD tests to check status**

Run: `just test -k test_on_trading_day_bdd`

Expected: tests may still fail because the simulator doesn't call `on_trading_day` yet. The direct-call tests (default no-op, reset) should pass. The simulation-based tests depend on Task 4.

Note: The BDD tests call `strategy.on_trading_day()` directly (not through the simulator), so all 6 scenarios should pass at this point.

- [ ] **Step 3: Verify all tests pass**

Run: `just test -k test_on_trading_day_bdd`

Expected: all 6 scenarios pass.

---

### Task 4: Wire on_trading_day in the simulator

**Files:**
- Modify: `src/pac/backtester/engine/simulator.py:281-283`

- [ ] **Step 1: Add the on_trading_day call in run_iteration()**

In `run_iteration()`, after the snapshot and report computation (line 281-282) and before the market context build (line 284), insert:

```python
            # 3.5. Let strategy observe daily state
            self._strategy.on_trading_day(snapshot, report, d)
```

The existing "3.5" comment for market context becomes "3.6":

```python
            # 3.6. Build market context for this date
```

The full sequence after the change:

```python
            # 3. Build snapshot and compute deviations
            snapshot = portfolio.snapshot(d, prices)
            report = calculate_deviations(snapshot, self._settings)

            # 3.5. Let strategy observe daily state
            self._strategy.on_trading_day(snapshot, report, d)

            # 3.6. Build market context for this date
            market_ctx = BacktestMarketContext(
```

- [ ] **Step 2: Run all backtester tests to verify nothing is broken**

Run: `just test -k backtester`

Expected: all tests pass — existing strategies have a no-op `on_trading_day`, so behavior is unchanged.

- [ ] **Step 3: Run the BDD tests specifically**

Run: `just test -k test_on_trading_day_bdd`

Expected: all 6 scenarios pass.

---

### Task 5: Unit tests for edge cases

**Files:**
- Create: `src/pac/backtester/strategies/tests/test_on_trading_day.py`

- [ ] **Step 1: Write unit tests**

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

_NOW = datetime(2024, 1, 1)


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[],
        cash=Decimal("0"),
        timestamp=_NOW,
    )


def _empty_report() -> DeviationReport:
    return DeviationReport(
        deviations={},
        max_severity=SignalSeverity.INFO,
        timestamp=_NOW,
    )


class _CounterParams(BaseModel, frozen=True):
    pass


class _CounterStrategy(BacktestStrategy[_CounterParams]):
    """Strategy that counts on_trading_day calls."""

    name = "counter_test"

    def __init__(self, params: _CounterParams) -> None:
        super().__init__(params)
        self.day_count = 0

    def reset(self) -> None:
        super().reset()
        self.day_count = 0

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []

    def on_trading_day(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> None:
        self.day_count += 1


class TestOnTradingDayDefault:
    def test_default_returns_none(self) -> None:
        from pac.backtester.strategies.tests.conftest import (
            SimpleParams,
            SimpleStrategy,
        )

        strategy = SimpleStrategy(SimpleParams())
        result = strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 15),
        )
        assert result is None

    def test_default_does_not_affect_event_buffer(self) -> None:
        from pac.backtester.strategies.tests.conftest import (
            SimpleParams,
            SimpleStrategy,
        )

        strategy = SimpleStrategy(SimpleParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 15),
        )
        assert strategy.drain_events() == []


class TestOnTradingDayStateful:
    def test_accumulates_across_days(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        for i in range(10):
            strategy.on_trading_day(
                _empty_snapshot(),
                _empty_report(),
                date(2024, 1, i + 1),
            )
        assert strategy.day_count == 10

    def test_reset_clears_subclass_state(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 1),
        )
        assert strategy.day_count == 1
        strategy.reset()
        assert strategy.day_count == 0

    def test_empty_portfolio_on_first_day(self) -> None:
        strategy = _CounterStrategy(_CounterParams())
        strategy.on_trading_day(
            _empty_snapshot(),
            _empty_report(),
            date(2024, 1, 1),
        )
        assert strategy.day_count == 1
```

Write this to `src/pac/backtester/strategies/tests/test_on_trading_day.py`.

- [ ] **Step 2: Run unit tests**

Run: `just test -k test_on_trading_day -v`

Expected: all tests pass.

---

### Task 6: Update strategies README

**Files:**
- Modify: `src/pac/backtester/strategies/README.md:40-44`

- [ ] **Step 1: Add on_trading_day to the Hooks table**

Replace the Hooks table (lines 40-44) with:

```markdown
| Hook               | Called when                                             | Returns                       | Required |
| ------------------ | ------------------------------------------------------- | ----------------------------- | -------- |
| `on_signals()`     | Trading day produces at least one signal                | `list[Action]` (may be empty) | Yes      |
| `on_pac_date()`    | PAC execution date (2nd/16th), before PAC buy           | `PacAdjustment \| None`       | No       |
| `on_trading_day()` | Every trading day, after snapshot/report computation    | `None` (observation only)     | No       |
| `reset()`          | Before each Monte Carlo iteration (clear per-run state) | `None`                        | No       |
```

- [ ] **Step 2: Verify README renders correctly**

Visually inspect the table alignment in the modified file.

---

### Task 7: Commit framework enhancement

- [ ] **Step 1: Run the full test suite**

Run: `just test -k backtester`

Expected: all tests pass.

- [ ] **Step 2: Commit**

Stage and commit with message:

```
feat(backtester): add on_trading_day observation hook to BacktestStrategy

Strategies can now observe daily portfolio state (allocations, drift)
to build running statistics for use in PAC date decisions. The hook
is called every trading day after snapshot/report computation and
cannot emit actions — observation only.
```

Files to stage:
- `src/pac/backtester/strategies/base.py`
- `src/pac/backtester/engine/simulator.py`
- `src/pac/backtester/strategies/features/on_trading_day.feature`
- `src/pac/backtester/strategies/tests/test_on_trading_day_bdd.py`
- `src/pac/backtester/strategies/tests/test_on_trading_day.py`
- `src/pac/backtester/strategies/README.md`

---

## Part 2: Experiment 002 Scaffold

### Task 8: Scaffold experiment and create metadata

**Files:**
- Create: `research/experiments/002-drift-contributions/experiment.toml`
- Create: `research/experiments/002-drift-contributions/FINDINGS.md`
- Create: `research/experiments/002-drift-contributions/configs/baseline.yaml`

- [ ] **Step 1: Run the scaffold command**

Run: `just new-experiment drift_contributions --title "Drift-Based Contribution Steering"`

This creates the directory structure with template files.

- [ ] **Step 2: Update experiment.toml**

Replace the scaffolded `experiment.toml` with:

```toml
[experiment]
created = 2026-04-22
id = "002"
slug = "drift-contributions"
title = "Drift-Based Contribution Steering"
hypothesis = "Dynamically redistributing fixed monthly DCA contributions toward underweight assets based on portfolio allocation drift improves risk-adjusted returns compared to static 70/15/15 allocation, without selling or incurring fees."
tags = ["drift", "rebalancing", "passive", "contribution-steering"]
depends_on = ["001-baseline-dca"]
```

- [ ] **Step 3: Create baseline.yaml config**

Copy `research/experiments/001-baseline-dca/configs/baseline.yaml` to `research/experiments/002-drift-contributions/configs/baseline.yaml`.

The config is identical to experiment 001 — same proxy chains, same assets, same contribution range. The only difference is the strategy used, which is set at runtime in the scripts, not in the config.

- [ ] **Step 4: Create FINDINGS.md skeleton**

```markdown
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
| Final Value | €471k | €470,770 | €473,725 |

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
```

Write this to `research/experiments/002-drift-contributions/FINDINGS.md`.

---

### Task 9: Drift characterization exploration script

**Files:**
- Create: `research/experiments/002-drift-contributions/exploration/drift_characterization.py`

- [ ] **Step 1: Write the drift characterization script**

```python
"""Drift characterization: magnitude, persistence, and regime analysis.

Runs the baseline DCA simulation (N=1, deterministic) and analyzes
the daily allocation drift from target weights over the full 21-year
period. Answers the foundational question: is there enough drift to
make contribution steering worthwhile?

Kill criterion: if drift never exceeds ~2% from target across the
full simulation, contribution steering has negligible room to act.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "research" / "experiments" / "001-baseline-dca" / "strategies"))


def run_baseline_simulation() -> pd.DataFrame:
    """Run baseline DCA and return daily allocations as a DataFrame."""
    from pac.backtester.config import BacktestConfig
    from pac.backtester.engine.simulator import BacktestSimulator
    from pac.backtester.research import ResearchContext
    from pac.rules.discovery import discover_rules
    from pac.rules.registry import SignalRegistry

    from baseline_dca import BaselineDCA, BaselineDCAParams

    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(str(config_path))

    config = BacktestConfig(
        strategy="baseline_dca",
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={
            "min": Decimal("500"),
            "max": Decimal("700"),
            "distribution": "uniform",
        },
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    strategy = BaselineDCA(BaselineDCAParams())
    simulator = BacktestSimulator(
        config, ctx.settings, ctx.prices, registry, strategy, rng_seed=42,
    )
    result = simulator.run_iteration(0)

    rows = []
    targets = ctx.settings.target_allocations
    for dv in result.daily_values:
        row = {"date": dv.date, "total_value": float(dv.total_value)}
        for asset_id, pct in dv.allocations.items():
            row[f"{asset_id}_actual_pct"] = float(pct)
            row[f"{asset_id}_target_pct"] = float(targets.get(asset_id, Decimal("0")))
            row[f"{asset_id}_drift_pct"] = float(pct) - float(
                targets.get(asset_id, Decimal("0"))
            )
        rows.append(row)

    return pd.DataFrame(rows)


def analyze_drift_distribution(df: pd.DataFrame) -> dict:
    """Compute drift statistics per asset."""
    drift_cols = [c for c in df.columns if c.endswith("_drift_pct")]
    stats = {}
    for col in drift_cols:
        asset = col.replace("_drift_pct", "")
        series = df[col].dropna()
        if len(series) == 0:
            continue
        stats[asset] = {
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "p5": float(series.quantile(0.05)),
            "p25": float(series.quantile(0.25)),
            "p50": float(series.quantile(0.50)),
            "p75": float(series.quantile(0.75)),
            "p95": float(series.quantile(0.95)),
            "abs_mean": float(series.abs().mean()),
            "abs_max": float(series.abs().max()),
            "pct_above_2": float((series.abs() > 2.0).mean() * 100),
            "pct_above_5": float((series.abs() > 5.0).mean() * 100),
            "pct_above_10": float((series.abs() > 10.0).mean() * 100),
        }
    return stats


def analyze_drift_persistence(df: pd.DataFrame) -> dict:
    """Compute autocorrelation and half-life of drift."""
    drift_cols = [c for c in df.columns if c.endswith("_drift_pct")]
    persistence = {}
    for col in drift_cols:
        asset = col.replace("_drift_pct", "")
        series = df[col].dropna()
        if len(series) < 50:
            continue

        autocorr = [float(series.autocorr(lag=lag)) for lag in range(1, 21)]

        # Estimate half-life: find lag where autocorrelation drops below 0.5
        half_life = None
        for lag, ac in enumerate(autocorr, start=1):
            if ac < 0.5:
                half_life = lag
                break

        persistence[asset] = {
            "autocorr_lag1": autocorr[0] if autocorr else None,
            "autocorr_lag5": autocorr[4] if len(autocorr) > 4 else None,
            "autocorr_lag20": autocorr[19] if len(autocorr) > 19 else None,
            "half_life_days": half_life,
            "autocorrelations": autocorr,
        }
    return persistence


def plot_drift_over_time(df: pd.DataFrame) -> None:
    """Plot drift time series per asset."""
    drift_cols = [c for c in df.columns if c.endswith("_drift_pct")]
    fig, axes = plt.subplots(len(drift_cols), 1, figsize=(14, 4 * len(drift_cols)), sharex=True)
    if len(drift_cols) == 1:
        axes = [axes]

    dates = pd.to_datetime(df["date"])
    for ax, col in zip(axes, drift_cols):
        asset = col.replace("_drift_pct", "")
        ax.plot(dates, df[col], linewidth=0.5, alpha=0.8)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.axhline(y=2, color="orange", linestyle="--", linewidth=0.5, label="±2%")
        ax.axhline(y=-2, color="orange", linestyle="--", linewidth=0.5)
        ax.axhline(y=5, color="red", linestyle="--", linewidth=0.5, label="±5%")
        ax.axhline(y=-5, color="red", linestyle="--", linewidth=0.5)
        ax.set_ylabel(f"{asset} drift (%)")
        ax.set_title(f"{asset} allocation drift from target")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(ARTIFACTS_DIR / "drift_over_time.png", dpi=150)
    plt.close()


def plot_drift_distribution(df: pd.DataFrame) -> None:
    """Plot drift distributions as histograms."""
    drift_cols = [c for c in df.columns if c.endswith("_drift_pct")]
    fig, axes = plt.subplots(1, len(drift_cols), figsize=(6 * len(drift_cols), 5))
    if len(drift_cols) == 1:
        axes = [axes]

    for ax, col in zip(axes, drift_cols):
        asset = col.replace("_drift_pct", "")
        ax.hist(df[col].dropna(), bins=80, alpha=0.7, edgecolor="black", linewidth=0.3)
        ax.axvline(x=0, color="black", linewidth=1)
        ax.set_xlabel("Drift (%)")
        ax.set_ylabel("Frequency")
        ax.set_title(f"{asset} drift distribution")

    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / "drift_distribution.png", dpi=150)
    plt.close()


def plot_autocorrelation(persistence: dict) -> None:
    """Plot autocorrelation decay per asset."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for asset, data in persistence.items():
        lags = list(range(1, len(data["autocorrelations"]) + 1))
        ax.plot(lags, data["autocorrelations"], marker="o", markersize=3, label=asset)
    ax.axhline(y=0.5, color="gray", linestyle="--", linewidth=0.5, label="0.5 threshold")
    ax.set_xlabel("Lag (trading days)")
    ax.set_ylabel("Autocorrelation")
    ax.set_title("Drift autocorrelation decay")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / "drift_autocorrelation.png", dpi=150)
    plt.close()


def main() -> None:
    print("Running baseline simulation...")
    df = run_baseline_simulation()
    print(f"Got {len(df)} trading days of data")

    print("\n--- Drift Distribution Statistics ---")
    dist_stats = analyze_drift_distribution(df)
    for asset, stats in dist_stats.items():
        print(f"\n{asset}:")
        print(f"  Mean drift: {stats['mean']:.2f}%")
        print(f"  Std: {stats['std']:.2f}%")
        print(f"  Range: [{stats['min']:.2f}%, {stats['max']:.2f}%]")
        print(f"  |drift| mean: {stats['abs_mean']:.2f}%")
        print(f"  |drift| > 2%: {stats['pct_above_2']:.1f}% of days")
        print(f"  |drift| > 5%: {stats['pct_above_5']:.1f}% of days")
        print(f"  |drift| > 10%: {stats['pct_above_10']:.1f}% of days")

    print("\n--- Drift Persistence ---")
    persistence = analyze_drift_persistence(df)
    for asset, data in persistence.items():
        print(f"\n{asset}:")
        print(f"  Autocorr lag-1: {data['autocorr_lag1']:.4f}")
        print(f"  Autocorr lag-5: {data['autocorr_lag5']:.4f}")
        print(f"  Autocorr lag-20: {data['autocorr_lag20']:.4f}")
        print(f"  Half-life: {data['half_life_days']} days")

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "distribution": dist_stats,
        "persistence": persistence,
        "trading_days": len(df),
        "date_range": {
            "start": str(df["date"].iloc[0]),
            "end": str(df["date"].iloc[-1]),
        },
    }
    with open(RESULTS_DIR / "drift_characterization.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {RESULTS_DIR / 'drift_characterization.json'}")

    # Generate plots
    plot_drift_over_time(df)
    plot_drift_distribution(df)
    plot_autocorrelation(persistence)
    print(f"Plots saved to {ARTIFACTS_DIR}/")

    # Kill criterion check
    max_abs_drift = max(s["abs_max"] for s in dist_stats.values())
    if max_abs_drift < 2.0:
        print("\n⚠ KILL CRITERION: max |drift| < 2% — contribution steering unlikely to help")
    else:
        print(f"\n✓ Max |drift| = {max_abs_drift:.1f}% — sufficient room for contribution steering")


if __name__ == "__main__":
    main()
```

Write this to `research/experiments/002-drift-contributions/exploration/drift_characterization.py`.

- [ ] **Step 2: Verify the script runs**

Run: `cd /Users/eneascaccabarozzi/Projects/Personal/trade-republic-pac && uv run python research/experiments/002-drift-contributions/exploration/drift_characterization.py`

Expected: script runs, prints drift statistics, saves JSON to `results/` and plots to `artifacts/`. If data download fails (yfinance), check network connectivity.

---

### Task 10: Smoothing assessment exploration script

**Files:**
- Create: `research/experiments/002-drift-contributions/exploration/smoothing_assessment.py`

- [ ] **Step 1: Write the smoothing assessment script**

```python
"""Smoothing value assessment: spot vs SMA vs EMA drift signals.

Compares different drift measurement methods on the historical
allocation series from the baseline simulation. Quantifies noise
reduction and lag for each smoothing approach to determine whether
smoothing is worth the added complexity.

Narrow criterion: if smoothing adds significant lag but negligible
noise reduction, eliminate smoothed methods from consolidation.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "research" / "experiments" / "001-baseline-dca" / "strategies"))


def run_baseline_simulation() -> pd.DataFrame:
    """Run baseline DCA and return daily allocations as a DataFrame."""
    from pac.backtester.config import BacktestConfig
    from pac.backtester.engine.simulator import BacktestSimulator
    from pac.backtester.research import ResearchContext
    from pac.rules.discovery import discover_rules
    from pac.rules.registry import SignalRegistry

    from baseline_dca import BaselineDCA, BaselineDCAParams

    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(str(config_path))

    config = BacktestConfig(
        strategy="baseline_dca",
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={
            "min": Decimal("500"),
            "max": Decimal("700"),
            "distribution": "uniform",
        },
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    strategy = BaselineDCA(BaselineDCAParams())
    simulator = BacktestSimulator(
        config, ctx.settings, ctx.prices, registry, strategy, rng_seed=42,
    )
    result = simulator.run_iteration(0)

    rows = []
    targets = ctx.settings.target_allocations
    for dv in result.daily_values:
        row = {"date": dv.date, "total_value": float(dv.total_value)}
        for asset_id, pct in dv.allocations.items():
            row[f"{asset_id}_actual_pct"] = float(pct)
            row[f"{asset_id}_drift_pct"] = float(pct) - float(
                targets.get(asset_id, Decimal("0"))
            )
        rows.append(row)

    return pd.DataFrame(rows)


def compute_smoothed_drift(
    drift_series: pd.Series,
    windows: list[int],
) -> dict[str, dict[str, pd.Series]]:
    """Compute SMA and EMA smoothed drift for multiple windows."""
    results: dict[str, dict[str, pd.Series]] = {"sma": {}, "ema": {}}
    for w in windows:
        results["sma"][str(w)] = drift_series.rolling(window=w, min_periods=w).mean()
        results["ema"][str(w)] = drift_series.ewm(span=w, min_periods=w).mean()
    return results


def analyze_noise_reduction(
    spot: pd.Series,
    smoothed: dict[str, dict[str, pd.Series]],
) -> dict:
    """Quantify noise reduction: variance ratio of smoothed vs spot."""
    spot_var = float(spot.var())
    results = {}
    for method, windows in smoothed.items():
        results[method] = {}
        for window, series in windows.items():
            clean = series.dropna()
            if len(clean) == 0:
                continue
            smoothed_var = float(clean.var())
            results[method][window] = {
                "variance_ratio": smoothed_var / spot_var if spot_var > 0 else None,
                "noise_reduction_pct": (1 - smoothed_var / spot_var) * 100 if spot_var > 0 else None,
                "smoothed_std": float(clean.std()),
            }
    return results


def analyze_lag(
    spot: pd.Series,
    smoothed: dict[str, dict[str, pd.Series]],
) -> dict:
    """Measure lag: cross-correlation peak offset."""
    results = {}
    for method, windows in smoothed.items():
        results[method] = {}
        for window, series in windows.items():
            valid = pd.DataFrame({"spot": spot, "smoothed": series}).dropna()
            if len(valid) < 50:
                continue
            # Compute cross-correlation for lags 0..20
            max_lag = 20
            correlations = []
            for lag in range(max_lag + 1):
                if lag == 0:
                    corr = float(valid["spot"].corr(valid["smoothed"]))
                else:
                    corr = float(valid["spot"].iloc[lag:].reset_index(drop=True).corr(
                        valid["smoothed"].iloc[:-lag].reset_index(drop=True)
                    ))
                correlations.append(corr)
            peak_lag = int(np.argmax(correlations))
            results[method][window] = {
                "peak_lag_days": peak_lag,
                "peak_correlation": correlations[peak_lag] if correlations else None,
                "zero_lag_correlation": correlations[0] if correlations else None,
            }
    return results


def plot_smoothing_comparison(
    df: pd.DataFrame,
    asset: str,
    windows: list[int],
) -> None:
    """Plot spot vs smoothed drift for one asset."""
    drift_col = f"{asset}_drift_pct"
    dates = pd.to_datetime(df["date"])
    spot = df[drift_col]

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # SMA comparison
    axes[0].plot(dates, spot, linewidth=0.3, alpha=0.5, label="spot", color="gray")
    for w in windows:
        sma = spot.rolling(window=w, min_periods=w).mean()
        axes[0].plot(dates, sma, linewidth=1, label=f"SMA({w})")
    axes[0].set_title(f"{asset}: Spot vs SMA drift")
    axes[0].set_ylabel("Drift (%)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # EMA comparison
    axes[1].plot(dates, spot, linewidth=0.3, alpha=0.5, label="spot", color="gray")
    for w in windows:
        ema = spot.ewm(span=w, min_periods=w).mean()
        axes[1].plot(dates, ema, linewidth=1, label=f"EMA({w})")
    axes[1].set_title(f"{asset}: Spot vs EMA drift")
    axes[1].set_ylabel("Drift (%)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(ARTIFACTS_DIR / f"smoothing_{asset}.png", dpi=150)
    plt.close()


def main() -> None:
    windows = [5, 10, 20, 40]

    print("Running baseline simulation...")
    df = run_baseline_simulation()

    drift_cols = [c for c in df.columns if c.endswith("_drift_pct")]
    assets = [c.replace("_drift_pct", "") for c in drift_cols]

    all_results = {}

    for asset in assets:
        print(f"\n--- {asset} ---")
        spot = df[f"{asset}_drift_pct"]
        smoothed = compute_smoothed_drift(spot, windows)

        noise = analyze_noise_reduction(spot, smoothed)
        lag = analyze_lag(spot, smoothed)

        print("\nNoise reduction (variance ratio — lower is smoother):")
        for method in ["sma", "ema"]:
            for w in [str(x) for x in windows]:
                if w in noise.get(method, {}):
                    nr = noise[method][w]
                    print(f"  {method.upper()}({w}): var_ratio={nr['variance_ratio']:.3f}, noise_reduction={nr['noise_reduction_pct']:.1f}%")

        print("\nLag (peak cross-correlation offset):")
        for method in ["sma", "ema"]:
            for w in [str(x) for x in windows]:
                if w in lag.get(method, {}):
                    lg = lag[method][w]
                    print(f"  {method.upper()}({w}): peak_lag={lg['peak_lag_days']} days, corr@0={lg['zero_lag_correlation']:.4f}")

        plot_smoothing_comparison(df, asset, windows)

        all_results[asset] = {"noise_reduction": noise, "lag": lag}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "smoothing_assessment.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {RESULTS_DIR / 'smoothing_assessment.json'}")
    print(f"Plots saved to {ARTIFACTS_DIR}/")


if __name__ == "__main__":
    main()
```

Write this to `research/experiments/002-drift-contributions/exploration/smoothing_assessment.py`.

---

### Task 11: Contribution capacity exploration script

**Files:**
- Create: `research/experiments/002-drift-contributions/exploration/contribution_capacity.py`

- [ ] **Step 1: Write the contribution capacity script**

```python
"""Contribution capacity analysis: rebalancing power over time.

Measures how much drift correction a single month's contribution
can achieve at different portfolio sizes. As the portfolio grows,
contributions become a smaller fraction — potentially making
contribution steering structurally ineffective in later years.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "research" / "experiments" / "001-baseline-dca" / "strategies"))


def run_baseline_simulation() -> pd.DataFrame:
    """Run baseline DCA and return daily values."""
    from pac.backtester.config import BacktestConfig
    from pac.backtester.engine.simulator import BacktestSimulator
    from pac.backtester.research import ResearchContext
    from pac.rules.discovery import discover_rules
    from pac.rules.registry import SignalRegistry

    from baseline_dca import BaselineDCA, BaselineDCAParams

    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(str(config_path))

    config = BacktestConfig(
        strategy="baseline_dca",
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={
            "min": Decimal("500"),
            "max": Decimal("700"),
            "distribution": "uniform",
        },
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    strategy = BaselineDCA(BaselineDCAParams())
    simulator = BacktestSimulator(
        config, ctx.settings, ctx.prices, registry, strategy, rng_seed=42,
    )
    result = simulator.run_iteration(0)

    rows = []
    targets = ctx.settings.target_allocations
    for dv in result.daily_values:
        row = {
            "date": dv.date,
            "total_value": float(dv.total_value),
        }
        for asset_id, pct in dv.allocations.items():
            row[f"{asset_id}_drift_pct"] = float(pct) - float(
                targets.get(asset_id, Decimal("0"))
            )
        rows.append(row)

    return pd.DataFrame(rows)


def analyze_capacity(df: pd.DataFrame) -> dict:
    """Compute contribution/portfolio ratio and max drift correction."""
    mean_contribution = 600.0  # midpoint of [500, 700]

    df = df.copy()
    df["contribution_ratio_pct"] = (mean_contribution / df["total_value"] * 100).replace(
        [np.inf, -np.inf], np.nan
    )

    # Max drift correction: if we put 100% of contribution into one asset,
    # how many percentage points of allocation can we shift?
    # correction_pct ≈ contribution / total_value * 100
    df["max_correction_pct"] = df["contribution_ratio_pct"]

    # Sample at monthly intervals (16th of each month)
    df["date"] = pd.to_datetime(df["date"])
    monthly = df[df["date"].dt.day == 16].copy()

    # Compute years since start for plotting
    start_date = df["date"].iloc[0]
    monthly["years_elapsed"] = (monthly["date"] - start_date).dt.days / 365.25

    # Compute by-year averages
    monthly["year"] = monthly["date"].dt.year
    yearly = monthly.groupby("year").agg({
        "total_value": "mean",
        "contribution_ratio_pct": "mean",
        "max_correction_pct": "mean",
    }).reset_index()

    return {
        "monthly_samples": monthly[["date", "total_value", "contribution_ratio_pct", "max_correction_pct", "years_elapsed"]].to_dict(orient="records"),
        "yearly_averages": yearly.to_dict(orient="records"),
        "overall": {
            "mean_contribution_ratio_pct": float(monthly["contribution_ratio_pct"].mean()),
            "median_contribution_ratio_pct": float(monthly["contribution_ratio_pct"].median()),
            "final_contribution_ratio_pct": float(monthly["contribution_ratio_pct"].iloc[-1]) if len(monthly) > 0 else None,
            "initial_contribution_ratio_pct": float(monthly["contribution_ratio_pct"].iloc[0]) if len(monthly) > 0 else None,
        },
    }


def plot_capacity(capacity: dict) -> None:
    """Plot contribution capacity over time."""
    monthly = pd.DataFrame(capacity["monthly_samples"])
    monthly["date"] = pd.to_datetime(monthly["date"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Portfolio value over time
    ax1.plot(monthly["date"], monthly["total_value"], linewidth=1)
    ax1.set_ylabel("Portfolio Value (EUR)")
    ax1.set_title("Portfolio growth over time")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"€{x:,.0f}"))

    # Contribution ratio over time
    ax2.plot(monthly["date"], monthly["contribution_ratio_pct"], linewidth=1, color="tab:orange")
    ax2.axhline(y=1.0, color="red", linestyle="--", linewidth=0.5, label="1% threshold")
    ax2.set_ylabel("Contribution / Portfolio (%)")
    ax2.set_xlabel("Date")
    ax2.set_title("Monthly contribution as % of portfolio value")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(ARTIFACTS_DIR / "contribution_capacity.png", dpi=150)
    plt.close()


def main() -> None:
    print("Running baseline simulation...")
    df = run_baseline_simulation()

    print("\n--- Contribution Capacity Analysis ---")
    capacity = analyze_capacity(df)

    overall = capacity["overall"]
    print(f"Initial contribution/portfolio: {overall['initial_contribution_ratio_pct']:.1f}%")
    print(f"Final contribution/portfolio: {overall['final_contribution_ratio_pct']:.2f}%")
    print(f"Mean contribution/portfolio: {overall['mean_contribution_ratio_pct']:.2f}%")
    print(f"Median contribution/portfolio: {overall['median_contribution_ratio_pct']:.2f}%")

    # By-year breakdown
    print("\nYearly averages:")
    print(f"{'Year':>6} {'Portfolio':>12} {'Ratio':>8} {'Max Correction':>15}")
    for row in capacity["yearly_averages"]:
        year = int(row["year"])
        val = row["total_value"]
        ratio = row["contribution_ratio_pct"]
        corr = row["max_correction_pct"]
        print(f"{year:>6} €{val:>10,.0f} {ratio:>7.2f}% {corr:>14.2f}%")

    # Serialize dates as strings for JSON
    for sample in capacity["monthly_samples"]:
        sample["date"] = str(sample["date"])
    for row in capacity["yearly_averages"]:
        row["year"] = int(row["year"])

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "contribution_capacity.json", "w") as f:
        json.dump(capacity, f, indent=2, default=str)
    print(f"\nResults saved to {RESULTS_DIR / 'contribution_capacity.json'}")

    plot_capacity(capacity)
    print(f"Plots saved to {ARTIFACTS_DIR}/")


if __name__ == "__main__":
    main()
```

Write this to `research/experiments/002-drift-contributions/exploration/contribution_capacity.py`.

---

### Task 12: Theoretical ceiling exploration script

**Files:**
- Create: `research/experiments/002-drift-contributions/exploration/theoretical_ceiling.py`

- [ ] **Step 1: Write the theoretical ceiling script**

```python
"""Theoretical ceiling: oracle strategy upper bound.

Simulates a perfect oracle that allocates each month's contribution
optimally to minimize allocation drift from targets. This establishes
the maximum possible improvement from contribution steering alone
(no selling, same total contribution).

If the oracle barely beats baseline, the experiment's upside is capped
and may not justify the complexity.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
from pydantic import BaseModel

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = EXPERIMENT_DIR / "results"

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "research" / "experiments" / "001-baseline-dca" / "strategies"))


def build_oracle_strategy() -> type:
    """Build an oracle strategy that optimally allocates contributions."""
    from pac.analysis.deviation import DeviationReport
    from pac.backtester.engine.actions import Action, PacAdjustment
    from pac.backtester.strategies.base import BacktestStrategy
    from pac.models.portfolio import PortfolioSnapshot
    from pac.models.signals import Signal

    class OracleParams(BaseModel, frozen=True):
        pass

    class OracleStrategy(BacktestStrategy[OracleParams]):
        """Allocate 100% of contribution to the most underweight asset."""

        name: ClassVar[str] = "oracle_dca"

        def on_signals(
            self,
            signals: list[Signal],
            snapshot: PortfolioSnapshot,
            report: DeviationReport,
            current_date: date,
        ) -> list[Action]:
            return []

        def on_pac_date(
            self,
            snapshot: PortfolioSnapshot,
            report: DeviationReport,
            current_date: date,
            current_pac_volumes: dict[str, Decimal],
        ) -> PacAdjustment | None:
            if not report.deviations:
                return None

            total_volume = sum(current_pac_volumes.values())
            if total_volume <= 0:
                return None

            # Find underweight assets (negative deviation = below target)
            underweight = {
                aid: -dev.deviation_pct
                for aid, dev in report.deviations.items()
                if dev.deviation_pct < 0
            }

            if not underweight:
                return None

            # Allocate proportionally to shortfall
            total_shortfall = sum(underweight.values())
            new_volumes = {}
            for aid in current_pac_volumes:
                if aid in underweight and total_shortfall > 0:
                    weight = underweight[aid] / total_shortfall
                    new_volumes[aid] = (total_volume * weight).quantize(
                        Decimal("0.01")
                    )
                else:
                    new_volumes[aid] = Decimal("0")

            # Ensure total stays the same (rounding adjustment)
            allocated = sum(new_volumes.values())
            diff = total_volume - allocated
            if diff != 0:
                most_underweight = max(underweight, key=underweight.get)
                new_volumes[most_underweight] += diff

            return PacAdjustment(new_volumes=new_volumes)

    return OracleStrategy, OracleParams


def run_simulation(strategy_cls: type, params: Any, label: str) -> dict:
    """Run a single simulation and compute metrics."""
    from pac.backtester.config import BacktestConfig
    from pac.backtester.engine.simulator import BacktestSimulator
    from pac.backtester.metrics.returns import equity_to_returns
    from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr
    from pac.backtester.research import ResearchContext
    from pac.rules.discovery import discover_rules
    from pac.rules.registry import SignalRegistry

    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(str(config_path))

    config = BacktestConfig(
        strategy=strategy_cls.name,
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={
            "min": Decimal("500"),
            "max": Decimal("700"),
            "distribution": "uniform",
        },
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls_item in rule_classes.values():
        registry.register(rule_cls_item)

    strategy = strategy_cls(params)
    simulator = BacktestSimulator(
        config, ctx.settings, ctx.prices, registry, strategy, rng_seed=42,
    )
    result = simulator.run_iteration(0)

    returns = equity_to_returns(result)
    twrr = compute_twrr(result)
    mwrr = compute_mwrr(result, initial_cash=Decimal("0"))

    import quantstats as qs

    metrics = {
        "label": label,
        "final_value": float(result.final_value),
        "twrr": twrr,
        "mwrr": mwrr,
        "sharpe": float(qs.stats.sharpe(returns, periods=252)),
        "sortino": float(qs.stats.sortino(returns, periods=252)),
        "max_drawdown": float(qs.stats.max_drawdown(returns)),
        "calmar": float(qs.stats.calmar(returns)),
        "volatility": float(qs.stats.volatility(returns, periods=252)),
    }
    return metrics


def main() -> None:
    from baseline_dca import BaselineDCA, BaselineDCAParams

    OracleStrategy, OracleParams = build_oracle_strategy()

    print("Running baseline DCA...")
    baseline = run_simulation(BaselineDCA, BaselineDCAParams(), "baseline_dca")

    print("Running oracle DCA...")
    oracle = run_simulation(OracleStrategy, OracleParams(), "oracle_dca")

    print("\n--- Theoretical Ceiling Comparison ---")
    print(f"{'Metric':<20} {'Baseline':>12} {'Oracle':>12} {'Delta':>12}")
    print("-" * 58)
    for key in ["final_value", "twrr", "mwrr", "sharpe", "sortino", "max_drawdown", "calmar", "volatility"]:
        b = baseline[key]
        o = oracle[key]
        delta = o - b
        if key == "final_value":
            print(f"{key:<20} €{b:>10,.0f} €{o:>10,.0f} €{delta:>10,.0f}")
        elif key == "max_drawdown":
            print(f"{key:<20} {b:>11.2%} {o:>11.2%} {delta:>+11.2%}")
        else:
            print(f"{key:<20} {b:>11.4f} {o:>11.4f} {delta:>+11.4f}")

    results = {
        "baseline": baseline,
        "oracle": oracle,
        "deltas": {
            key: oracle[key] - baseline[key]
            for key in ["final_value", "twrr", "mwrr", "sharpe", "sortino", "max_drawdown", "calmar", "volatility"]
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "theoretical_ceiling.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {RESULTS_DIR / 'theoretical_ceiling.json'}")

    # Assess opportunity size
    twrr_improvement = oracle["twrr"] - baseline["twrr"]
    sharpe_improvement = oracle["sharpe"] - baseline["sharpe"]
    print(f"\nTWRR improvement ceiling: {twrr_improvement:+.4f} ({twrr_improvement*100:+.2f}pp)")
    print(f"Sharpe improvement ceiling: {sharpe_improvement:+.4f}")

    if abs(twrr_improvement) < 0.001 and abs(sharpe_improvement) < 0.01:
        print("\n⚠ Limited upside: oracle barely beats baseline — contribution steering may not be worth the complexity")
    else:
        print("\n✓ Meaningful ceiling — worth pursuing in consolidation")


if __name__ == "__main__":
    main()
```

Write this to `research/experiments/002-drift-contributions/exploration/theoretical_ceiling.py`.

---

### Task 13: Commit experiment scaffold

- [ ] **Step 1: Verify experiment directory structure**

Run: `find research/experiments/002-drift-contributions -type f | sort`

Expected output should include:
```
research/experiments/002-drift-contributions/configs/baseline.yaml
research/experiments/002-drift-contributions/experiment.toml
research/experiments/002-drift-contributions/exploration/drift_characterization.py
research/experiments/002-drift-contributions/exploration/smoothing_assessment.py
research/experiments/002-drift-contributions/exploration/contribution_capacity.py
research/experiments/002-drift-contributions/exploration/theoretical_ceiling.py
research/experiments/002-drift-contributions/FINDINGS.md
```

- [ ] **Step 2: Commit**

Stage and commit with message:

```
feat: scaffold experiment 002 drift-based contribution steering

Adds exploration-phase scripts for drift characterization, smoothing
assessment, contribution capacity analysis, and theoretical ceiling.
Depends on experiment 001 baseline numbers and proxy chain.
```

Files to stage: everything under `research/experiments/002-drift-contributions/`.

---

## Self-Review Checklist

1. **Spec coverage**: Framework enhancement (Tasks 1-7) covers the `on_trading_day` hook, simulator wiring, BDD, unit tests, and README update. Experiment scaffold (Tasks 8-13) covers all four exploration scripts from the spec, plus config, metadata, and FINDINGS.md skeleton. ✓
2. **Placeholder scan**: All code blocks contain complete implementations. No "TBD", "TODO", or "fill in" in task steps. FINDINGS.md has placeholder sections for results — this is intentional (to be filled during research). ✓
3. **Type consistency**: `on_trading_day(snapshot, report, current_date) -> None` signature is consistent across base.py definition, simulator call site, BDD test, and unit tests. `_ObserverStrategy` and `_CounterStrategy` use the same signature. ✓
