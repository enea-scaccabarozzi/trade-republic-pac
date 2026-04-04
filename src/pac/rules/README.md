# Rules

Signal rule engine — evaluates portfolio state against configurable rules and produces typed signals. Rules are stateless; typed params are validated and passed to `evaluate()` at call time.

## Architectural Role

| Aspect      | Details                                                                                                                  |
| ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| Depends on  | [`models`](../models/) (`Signal`, `PortfolioSnapshot`, `SignalSeverity`), [`analysis`](../analysis/) (`DeviationReport`) |
| Consumed by | [`orchestrator`](../orchestrator/) (`SignalRegistry` evaluates signals, `build_template_data` produces template context) |
| Boundary    | Rule evaluation, param validation, signal generation                                                                     |

## Key Components

| Component                | File                   | Description                                                                |
| ------------------------ | ---------------------- | -------------------------------------------------------------------------- |
| `SignalRule[ParamsT]`    | `base.py`              | ABC + Generic base class; `__init_subclass__` auto-extracts `params_model` |
| `SignalRegistry`         | `registry.py`          | Collects rule classes, validates params, dispatches evaluation             |
| `discover_rules()`       | `discovery.py`         | Scans `builtin/` for concrete `SignalRule` subclasses                      |
| `ThresholdDeviationRule` | `builtin/threshold.py` | Fires on per-asset deviation thresholds                                    |
| `CycleInversionRule`     | `builtin/cycle.py`     | Detects diverging asset pairs                                              |
| `PacPlanRule`            | `builtin/pac_plan.py`  | Computes monthly PAC allocation plan                                       |

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

## Commands

```bash
just test -k test_signals              # rule evaluation unit tests
just test -k test_discovery            # rule discovery unit tests
just test -k test_rule_discovery_bdd   # discovery BDD scenarios
just test -k test_threshold_rule_bdd   # threshold rule BDD scenarios
just test -k test_cycle_rule_bdd       # cycle rule BDD scenarios
```

## See Also

- [Analysis](../analysis/) — `DeviationReport` passed to `evaluate()`
- [Models](../models/) — `Signal`, `PortfolioSnapshot` used as inputs/outputs
- [Orchestrator](../orchestrator/) — wires registry and calls `evaluate_signal()`
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — rule design rationale
