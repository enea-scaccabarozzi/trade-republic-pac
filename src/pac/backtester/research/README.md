# Research Framework

Zero-ceremony research API for backtesting experiments. Provides `ResearchContext` — a single entry point that replaces ~40 lines of boilerplate for data loading, indicator registration, and simulation setup. Also provides `IndicatorRegistry`, `EventCalendar`, and out-of-sample validation helpers.

## Architectural Role

Depends on: [`backtester/data`](../data/), [`backtester/engine`](../engine/), [`backtester/strategies`](../strategies/), [`config`](../../config/), [`models`](../../models/), [`rules`](../../rules/).
Consumed by: research scripts in `research/experiments/`, CLI research commands.

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/data` | `pac.backtester.data` | Fetches and caches historical price series for all assets | `MarketDataProvider`, `PriceSeries` |
| `backtester/engine` | `pac.backtester.engine` | Runs Monte Carlo simulation iterations | `BacktestSimulator`, `SimulationResult` |
| `backtester/strategies` | `pac.backtester.strategies` | Strategy discovery and base class for research variants | `discover_strategies`, `BacktestStrategy` |
| `config` | `pac.config` | Loads and validates the pac.yaml configuration file | `Settings`, `load_config` |
| `models` | `pac.models` | Portfolio and market data types used throughout research computations | `PriceSeries` |
| `rules` | `pac.rules` | Signal rule discovery and registry reused in simulation | `discover_rules`, `SignalRegistry` |

## Key Components

| Component | File | Purpose |
|---|---|---|
| `ResearchContext` | `context.py` | Zero-ceremony facade: load config, fetch data, run simulations, compare variants |
| `IndicatorRegistry` | `indicators.py` | Opt-in indicator registry; empty by default, populated via `register_pack()` |
| `EventCalendar` | `events.py` | Named calendar of market events (recessions, crises) for event-driven analysis |
| `ExperimentManifest` | `manifest.py` | Scans `research/experiments/` and surfaces experiment metadata |
| `Experiment` | `experiment.py` | Single experiment: immutable `experiment.toml` seed + auto-computed state |

## Usage

```python
from pac.backtester.research.context import ResearchContext

ctx = ResearchContext.from_config(
    "backtest/pac-backtest.yaml",
    start_date=date(1996, 1, 1),
    packs=["crisis"],
)

# Run a quick single-iteration simulation
result = ctx.run(strategy="pac_alignment")

# Compare two variants
table = ctx.compare(
    baseline={"strategy": "pac_alignment"},
    variant={"strategy": "crisis_exploit"},
)

# Out-of-sample validation
oos = ctx.walk_forward(strategy="crisis_exploit", folds=5)
```

## Commands

```bash
just new-experiment <name>       # scaffold a new research experiment
just test -k test_research       # run research module tests
just test -k backtester          # run all backtester tests
```

## See Also

- [Backtester README](../README.md) — full architecture and data flow
- [Engine](../engine/) — `BacktestSimulator` and `SimulationResult`
- [Strategies](../strategies/) — `BacktestStrategy` ABC
- [ADR-008: Research Framework](../../../../docs/architecture/ADR-008-research-framework.md)
