# MarketContext Protocol & Crisis Detection Architecture

**Source:** Task 009 (April 2026)

## Decision

Introduce a `MarketContext` protocol that provides date-aware historical price access to signal rules, enabling a composable crisis detection system built from independent indicator rules with N-of-M voting.

## Why

- Crisis detection rules need historical price data (moving averages, drawdowns, volatility), but signal rules were previously limited to portfolio snapshot data only
- Backtesting requires look-ahead bias protection — rules must not see future prices
- A single monolithic crisis rule would be fragile; independent indicators with composite voting produce rare, high-confidence signals (2–5 per decade)
- Price data models (`PriceSeries`, `PriceBar`) were locked inside the backtester module despite being needed by production code
- ETFs in the portfolio are too recent for 30-year backtests; proxy ticker stitching fills historical gaps

## Problem Statement

Signal rules could only inspect the current `PortfolioSnapshot` and `DeviationReport`. Rules that detect market regime changes (drawdowns, volatility spikes, cross-asset divergence) need lookback windows over historical price data. In backtesting, this data must be filtered to the simulated date to prevent look-ahead bias. No abstraction existed to bridge these two contexts.

## Solution

### Before

- `SignalRule.evaluate()` received only `(snapshot, deviation_report)`
- No access to historical price data in rules
- `PriceSeries`/`PriceBar` lived in `pac.backtester.data.models` — inaccessible to production code
- Crisis detection did not exist

### After

- `SignalRule.evaluate()` receives optional `market_ctx: MarketContext | None`
- `MarketContext` protocol with two implementations: `LiveMarketContext` (production) and `BacktestMarketContext` (simulation)
- `PriceSeries`/`PriceBar`/`Interval` moved to `pac.models.market_data` as shared vocabulary (re-exported from backtester for backward compat)
- 6 independent crisis indicator rules + 1 composite rule with N-of-M voting
- Pure indicator math separated into `_indicators.py` helper module

## Implementation Phases

| Phase                  | What Changed                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------ |
| 1. Research            | Historical crisis analysis (1996-2025), proxy asset validation, indicator parameter calibration        |
| 2. MarketContext       | Protocol definition, Live/Backtest implementations, `evaluate()` signature extension, proxy tickers    |
| 3. Refine Existing     | `pac_plan` day=16, `cycle_inversion` min_pct=3.0, rationale docs for threshold defaults                |
| 4. Crisis Rules        | 6 indicator rules + composite + `_indicators.py` + crisis_alert template + BDD tests                   |
| 5. Crisis Strategy     | `CrisisExploitStrategy` with cooldown, severity sizing, allocation floors, `reset()` ABC hook          |
| 6. Backtest Validation | Validation script (15 scenarios), `pac-backtest.yaml` with proxy tickers, `ANALYSIS.md`                |
| 7. Documentation       | READMEs, CHANGELOG, MarketContext docs, proxy ticker docs                                              |
| 8. Indicator Redesign  | Replaced vol_ratio with death_cross, removed Type C veto, tuned thresholds (Task 010)                  |
| 9. Strategy Redesign   | Two-mechanism strategy: PAC tilt (cash flow redirect) + hard rebalance at extreme drawdowns (Task 010) |
| 10. Research Paper     | Publication-ready paper with companion validation script and generated figures (Task 010)              |

## Key Architectural Patterns

### MarketContext Protocol (structural typing)

```python
# src/pac/market_context.py
class MarketContext(Protocol):
    @property
    def current_date(self) -> date: ...

    def get_prices(self, ticker: str, lookback_days: int) -> PriceSeries: ...
```

- **Production:** `LiveMarketContext` wraps yfinance with disk caching, `current_date = today`
- **Backtesting:** `BacktestMarketContext` slices pre-loaded data, `current_date = simulated date` (look-ahead protection)
- Rules call `market_ctx.get_prices(ticker, lookback_days=200)` — same API in both contexts
- Existing rules that don't use market data ignore the parameter (backward compatible)

### Composite Crisis Voting (N-of-M)

