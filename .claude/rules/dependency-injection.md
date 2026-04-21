# Dependency Injection Rules

## Before Modifying a Module

1. Read the module's `## Dependencies` table in its `README.md`
2. Read the READMEs of each listed dependency to understand the types and contracts
3. Do not import from a module not listed as a dependency — add it to the table first

## Module Dependency Declaration

Every module README must have a `## Dependencies` section.

### Format

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module   | Import Path  | Why Required                                           | Representative Exports                    |
| -------- | ------------ | ------------------------------------------------------ | ----------------------------------------- |
| `models` | `pac.models` | Core domain types shared across the system             | `PortfolioSnapshot`, `Signal`, `Position` |
| `config` | `pac.config` | Validated application settings and asset configuration | `Settings`, `AssetConfig`                 |
```

For modules with **no internal pac dependencies** (e.g., `models`, `config`):

```markdown
## Dependencies

This module has no internal `pac` imports — it is the foundation layer.
```

### Why Required Column

Write a sentence explaining the role this dependency plays — not just what it exports.

- Good: "Core domain types shared across the system"
- Bad: "Provides PortfolioSnapshot"

The "Why Required" is the stable part. Specific exports can change; the reason a dependency exists rarely does.

## Dependency Direction

```
models       ← no pac imports (foundation)
config       ← no pac imports (foundation)
tr           ← models
analysis     ← models, config
rules        ← models, analysis, market_context (root)
delivery     ← models
templates    ← delivery (RenderedMessage), models
orchestrator ← analysis, config, delivery, models, rules, templates, tr
backtester   ← analysis, config, models, rules (+ external: yfinance, quantstats)
```

Rules:

- Never import upward (e.g., `models` must never import from `rules`)
- Never create circular imports between submodules
- `backtester` is isolated — zero imports from `app.py` or the HTTP layer

## DI Pattern

External collaborators must be injected, never created inside functions:

```python
# Good — caller controls the dependency
def dispatch_signal(orchestrator: Orchestrator, signal_name: str) -> list[Signal]:
    return orchestrator.evaluate_signal(signal_name)

# Bad — hidden dependency, untestable
def dispatch_signal(signal_name: str) -> list[Signal]:
    orchestrator = Orchestrator.from_settings(load_config("pac.yaml"))  # ← hidden
    return orchestrator.evaluate_signal(signal_name)
```

In tests: inject real Pydantic model fixtures, fake only external boundaries (network, filesystem, Telegram API).
