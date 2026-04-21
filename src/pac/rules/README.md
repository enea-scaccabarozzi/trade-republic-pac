# Rules

Signal rule engine — evaluates portfolio state against configurable rules and produces typed signals. Rules are stateless; typed params are validated and passed to `evaluate()` at call time.

## Architectural Role

| Aspect      | Details                                                                                                                  |
| ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| Depends on  | [`models`](../models/) (`Signal`, `PortfolioSnapshot`, `SignalSeverity`), [`analysis`](../analysis/) (`DeviationReport`) |
| Consumed by | [`orchestrator`](../orchestrator/) (`SignalRegistry` evaluates signals, `build_template_data` produces template context) |
| Boundary    | Rule evaluation, param validation, signal generation                                                                     |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Input and output types for rule evaluation | `Signal`, `PortfolioSnapshot`, `SignalSeverity` |
| `analysis` | `pac.analysis` | Deviation computation required by most rules' `evaluate()` implementations | `DeviationReport`, `DeviationResult` |
| `market_context` | `pac.market_context` | Protocol for date-aware price access used by crisis rules | `MarketContext` |

## Key Components

| Component                  | File                                | Description                                                                |
| -------------------------- | ----------------------------------- | -------------------------------------------------------------------------- |
| `SignalRule[ParamsT]`      | `base.py`                           | ABC + Generic base class; `__init_subclass__` auto-extracts `params_model` |
| `SignalRegistry`           | `registry.py`                       | Collects rule classes, validates params, dispatches evaluation             |
| `discover_rules()`         | `discovery.py`                      | Scans `builtin/` for concrete `SignalRule` subclasses                      |
| `ThresholdDeviationRule`   | `builtin/threshold.py`              | Fires on per-asset deviation thresholds                                    |
| `CycleInversionRule`       | `builtin/cycle.py`                  | Detects diverging asset pairs                                              |
| `PacPlanRule`              | `builtin/pac_plan.py`               | Computes monthly PAC allocation plan                                       |
| `_indicators`              | `builtin/_indicators.py`            | Pure indicator math (drawdown, divergence, volatility, correlation)        |
| `EquityDrawdownRule`       | `builtin/equity_drawdown.py`        | Drawdown depth + velocity detection (requires `MarketContext`)             |
| `GoldEquityDivergenceRule` | `builtin/gold_equity_divergence.py` | Flight-to-safety divergence detection                                      |
| `VolatilityRegimeRule`     | `builtin/volatility_regime.py`      | Vol regime shift detection (short/long ratio)                              |
| `RelativeStrengthRule`     | `builtin/relative_strength.py`      | Gold/equity RS ratio MA breakout                                           |
| `DeathCrossRule`           | `builtin/death_cross.py`            | SMA 50/200 death cross detection                                           |
| `CrisisCompositeRule`      | `builtin/crisis_composite.py`       | N-of-M voting composite + Type C bond-equity guard                         |

## Configuration

Rules are referenced by name in `pac.yaml` signal configs. Each signal specifies a `rule:` name and a `params:` dict. The `SignalRegistry` validates the raw params dict against the rule's `params_model` (two-phase validation: config parsing is separated from rule logic).

## Usage

```python
from pac.rules import SignalRule, SignalRegistry, discover_rules

# Discovery — returns {name: class} mapping
rule_classes = discover_rules()

# Registry — register and evaluate
registry = SignalRegistry()
for rule_cls in rule_classes.values():
    registry.register(rule_cls)

# Evaluate with raw params from config
signals = registry.evaluate_signal(
    "threshold_deviation",
    {"warning_pct": 3.0, "critical_pct": 5.0},
    report,
    snapshot,
)
```

### Adding a Rule

```bash
just new-rule my_rule_name
```

Subclass `SignalRule[YourParams]`, implement `name` and `evaluate()`, and place the module in `builtin/`. Discovery is automatic.

## MarketContext Integration

Crisis rules receive an optional `MarketContext` via the `evaluate()` method's `market_ctx` parameter (defaults to `None`). Rules that don't need historical data (threshold, cycle, pac_plan) ignore it. Crisis rules use `market_ctx.get_asset_prices(asset_id, lookback_days)` for indicator calculations.

In production, the `Orchestrator` passes a `LiveMarketContext` (wraps yfinance). During backtesting, the `BacktestSimulator` passes a `BacktestMarketContext` that filters pre-loaded price data up to the current simulation date (zero look-ahead bias).

See [`src/pac/market_context.py`](../market_context.py) for the protocol definition.

## Crisis Detection System

The crisis detection system consists of 5 independent voting indicators plus 1 guard rule, composed by the `CrisisCompositeRule`:

| Indicator                  | What it detects                                    |
| -------------------------- | -------------------------------------------------- |
| `EquityDrawdownRule`       | Drawdown depth exceeding threshold + velocity      |
| `GoldEquityDivergenceRule` | Gold rising while equities fall (flight-to-safety) |
| `VolatilityRegimeRule`     | Short-term vol exceeding long-term vol ratio       |
| `RelativeStrengthRule`     | Gold/equity RS ratio breaking above its MA         |
| `DeathCrossRule`           | SMA 50 crossing below SMA 200                      |

The composite rule uses **N-of-M activation** (default: 3 of 5 indicators must be active) to fire a crisis signal. A **Type C guard** (bond-equity correlation) can veto the signal when bonds and equities fall together (2022-style inflation events where defensive selling would be counterproductive).

Each indicator can also be used standalone for monitoring without the composite voting logic.

See [`docs/crisis-indicators-research.md`](../../../docs/crisis-indicators-research.md) for 30-year historical validation of indicator selection and thresholds.

## Commands

```bash
just test -k test_signals              # rule evaluation unit tests
just test -k test_discovery            # rule discovery unit tests
just test -k test_rule_discovery_bdd   # discovery BDD scenarios
just test -k test_threshold_rule_bdd   # threshold rule BDD scenarios
just test -k test_cycle_rule_bdd       # cycle rule BDD scenarios
just test -k test_equity_drawdown      # drawdown rule tests
just test -k test_death_cross          # death cross rule tests
just test -k test_crisis_composite     # composite rule tests
just test -k test_gold_equity          # gold-equity divergence tests
just test -k test_volatility_regime    # volatility regime tests
just test -k test_relative_strength    # relative strength tests
```

## See Also

- [Analysis](../analysis/) — `DeviationReport` passed to `evaluate()`
- [Models](../models/) — `Signal`, `PortfolioSnapshot` used as inputs/outputs
- [Orchestrator](../orchestrator/) — wires registry and calls `evaluate_signal()`
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — rule design rationale
