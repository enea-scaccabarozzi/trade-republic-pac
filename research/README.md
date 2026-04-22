# Research

Structured research environment for iterative strategy development and validation. Every experiment is a self-contained, committable unit of research that becomes a permanent asset of the project — a building block for future work by any contributor, human or agentic.

## The Research Loop

Research follows a natural trial-and-error process that moves through three regions: **Exploration**, **Consolidation**, and **Validation**. These are not gates or stages — they are orientations. The researcher moves between them freely as understanding develops. A validation run that reveals a flaw sends you back to consolidation or even exploration. A dead end in exploration can redirect the entire hypothesis.

The experiment folder accumulates everything: false starts, reworked approaches, multiple strategy versions. The value is in the trail, not just the final answer.

```
  ┌─────────────┐      ┌────────────────┐      ┌──────────────┐
  │ EXPLORATION  │◄────►│ CONSOLIDATION  │◄────►│  VALIDATION  │
  │              │      │                │      │              │
  │ Does this    │      │ Can this work  │      │ Does this    │
  │ idea have    │      │ as a strategy  │      │ hold up      │
  │ merit?       │      │ in the         │      │ under        │
  │              │      │ framework?     │      │ scrutiny?    │
  └──────────────┘      └────────────────┘      └──────────────┘
```

### Exploration

The question: **"Is there signal here?"**

Pure data science with no framework constraints. Fetch prices from yfinance, compute indicators with tulipy or pandas, plot distributions, run statistical tests, look for patterns. Marimo notebooks are the natural medium — interactive, visual, iterative.

Typical activities:
- Fetch and inspect price data with `yfinance` and `pandas`
- Compute technical indicators (`tulipy`, custom functions)
- Statistical analysis (correlations, regime detection, distribution fitting)
- Visual inspection (matplotlib, plotly)
- Literature review, hypothesis refinement

The output is **insight**: "this indicator combination seems to predict X" or "this regime behaves differently under Y conditions." No framework code is required at this stage.

### Consolidation

The question: **"Can this idea work inside the simulator?"**

Translate exploration insights into framework terms. Write a `SignalRule`, a `BacktestStrategy`, or adjust parameters of an existing one. Wire it through `ResearchContext.simulate()` to confirm the idea works in the backtester's world — same engine, same portfolio model, same contribution schedule, same tax regime.

Typical activities:
- Write new `SignalRule` or `BacktestStrategy` subclass(es) inside the experiment folder
- Run quick deterministic simulations (`ctx.simulate()`, N=1, no slippage)
- Compare variants (`ctx.compare()`) to see if the idea outperforms the baseline
- Iterate on implementation — adjust thresholds, logic, timing
- Run parameter sweeps (`ctx.sweep()`) to find promising regions

The output is a **working strategy + parameters** that shows promise in quick simulations. The code lives inside the experiment folder — it is not yet part of `src/pac/`.

### Validation

The question: **"Does this hold up under real-world conditions?"**

The strategy implementation is mature enough to stress-test. Apply the full validation toolkit to gather evidence for a go/no-go decision. The researcher may still iterate (adjusting params, going back to consolidation), but the focus is on building confidence, not exploring.

Typical activities:
- Full Monte Carlo runs (`ctx.simulate_mc()`, N=50+, with slippage)
- Out-of-sample holdout (`ctx.validate_oos()`)
- Walk-forward analysis (`ctx.walk_forward()`)
- Event-based evaluation (`ctx.evaluate_events()` against crisis/bull/correction calendars)
- QuantStats tearsheets (`ctx.quantstats_report()`)
- Rolling metric analysis (`ctx.quantstats_rolling()`)
- Parameter sensitivity analysis (does performance degrade sharply at nearby params?)

The output is **evidence**: enough quantitative data to make a decision, fully documented in `FINDINGS.md`.

## Experiment Directory Structure

Each experiment is a self-contained directory under `research/experiments/`:

```
research/experiments/003-dd-threshold-sweep/
├── experiment.toml            # Seed metadata: hypothesis, tags, references
├── explore.py                 # Marimo notebook — exploration workspace
├── consolidate.py             # Marimo notebook — strategy dev & quick tests
├── validate.py                # Marimo notebook — full validation runs
├── configs/                   # Experiment-local configuration variants
│   ├── baseline.yaml          # Copy of pac.yaml with experiment-specific overrides
│   └── aggressive.yaml        # Alternative config for a variant
├── strategies/                # Experiment-local strategy/signal code
│   ├── my_strategy.py
│   └── my_signal_rule.py
├── results/                   # Structured outputs (JSON, CSV)
│   ├── baseline_comparison.json
│   ├── sweep_results.json
│   └── oos_validation.json
├── artifacts/                 # Plots, HTML tearsheets, figures
│   ├── equity_curves.png
│   └── tearsheet.html
└── FINDINGS.md                # Research narrative — the deliverable
```

Not every experiment needs every directory. A pure exploration experiment might only have `explore.py` and a short `FINDINGS.md`. A thorough validation will have all of them.

### What goes where

