# Backtester & Research Framework Improvements

Targeted improvements to the backtester simulation engine, research interface, and overall performance. Three framework enhancements (tax regimes, slippage correction, variable contributions) and three performance improvements (parallel tests, vectorization, concurrency).

## 1. Tax Regime System

### Core Abstraction

A `TaxRegime` ABC injected into `SimulatedPortfolio` via DI. The portfolio calls the regime on every sell to compute tax owed. The regime tracks its own state (loss carryforward) across trading days within an iteration.

```
TaxRegime (ABC)
├── ItalianTaxRegime     (26% general / 12.5% gov bonds, 4-year loss carryforward)
├── NoTaxRegime          (opt-out: zero tax, always)
└── (future: GermanTaxRegime, etc.)
```

### Interface

```python
class TaxRegime(ABC):
    @abstractmethod
    def compute_tax(self, proceeds: Decimal, cost_basis: Decimal,
                    asset_meta: AssetTaxMeta) -> TaxResult: ...

    @abstractmethod
    def reset(self) -> None: ...  # Between MC iterations

    @abstractmethod
    def name(self) -> str: ...
```

**`AssetTaxMeta`**: Frozen model with fields like `government_bond: bool` for Italy's reduced 12.5% rate. Derived from asset config — each `AssetConfig` gets an optional `tax_meta` section.

**`TaxResult`**: Frozen model with `tax_owed: Decimal`, `loss_recorded: Decimal`, `effective_rate: Decimal`. The portfolio deducts `tax_owed` from cash (can be zero when losses offset gains).

### Italian Regime Specifics

- **Rate**: 26% on realized gains (redditi diversi), 12.5% for government bond instruments.
- **Loss carryforward**: Losses stored in a ledger keyed by fiscal year of origin. On a profitable sell, prior losses offset gains FIFO by year. Losses expire after 4 fiscal years.
- **Application point**: Inside `SimulatedPortfolio._execute_rebalance_orders()` on sell trades. The hook also exists in `execute_pac()` for completeness, though PAC is buy-only in practice.

### Config

```yaml
backtest:
  tax_regime: "italian"  # or "none" to opt out. Default: "italian"
  tax_params:
    default_rate: 0.26
    government_bond_rate: 0.125
    loss_carryforward_years: 4
```

`BacktestConfig` gains `tax_regime: str = "italian"` and `tax_params: dict[str, Any] = {}`. A registry (same pattern as strategies/rules) maps names to regime classes.

### Portfolio Integration

The portfolio receives `TaxRegime` at construction. On sell:

1. Compute `cost_basis = quantity_sold * position.avg_cost`
2. Compute `proceeds = quantity_sold * execution_price`
3. Call `regime.compute_tax(proceeds, cost_basis, asset_meta)`
4. Deduct `tax_result.tax_owed` from cash
5. Record tax in `ExecutedTrade` (new field: `tax: Decimal = Decimal(0)`)

`TaxRegime.reset()` is called alongside `portfolio.reset()` between MC iterations to clear loss carryforward state.

### Tracking in Results

`ExecutedTrade` gains a `tax: Decimal` field. `IterationResult` gains a `total_tax_paid: Decimal` summary. This flows through to metrics without changing the metrics interface.

---

## 2. Slippage Fix — PAC vs Hard Trades

### Current Behavior

Slippage (random delay in trading days) is sampled once per MC iteration and applied to all strategy-emitted actions via `_find_execution_date()`. PAC trades already execute on fixed calendar dates with no slippage delay — this is correct.

### What Changes

The fix is about **intraday price simulation for PAC trades**. Currently PAC trades execute at bar `close` price. In reality, Trade Republic PAC executes at a random hour on the target day — the user cannot control timing. PAC should execute at a random price within the day's [low, high] range, not at close.

In `SimulatedPortfolio.execute_pac()`, replace:

```python
quantity = volume / bar.close
```

With:

```python
pac_price = low + rng.random() * (high - low)
quantity = volume / pac_price
```

The `rng` (seeded `random.Random`) is passed into the portfolio so PAC intraday randomness is deterministic and reproducible across MC iterations.

### Hard Rebalance — No Change

Hard rebalance trades keep their existing behavior: configurable slippage delay (trading days), execution at `close +/- spread_bps`, settlement fee.

### Summary

| Trade Type | Current | After |
|---|---|---|
| PAC | Execute at `bar.close`, no delay | Execute at random price in `[low, high]`, no delay |
| Hard rebalance | Slippage delay + spread + fee | No change |

---

## 3. Variable Contribution Amounts

### Current Behavior

`BacktestConfig.monthly_contribution` is a fixed `Decimal`. Every month, the same amount is added to cash and split across PAC days.

