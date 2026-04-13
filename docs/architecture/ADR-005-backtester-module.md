# Backtester Module — Signal Validation Engine

**Source:** Task 005 (April 2026)
**Status:** Accepted

## Updates

| Date       | Task | Change                                                                                        |
| ---------- | ---- | --------------------------------------------------------------------------------------------- |
| April 2026 | 008  | Added NiceGUI web dashboard, CLI chart enhancements (plotext), shared `run_pipeline()` runner |

## Context

The PAC system generates trading signals from live portfolio data but provided no
way to validate whether a signal configuration is historically effective. Developers
adding new `SignalRule` implementations could not measure their impact before
deploying to production. Users could not compare strategy configurations against
a passive baseline (buy-and-hold).

Specific gaps before this ADR:

- **No historical replay.** The system only operated on live portfolio data;
  there was no mechanism to replay past market conditions.
- **No strategy abstraction.** The connection between "signal fires" and
  "trader acts" was implicit. Different users react differently to the same
  signal — this needed to be modeled.
- **No statistical robustness.** Single-path simulations produce misleading
  results. Human decision timing introduces meaningful variance.
- **Tight coupling risk.** A naive backtester would duplicate signal evaluation
  logic, diverging from the production code path over time.

## Decision

Add a `backtester` submodule (`src/pac/backtester/`) that:

1. **Reuses the production signal pipeline.** The same `SignalRule` subclasses
   registered in `pac.rules.builtin` evaluate synthetic `PortfolioSnapshot`
   objects built from historical prices. Rules are never aware they are being
   backtested.

2. **Introduces a `BacktestStrategy` ABC** (same pattern as `SignalRule` and
   `DeliveryChannel`). Strategies translate generated signals into concrete
   actions (PAC volume adjustments or hard rebalance orders). Contributors
   subclass `BacktestStrategy[ParamsT]`, implement `on_signals()`, and drop
   the file in `strategies/builtin/` — auto-discovered with no registration step.

3. **Models Trade Republic execution constraints faithfully.** PAC executions
   occur only on the 2nd/16th of each month (fee-free). Hard rebalances carry
   a €1 flat fee plus configurable spread. Cash sufficiency is checked.

4. **Uses Monte Carlo simulation for statistical robustness.** Each run repeats N
   iterations (default 100) with per-iteration human decision delay sampled from
   a configurable uniform distribution. Metrics are reported as median with P5/P95
   confidence intervals rather than single-path estimates.

5. **Is an optional, isolated module.** The backtester lives under
   `src/pac/backtester/` and has its own optional dependency group (`backtest`).
   The main `pac` application has zero imports from it. CLI entry point:
   `uv run python -m pac.backtester` / `just backtest`.

## Solution

### Architecture

```
src/pac/backtester/
├── config.py              # BacktestConfig — run parameters (Pydantic)
├── cli.py                 # typer CLI (run, strategies, results, show)
├── data/                  # MarketDataProvider — yfinance + filesystem cache
├── engine/                # BacktestSimulator — Monte Carlo event loop
│   ├── clock.py           # SimulationClock — trading day iterator
│   ├── portfolio.py       # SimulatedPortfolio — state machine
│   ├── simulator.py       # Main loop + IterationResult / SimulationResult
│   └── actions.py         # PacAdjustment, HardRebalanceOrder, Action, ExecutedTrade
├── strategies/            # BacktestStrategy ABC + builtin strategies
│   ├── base.py            # ABC+Generic[ParamsT], __init_subclass__ extraction
│   ├── registry.py        # StrategyRegistry — instantiate with validated params
│   ├── discovery.py       # discover_strategies() — scans builtin/ package
│   └── builtin/           # pac_alignment.py, cycle_exploit.py
├── metrics/               # quantstats wrapper + benchmark comparison
│   ├── calculator.py      # MetricsCalculator — per-iteration + aggregation
│   ├── benchmark.py       # run_benchmark() — passive buy-and-hold run
│   ├── report.py          # compute_report() — top-level orchestrator
│   └── models.py          # MetricResult, MetricSet, BacktestReport
└── results/               # Frontend-agnostic JSON persistence
    ├── store.py            # ResultStore — save/load/list/delete
    ├── models.py           # RunResult, EquityCurvePoint, AllocationPoint
    └── aggregation.py      # build_run_result() — BacktestReport → RunResult
```

### BacktestStrategy ABC

```python
class BacktestStrategy(ABC, Generic[ParamsT]):
    params_model: ClassVar[type[BaseModel]]  # auto-extracted by __init_subclass__
    name: ClassVar[str]                      # validated at class-definition time

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]: ...

    def on_pac_date(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
        current_pac_volumes: dict[str, Decimal],
    ) -> PacAdjustment | None:
        return None  # default: maintain current PAC volumes
```

**Stateful vs stateless:** `SignalRule.evaluate()` receives params per call and is
stateless. `BacktestStrategy.__init__()` stores params once; a fresh instance is
created per Monte Carlo iteration, so strategies may accumulate state across time
steps within one iteration.

### Simulation Loop (per iteration)

For each trading day:
1. Update prices from pre-built `{ticker: PriceSeries}` index
2. Execute slippage-delayed pending actions whose `execute_on ≤ today`
3. Trigger PAC execution if today is a PAC date (fee-free)
4. Build `PortfolioSnapshot` compatible with the live analysis pipeline
5. Compute `DeviationReport` via `analysis.deviation.calculate_deviations()`
6. Evaluate all configured `SignalRule` instances via `SignalRegistry`
7. Call `strategy.on_signals()` → receive `list[Action]`
8. Apply sampled slippage delay, queue actions for future execution
9. Record `DayResult` (total value, allocations, cash)

### Monte Carlo Aggregation