| Content | Location |
|---|---|
| Marimo notebooks (all phases) | Experiment root (`explore.py`, `consolidate.py`, `validate.py`, ...) |
| Configuration variants for `ResearchContext.from_config()` | `configs/` |
| New strategies or signal rules | `strategies/` |
| Complex reusable logic (shared across notebooks) | `lib/` or standalone `.py` modules |
| Simulation results, comparison tables, sweep outputs | `results/` (JSON, CSV) |
| Plots, tearsheets, generated figures | `artifacts/` |
| The research narrative | `FINDINGS.md` |
| Immutable experiment metadata | `experiment.toml` |

### Marimo notebooks as the primary interface

All research phases use **Marimo notebooks** (`.py` format) as the primary interface. Marimo notebooks are interactive, reproducible, and version-control friendly. They are easier to run than scripts and provide immediate visual feedback.

Common notebook patterns:
- `explore.py` — initial data exploration, indicator analysis, visual inspection
- `consolidate.py` — strategy development, quick simulations, variant comparison
- `validate.py` — full validation runs, MC simulations, OOS analysis, tearsheets

An experiment can have as many notebooks as needed. The scaffolded `explore.py` is a starting point, not a constraint. When logic grows complex, extract it into standalone `.py` modules or a `lib/` folder and import from notebooks.

### Configuration variants

Many `ResearchContext` methods require a config path. The `configs/` folder holds experiment-specific configuration variants — copies of `pac.yaml` with modified asset allocations, different tickers, alternative contribution schedules, or any config-level hypothesis.

```python
# In a Marimo notebook cell
ctx = ResearchContext.from_config("configs/aggressive.yaml", packs=["crisis"])
```

This keeps the experiment self-contained — no need to modify the project-level `pac.yaml`.

## Housekeeping

Research is messy. Notebooks proliferate, ad-hoc scripts appear, artifacts land in the root directory, and temporary files accumulate. This is fine during exploration — the creative phase should not be constrained by folder structure.

However, **before entering validation, the experiment directory must be organized**. This is a required step, not a suggestion. A cluttered directory produces unreliable results and makes the experiment unreadable for future researchers.

### What housekeeping means

- Move plots and figures to `artifacts/`
- Move result files (JSON, CSV) to `results/`
- Move configuration variants to `configs/`
- Group strategy/signal code into `strategies/`
- Extract shared logic from notebooks into standalone modules if needed

### What housekeeping does NOT mean

- **Never delete files, even failed attempts.** Every path taken — including dead ends — must remain in the experiment folder. Failed approaches are evidence; they explain why the final approach was chosen and prevent future researchers from repeating the same mistakes.
- **Never hide unsuccessful results.** Move them to `results/` with a clear name (e.g., `results/attempt_1_rsi_only.json`). Reference them in FINDINGS.md, even briefly.

The experiment directory is a complete record. If something was tried, it stays. The difference between "useful" and "not useful" is captured in FINDINGS.md through narrative context and emphasis — not by removing files.

## FINDINGS.md

The research narrative. This is the primary deliverable of every experiment — the document a future researcher reads to understand what was done, what was learned, and why.

It grows as the experiment progresses. Each research phase adds a section. Early experiments might only have an exploration section; fully validated experiments have all three.

### Structure

```markdown
# {Title}

> **Hypothesis**: {one-sentence hypothesis from experiment.toml}
> **Status**: {exploring | concluded | rejected | superseded}
> **Date**: {created date}

## Exploration

What data was examined. What patterns were found (or not found).
Initial observations, plots, statistical results.
What led to the next step — or why the idea was abandoned.

## Consolidation

How the insight was translated into a strategy/signal.
Which existing strategies or rules were used as a base.
Quick simulation results and comparisons against baseline.
Iterations: what was tried, what worked, what didn't.

## Validation

Full MC results (N, slippage config, tax regime).
OOS holdout results (split date, degradation ratio).
Walk-forward stability (window config, stability score).
Event-based analysis (which calendars, per-event performance).
Parameter sensitivity (does it degrade near the chosen params?).

## Conclusion

Go/no-go decision and rationale.
Key numbers that support the decision.
Limitations, caveats, open questions.
Implications for future experiments.
```

Not every section needs to be long. A rejected hypothesis might have two paragraphs in Exploration and a one-line Conclusion. The important thing is that the reasoning is captured.

### Linking to artifacts

Keep FINDINGS.md readable by linking to detailed outputs rather than inlining them:

```markdown
Full tearsheet: [artifacts/tearsheet.html](artifacts/tearsheet.html)
Sweep results: [results/sweep.json](results/sweep.json)
See the exploration notebook: [explore.py](explore.py)
```

## experiment.toml Reference

The seed manifest. Metadata is immutable after creation (except `status` and `tags`).

