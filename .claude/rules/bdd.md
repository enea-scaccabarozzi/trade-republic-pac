# BDD Rules

## When to Write a Feature File

| Change Type                        | Feature File?                                                                                              |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| New signal rule                    | Yes                                                                                                        |
| New delivery channel               | Yes                                                                                                        |
| New template                       | Yes                                                                                                        |
| Config validation rule             | Yes                                                                                                        |
| New orchestrator pipeline feature  | Yes                                                                                                        |
| Auto-discovery (rules or channels) | Yes                                                                                                        |
| New research framework capability  | Yes                                                                                                        |
| Pydantic model field addition      | No                                                                                                         |
| Analysis pure function             | No                                                                                                         |
| Internal helper refactor           | No                                                                                                         |
| HTTP endpoints                     | No — use integration tests                                                                                 |
| Bug fix to existing behavior       | Only if the bug reveals a missing behavioral spec that has no existing scenario; otherwise use a unit test |

Before writing a feature file, ALL three must be true:

1. Does this change produce an observable outcome a stakeholder could describe in business terms?
2. Can I write Given/When/Then without mentioning class names, method signatures, or dict keys?
3. Would a new contributor understand the expected behavior just from reading the scenarios?

If all three → feature file. Otherwise → unit test.

## File Placement

- Feature file: `src/pac/<module>/features/<name>.feature`
- Step definitions: `src/pac/<module>/tests/test_<name>_bdd.py`

## Anatomy Rules

### Given / When / Then

- **Given** = precondition (state setup), never an action
- **When** = the single action under test
- **Then** = observable outcome to verify
- Use `Scenario Outline` + `Examples:` when behavior is identical but values vary

### Anti-Patterns

| Bad (implementation detail)                        | Good (behavior)                                         |
| -------------------------------------------------- | ------------------------------------------------------- |
| Given the ThresholdDeviationRule is instantiated   | Given a portfolio with deviations above threshold       |
| When rule.evaluate(report, params) is called       | When the threshold rule evaluates with default params   |
| Then the `_rules` dict has 3 entries               | Then the discovered rules include "threshold_deviation" |
| Then the result list length is 1                   | Then a WARNING signal is emitted for stocks             |
| Given a DeviationReport with max_severity=CRITICAL | Given stocks are at 76% (6pp above target)              |

### Background Section

Use `Background:` only for preconditions that apply to ALL scenarios in the file.

## Step Definition Patterns

Auto-bind all scenarios in a feature file:

```python
from pytest_bdd import scenarios
scenarios("../features/<name>.feature")
```

Pass state via a `ctx` dict fixture:

```python
@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}
```

Use `parsers.parse()` for typed parameters:

```python
from pytest_bdd import given, when, then, parsers

@given(parsers.parse('the environment variable "{var}" is set to "{value}"'))
def given_env_var(monkeypatch: pytest.MonkeyPatch, var: str, value: str) -> None:
    monkeypatch.setenv(var, value)

@when("the threshold rule evaluates with default params")
def when_evaluate(ctx: dict[str, Any]) -> None:
    ctx["signals"] = ctx["rule"].evaluate(ctx["report"], ctx["snapshot"])

@then("a WARNING signal is emitted for stocks")
def then_warning_signal(ctx: dict[str, Any]) -> None:
    assert any(
        s.severity == SignalSeverity.WARNING and "stocks" in s.message
        for s in ctx["signals"]
    )
```

One step function per unique Given/When/Then text. Steps are reused across scenarios in the same file.

## Workflow

1. Identify the capability — describe the behavior in one sentence
2. Create: `src/pac/<module>/features/<name>.feature`
3. Write scenarios — declarative, no implementation details
4. Confirm non-developers can understand the expected behavior
5. Create: `src/pac/<module>/tests/test_<name>_bdd.py`
6. Implement steps with `ctx` dict, `parsers.parse()`, real fixtures
7. Run: `just test -k test_<name>_bdd`

## Pre-Commit Checklist

- [ ] Each scenario tests ONE behavior?
- [ ] Background only has truly shared preconditions?
- [ ] Step text is generic enough to reuse across scenarios in the same file?
- [ ] All three pre-writing criteria above were confirmed before writing the file?