### New Config Model

Contribution config becomes a union — either fixed (backward-compatible default) or variable:

```yaml
# Fixed (current behavior, still the default)
backtest:
  monthly_contribution: 500

# Variable with range
backtest:
  monthly_contribution:
    min: 500
    max: 750
    distribution: "uniform"  # or "normal"
```

When `monthly_contribution` is a plain number, it behaves exactly as today. When it's an object, the simulator samples a new amount each month per MC iteration.

### Distribution Abstraction

```
ContributionDistribution (ABC)
├── FixedContribution          (always returns the same amount)
├── UniformContribution        (uniform over [min, max])
├── NormalContribution         (truncated normal, mean=(min+max)/2, std configurable, clipped to [min, max])
└── (future: custom distributions)
```

Interface (stateless — no `reset()` needed between MC iterations, unlike `TaxRegime`):

```python
class ContributionDistribution(ABC):
    @abstractmethod
    def sample(self, rng: random.Random) -> Decimal: ...

    @abstractmethod
    def name(self) -> str: ...
```

### Config Validation

`BacktestConfig` gets a new field:

```python
monthly_contribution: Decimal | ContributionConfig = Decimal("500")
```

Where `ContributionConfig` is:

```python
class ContributionConfig(BaseModel, frozen=True):
    min: Decimal
    max: Decimal
    distribution: str = "uniform"  # "uniform" | "normal"
    std: Decimal | None = None     # For normal: defaults to (max - min) / 4
```

A validator on `BacktestConfig` normalizes both forms. If it's a plain `Decimal`, it wraps it in `FixedContribution`. If it's a `ContributionConfig`, it resolves the distribution by name from a registry.

### Simulator Integration

In `run_iteration()`, at the start of each month (first PAC day):

```python
monthly_amount = self._contribution_dist.sample(self._rng)
```