After all iterations:
- Compute per-iteration daily return series via `equity_to_returns()`
- Apply quantstats metric functions per iteration
- Aggregate: `median = nanpercentile(values, 50)`, `p5`, `p95`
- Run benchmark (`_BenchmarkStrategy` — PAC-only, no signals, zero slippage)
  if `BacktestConfig.benchmark` is `True`

### JSON Result Schema

Each saved result is a timestamped JSON file in `.pac/backtests/` with:
- `run_id`, `created_at`, `config` (full `BacktestConfig` for reproducibility)
- `metrics` — strategy and benchmark metrics with P5/median/P95
- `equity_curve` — daily `{date, p5, median, p95}` points
- `allocations` — daily per-asset allocation bands
- `trades` — trade log extracted from the median iteration
- `summary` — `total_invested`, `final_value` bands, `total_fees` bands

### DX Scaffolding

```bash
just new-strategy <name>   # scaffold BacktestStrategy skeleton + test
just backtest              # interactive CLI run
just backtest-sync         # install optional deps
just dashboard             # start web dashboard
just dashboard-sync        # install dashboard deps
```

## Dashboard UI Layer (Task 008)

### Decision

Add a NiceGUI web dashboard and plotext-based CLI charts as two optional
presentation layers over the existing `RunResult` JSON schema.

### Why

- The CLI `show` command produced text-only output — no charts, no drawdown
  info, no color-coded metric comparisons.
- Interactive exploration (filtering, zooming, comparing runs) requires a
  web-based UI; terminal output cannot provide this.
- The backtest wizard (interactive config via `questionary`) was CLI-coupled;
  a web form provides richer validation and parameter editing.

### Framework Choice: NiceGUI

NiceGUI was selected over Streamlit, Dash, and Panel for:

- **AG Grid** integration for trade tables (sort, filter, export)
- **Plotly** integration for equity curves with confidence bands
- **WebSocket-based** architecture for real-time progress during backtest runs
- **`ui.timer` + `background_tasks`** for long-running backtests without blocking
- **`@ui.page` routing** for multi-page app (results, wizard, compare)
- **Tailwind CSS** for custom styling

### Architecture

```
src/pac/backtester/
├── cli_charts.py              # plotext terminal chart builders
├── runner.py                  # run_pipeline() — shared backtest pipeline (CLI + dashboard)
└── dashboard/
    ├── __main__.py            # python -m pac.backtester.dashboard entry point
    ├── app.py                 # NiceGUI app init, @ui.page route registration
    ├── charts.py              # Pure Plotly figure builders (equity, allocation, drawdown)
    ├── state.py               # DashboardState — ResultStore wrapper + loaded runs cache
    ├── components/
    │   └── layout.py          # Shared layout shell (header, sidebar navigation)
    └── pages/
        ├── results_list.py    # Run listing with metadata table
        ├── result_detail.py   # Single run viewer (charts, KPI cards, trade log)
        ├── run.py             # Backtest wizard form + live progress
        └── compare.py         # Multi-run comparison (overlaid charts, metrics table)
```

### Key Patterns

**Shared pipeline:** `run_pipeline()` in `runner.py` extracts the core backtest
orchestration from the CLI, making it reusable by both `cli.py` and the dashboard
wizard. The CLI and dashboard provide their own progress reporting.

**Pure chart builders:** `dashboard/charts.py` contains stateless functions that
accept `RunResult` data and return Plotly `Figure` objects. These are decoupled
from NiceGUI rendering and independently testable.

**State caching:** `DashboardState` wraps `ResultStore` and caches loaded
`RunResult` objects to avoid re-parsing JSON on each page navigation.

**Side-effect page registration:** Pages use `@ui.page` decorators and are
registered via module-level side-effect imports in `app.py`.

### Dependency Groups

The dashboard introduces a second optional dependency group:

| Group       | Packages             | Purpose                     |
| ----------- | -------------------- | --------------------------- |
| `backtest`  | yfinance, quantstats | Simulation engine + metrics |
| `dashboard` | nicegui, plotly      | Web dashboard UI            |
| `backtest`  | plotext              | CLI terminal charts         |

### CLI Enhancements (plotext)

The `show` command renders terminal charts via plotext:
- Equity curve with P5/median/P95 bands
- Asset allocation stacked area chart
- Drawdown from peak chart
- Color-coded metric comparison (green/red for better/worse vs benchmark)

## Consequences

### Positive

- **Production code reuse.** Signal rules are never duplicated; the backtester
  tests the exact logic that runs in production.
- **Consistent contributor DX.** `BacktestStrategy` follows the same
  ABC+Generic+auto-discovery pattern as `SignalRule` and `DeliveryChannel`.
  Muscle memory from adding a rule transfers directly.
- **Statistical validity.** Monte Carlo slippage sampling avoids the
  "lucky timing" problem of single-path backtests. P5/P95 bands make
  uncertainty explicit.
- **Frontend-agnostic results.** The JSON schema is designed for graphing
  without transformation — usable from CLI tables, Jupyter, or web dashboards.
- **Zero main-app coupling.** The backtester is an optional feature. The core
  PAC application has no import dependency on `pac.backtester`.

### Negative / Trade-offs

- **Separate dependency group.** `yfinance` and `quantstats` are heavy; users
  who don't need backtesting install a lighter `pac` package.
- **ISIN → ticker mapping is manual.** yfinance does not accept ISINs;
  each asset in `pac.yaml` must have a `ticker` field. This is a one-time
  per-asset setup but a potential source of misconfiguration.
- **Daily granularity only.** The engine uses daily OHLCV bars. Intraday
  timing effects (e.g., exact execution time on PAC dates) are not modeled.
- **Benchmark is simplified.** The passive benchmark uses a fixed target
  allocation throughout; it does not model drift between PAC dates.
