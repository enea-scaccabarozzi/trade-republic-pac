# Agentic Readiness — Design Spec
Date: 2026-04-21

## Goal

Make the repository fully ready for agentic development by establishing consistent, machine-readable conventions for rules, documentation, dependency declarations, and test coverage.

---

## Execution Strategy

Two sequential phases. Phase 2 depends on Phase 1 completing and being reviewed.

---

## Phase 1: Rules, Docs, and AGENTS.md

### 1. AGENTS.md Restructure (hub document)

AGENTS.md becomes the central index — short enough to read in full, explicit pointers to every rule and guideline.

**Structure:**

| Section | Change |
|---|---|
| Project Overview | Keep; expand 2 lines to mention backtesting |
| Tech Stack | Keep as-is |
| Repository Structure | Update backtester submodule list |
| **Rules & Guidelines** (new) | Table: rule file → one-line purpose; replaces inline Key Conventions prose |
| **Module Dependency Map** (new) | Formalizes per-module depends-on / consumed-by |
| Important Patterns | Keep; trim entries now covered by rule files |
| Learned Patterns | Keep; prune entries now covered by rules |
| Do NOT Modify | Keep as-is |

**Rules & Guidelines table:**

```
| Rule File | Governs |
|---|---|
| .claude/rules/bdd.md | When/how to write feature files and step definitions |
| .claude/rules/testing.md | Testing philosophy, DI patterns, mocking boundaries |
| .claude/rules/documentation.md | Doc standards, README template, docstring style |
| .claude/rules/dependency-injection.md | Module dependency declarations, DI conventions |
```

---

### 2. `.claude/rules/` files (agent-optimized)

Four files in `.claude/rules/` at the project root. Imperative, checklist-driven, no tutorial prose.

**`bdd.md`** — distilled from `docs/bdd.md`:
- Decision matrix: which change types require a feature file
- 3-question checklist before writing a feature file
- File placement convention
- Given/When/Then constraints and anti-patterns table
- Step definition patterns: `ctx` dict, `parsers.parse()`, `scenarios()` binding
- 7-step workflow checklist

**`testing.md`** — distilled from `docs/testing.md`:
- 3 core principles (black-box, DI-first, no mocking internals)
- Decision matrix: what to test and how
- Mocking boundary table
- `make_settings()` factory pattern
- Backtester-specific testing patterns (BacktestStrategy, Monte Carlo fixtures)

**`documentation.md`** — distilled from `docs/documentation.md`:
- When-code-changes-what-docs-update table
- Submodule README required sections
- Docstring standards (Google style, required/skip rules)
- Anti-patterns list

**`dependency-injection.md`** — new:
- Every module README must have a `## Dependencies` table (format below)
- Dependency direction rule: no circular deps, no upward imports
- DI pattern: external collaborators injected, never imported inside functions
- Agent instruction: read module's `## Dependencies` table before modifying it

---

### 3. `docs/` updates (human-readable guides)

**`docs/bdd.md`:**
- Remove the feature file inventory table (self-documenting; maintaining counts causes drift)
- Add a backtester BDD example (one concrete scenario from simulation or strategies)

**`docs/testing.md`:**
- Add "Backtester Testing Patterns" subsection: faking `MarketDataProvider`, testing `BacktestStrategy.reset()`, Monte Carlo fixture pattern

**`docs/documentation.md`:**
- Add one row to the File Ownership Map for `src/pac/backtester/<submodule>/README.md`

---

### 4. Module README Dependency Tables

All 9 top-level modules and all backtester submodules get a standardized `## Dependencies` section.

**Format:**

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Core domain types shared across the system | `PortfolioSnapshot`, `Signal`, `Position` |
| `config` | `pac.config` | Validated application settings | `Settings`, `AssetConfig` |
```

- `models` module: explicitly empty table with a note ("no internal pac imports — dependency-free foundation")
- Each backtester submodule (`engine`, `strategies`, `metrics`, `results`, `data`, `research`, `api`) gets its own table

**Why the table format survives drift:** the "Why Required" column captures intent; even if specific exports change, the reason for the dependency stays stable. The representative exports note prevents the table from being treated as exhaustive.

---

## Phase 2: BDD Additions and Module Docstrings

*Depends on Phase 1 completing.*

### BDD additions

New feature files for backtester submodules currently without coverage:

| Submodule | Proposed Feature File | Key Scenarios |
|---|---|---|
| `research/` | `research_context.feature` | `ResearchContext.from_config()` zero-ceremony API, indicator pack loading, event calendar access |
| `research/` | `indicator_registry.feature` | Empty registry, pack registration, unknown pack error |
| `backtester/api/` | `research_api.feature` | Experiment list, paper list, run management endpoints |

`tr/` module: no BDD added — thin boundary adapter; existing unit tests are sufficient.
`analysis/` and `models/`: no BDD added — pure functions and Pydantic models per decision matrix.

### Module docstrings sweep

Sweep all `__init__.py`, public classes, and public functions in modules currently lacking Google-style docstrings. Follow standards in `.claude/rules/documentation.md`.

---

## Constraints

- No content duplication between `.claude/rules/` and `docs/` — rules files reference docs for deeper context
- Feature file inventory tables removed from all docs (self-documenting, drift-prone)
- `pac.yaml.example` default values not modified
- Trade execution guarantee never modified