```python
# src/pac/rules/builtin/crisis_composite.py
class CrisisCompositeParams(BaseModel):
    min_active_indicators: int = 3  # N-of-M voting threshold

    # Per-indicator thresholds (drawdown depth/velocity, divergence, death cross, RS)
    drawdown_warning_pct: float = -12.0
    drawdown_critical_pct: float = -20.0
    # ... more indicator thresholds
```

- 5 voter indicators: drawdown depth, drawdown velocity, gold-equity divergence, death cross (SMA50/200), relative strength breakout
- No guard/veto — Type C bond-equity correlation was removed (never fired in 20 years of data)
- Default activation: 3-of-5 voters active → composite fires
- Severity: ≥2 critical indicators → CRITICAL, otherwise WARNING

### Indicator Math Separation

```python
# src/pac/rules/builtin/_indicators.py — pure functions, no rule logic
compute_drawdown(equity_prices) -> DrawdownResult
compute_divergence(gold_prices, equity_prices) -> DivergenceResult
compute_relative_strength(gold_prices, equity_prices) -> RelativeStrengthResult
compute_death_cross(equity_prices, short_window, long_window) -> DeathCrossResult
```

- Individual rules and the composite rule both call the same functions
- Functions raise `ValueError` on insufficient data; callers catch and return empty signals (graceful degradation)
- `compute_volatility_regime()` and `compute_correlation()` still exist in `_indicators.py` for standalone rules but are **not used** by the composite

### Two-Mechanism Crisis Exploitation Strategy

```python
# src/pac/backtester/strategies/builtin/crisis_exploit.py
class CrisisExploitParams(BaseModel):
    # Mechanism 1: PAC Tilt — redirect contributions to equity (fee-free)
    pac_tilt_equity_pct: Decimal = Decimal("100")  # 100/0/0 during crisis
    recovery_days: int = 120  # tilt persists 120d after last signal

    # Mechanism 2: Hard Rebalance — sell gold overweight at extreme DD
    dd_threshold_pct: float = -20.0  # gate: only at DD ≤ -20%
    sell_fraction: Decimal = Decimal("1.0")  # sell 100% of gold overweight
    cooldown_days: int = 90  # 90d between hard rebalance trades
    min_gold_pct: Decimal = Decimal("5.0")  # floor: never sell below 5%
```

- **PAC tilt** (primary alpha source, ~78%): redirects all contributions to equity during crisis + 120-day recovery window — zero transaction cost
- **Hard rebalance** (marginal alpha, ~22%): sells gold overweight → buys equity at DD ≤ −20%, 90-day cooldown — only 4 trades in 20 years
- Strategy state machine: NORMAL → CRISIS_ACTIVE → HARD_REBALANCE → COOLDOWN → back
- `on_pac_date()` returns `PacAdjustment` to modify contribution allocation; `on_signals()` returns `Action(HARD_REBALANCE)` for sell/buy orders

### Multi-Segment Proxy Chains with FX Conversion

```python
# src/pac/config/models.py
class ProxySpec(BaseModel):
    ticker: str           # e.g. "^SP500TR"
    end: date             # handoff date to next segment
    currency: str = "EUR"  # source currency for FX conversion

class AssetConfig(BaseModel):
    proxy_chain: list[ProxySpec] = []  # ordered segments, earliest first
    # Legacy proxy_ticker/proxy_end auto-migrated via model_validator
```

- Each segment can have a different currency; `fx.py` converts to EUR using daily exchange rates with forward-fill
- `proxy_quality.py` computes Pearson correlation + vol-ratio during overlap periods between adjacent segments
- `fetch_with_proxy()` traverses the chain, applies per-segment FX conversion, and stitches series via `normalize_and_stitch()`

### Stateful Strategy Reset Hook

```python
# src/pac/backtester/strategies/base.py
class BacktestStrategy(ABC, Generic[ParamsT]):
    def reset(self) -> None:  # no-op default
        """Called between Monte Carlo iterations to clear per-run state."""
```

- `CrisisExploitStrategy` tracks `_last_signal_date` and `_last_hard_rebalance_date` — must be reset between iterations
- Simulator calls `strategy.reset()` at the start of each Monte Carlo iteration

## Current Structure

