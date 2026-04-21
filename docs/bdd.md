# BDD Guidelines

This guide covers when and how to write Gherkin feature files and pytest_bdd step definitions in the PAC project.

## When to Write Feature Files

Use this decision matrix to decide whether a change needs a `.feature` file:

| Change Type                        | Feature File? | Why                                                              |
| ---------------------------------- | ------------- | ---------------------------------------------------------------- |
| New signal rule                    | ✅ Yes         | Rules have observable evaluate → signal behavior                 |
| New delivery channel               | ✅ Yes         | Channels have observable send/lifecycle contracts                |
| New template                       | ✅ Yes         | Template rendering is a behavioral contract                      |
| Config validation rule             | ✅ Yes         | "Valid config → loads; invalid config → error" is business logic |
| New orchestrator pipeline feature  | ✅ Yes         | End-to-end signal dispatch is the core behavioral contract       |
| Auto-discovery (rules or channels) | ✅ Yes         | "Scan package → find implementations" is observable              |
| Pydantic model field addition      | ❌ No          | Structural change — unit test the serialization if non-trivial   |
| Analysis pure function             | ❌ No          | Pure math — unit tests with edge cases are more appropriate      |
| Internal helper refactor           | ❌ No          | No observable behavior change                                    |
| Bug fix to existing behavior       | ⚠️ Maybe       | Add a scenario if the bug represents a missing behavioral spec   |

**Checklist before writing a feature file:**
1. Does this change produce an observable outcome a stakeholder could describe in business terms?
2. Can I write Given/When/Then without mentioning class names, method signatures, or dict keys?
3. Would a new contributor understand the expected behavior just from reading the scenarios?

If all three → write a feature file. If not → unit test is sufficient.

## Where Feature Files Live

| Path Pattern                                | Purpose                       |
| ------------------------------------------- | ----------------------------- |
| `src/pac/<module>/features/<name>.feature`  | Feature specification         |
| `src/pac/<module>/tests/test_<name>_bdd.py` | Step definitions (pytest_bdd) |


## Anatomy of a Good Feature File

### Feature Title
Use a noun phrase describing the capability, not the implementation:
- ✅ `Feature: Threshold Deviation Rule`
- ✅ `Feature: Channel Auto-Discovery`
- ❌ `Feature: ThresholdDeviationRule.evaluate() method`

### Background Section
Use `Background:` for shared preconditions that apply to ALL scenarios in the file.
Do NOT use Background if some scenarios need different setup.

Example from `threshold_rule.feature`:
```gherkin
Background:
  Given a portfolio with target allocation 70/15/15 for stocks/gold/bonds
```

### Scenario vs Scenario Outline
- **Scenario**: one specific case with specific values
- **Scenario Outline**: same behavior tested with multiple input/output combinations

Use Scenario Outline when the behavior is identical but values differ. Example from `threshold_rule.feature`:
```gherkin
Scenario Outline: Severity classification
  Given an asset deviating by <deviation>pp
  When the threshold rule evaluates with warning_pct=3.0 and critical_pct=5.0
  Then <outcome>

  Examples:
    | deviation | outcome                      |
    | 2.0       | no signal is emitted         |
    | 3.0       | a WARNING signal is emitted  |
    | 5.0       | a CRITICAL signal is emitted |
```

### Given/When/Then Rules
- **Given** = precondition (state setup), never an action
- **When** = the single action under test
- **Then** = observable outcome to verify

### Anti-Patterns

| ❌ Bad (implementation detail)                             | ✅ Good (behavior)                                       |
| --------------------------------------------------------- | ------------------------------------------------------- |
| Given the ThresholdDeviationRule is instantiated          | Given a portfolio with deviations above threshold       |
| When rule.evaluate(report, params) is called              | When the threshold rule evaluates with default params   |
| Then the `_rules` dict has 3 entries                      | Then the discovered rules include "threshold_deviation" |
| Then the result list length is 1                          | Then a WARNING signal is emitted for stocks             |
| Given a `DeviationReport` with `max_severity=CRITICAL`    | Given stocks are at 76% (6pp above target)              |
| Then `channel.send()` was called with a `RenderedMessage` | Then the message is delivered to the configured chat    |

## Writing Step Definitions with pytest_bdd

### Binding
Auto-bind all scenarios in a feature file with a single call:
```python
from pytest_bdd import scenarios
scenarios("../features/<name>.feature")
```

### Shared Context Pattern
Steps pass state via a `ctx` dict fixture:
```python
from typing import Any
import pytest

@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared context for step definitions."""
    return {}
```

### Parsers for Typed Parameters
Use `parsers.parse()` for extracting typed values from step text:
```python
from pytest_bdd import given, parsers

@given(parsers.parse('the environment variable "{var}" is set to "{value}"'))
def given_env_var_set(monkeypatch: pytest.MonkeyPatch, var: str, value: str) -> None:
    monkeypatch.setenv(var, value)
```

### Step Function Mapping
One step function per unique Given/When/Then text. Steps are reused across scenarios in the same file.

### Real Example (from `test_rule_discovery_bdd.py`)
```python
from pytest_bdd import scenarios, when, then, parsers
from pac.rules.discovery import discover_rules

scenarios("../features/rule_discovery.feature")

@pytest.fixture
def context() -> dict[str, Any]:
    return {}

@when("the builtin rules package is scanned")
def scan_builtin(context: dict[str, Any]) -> None:
    context["rules"] = discover_rules()

@then(parsers.parse('the discovered rules include "{name}"'))
def rules_include(context: dict[str, Any], name: str) -> None:
    assert name in context["rules"]
```

### Backtester Example (from `test_indicator_registry_bdd.py`)

Feature files work the same way for stateful, multi-step backtester components. The key is still describing observable behavior without exposing implementation internals:

```gherkin
Feature: Indicator Registry

  Scenario: Registry starts with no indicators registered
    Given a new indicator registry with price data
    Then no indicators are registered

  Scenario: Registering the crisis pack makes crisis indicators available
    Given a new indicator registry with price data
    When the "crisis" indicator pack is registered
    Then the registry contains the "equity_drawdown" indicator

  Scenario: Registering an unknown pack raises a clear error
    Given a new indicator registry with price data
    When the "nonexistent" indicator pack is registered
    Then a ValueError is raised mentioning the unknown pack name
```

Step definitions follow the same `ctx` dict + real fixtures pattern — the difference is the fixtures provide pre-built `PriceSeries` objects instead of portfolio snapshots.

## Full Workflow: Adding a New BDD Feature

1. **Identify the capability** — describe the behavior in one sentence
2. **Create the feature file** — `src/pac/<module>/features/<name>.feature`
3. **Write scenarios** — declarative, no implementation details, business-readable
4. **Review scenarios** — can a non-developer understand what the system should do?
5. **Create step def file** — `src/pac/<module>/tests/test_<name>_bdd.py`
6. **Implement steps** — use `ctx` dict, `parsers.parse()`, real fixtures
7. **Run and verify** — `just test -k test_<name>_bdd`

**Review checklist:**
- [ ] Scenarios are business-readable (no class names, no method signatures)?
- [ ] No implementation details leaked into feature file?
- [ ] Each scenario tests ONE behavior?
- [ ] Background section only has truly shared preconditions?
- [ ] Step text is reusable across scenarios (avoid over-specific phrasing)?
