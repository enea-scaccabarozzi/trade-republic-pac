# Engine

Simulation engine for the backtester. Provides a time-stepping event loop that replays historical market data, evaluates signal rules against synthetic portfolio snapshots, delegates to a strategy for action decisions, and executes the resulting trades with realistic Trade Republic constraints.

## Architectural Role

| Aspect | Details |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on | [`data`](../data/) (price series), [`config`](../config.py) (`BacktestConfig`), [`analysis`](../../analysis/) (deviation), [`rules`](../../rules/) (signal evaluation), [`models`](../../models/) (portfolio/signal types) |
| Consumed by | Backtester strategies (Phase 3), CLI interface (Phase 6) |
| Boundary | Pure computation — no I/O, no network calls, deterministic with seed |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `analysis` | `pac.analysis` | Deviation computation reused on every simulation tick to match production logic | `DeviationReport`, `calculate_deviations` |
| `backtester/data` | `pac.backtester.data` | Price series consumed by the simulation clock and portfolio state machine | `PriceSeries`, `PriceBar` |
| `backtester/results` | `pac.backtester.results` | Result models populated as the simulation progresses | `IterationResult`, `SimulationResult` |
| `backtester/strategies` | `pac.backtester.strategies` | Strategy interface for translating signals into actions each tick | `BacktestStrategy` |
| `config` | `pac.config` | Simulation parameters (dates, contributions, spread) from `BacktestConfig` | `Settings` |
| `rules` | `pac.rules` | Existing production signal rules evaluated on each synthetic snapshot | `SignalRegistry` |

## Key Components

| Component | File | Description |
| -------------------- | -------------- | ---------------------------------------------------------------------------------------------- |
| `SimulationClock` | `clock.py` | Iterates trading days from a `PriceSeries`, detects PAC execution dates with weekend rollover |
| `SimulatedPortfolio` | `portfolio.py` | Mutable portfolio state machine — tracks positions, cash, PAC volumes, pending actions |
| `SimulatedPosition` | `portfolio.py` | Internal position tracking (asset_id, ISIN, name, quantity, avg_cost) |
| `BacktestSimulator` | `simulator.py` | Main event loop — Monte Carlo iterations with per-iteration slippage sampling |
| `StrategyProtocol` | `simulator.py` | Protocol interface strategies must implement (`on_signals()`) |
| `Action` | `actions.py` | Strategy-emitted action envelope (PAC adjustment or hard rebalance) |
| `PacAdjustment` | `actions.py` | Adjust PAC volumes — applied on next PAC date, fee-free |
| `HardRebalanceOrder` | `actions.py` | Single buy/sell order — €1 settlement fee + configurable spread per order |
| `ExecutedTrade` | `actions.py` | Immutable record of an executed trade (for trade log), tracks partial fills and skipped trades |
| `PendingAction` | `actions.py` | Action delayed by human slippage — queued until `execute_on` date |
| `DayResult` | `simulator.py` | End-of-day portfolio snapshot (total value, allocations, cash) |
| `IterationResult` | `simulator.py` | Single Monte Carlo iteration result (daily snapshots + trade log) |
| `SimulationResult` | `simulator.py` | Aggregated result across all MC iterations |

## Configuration

`BacktestConfig` (`src/pac/backtester/config.py`) controls simulation parameters:

| Parameter | Default | Description |
| ------------------------ | ------------------------ | --------------------------------------------------- |
| `strategy` | *(required)* | Strategy name (registered) |
| `strategy_params` | `{}` | Strategy-specific parameters |
| `start_date` | *(required)* | Backtest start date |
| `end_date` | *(required)* | Backtest end date (must be after start) |
| `initial_cash` | `10000` | Starting cash in EUR |
| `monthly_contribution` | `500` | Monthly PAC contribution in EUR |
| `pac_execution_days` | `[2, 16]` | Day-of-month for PAC executions (1–28) |
| `settlement_fee` | `1.00` | Fee per hard rebalance order in EUR |
| `spread_bps` | `10` | Spread in basis points applied to execution price |
| `slippage_days` | `(0, 3)` | Uniform distribution range for human decision delay |
| `monte_carlo_iterations` | `100` | Number of MC iterations per backtest run |
| `metrics` | `[sortino, calmar, ...]` | Metric names for post-run analysis |
| `benchmark` | `true` | Compare against passive buy-and-hold |

## Simulation Loop

Each Monte Carlo iteration follows this sequence per trading day:

1. **Update prices** — look up `PriceBar` for each asset from pre-built index
1. **Process pending actions** — execute slippage-delayed actions whose `execute_on ≤ today`
1. **PAC execution** — if today is a PAC date, buy each asset at current PAC volumes (fee-free)
1. **Build snapshot** — construct a `PortfolioSnapshot` compatible with the live analysis pipeline
1. **Compute deviations** — reuse `analysis.deviation.calculate_deviations()`
1. **Evaluate signals** — run all configured `SignalRule` instances via `SignalRegistry`
1. **Strategy decision** — feed signals to `strategy.on_signals()` → get `Action` list
1. **Queue actions** — apply sampled slippage delay, queue for future execution
1. **Record snapshot** — store `DayResult` (total value, allocations, cash)

## Trade Republic Constraints Modeled

| Constraint | How modeled |
| ------------------ | ------------------------------------------------------------------------- |
| PAC execution days | Only 2nd/16th (configurable); weekends/holidays roll to next trading day |
| PAC fee | €0 — PAC buys are fee-free |
| Manual order fee | €1 flat settlement fee per hard rebalance order |
| Spread | Configurable basis points (default 10bps) applied to close price |
| Cash sufficiency | Buy orders skipped if cash < amount + fee; sell orders capped at held qty |
| Human latency | Per-iteration slippage sampled from `uniform(min, max)` trading days |

## Usage

```python
from pac.backtester.engine import BacktestSimulator, SimulationResult

simulator = BacktestSimulator(
    config=backtest_config,
    settings=settings,
    price_data=price_data,       # dict[ticker, PriceSeries]
    signal_registry=registry,
    strategy=my_strategy,
    rng_seed=42,                 # deterministic results
)

# Run all Monte Carlo iterations
result: SimulationResult = simulator.run()

# Or run a single iteration
iteration = simulator.run_iteration(iteration=0)
iteration.final_value   # Decimal
iteration.trades        # list[ExecutedTrade]
iteration.daily_values  # list[DayResult]
```

## Commands

```bash
just test -k test_clock         # SimulationClock tests
just test -k test_portfolio     # SimulatedPortfolio tests
just test -k test_simulator     # BacktestSimulator tests
just test -k test_actions       # Action model tests
```

## See Also

- [Data](../data/) — market data provider consumed by the simulator
- [Config](../config.py) — `BacktestConfig` model for run parameters
- [Analysis](../../analysis/) — `calculate_deviations()` reused during simulation
- [Rules](../../rules/) — signal rules evaluated at each time step