```
src/pac/
├── market_context.py              # MarketContext protocol
├── live_market_context.py         # Production implementation (yfinance + cache)
├── models/
│   └── market_data.py             # PriceSeries, PriceBar, Interval (shared vocabulary)
├── config/
│   └── models.py                  # ProxySpec model, AssetConfig.proxy_chain
├── rules/builtin/
│   ├── _indicators.py             # Pure indicator math (6 compute functions)
│   ├── equity_drawdown.py         # Drawdown depth + velocity rule
│   ├── gold_equity_divergence.py  # Gold-equity divergence rule
│   ├── volatility_regime.py       # Realized volatility regime shift rule (standalone only)
│   ├── relative_strength.py       # Gold/equity relative strength rule
│   ├── death_cross.py             # 50/200 MA crossover rule
│   ├── crisis_composite.py        # N-of-M composite (5 voters, no veto)
│   ├── threshold.py               # Threshold deviation (unchanged)
│   ├── cycle.py                   # Cycle inversion (min_pct tuned)
│   └── pac_plan.py                # PAC plan (day=16)
├── templates/builtin/
│   └── crisis_alert.j2            # Crisis alert template
└── backtester/
    ├── data/
    │   ├── fx.py                   # FX conversion helper (EUR/USD, EUR/GBP)
    │   ├── proxy_quality.py        # Proxy chain overlap quality assessment
    │   └── provider.py             # fetch_with_proxy(), normalize_and_stitch()
    ├── strategies/builtin/
    │   └── crisis_exploit.py      # Two-mechanism: PAC tilt + hard rebalance
    └── engine/
        └── simulator.py           # Passes BacktestMarketContext, calls strategy.reset()

research/papers/crisis-strategy/
├── paper.md                       # Publication-ready research paper
├── generate_figures.py            # Companion script (figures + claim validation)
├── figures/                       # Generated PNG figures
└── README.md                      # Reproduction instructions
```

## Deleted

- `stitch_proxy_series()` in `provider.py` — replaced by `normalize_and_stitch()` with per-segment FX conversion
- `PriceSeries`/`PriceBar`/`Interval` definitions moved from `pac.backtester.data.models` to `pac.models.market_data`; original module re-exports for backward compatibility
- Original `CrisisExploitParams` (severity-based sell fractions, dual gold+bonds selling) — replaced by two-mechanism params

## Architectural Note: Cash Flow Manipulation vs Market Timing

Iterative backtest research (Task 010, 9 hypotheses, 2006-2026, €10k initial + €500/month) found that **cash flow manipulation dominates market timing** for PAC portfolios:

| Metric                  | Baseline | Strategy |    Delta |
| ----------------------- | -------: | -------: | -------: |
| Final Portfolio Value   | €388,254 | €436,451 | +€48,197 |
| Return on Contributions |   195.3% |   231.9% |  +36.7pp |
| Maximum Drawdown        |   −39.3% |   −31.8% |   +7.5pp |
| Hard Rebalance Trades   |        0 |        4 |        4 |

**Key finding:** The primary alpha source (~78%) is fee-free PAC tilt — redirecting monthly contributions from 70/15/15 to 100/0/0 during crisis + 120-day recovery. Hard rebalancing at extreme drawdowns adds marginal alpha (~22%) through only 4 trades in 20 years. Three timing-asymmetry hypotheses (RS peak sell, velocity inflection buy, decoupled state machine) all failed — crisis conditions co-occur rather than sequence.

**Caveats:** Single historical path, 5 crisis episodes, parameters optimized on validation data, mediocre GFC-era proxy quality (r=0.57). Full analysis in [paper.md](../../research/papers/crisis-strategy/paper.md).

The crisis composite rule serves dual purposes: (1) **monitoring/alerting** via Telegram notifications, and (2) **strategy input** for the two-mechanism exploitation strategy in backtesting.

## Updates

| Date       | Task | Summary                                                                                                                                                                                                 |
| ---------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| April 2026 | 010  | Replaced vol_ratio with death_cross, removed Type C veto; added multi-segment proxy chains with FX conversion; redesigned strategy to PAC tilt + hard rebalance (+€48k alpha); published research paper |
