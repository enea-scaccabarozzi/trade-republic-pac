# Strategies

ABC+Generic framework for backtest strategies. Strategies translate signals into concrete actions (PAC adjustments, hard rebalance orders) during backtester simulation.

## Architectural Role

| Aspect      | Details                                                                                                                                                     |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | [`models`](../../models/) (portfolio, signals), [`analysis`](../../analysis/) (deviation), [`engine.actions`](../engine/actions.py) (PAC/rebalance actions) |
| Consumed by | [`engine.BacktestSimulator`](../engine/simulator.py) (called per trading day), CLI interface (Phase 6)                                                      |
| Boundary    | Pure computation — no I/O, stateful across time steps within a Monte Carlo iteration                                                                        |

## Key Components

| Component             | File           | Description                                                                      |
| --------------------- | -------------- | -------------------------------------------------------------------------------- |
| `BacktestStrategy`    | `base.py`      | ABC+Generic[ParamsT] base — auto-extracts `params_model` via `__init_subclass__` |
| `ParamsT`             | `base.py`      | TypeVar bound to `BaseModel` — concrete strategies parameterize with their own   |
| `_NoStrategyParams`   | `base.py`      | Sentinel default for `params_model` — catches missing Generic type arg           |
| `StrategyRegistry`    | `registry.py`  | Collects strategy classes, instantiates with validated Pydantic params           |
| `discover_strategies` | `discovery.py` | Scans `strategies/builtin/` for concrete subclasses, returns `{name: class}` map |

## Strategy Lifecycle

Strategies are **stateful** — unlike `SignalRule`, they store params on `self` and can track decisions across time steps within a single Monte Carlo iteration. A fresh instance is created per iteration.

### Hooks

| Hook            | Called when                                   | Returns                       | Required |
| --------------- | --------------------------------------------- | ----------------------------- | -------- |
| `on_signals()`  | Trading day produces at least one signal      | `list[Action]` (may be empty) | Yes      |
| `on_pac_date()` | PAC execution date (2nd/16th), before PAC buy | `PacAdjustment \| None`       | No       |

## Usage

### Implementing a strategy

```python
from pydantic import BaseModel
from pac.backtester.strategies import BacktestStrategy
from pac.backtester.engine.actions import Action

class MyParams(BaseModel):
    threshold: float = 5.0

class MyStrategy(BacktestStrategy[MyParams]):
    name = "my_strategy"

    def on_signals(self, signals, snapshot, report, current_date):
        actions: list[Action] = []
        # Inspect signals, decide on PAC adjustments or hard rebalances
        return actions
```

Drop the file in `strategies/builtin/` — `discover_strategies()` picks it up automatically.

### Registry workflow

```python
from pac.backtester.strategies import (
    StrategyRegistry,
    discover_strategies,
)

registry = StrategyRegistry()
for cls in discover_strategies().values():
    registry.register(cls)

strategy = registry.instantiate("my_strategy", {"threshold": 3.0})
```

## Design Notes

**Same DX as SignalRule/DeliveryChannel:** `BacktestStrategy` uses the same ABC+Generic pattern — subclass, set `name`, implement abstract methods, drop in `builtin/`. `__init_subclass__` auto-extracts `params_model` from the Generic type arg.

**Stateful vs stateless:** `SignalRule.evaluate()` is stateless (params passed per call). `BacktestStrategy` stores params on `self` and persists state across time steps — strategies can track previous decisions, cooldowns, or accumulated metrics.

**Concrete name validation:** `__init_subclass__` validates that concrete (non-abstract) subclasses define `name` as a `str` class attribute. Missing or non-string `name` raises `TypeError` at class definition time.

## Commands

```bash
just test -k test_base         # BacktestStrategy ABC tests
just test -k test_registry     # StrategyRegistry tests
just test -k test_discovery    # discover_strategies() tests
```

## See Also

- [Engine](../engine/) — `BacktestSimulator` calls strategy hooks during simulation
- [Rules](../../rules/) — `SignalRule` ABC follows the same Generic pattern
- [Analysis](../../analysis/) — `DeviationReport` passed to strategy hooks
