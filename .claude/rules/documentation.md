# Documentation Rules

## When Code Changes, What Docs Update?

| I just...                       | Update                                                            |
| ------------------------------- | ----------------------------------------------------------------- |
| Changed a public API signature  | Update its docstring (Args/Returns/Raises)                        |
| Added a new submodule           | Create `src/pac/<module>/README.md` from the template below       |
| Added a new signal rule         | Update `src/pac/rules/README.md` Key Components table             |
| Added a new delivery channel    | Update `src/pac/delivery/README.md` Key Components table          |
| Added a new template            | Update `src/pac/templates/README.md` Built-in Templates table     |
| Changed config schema           | Update relevant module README "Configuration" section             |
| Added a new backtester strategy | Update `src/pac/backtester/strategies/README.md`                  |
| Added a new research capability | Update `src/pac/backtester/research/README.md` (create if absent) |
| Added a new feature             | Update `CHANGELOG.md` [Unreleased] section                        |
| Changed contributing workflow   | Update `CONTRIBUTING.md`                                          |
| Made an architecture decision   | Write an ADR in `docs/architecture/`                              |
| Added a BDD feature file        | No doc update needed — feature files are self-documenting         |
| Fixed a bug                     | Update `CHANGELOG.md` [Unreleased] section                        |

## Submodule README Required Sections

Every submodule README must have these sections in order:

```markdown
# <Module Name>

<1-2 sentence purpose statement>

## Architectural Role

Depends on: [`models`](../models/README.md).
Consumed by: [`orchestrator`](../orchestrator/README.md).

## Dependencies

> Exported items listed below are representative — other exports may also be imported.

| Module   | Import Path  | Why Required | Representative Exports        |
| -------- | ------------ | ------------ | ----------------------------- |
| `models` | `pac.models` | ...          | `PortfolioSnapshot`, `Signal` |

## Key Components

| Component   | File      | Purpose              |
| ----------- | --------- | -------------------- |
| `ClassName` | `file.py` | One-line description |

## Configuration

(if applicable)

## Usage

(code example)

## Commands

- `just test -k <module>` — run module tests

## See Also

- [Related Module README](../related/README.md)
```

## Docstring Standards

- **Style:** Google
- **Required on:** public classes, public methods, public functions
- **Skip:** trivial getters, `__init__` with only field assignment, private methods with obvious purpose
- **Include sections only when they add information:** Args, Returns, Raises

```python
def calculate_deviations(
    snapshot: PortfolioSnapshot,
    settings: Settings,
    *,
    warning_pct: Decimal = Decimal("3.0"),
) -> DeviationReport:
    """Calculate portfolio deviations from target allocations.

    Cash is included in total_value (denominator). When cash > 0, actual_pct
    values sum to less than 100%, correctly signalling underinvestment.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets.
        warning_pct: Deviation % to trigger WARNING severity.

    Returns:
        A DeviationReport with per-asset results and the worst severity.
    """
```

## Anti-Patterns

- **Duplicating README content** — submodule READMEs must not repeat root README. Link instead.
- **Docstrings as implementation guides** — docstrings describe the contract (what), not the algorithm (how). Use code comments for "why."
- **Orphan headings** — empty sections signal incompleteness. Remove or fill.
- **Stale TODO stubs** — `TODO: Document...` is worse than no section. Write the content or delete the placeholder.
- **Over-documenting thin wrappers** — route handlers that delegate to orchestrator don't need full Args/Returns/Raises.
