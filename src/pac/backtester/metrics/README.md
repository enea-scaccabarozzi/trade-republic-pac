# Metrics

Performance metrics framework for the backtester. Computes per-iteration risk/return metrics via quantstats, aggregates across Monte Carlo iterations with percentile confidence intervals, and optionally compares against a passive buy-and-hold benchmark.

## Architectural Role

| Aspect      | Details                                                                                                                                                                                                                                                                                 |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | [`engine`](../engine/) (`IterationResult`, `SimulationResult`, `BacktestSimulator`), [`data`](../data/) (`PriceSeries`), [`config`](../config.py) (`BacktestConfig`), [`analysis`](../../analysis/) (deviation), [`rules`](../../rules/) (signal registry), `quantstats` (optional dep) |
| Consumed by | Backtester CLI (Phase 6), strategy comparison workflows                                                                                                                                                                                                                                 |
| Boundary    | Pure computation — no I/O, no network calls                                                                                                                                                                                                                                             |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/engine` | `pac.backtester.engine` | Per-iteration simulation results aggregated into metric distributions | `IterationResult` |

## Key Components

| Component             | File            | Description                                                                                 |
| --------------------- | --------------- | ------------------------------------------------------------------------------------------- |
| `MetricsCalculator`   | `calculator.py` | Wraps quantstats.stats functions, computes per-iteration values, aggregates via percentiles |
| `MetricResult`        | `models.py`     | Single metric's aggregated value: median, P5, P95, and per-iteration raw values             |
| `MetricSet`           | `models.py`     | All computed metrics for a single scenario (strategy or benchmark)                          |
| `BacktestReport`      | `models.py`     | Complete report: strategy metrics, benchmark metrics (optional), config, iteration data     |
| `compute_report()`    | `report.py`     | Top-level orchestrator: strategy metrics → benchmark run → benchmark metrics → report       |
| `run_benchmark()`     | `benchmark.py`  | Runs a passive buy-and-hold simulation (PAC-only, no signals, no strategy actions)          |
| `equity_to_returns()` | `returns.py`    | Converts an iteration's equity curve to a daily return series for quantstats                |

## Supported Metrics

All metrics are computed via quantstats with annualized defaults (252 trading days):

| Metric         | Description                                    |
| -------------- | ---------------------------------------------- |
| `sharpe`       | Sharpe ratio (annualized)                      |
| `sortino`      | Sortino ratio (annualized, downside deviation) |
| `calmar`       | Calmar ratio (CAGR / max drawdown)             |
| `max_drawdown` | Maximum peak-to-trough drawdown                |
| `cagr`         | Compound annual growth rate                    |
| `volatility`   | Annualized volatility (standard deviation)     |

Metrics are selected via `BacktestConfig.metrics` — only requested metrics are computed.

## Monte Carlo Aggregation

Each metric is computed per MC iteration, then aggregated:

- **Median** — `np.nanpercentile(values, 50)`
- **P5** — 5th percentile (pessimistic bound)
- **P95** — 95th percentile (optimistic bound)

NaN-safe: iterations producing NaN for a metric are excluded from aggregation.

## Benchmark Comparison

When `BacktestConfig.benchmark` is `True`, `compute_report()` runs a second simulation using `_BenchmarkStrategy` — a passive buy-and-hold that takes no actions beyond regular PAC contributions at target allocation. The benchmark uses:

- Empty `SignalRegistry` (no rules evaluated)
- `slippage_days=(0, 0)` (no human decision delay)
- Same MC iteration count, PAC settings, and date range as the strategy

This answers: *"What if I just did regular PAC contributions and never acted on signals?"*

## Usage

```python
from pac.backtester.metrics import compute_report, BacktestReport

report: BacktestReport = compute_report(
    strategy_result=simulation_result,
    settings=settings,
    price_data=price_data,
    rng_seed=42,
)

# Strategy metrics
sortino = report.strategy.metrics["sortino"]
sortino.median  # float
sortino.p5      # 5th percentile
sortino.p95     # 95th percentile

# Benchmark comparison (if enabled)
if report.benchmark:
    bench_sortino = report.benchmark.metrics["sortino"]
```

## Commands

```bash
just test -k test_calculator    # MetricsCalculator unit tests
just test -k test_benchmark     # Benchmark simulation tests
just test -k test_report        # Report orchestration tests
just test -k test_returns       # Equity-to-returns conversion tests
```
