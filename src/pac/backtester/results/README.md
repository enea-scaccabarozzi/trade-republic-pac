# Results Persistence

Frontend-agnostic JSON sidecar for backtest results. Converts a `BacktestReport` (internal simulation data with `Decimal` fields and per-iteration details) into a `RunResult` (JSON-serializable model with floats, equity curve bands, and allocation percentages).

## Public API

| Symbol               | Description                                                 |
| -------------------- | ----------------------------------------------------------- |
| `RunResult`          | Pydantic model — the JSON schema for a saved backtest run   |
| `build_run_result()` | Converts `BacktestReport` → `RunResult` with MC aggregation |
| `ResultStore`        | Save/load/list/delete JSON files in `.pac/backtests/`       |

## JSON Schema

```json
{
  "run_id": "2024-01-02T10-00-00_my_strategy",
  "created_at": "2024-01-02T10:00:00+00:00",
  "config": { "...": "BacktestConfig fields" },
  "monte_carlo": { "iterations": 100, "slippage_range": [0, 3] },
  "metrics": {
    "strategy": { "sharpe": { "p5": 0.3, "median": 0.5, "p95": 0.7 } },
    "benchmark": { "sharpe": { "p5": 0.4, "median": 0.4, "p95": 0.4 } }
  },
  "equity_curve": [
    { "date": "2024-01-02", "p5": 9800, "median": 10000, "p95": 10200 }
  ],
  "allocations": [
    { "date": "2024-01-02", "assets": { "stocks": { "p5": 68, "median": 70, "p95": 72 }, "cash": { "p5": 0, "median": 0, "p95": 0 } } }
  ],
  "trades": [
    { "date": "2024-01-02", "type": "pac_execution", "asset_id": "stocks", "direction": "buy", "amount_eur": 175.0, "quantity": 1.75, "price": 100.0, "fee": 0.0, "skipped": false }
  ],
  "summary": {
    "total_invested": 11000.0,
    "final_value": { "p5": 10500, "median": 11000, "p95": 11800 },
    "total_fees": { "p5": 1.0, "median": 2.0, "p95": 3.0 },
    "total_trades": { "p5": 1, "median": 1, "p95": 2 },
    "total_pac_executions": 12
  }
}
```

## Aggregation Logic

1. **Median iteration**: iteration whose `final_value` is closest to the overall median
2. **Equity curve**: P5/median/P95 of `total_value` at each date across all iterations
3. **Allocations**: P5/median/P95 per asset (+ cash pseudo-asset) at each date
4. **Trades**: extracted from the median iteration (Decimal → float conversion)
5. **Summary**: `total_invested = initial_cash + contribution_per_pac × actual_pac_count`
6. **Benchmark metrics**: `p5 = p95 = median` (deterministic, uniform shape)

## Usage

```python
from pac.backtester.results import build_run_result, ResultStore

result = build_run_result(report)
store = ResultStore()
store.save(result)

loaded = store.load(result.run_id)
all_runs = store.list_runs()
store.delete(result.run_id)
```
