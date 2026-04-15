# Research Framework — Structured Experiment Workflow

**Source:** Task 012 (April 2026)
**Status:** Accepted

## Decision

Add a research-first layer to the backtester that treats experimental work as a first-class project asset — from initial exploration through publication.

## Why

Task 010 (crisis strategy research) exposed fundamental gaps in the framework's support for iterative research. Over 9 hypotheses, every validation script was a throwaway `/tmp/` file. Data fetching, indicator computation, and simulation were re-bootstrapped each time. Results were hand-transcribed into Markdown. When a publication paper was produced, figure data had to be hardcoded from memory because no machine-readable artifacts survived.

The root problem is not a missing feature — it is the absence of a coherent **research workflow** that treats experimental work as a first-class project asset.

## Problem Statement

1. Research artifacts are ephemeral — scripts live in `/tmp/`, results are hand-copied, only the final "winner" survives
2. Framework bootstrapping is 40 lines of ceremony per script (config, provider, tickers, registry, strategy, BacktestConfig)
3. No indicator batch API — computing "indicator X across all trading days" requires hand-written sliding-window loops
4. Indicators are static — no mechanism to register custom indicators or compose ad-hoc indicator pipelines per experiment
5. No standard TA library — researchers re-implement EMA, RSI, MACD from scratch each time
6. No experiment comparison — `ResultStore` saves timestamped JSON with no labels, tags, or comparison
7. No parameter sweep primitive — testing a grid of parameters requires a hand-written loop
8. Dashboard disconnected from research — no awareness of experiments, artifacts, or iteration flow
9. No quick-test mode — every run goes through full Monte Carlo; no "single deterministic path in ~10s" mode
10. No out-of-sample validation — no mechanism to verify strategy parameters on unseen market regimes
11. Quantstats integration is shallow — only used internally for MC metric aggregation; no tearsheets, HTML reports, or rolling analytics

## Solution

### Before

- Research scripts in `/tmp/`, hand-transcribed results
- 40-line bootstrap ceremony per script
- Fixed 5-indicator set, no standard TA library
- No OOS validation, no event calendars
- Dashboard unaware of research

### After

- `research/` directory with auto-managed experiments (`experiment.toml` immutable seed, state computed from contents)
- `ResearchContext` zero-ceremony API for data access, indicator computation, and simulation
- `IndicatorRegistry` with empty-by-default design and opt-in packs (tulipy 104 TA indicators, crisis indicators)
- Dynamic indicator composition with `composite_series()` N-of-M voting and threshold helpers
- Quick-test mode (N=1, deterministic, ~10s) as default, with `compare()` and `sweep()` for variant testing
- `EventCalendar` system with built-in calendars (crises, bull runs, corrections, regime changes)
- OOS validation: temporal holdout, expanding walk-forward, event-leave-one-out cross-validation
- Deep quantstats integration (full tearsheet/HTML export, rolling analytics, plots, auto-attach to runs)
- `ResultStore` enhancements (`label`, `tags`, `experiment_id`, `quantstats_report`, search/compare APIs)
- Research API endpoints (`/api/research/*`) + React dashboard research browser
- Marimo notebook template for interactive exploration

## Architecture

```
research/                          # Convention — not a Python package
├── experiments/NNN-slug/          # Auto-managed experiments
│   ├── experiment.toml            # Immutable seed (hypothesis, strategy, dates)
│   └── explore.py                 # Marimo notebook (.py format)
├── papers/                        # Published research papers
└── strategies/                    # Named strategy parameter snapshots

src/pac/backtester/research/       # Python package — research API
├── context.py                     # ResearchContext facade
├── indicators.py                  # IndicatorRegistry + IndicatorResult
├── events.py                      # EventCalendar + MarketEvent
├── events_builtin.py              # Built-in calendars (crises, bull runs, etc.)
├── experiment.py                  # ExperimentState + load_experiment()
├── manifest.py                    # ExperimentManifest (directory scanner)
├── models.py                      # ComparisonTable, OOSResult, SweepResult, etc.
├── _quantstats_helpers.py         # Quantstats integration helpers
└── packs/                         # Opt-in indicator packs
    ├── crisis/                    # Crisis indicators (drawdown, divergence, etc.)
    └── tulipy_bridge/             # 104 compiled TA indicators

src/pac/backtester/api/routes/     # REST API
└── research.py                    # /api/research/* endpoints
```

## Key Design Decisions

1. **Empty-by-default indicator registry.** No indicators enforced; researchers opt-in to packs via `ctx.register_pack("tulipy")`. This avoids dependency bloat and lets each experiment declare exactly what it needs.

2. **Auto-managed experiment state.** `experiment.toml` is an immutable seed (hypothesis, strategy, dates). Status is computed from directory contents — has results? → validated. No manual metadata updates.

3. **Quick-test as default.** N=1 deterministic ~10s runs are the default research mode. Full Monte Carlo is an explicit graduation step. This inverts the prior assumption that every run needs statistical confidence.

4. **Event-based OOS validation.** Suited to long-term investing where only 4–5 major crises exist in 30 years of data. Event-leave-one-out cross-validation tests generalization across crisis regimes, not just temporal splits.

5. **Research as backtester submodule.** `pac.backtester.research` lives alongside the engine, not as a separate top-level package. Research reuses backtester infrastructure (data provider, simulator, result store) without circular dependencies.

## Implementation Phases

| #   | Phase                                      | Description                                                                         |
| --- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| 1   | Research directory + auto-managed manifest | `research/` structure, `experiment.toml` seed, auto-state, scaffolding              |
| 2   | Indicator registry + packs                 | `IndicatorRegistry` (empty by default), opt-in packs (tulipy, crisis), custom funcs |
| 3   | `ResearchContext` core API                 | Data access, `indicator_series()`, `simulate()`, `to_dataframe()`                   |
| 4   | Dynamic indicator composition              | `CompositeResult`, `threshold()`, `composite_series()` N-of-M voting                |
| 5   | Quick-test mode + comparison + sweep       | N=1 `simulate()`, `compare()`, `sweep()`, CLI commands                              |
| 6   | Event calendar + OOS validation            | `EventCalendar`, built-in calendars, holdout, walk-forward, event-leave-one-out     |
| 7   | Quantstats deep integration                | Full tearsheet/HTML export, rolling analytics, plots, auto-attach to runs           |
| 8   | ResultStore enhancements                   | `label`, `tags`, `experiment_id`, `search()`, `compare()`, OOS metadata             |
| 9   | Research API endpoints                     | `/api/research/*` routes, response models, file serving, security                   |
| 10  | Research browser UI                        | React pages, TS types, React Query hooks, sidebar nav, experiment viewer            |
| 11a | Documentation                              | ADR-008, AGENTS.md patterns, CHANGELOG entries                                      |
| 11b | Migration + experiment backfill            | Move `docs/research/` → `research/papers/`, backfill experiment 001, fix links      |

## Updates

| Date       | Task | Summary                 |
| ---------- | ---- | ----------------------- |
| 2026-04-14 | 012  | Initial decision record |
