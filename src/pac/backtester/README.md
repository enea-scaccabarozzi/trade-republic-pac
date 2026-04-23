# Backtester

Signal validation engine for the PAC automation system. Replays historical market
data, evaluates existing signal rules against synthetic portfolio snapshots, delegates
to a configurable Strategy to translate signals into actions, and simulates the
resulting portfolio with realistic Trade Republic constraints.

Not a traditional backtester — signals do not map directly to trades. The
**Strategy** class (ABC+Generic, same DX as `SignalRule`/`DeliveryChannel`) owns
that translation.

## Architectural Role

| Aspect | Details |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on | [`analysis`](../analysis/) (deviation), [`rules`](../rules/) (signal evaluation), [`models`](../models/) (portfolio/signal types), [`config`](../config/) (Settings) |
| Consumed by | CLI only (`just backtest`) — standalone module, not wired into the main `app.py` |
| Boundary | Network (yfinance fetch), filesystem (`.pac/backtests/` write, cache read/write), pure computation |

## Submodules

| Submodule | Path | Description |
| ---------- | ---------------------------- | ----------------------------------------------- |
| Data | [`data/`](data/) | yfinance wrapper + filesystem JSON cache |
| Engine | [`engine/`](engine/) | Monte Carlo event loop, portfolio state machine |
| Strategies | [`strategies/`](strategies/) | BacktestStrategy ABC + builtin strategies |
| Metrics | [`metrics/`](metrics/) | quantstats wrapper, benchmark comparison |
| Results | [`results/`](results/) | JSON persistence to `.pac/backtests/` |
| Dashboard | [`dashboard/`](dashboard/) | Interactive web UI for results exploration |

## Architecture

### Data Flow

```text
CLI (typer)
  │
  ▼ parse args / interactive prompts
BacktestConfig (run parameters)
  │
  ▼ load market data
MarketDataProvider (yfinance + cache)
  │
  ▼ initialize
BacktestSimulator
  │
  ├── SimulationClock (iterate trading days)
  ├── SimulatedPortfolio (track positions + cash)
  ├── SignalRegistry (reuse existing rules)
  └── BacktestStrategy (translate signals → actions)
  │
  ▼ for each Monte Carlo iteration (N times):
  │   for each trading day:
  │     1. Update prices from historical data
  │     2. Build PortfolioSnapshot (same model as live)
  │     3. Compute DeviationReport (reuse analysis.deviation)
  │     4. Construct BacktestMarketContext(prices, current_date)
  │     5. Evaluate signal rules with market context (reuse rules.registry)
  │     6. Feed signals to strategy → get actions
  │     7. Execute queued actions (with sampled slippage delay)
  │     8. On PAC dates: execute PAC with current volumes
  │     9. Record equity curve point + allocation snapshot
  │
  ▼ after all iterations
MetricsCalculator (quantstats per iteration → aggregate)
  │
  ▼ compute metrics distribution (median, P5, P95) + benchmark
BacktestReport
  │
  ├── ResultStore → .pac/backtests/{timestamp}.json
  └── Rich terminal output (tables, charts)
```

### Trade Republic Constraints Modeled

| Constraint | How Modeled |
| ------------------- | -------------------------------------------------------------------- |
| PAC execution dates | 2nd / 16th of month only; weekends roll to next trading day |
| PAC fee | €0 — fee-free |
| Manual order fee | €1 flat settlement fee per hard rebalance order |
| Spread | Configurable basis points (default 10 bps) applied to close price |
| Human latency | Per-iteration slippage sampled from `uniform(min, max)` trading days |

## Getting Started

### Prerequisites

Install the optional backtester dependencies:

```bash
just backtest-sync
```

Assets must define a `ticker` field in `pac.yaml` for the backtester to resolve
Yahoo Finance symbols:

```yaml
assets:
  - id: stocks
    name: "World ETF"
    isin: IE00B4L5Y983
    target_pct: 70
    ticker: EUNL.DE        # Required for backtesting
```

### Running a Backtest

```bash
# Interactive mode (guided prompts)
just backtest

# Batch mode
just backtest run \
  --strategy pac_alignment \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --initial-cash 10000 \
  --monthly-contribution 500

# List available strategies
just backtest strategies

# List saved results
just backtest results

# Show a specific result
just backtest show <run-id>
```

Results are saved to `.pac/backtests/{timestamp}_{strategy}.json`.

## Proxy Tickers

Assets can define `proxy_ticker` and `proxy_end` fields in `pac.yaml` (or a backtest-specific YAML like `backtest/pac-backtest.yaml`) for stitching pre-ETF data into longer backtests. This enables 30+ year validation periods for assets whose ETFs launched recently.

| Asset | Primary Ticker | Proxy Ticker | Proxy End | Coverage |
| ------ | -------------- | ------------ | ---------- | ------------ |
| Stocks | VWCE.DE | ^GSPC | 2019-07-22 | 1996–present |
| Gold | IGLN.L | GC=F | 2011-04-11 | 1996–present |
| Bonds | AGGH.L | ^IRX | 2017-11-06 | 1996–present |