This replaces the current `self._config.monthly_contribution` reference. The sampled amount is then split across PAC days within that month (same as today's splitting logic).

### Impact on MC

Variable contributions add a randomness dimension to Monte Carlo. With fixed contributions, MC variance comes only from slippage timing and PAC intraday price. With variable contributions, monthly cash injection also varies — making the MC spread more realistic for users whose income fluctuates.

---

## 4. Parallel pytest Execution

### Issues to Fix

**1. `tests/test_setup_gcp.py` — module-level state mutation.** `TestRunGcloud` uses `setup_method`/`teardown_method` to save/restore `scripts.setup_gcp._ACTIVE_ACCOUNT`. If two workers run tests from this class simultaneously, they race. Fix: refactor to function-scoped fixtures with `monkeypatch`.

**2. `src/pac/backtester/research/tests/test_quantstats.py` — matplotlib global state.** `TestQuantstatsPlot` calls `plt.close("all")` in setup/teardown. Fix: add `@pytest.mark.xdist_group("matplotlib")` to group these tests on one worker.

### Configuration

```toml
[tool.pytest.ini_options]
addopts = "--ignore-glob=**/dashboard.legacy/** -n auto --dist loadscope"
```

- `-n auto`: one worker per CPU core.
- `--dist loadscope`: group tests by module/class, then distribute groups across workers. Naturally keeps related tests together.

Tests that surface as flaky after enabling xdist can be marked `@pytest.mark.xdist_group("serial")`.

---

## 5. DataFrame Vectorization

### 5.1 `provider.py:147` — `iterrows()` to `itertuples()`

Convert yfinance DataFrame to PriceSeries. `iterrows()` allocates a Series per row. Fix with `itertuples()` (~10-100x faster for row access):

```python
bars = [
    PriceBar(
        date=row.Index.date(),
        open=Decimal(str(row.Open)),
        high=Decimal(str(row.High)),
        low=Decimal(str(row.Low)),
        close=Decimal(str(row.Close)),
        volume=int(row.Volume),
    )
    for row in df.itertuples()
]
```

### 5.2 `proxy_quality.py:72-80` — daily returns loop to numpy

Sequential loop computing returns for correlation. Vectorize:

```python
proxy_prices = np.array([float(proxy_dates[d].close) for d in overlap_dates])
target_prices = np.array([float(target_dates[d].close) for d in overlap_dates])
proxy_returns = np.diff(proxy_prices) / proxy_prices[:-1]
target_returns = np.diff(target_prices) / target_prices[:-1]
```

### 5.3 `results/aggregation.py` — nested iteration for equity curves

Triple-nested loop building numpy matrix. Fix with direct list comprehension to `np.array`:

```python
matrix = np.array([
    [float(dv.total_value) for dv in it.daily_values]
    for it in iterations
])
```

Same pattern for `_build_allocations()`.

### Not Vectorized (intentional)

- Per-day trading loop in simulator — inherently sequential (state dependency).
- Metrics calculation — already uses numpy/quantstats vectorized ops.
- Price index building — runs once, O(n), not a bottleneck.

---

## 6. Concurrency — MC Parallelization and Async I/O

### Monte Carlo Parallelization

Each MC iteration is independent: own RNG seed, own portfolio state, own tax regime state. Uses `ProcessPoolExecutor` for true parallelism (bypasses GIL for CPU-bound Decimal math).

**Worker function:**

```python
def _run_iteration_worker(args: IterationWorkerArgs) -> IterationResult:
    """Top-level picklable function. Reconstructs simulator, runs one iteration."""
    simulator = BacktestSimulator(args.config, args.settings, args.price_data, ...)
    return simulator.run_iteration(args.iteration_index)
```

Each worker gets the full config, settings, and price data (serialized once via pickle). Iteration index derives the seed: `seed = base_seed + iteration_index` for deterministic RNG.

**Worker count:** `min(cpu_count(), monte_carlo_iterations)`. No pool overhead for `N=1` quick-test mode — runs in-process.

**Progress reporting:** Parent process collects results via `as_completed()` and fires the existing `on_progress` callback as each future resolves.

### Concurrent Data Fetching

`MarketDataProvider.fetch_multiple()` gains concurrent execution using `ThreadPoolExecutor` (threads are correct for I/O-bound network calls):

```python
def fetch_multiple(self, requests: list[DataRequest]) -> dict[str, PriceSeries]:
    with ThreadPoolExecutor(max_workers=min(len(requests), 8)) as pool:
        futures = {pool.submit(self.fetch, req): req.ticker for req in requests}
        results = {}
        for future in as_completed(futures):
            ticker = futures[future]
            results[ticker] = future.result()
        return results
```

The asset fetch loop in `runner.py` similarly becomes concurrent. File-based cache is safe for concurrent access — each ticker has a unique cache key; worst case two threads cache the same ticker and the last write wins (idempotent).

### What Stays Single-Threaded

- **Per-day trading loop** — inherently sequential (each day depends on previous day's portfolio state).
- **Metrics aggregation** — already fast with numpy; parallelization overhead would exceed gains.
- **Strategy evaluation** — lightweight per-day calls; not worth dispatch cost.
- **API layer** — already async via FastAPI/uvicorn.

### Concurrency Summary

| Component | Current | After | Expected Speedup |
|---|---|---|---|
| MC iterations | Sequential loop | `ProcessPoolExecutor` | ~Nx (N = CPU cores) |
| Data fetching | Sequential per-asset | `ThreadPoolExecutor` | ~Nx (N = assets) |
| Quick-test (N=1) | In-process | In-process (no change) | None (no overhead) |
| Per-day simulation | Sequential | Sequential (no change) | N/A |

---

## File Impact Summary

| File | Changes |
|---|---|
| `src/pac/backtester/engine/tax.py` | **New** — `TaxRegime` ABC, `ItalianTaxRegime`, `NoTaxRegime`, `AssetTaxMeta`, `TaxResult` |
| `src/pac/backtester/engine/contributions.py` | **New** — `ContributionDistribution` ABC, `FixedContribution`, `UniformContribution`, `NormalContribution`, `ContributionConfig` |
| `src/pac/backtester/engine/portfolio.py` | Tax regime integration on sells, RNG injection for PAC intraday price |
| `src/pac/backtester/engine/simulator.py` | Variable contributions per month, pass RNG to portfolio, parallel MC support |
| `src/pac/backtester/engine/actions.py` | `ExecutedTrade.tax` field, `IterationResult.total_tax_paid` field |
| `src/pac/backtester/config.py` | `tax_regime`, `tax_params`, `monthly_contribution` union type, `ContributionConfig` |
| `src/pac/backtester/runner.py` | `ProcessPoolExecutor` for MC, concurrent data fetching |
| `src/pac/backtester/data/provider.py` | `itertuples()` fix, `ThreadPoolExecutor` in `fetch_multiple()` |
| `src/pac/backtester/data/proxy_quality.py` | Vectorized daily returns |
| `src/pac/backtester/results/aggregation.py` | Vectorized matrix construction |
| `src/pac/config/models.py` | `AssetConfig.tax_meta` optional field |
| `pyproject.toml` | pytest `-n auto --dist loadscope` |
| `tests/test_setup_gcp.py` | Refactor to function-scoped fixtures |
| `src/pac/backtester/research/tests/test_quantstats.py` | Add `xdist_group` marker |