```toml
[experiment]
created = 2026-04-22
id = "003"
slug = "dd-threshold-sweep"
title = "Drawdown Threshold Sensitivity"
hypothesis = "Lowering dd_threshold from -20% to -15% improves crisis CAGR without degrading Sharpe"
tags = ["crisis", "sensitivity", "params"]

# Manual status override (auto-computed if absent)
# status = "rejected"

# Optional: reference other experiments this builds on
# depends_on = ["001-baseline-pac"]

# Optional: strategy under study
# [experiment.strategy]
# name = "crisis_exploit"
# params_file = "../../strategies/crisis_exploit_v1.yaml"
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Zero-padded 3-digit ID (e.g., `"003"`) |
| `slug` | `string` | Hyphenated name (e.g., `"dd-threshold-sweep"`) |
| `title` | `string` | Human-readable title |
| `hypothesis` | `string` | What you are testing — fill in after scaffold |
| `created` | `date` | TOML bare date |
| `tags` | `list[str]` | Categorization tags |

### Auto-computed status

When `status` is not manually set in the toml:

1. `results/` contains `.json` or `.csv` files → `"validated"`
2. Default → `"exploring"`

To force a status (e.g., `"rejected"`, `"superseded"`), set it explicitly in the toml.

## Cross-Experiment References

Experiments can reference results from prior experiments. Keep it simple:

- **In FINDINGS.md**: Link to the other experiment's findings or results by relative path:
  ```markdown
  Baseline established in [001-baseline-pac](../001-baseline-pac/FINDINGS.md).
  ```
- **In experiment.toml**: Use the `depends_on` field to declare the relationship:
  ```toml
  depends_on = ["001-baseline-pac"]
  ```
- **In code**: Load results from another experiment's `results/` directory by path. Experiments should not import Python code from each other.

## Available Tools by Phase

### Exploration (no framework required)

```python
import yfinance as yf
import pandas as pd

# Direct data access
df = yf.download("EUNL.DE", start="2000-01-01")

# Or via ResearchContext for convenience
from pac.backtester.research import ResearchContext
ctx = ResearchContext.from_config("pac.yaml", packs=["tulipy", "crisis"])
df = ctx.to_dataframe("stocks")

# Indicators
series = ctx.indicator_series("sma", start, end, period=200)
composite = ctx.composite_series(["sma_cross", "rsi_extreme"], min_active=2, start=start, end=end)
```

### Consolidation (framework simulation)

```python
# Quick deterministic simulation (N=1, no slippage, ~seconds)
result = ctx.simulate("crisis_exploit", {"dd_threshold_pct": -15})
metrics = ctx.compute_metrics(result)

# Compare variants
table = ctx.compare([
    {"strategy": "crisis_exploit", "params": {"dd_threshold_pct": -20}, "label": "baseline"},
    {"strategy": "crisis_exploit", "params": {"dd_threshold_pct": -15}, "label": "candidate"},
])

# Parameter sweep
sweep = ctx.sweep("crisis_exploit",
    grid={"dd_threshold_pct": [-10, -15, -20, -25, -30]},
    base_params={"recovery_days": 120},
)
print(f"Best: {sweep.best.label} → Sharpe {sweep.best.metrics['sharpe']:.3f}")
```

### Validation (full rigor)

```python
# Monte Carlo (N=50, with slippage)
mc_result = ctx.simulate_mc("crisis_exploit", params=best_params, iterations=50, seed=42)

# Out-of-sample holdout
oos = ctx.validate_oos("crisis_exploit", params=best_params, split_ratio=0.7)
print(f"OOS degradation: {oos.degradation_ratio:.2f}")

# Walk-forward
wf = ctx.walk_forward("crisis_exploit", params=best_params, window_years=10, step_years=5)
print(f"Stability: {wf.stability_score:.2f} ({wf.consistent_windows}/{len(wf.windows)} windows)")

# Event-based analysis
events = ctx.evaluate_events("crisis_exploit", params=best_params, calendar=ctx.calendars["crises"])
print(f"Mean crisis return: {events.mean_event_return:.2%}")

# QuantStats tearsheet
ctx.quantstats_report(mc_result, output="artifacts/tearsheet.html", title="Crisis Exploit v2")
```

## Quick Start

```bash
# Scaffold a new experiment
just new-experiment shallow_corrections --title "Shallow Correction Tilt Strategy"

# Fill in the hypothesis in experiment.toml
# Open the exploration notebook
marimo edit research/experiments/001-shallow-corrections/explore.py

# Later: open consolidation or validation notebooks
marimo edit research/experiments/001-shallow-corrections/consolidate.py
marimo edit research/experiments/001-shallow-corrections/validate.py
```

## Conventions

- Experiment IDs are auto-incremented (`001`, `002`, ...) by the scaffold script
- Marimo notebooks use `.py` format for version-control compatibility
- Generated HTML reports in `artifacts/` are typically gitignored — commit only if small or essential
- Results in `results/` (JSON, CSV) are committed — they are the quantitative record
- Strategy/signal code inside experiments is not auto-discovered by the production framework — it must be explicitly imported or promoted to `src/pac/` (promotion process is separate)
- Negative results are valuable — document why something didn't work

## Commands

```bash
just new-experiment <name> [--title "Title"]   # scaffold a new experiment
marimo edit <path/to/explore.py>               # open a Marimo notebook
just test -k research                          # run research framework tests
```
