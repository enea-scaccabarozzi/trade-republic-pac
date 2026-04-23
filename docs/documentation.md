# Documentation Standards

This guide defines where documentation lives, what format it follows, and how to keep it in sync with code changes.

## Framework: Diátaxis in This Repo

| Mode | Where in Repo | Examples |
| ----------- | ------------------------------------------------------------ | ------------------------------------------------ |
| Tutorial | `CONTRIBUTING.md` "Getting Started" + "Extending the System" | Setup walkthrough, adding a first rule |
| How-to | `docs/*.md` guides, `CONTRIBUTING.md` sections | "Adding a Signal Rule", "Writing a BDD Feature" |
| Reference | Submodule READMEs, docstrings, `pac.yaml.example` | API tables, config schema, component tables |
| Explanation | ADRs in `docs/architecture/`, `AGENTS.md` "Key Decisions" | Why ABC+Generic over Protocol, serverless design |

## Documentation Hierarchy

```text
Code comments → Docstrings → Submodule READMEs → docs/ guides → Root README
```

**Authority flows downward:** code is truth, docstrings describe the contract, READMEs give context, guides teach practices, README markets the project.

**Rule:** facts live in ONE place, everything else links. Don't duplicate the root README content in submodule READMEs.

## Submodule README Template

Every submodule README follows this structure:

```markdown
# <Module Name>
<1-2 sentence purpose statement>

## Architectural Role
Depends on: [`models`](../models/README.md), [`config`](../config/README.md).
Consumed by: [`orchestrator`](../orchestrator/README.md).

## Key Components

| Component       | File      | Purpose              |
| --------------- | --------- | -------------------- |
| `ClassName`     | `file.py` | One-line description |
| `function_name` | `file.py` | One-line description |

## Configuration
(if applicable — config keys from pac.yaml, env vars)

## Usage
(code example or command showing how to use the module)

## Key Commands
- `just test -k <module>` — run module tests
- `just test -k test_<name>_bdd` — run BDD scenarios

## See Also
- [Related Module README](../related/README.md)
- [Relevant ADR](../../docs/architecture/ADR-NNN.md)
- [Relevant Guide](../../docs/guide.md)
```

## Docstring Standards

- **Style:** Google
- **Required on:** public classes, public methods, public functions
- **Skip:** trivial getters, `__init__` with only field assignment, private methods with obvious purpose, models that already have adequate one-liner docstrings
- **Sections:** brief description, Args, Returns, Raises (only include sections that add information)

Example from this codebase:

```python
def calculate_deviations(
    snapshot: PortfolioSnapshot,
    settings: Settings,
    *,
    warning_pct: Decimal = Decimal("3.0"),
    critical_pct: Decimal = Decimal("5.0"),
) -> DeviationReport:
    """Calculate portfolio deviations from target allocations.

    Cash is intentionally included in ``total_value`` (the denominator).
    When cash > 0, ``actual_pct`` values sum to less than 100%, correctly
    signalling underinvestment.

    Args:
        snapshot: Current portfolio state.
        settings: Application settings with targets.
        warning_pct: Deviation % to trigger WARNING severity.
        critical_pct: Deviation % to trigger CRITICAL severity.

    Returns:
        A DeviationReport with per-asset results and the worst severity.
    """
```

## When Code Changes, What Docs Update?

| I just... | Update |
| ------------------------------ | ------------------------------------------------------------- |
| Changed a public API signature | Update its docstring (Args/Returns/Raises) |
| Added a new submodule | Create `src/pac/<module>/README.md` from the template above |
| Added a new signal rule | Update `src/pac/rules/README.md` Key Components table |
| Added a new delivery channel | Update `src/pac/delivery/README.md` Key Components table |
| Added a new template | Update `src/pac/templates/README.md` Built-in Templates table |
| Changed config schema | Update relevant module README "Configuration" section |
| Added a new feature | Update `CHANGELOG.md` [Unreleased] section |
| Changed contributing workflow | Update `CONTRIBUTING.md` |
| Made an architecture decision | Write an ADR in `docs/architecture/` |
| Added a BDD feature file | No doc update needed (feature files are self-documenting) |
| Fixed a bug | Update `CHANGELOG.md` [Unreleased] section |

## File Ownership Map

| File | Owns Documentation For | NOT In |
| ------------------------------ | ------------------------------------------------- | ---------------------------- |
| `README.md` | Project overview, quick start, deployment | Implementation details |
| `CONTRIBUTING.md` | Dev setup, workflow, commit conventions | Architecture decisions |
| `AGENTS.md` | AI agent context, key decisions, learned patterns | User-facing docs |
| `CHANGELOG.md` | Release history, unreleased changes | — |
| `SECURITY.md` | Vulnerability reporting | — |
| `CODE_OF_CONDUCT.md` | Community standards | — |
| `docs/bdd.md` | BDD conventions, feature file guide | Testing philosophy |
| `docs/testing.md` | Testing approach, DI patterns, mocking | BDD-specific conventions |
| `docs/documentation.md` | Doc standards, README template, docstring style | Code conventions |
| `docs/architecture/ADR-*.md` | Architecture decisions with rationale | How-to instructions |
| `pac.yaml.example` | Config schema reference (by example) | Explanatory prose |
| `src/pac/<module>/README.md` | Module purpose, components, usage, commands | Root-level project info |
| `src/pac/backtester/<submodule>/README.md` | Backtester submodule purpose, components, dependency table | Root-level project info |
| Docstrings (in `.py` files) | API contract: args, returns, raises, brief why | Implementation walk-throughs |
| Code comments (in `.py` files) | "Why" for non-obvious implementation choices | API documentation |

## Anti-Patterns

- **Duplicating README content** — submodule READMEs should not repeat the root README. Link instead.
- **Docstrings as implementation guides** — docstrings describe the contract (what), not the algorithm (how). Use code comments for "why."
- **Orphan headings** — empty sections with no content signal incompleteness. Remove or fill.
- **Stale TODO stubs** — `TODO: Document...` is worse than no section at all. Either write the content or delete the placeholder.
- **Over-documenting thin wrappers** — Starlette route handlers that just delegate to the orchestrator don't need Args/Returns/Raises sections. A one-liner plus an auth note is sufficient.