The data layer automatically stitches proxy and primary ticker data at the `proxy_end` date. See [`docs/crisis-indicators-research.md`](../../docs/crisis-indicators-research.md) Section 2 for proxy ticker validation and correlation analysis.

## Adding a New Strategy

1. **Scaffold the skeleton:**

   ```bash
   just new-strategy my_strategy
   ```

   This creates:

   - `src/pac/backtester/strategies/builtin/my_strategy.py`
   - `src/pac/backtester/strategies/tests/test_my_strategy.py`

1. **Implement `on_signals()`** in the generated file. The method receives:

   - `signals: list[Signal]` — rules that fired this tick
   - `snapshot: PortfolioSnapshot` — current holdings
   - `report: DeviationReport` — allocation deviations
   - `current_date: date` — simulation date

1. **Return actions** — any combination of `PacAdjustment` and
   `HardRebalanceOrder` objects wrapped in `Action`.

1. **Optionally override `on_pac_date()`** to dynamically set PAC volumes on
   execution dates (2nd/16th).

1. **Run via CLI:**

   ```bash
   just backtest strategies        # should list my_strategy
   just backtest run --strategy my_strategy --start 2022-01-01 --end 2024-12-31
   ```

Discovery is automatic — no registration step needed.

### Dashboard

Interactive web UI for exploring results, running backtests, and comparing runs.

```bash
# Install dashboard dependencies
just dashboard-sync

# Start the dashboard
just dashboard

# With options
just dashboard --port 9000 --reload
```

See [`dashboard/README.md`](dashboard/README.md) for architecture and development details.

### Strategy Skeleton

```python
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class MyStrategyParams(BaseModel):
    """Strategy parameters — validated from BacktestConfig.strategy_params."""

    threshold: float = 5.0


class MyStrategy(BacktestStrategy[MyStrategyParams]):
    """Describe what your strategy does."""

    name = "my_strategy"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        actions: list[Action] = []
        # Inspect signals and snapshot, emit actions
        return actions
```

## Crisis Exploitation Validation

The `backtest/` directory contains configuration and tooling for validating crisis detection and exploitation strategies against 30 years of historical data:

| File | Purpose |
| ------------------------------------ | --------------------------------------------------------------- |
| `backtest/pac-backtest.yaml` | 30-year config with proxy tickers and crisis signal definitions |
| `backtest/ANALYSIS.md` | Template for recording A/B comparison results |
| `scripts/run_backtest_validation.py` | Automation for baseline vs crisis-aware scenarios (15 configs) |

Run the full validation suite:

```bash
uv run python scripts/run_backtest_validation.py         # full run
uv run python scripts/run_backtest_validation.py --quick  # reduced iterations
```

## Configuration Reference

All simulation parameters are documented in `config.py` (`BacktestConfig`). Key fields:

| Parameter | Default | Description |
| ------------------------ | ---------------- | ----------------------------------------- |
| `strategy` | *(required)* | Strategy name (auto-discovered) |
| `strategy_params` | `{}` | Dict passed to strategy params model |
| `start_date` | *(required)* | Backtest start |
| `end_date` | *(required)* | Backtest end |
| `initial_cash` | `10000` | Starting cash (EUR) |
| `monthly_contribution` | `500` | Monthly PAC contribution (EUR) |
| `monte_carlo_iterations` | `100` | Number of MC iterations |
| `slippage_days` | `(0, 3)` | Human decision delay range (trading days) |
| `spread_bps` | `10` | Execution spread in basis points |
| `metrics` | `[sortino, ...]` | Metrics to compute |
| `benchmark` | `true` | Compare vs. passive buy-and-hold |

## Commands

```bash
just backtest-sync              # install optional dependencies
just backtest                   # interactive run
just backtest run [flags]       # batch run
just backtest strategies        # list available strategies
just backtest results           # list saved results
just backtest show <run-id>     # show a saved result
just new-strategy <name>        # scaffold a new strategy
just test -k backtester         # run backtester tests
```

## See Also

- [Data](data/) — `MarketDataProvider`, `PriceSeries`, `DataRequest`
- [Engine](engine/) — `BacktestSimulator`, `SimulatedPortfolio`, action models
- [Strategies](strategies/) — `BacktestStrategy` ABC, `discover_strategies()`
- [Metrics](metrics/) — `MetricsCalculator`, `BacktestReport`, quantstats integration
- [Results](results/) — `RunResult` JSON schema, `ResultStore`
- [ADR-003](../../../docs/architecture/ADR-003-backtester-module.md) — Architecture decision record
- [Analysis](../analysis/) — `DeviationReport` used by strategies
- [Rules](../rules/) — `SignalRule` instances reused by the backtester
