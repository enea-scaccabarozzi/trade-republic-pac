# Agentic Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish consistent rules, documentation, dependency declarations, and test coverage so AI agents can work in this codebase reliably without repeated context-gathering.

**Architecture:** Phase 1 rewrites AGENTS.md as a hub document, creates four `.claude/rules/` files (agent-optimized), updates the three `docs/` guides, and standardises dependency tables in every module README. Phase 2 adds BDD feature files for the backtester research submodule and sweeps missing docstrings.

**Tech Stack:** Markdown (rules + docs), pytest-bdd (Phase 2 BDD), Python 3.11+ (docstrings)

---

## PHASE 1 — Rules, Docs, and AGENTS.md

---

### Task 1: Create `.claude/rules/bdd.md`

**Files:**
- Create: `.claude/rules/bdd.md`

- [ ] **Step 1: Create `.claude/rules/` directory and write the file**

```markdown
# BDD Rules

## When to Write a Feature File

| Change Type | Feature File? |
|---|---|
| New signal rule | Yes |
| New delivery channel | Yes |
| New template | Yes |
| Config validation rule | Yes |
| New orchestrator pipeline feature | Yes |
| Auto-discovery (rules or channels) | Yes |
| New research framework capability | Yes |
| Pydantic model field addition | No |
| Analysis pure function | No |
| Internal helper refactor | No |
| HTTP endpoints | No — use integration tests |
| Bug fix to existing behavior | Maybe — add scenario if the bug represents a missing behavioral spec |

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

| Bad (implementation detail) | Good (behavior) |
|---|---|
| Given the ThresholdDeviationRule is instantiated | Given a portfolio with deviations above threshold |
| When rule.evaluate(report, params) is called | When the threshold rule evaluates with default params |
| Then the `_rules` dict has 3 entries | Then the discovered rules include "threshold_deviation" |
| Then the result list length is 1 | Then a WARNING signal is emitted for stocks |
| Given a DeviationReport with max_severity=CRITICAL | Given stocks are at 76% (6pp above target) |

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
from pytest_bdd import given, parsers

@given(parsers.parse('the environment variable "{var}" is set to "{value}"'))
def given_env_var(monkeypatch: pytest.MonkeyPatch, var: str, value: str) -> None:
    monkeypatch.setenv(var, value)
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

- [ ] Scenarios are business-readable (no class names, no method signatures)?
- [ ] No implementation details in the feature file?
- [ ] Each scenario tests ONE behavior?
- [ ] Background only has truly shared preconditions?
- [ ] Step text is reusable across scenarios?
```

- [ ] **Step 2: Verify the file is valid markdown with no placeholders**

```bash
just lint
```

Expected: no errors (lint ignores `.claude/` but confirms the command runs).

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/bdd.md
git commit -m "chore: add .claude/rules/bdd.md agent rule"
```

---

### Task 2: Create `.claude/rules/testing.md`

**Files:**
- Create: `.claude/rules/testing.md`

- [ ] **Step 1: Write the file**

```markdown
# Testing Rules

## Core Principles

1. **Black-box testing** — test observable behavior, never internals. Verify what a function returns or what side effects it produces, not how it achieves them.
2. **DI-first** — all external dependencies are injected and faked at the boundary. The module under test uses real code; only its collaborators are faked.
3. **No mocking internals** — never patch private methods or internal state of the unit under test.

## Decision Matrix

| Change Type | Approach |
|---|---|
| New signal rule | BDD feature + unit edge cases |
| New delivery channel | BDD feature + lifecycle tests |
| Config validation | BDD feature (comprehensive) |
| Analysis pure function | Unit tests (edge cases, boundaries) |
| Template rendering | BDD feature |
| Auto-discovery | BDD feature |
| HTTP endpoints | Integration tests in `tests/test_app.py` |
| Orchestrator pipeline | BDD feature + unit tests |
| BacktestStrategy | Unit tests + BDD for observable strategy behavior |
| Research framework capability | BDD feature |
| Pure indicator math | Unit tests (numeric precision) |

Add unit tests beyond BDD when: edge cases, boundary values, error handling, parameterised math with many numeric combinations.

## `make_settings()` Factory

All settings fixtures use `make_settings()` from `tests/conftest.py`. It builds a valid `Settings` with test defaults and accepts keyword overrides:

```python
from tests.conftest import make_settings

settings = make_settings()  # all defaults
settings = make_settings(signals=[])  # override one field
```

Never construct `Settings` directly in tests — use `make_settings()`.

## Mocking Boundaries

| Boundary | Mock? | How |
|---|---|---|
| TR WebSocket API | Yes | Patch `tr_session` in orchestrator tests |
| Telegram Bot API | Yes | Patch PTB `Application.bot.send_message` |
| Filesystem (config YAML) | Yes | Write temp YAML via `tmp_path` fixture |
| Environment variables | Yes | `monkeypatch.setenv()` / `monkeypatch.delenv()` |
| yfinance (backtester) | Yes | Patch `MarketDataProvider` with pre-loaded `PriceSeries` fixtures |
| Module under test | No | Use real implementation |
| Pydantic validation | No | Use real model — faking validators hides bugs |
| Internal helpers | No | Part of the module under test |
| Other submodules (rules) | No | Pass real `DeviationReport` fixtures |

## Backtester Testing Patterns

### Faking MarketDataProvider

Inject a pre-built `dict[str, PriceSeries]` directly — do not hit yfinance in tests:

```python
from pac.backtester.data.models import PriceBar, PriceSeries
from decimal import Decimal
from datetime import date

@pytest.fixture
def price_data() -> dict[str, PriceSeries]:
    bars = [
        PriceBar(date=date(2023, 1, d), open=Decimal("100"), high=Decimal("105"),
                 low=Decimal("98"), close=Decimal("102"), volume=1000)
        for d in range(2, 32)
    ]
    series = PriceSeries(ticker="EUNL.DE", bars=bars)
    return {"stocks": series}
```

### Testing BacktestStrategy

Always call `strategy.reset()` between Monte Carlo iterations to clear per-iteration state (e.g., cooldown dates):

```python
def test_strategy_resets_between_iterations(strategy):
    strategy.on_signals(signals, snapshot, report, date(2023, 1, 10))
    strategy.reset()  # must clear cooldown
    result = strategy.on_signals(signals, snapshot, report, date(2023, 1, 11))
    assert result  # should fire again after reset
```

### Monte Carlo Fixture Pattern

Use `N=1, seed=42` for deterministic fast tests:

```python
@pytest.fixture
def backtest_config(tmp_path) -> BacktestConfig:
    return BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        monte_carlo_iterations=1,
    )
```

## Commands

```bash
just test                               # all tests
just test -k test_deviation             # single test by name
just test -k "test_config and not bdd"  # unit tests only for config
just test -k test_threshold_rule_bdd    # single BDD feature
just validate                           # lint + typecheck + test
```
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/testing.md
git commit -m "chore: add .claude/rules/testing.md agent rule"
```

---

### Task 3: Create `.claude/rules/documentation.md`

**Files:**
- Create: `.claude/rules/documentation.md`

- [ ] **Step 1: Write the file**

```markdown
# Documentation Rules

## When Code Changes, What Docs Update?

| I just... | Update |
|---|---|
| Changed a public API signature | Update its docstring (Args/Returns/Raises) |
| Added a new submodule | Create `src/pac/<module>/README.md` from the template below |
| Added a new signal rule | Update `src/pac/rules/README.md` Key Components table |
| Added a new delivery channel | Update `src/pac/delivery/README.md` Key Components table |
| Added a new template | Update `src/pac/templates/README.md` Built-in Templates table |
| Changed config schema | Update relevant module README "Configuration" section |
| Added a new backtester strategy | Update `src/pac/backtester/strategies/README.md` |
| Added a new research capability | Update `src/pac/backtester/research/` README (create if absent) |
| Added a new feature | Update `CHANGELOG.md` [Unreleased] section |
| Changed contributing workflow | Update `CONTRIBUTING.md` |
| Made an architecture decision | Write an ADR in `docs/architecture/` |
| Added a BDD feature file | No doc update needed — feature files are self-documenting |
| Fixed a bug | Update `CHANGELOG.md` [Unreleased] section |

## Submodule README Template

Every submodule README must include these sections in order:

```markdown
# <Module Name>
<1-2 sentence purpose statement>

## Architectural Role

Depends on: [`models`](../models/README.md), [`config`](../config/README.md).
Consumed by: [`orchestrator`](../orchestrator/README.md).

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | ... | `PortfolioSnapshot`, `Signal` |

## Key Components

| Component | File | Purpose |
|---|---|---|
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
- **Sections to include:** brief description, Args, Returns, Raises — only when they add information

Example:
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
- **Over-documenting thin wrappers** — Starlette route handlers that delegate to orchestrator don't need full Args/Returns/Raises.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/documentation.md
git commit -m "chore: add .claude/rules/documentation.md agent rule"
```

---

### Task 4: Create `.claude/rules/dependency-injection.md`

**Files:**
- Create: `.claude/rules/dependency-injection.md`

- [ ] **Step 1: Write the file**

```markdown
# Dependency Injection Rules

## Before Modifying a Module

1. Read the module's `## Dependencies` table in its `README.md`
2. Read the READMEs of each listed dependency to understand the types and contracts
3. Do not import from a module that is not listed as a dependency — add it to the table first

## Module Dependency Declaration

Every module README must have a `## Dependencies` section.

### Format

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Core domain types shared across the system | `PortfolioSnapshot`, `Signal`, `Position` |
| `config` | `pac.config` | Validated application settings and asset configuration | `Settings`, `AssetConfig` |
```

For modules with **no internal pac dependencies** (e.g., `models`, `config`):

```markdown
## Dependencies

This module has no internal `pac` imports — it is the foundation layer.
```

### Why Required Column

Write a sentence explaining the role this dependency plays — not just what it exports.
Good: "Core domain types shared across the system"
Bad: "Provides PortfolioSnapshot"

The "Why Required" is the stable part. Specific exports can change; the reason a dependency exists rarely does.

## Dependency Direction Rules

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

- Never import upward (e.g., `models` must never import from `rules`)
- Never create circular imports between submodules
- The `backtester` module is isolated — zero imports from `app.py` or the HTTP layer

## DI Pattern

External collaborators must be injected, never created inside functions:

```python
# Good — caller controls the dependency
def dispatch_signal(
    orchestrator: Orchestrator,
    signal_name: str,
) -> list[Signal]:
    return orchestrator.evaluate_signal(signal_name)

# Bad — hidden dependency, untestable
def dispatch_signal(signal_name: str) -> list[Signal]:
    orchestrator = Orchestrator.from_settings(load_config("pac.yaml"))  # ← hidden
    return orchestrator.evaluate_signal(signal_name)
```

In tests: inject real Pydantic model fixtures, fake only external boundaries (network, filesystem, Telegram API).
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/dependency-injection.md
git commit -m "chore: add .claude/rules/dependency-injection.md agent rule"
```

---

### Task 5: Update `docs/bdd.md`

**Files:**
- Modify: `docs/bdd.md`

- [ ] **Step 1: Remove the feature file inventory table**

In `docs/bdd.md`, delete the entire "**Existing feature files (10 total, 69 scenarios):**" table block (currently lines 36-49). Feature files are self-documenting — counts in docs cause drift.

- [ ] **Step 2: Add a backtester BDD example section**

After the "Real Example (from `test_rule_discovery_bdd.py`)" block, add:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add docs/bdd.md
git commit -m "docs: update bdd.md — remove inventory table, add backtester example"
```

---

### Task 6: Update `docs/testing.md`

**Files:**
- Modify: `docs/testing.md`

- [ ] **Step 1: Add "Backtester Testing Patterns" subsection**

In `docs/testing.md`, after the "Faking the TR WebSocket Client" section, add:

```markdown
### Faking MarketDataProvider (Backtester Tests)

Backtester tests inject pre-built `PriceSeries` objects directly — no yfinance calls:

```python
from pac.backtester.data.models import PriceBar, PriceSeries
from decimal import Decimal
from datetime import date

@pytest.fixture
def price_data() -> dict[str, PriceSeries]:
    bars = [
        PriceBar(
            date=date(2023, 1, d), open=Decimal("100"), high=Decimal("105"),
            low=Decimal("98"), close=Decimal("102"), volume=1000,
        )
        for d in range(2, 32)
    ]
    return {"stocks": PriceSeries(ticker="EUNL.DE", bars=bars)}
```

### Testing BacktestStrategy

`BacktestStrategy.reset()` clears per-iteration state (e.g., cooldown dates). Tests must verify that `reset()` actually resets the strategy:

```python
def test_cooldown_clears_after_reset(strategy, signals, snapshot, report):
    # first call sets cooldown
    strategy.on_signals(signals, snapshot, report, date(2023, 1, 10))
    strategy.reset()
    # should fire again after reset, not be suppressed by cooldown
    result = strategy.on_signals(signals, snapshot, report, date(2023, 1, 11))
    assert len(result) > 0
```

### Monte Carlo: Fast Deterministic Fixture

Use `monte_carlo_iterations=1` for tests that need a full simulation run but should be fast:

```python
@pytest.fixture
def backtest_config() -> BacktestConfig:
    return BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        monte_carlo_iterations=1,
    )
```
```

- [ ] **Step 2: Add one row to the Commands section**

After the existing `just test -k test_threshold_rule_bdd` example, ensure this line is present:

```bash
just test -k backtester    # all backtester tests
```

- [ ] **Step 3: Commit**

```bash
git add docs/testing.md
git commit -m "docs: add backtester testing patterns to testing.md"
```

---

### Task 7: Update `docs/documentation.md`

**Files:**
- Modify: `docs/documentation.md`

- [ ] **Step 1: Add backtester README row to the File Ownership Map**

In the "File Ownership Map" table in `docs/documentation.md`, add one row after the `src/pac/<module>/README.md` row:

```
| `src/pac/backtester/<submodule>/README.md` | Submodule purpose, components, dependency table | Root-level project info |
```

- [ ] **Step 2: Commit**

```bash
git add docs/documentation.md
git commit -m "docs: add backtester submodule README row to file ownership map"
```

---

### Task 8: Rewrite `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

This is the largest change. AGENTS.md becomes a hub document — short enough to read in full, with explicit pointers to every rule and guideline.

- [ ] **Step 1: Read the current `AGENTS.md` to understand what to keep**

Open `AGENTS.md`. The sections to keep (trimmed/updated): Project Overview, Tech Stack, Repository Structure, Important Patterns, Do NOT Modify, Learned Patterns.

The sections to remove or replace: "Key Conventions" block (now in `.claude/rules/` files).

- [ ] **Step 2: Rewrite `AGENTS.md` with the new structure**

Replace the entire content of `AGENTS.md` with:

```markdown
# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Automated portfolio rebalancing assistant for Trade Republic. Reads portfolio positions via the `pytr` library (read-only WebSocket API), detects deviations from a configurable target allocation (default 70/15/15: Stocks/Gold/Bonds), and sends Telegram notifications with rebalancing recommendations. **Never executes trades.**

Includes a full backtesting and research framework for validating signal rules against 30+ years of historical market data, and a React-based dashboard for exploring results.

## Tech Stack

- **Python 3.11+**
- **uv** — package manager
- **just** — command runner (see `Justfile`)
- **Starlette** — ASGI web framework (webhook + job endpoints)
- **pytr** — Trade Republic WebSocket client (read-only)
- **python-telegram-bot** — Telegram bot API
- **pydantic** — data models and configuration validation
- **pyyaml** — YAML config file parsing
- **Jinja2** — template rendering (SandboxedEnvironment)
- **structlog** — structured logging
- **uvicorn** — ASGI server
- **yfinance** — historical market data (backtester)
- **quantstats** — portfolio metrics (backtester)
- **FastAPI** — REST API for backtester dashboard
- **React + Vite** — dashboard frontend

## Repository Structure

```
src/pac/
├── __main__.py               # Structlog config + uvicorn runner
├── app.py                    # Thin HTTP adapter over Orchestrator
├── market_context.py         # MarketContext protocol (date-aware price access)
├── live_market_context.py    # Production MarketContext (yfinance + cache)
├── config/                   # Settings loaded from pac.yaml
├── models/                   # Pydantic data models (portfolio, signals)
├── tr/                       # TRClient wrapper + tr_session() context manager
├── analysis/                 # Deviation calculation, PAC redistribution
├── rules/                    # SignalRule ABC+Generic, registry, auto-discovery
│   └── builtin/              # Threshold, cycle, PAC plan, crisis detection rules
├── delivery/                 # DeliveryChannel ABC+Generic, RenderedMessage
│   └── channels/telegram/    # TelegramChannel implementation
├── templates/                # Jinja2 template engine + format adapters
│   └── builtin/              # .j2 templates (threshold_alert, cycle_alert, etc.)
└── orchestrator/             # Orchestrator — framework-agnostic signal dispatch
src/pac/backtester/
├── config.py                 # BacktestConfig (simulation parameters)
├── runner.py                 # run_pipeline() — shared CLI + API entry point
├── data/                     # yfinance wrapper + filesystem JSON cache
├── engine/                   # Monte Carlo event loop, portfolio state machine
├── strategies/               # BacktestStrategy ABC + builtin strategies
├── metrics/                  # quantstats wrapper, benchmark comparison
├── results/                  # JSON persistence to .pac/backtests/
├── research/                 # ResearchContext, IndicatorRegistry, EventCalendar
├── api/                      # FastAPI REST API (research routes, run management)
└── dashboard/                # React + Vite web UI
tests/                        # Shared fixtures + integration tests
docs/                         # Project documentation + ADRs
research/                     # Research experiments, papers, strategy snapshots
scripts/                      # DX scaffolding & validation CLIs
```

## Rules & Guidelines

All behavioral rules for agents are in `.claude/rules/`. Read the relevant rule file before performing any task in its domain.

| Rule File | Governs |
|---|---|
| `.claude/rules/bdd.md` | When and how to write BDD feature files and step definitions |
| `.claude/rules/testing.md` | Testing philosophy, DI patterns, mocking boundaries, backtester test patterns |
| `.claude/rules/documentation.md` | Doc standards, submodule README template, docstring style |
| `.claude/rules/dependency-injection.md` | Module dependency declarations, DI conventions, import direction rules |

## Module Dependency Map

Quick reference — see each module's `README.md` for the full `## Dependencies` table.

| Module | Depends On | Consumed By |
|---|---|---|
| `models` | *(none — foundation)* | all other modules |
| `config` | *(none — foundation)* | analysis, rules, orchestrator, backtester |
| `tr` | models | orchestrator |
| `analysis` | models, config | rules, orchestrator, backtester/engine |
| `rules` | models, analysis, market_context | orchestrator, backtester/engine |
| `delivery` | models | orchestrator, templates |
| `templates` | delivery, models | orchestrator |
| `orchestrator` | analysis, config, delivery, models, rules, templates, tr | app.py |
| `backtester/data` | config, backtester.data.models | backtester/engine, backtester/research |
| `backtester/engine` | analysis, backtester/data, backtester/results, backtester/strategies, config | backtester/research, runner |
| `backtester/strategies` | models, analysis, backtester/engine | backtester/engine, backtester/research |
| `backtester/metrics` | backtester/engine | runner |
| `backtester/results` | models | backtester/engine, backtester/api |
| `backtester/research` | backtester/data, backtester/engine, backtester/strategies, config, models, rules | scripts, notebooks |
| `backtester/api` | backtester/results, backtester/research, config | dashboard |

## Important Patterns

### `tr_session()` Context Manager
All Trade Republic API access goes through `tr_session()` in `src/pac/tr/client.py`. Opens a WebSocket, yields a `TRClient`, closes on exit. Never hold connections open long-term.

### `SignalRule` ABC + Generic
Rules use `ABC + Generic[ParamsT]`. Each rule declares a Pydantic params model via its Generic type arg — `__init_subclass__` auto-extracts `params_model`. Rules are stateless; typed params are passed to `evaluate()`. To add a rule: subclass `SignalRule[YourParams]`, implement `name` and `evaluate()`, place in `src/pac/rules/builtin/`. Discovery is automatic.

### `DeliveryChannel` ABC + Generic
Same `ABC + Generic[ConfigT]` pattern as `SignalRule`. Channels implement `name`, `supported_formats`, `send()`. Optional lifecycle hooks: `start()`, `stop()`, `process_update()`. Place in `src/pac/delivery/channels/<name>/`. Discovery is automatic.

### `BacktestStrategy` ABC + Generic
Same `ABC + Generic[ParamsT]` pattern. Strategies translate signals into concrete actions (`PacAdjustment`, `HardRebalanceOrder`). Stateful — `reset()` is called between Monte Carlo iterations. To add a strategy: `just new-strategy <name>`. Discovery is automatic.

### Template Engine + FormatAdapter
`TemplateEngine` uses Jinja2 `SandboxedEnvironment`. `FormatAdapter` ABC defines formatting methods (bold, escape, literal, etc.) injected as Jinja2 globals. Two adapters: `MarkdownV2Adapter`, `PlainTextAdapter`. `TemplateEngine.render()` returns a `RenderedMessage`.

### Orchestrator
`Orchestrator.from_settings()` wires config → rules → templates → channels with zero network calls. Key methods: `dispatch_signal()`, `evaluate_signal()`, `get_portfolio_status()`, `compute_pac_plan()`. `app.py` is a thin HTTP adapter — all business logic lives in `Orchestrator`.

### YAML Config System
Config loaded from `pac.yaml` via `load_config()`. Secrets use `${ENV_VAR}` interpolation. Config models in `src/pac/config/models.py`.

### ResearchContext
`ResearchContext.from_config()` is the zero-ceremony entry point for research scripts. Replaces ~40 lines of boilerplate (load config, fetch data, build registry). Load indicator packs via `register_pack("crisis")` or `register_pack("tulipy")` after construction.

### MarketContext Protocol
`MarketContext` provides date-aware price access. Production: `LiveMarketContext` (yfinance + cache). Backtest: `BacktestMarketContext` (pre-loaded prices, zero look-ahead bias). Crisis rules receive `market_ctx` in `evaluate()` — rules that don't need market data receive `None`.

## Commands

```bash
just sync               # install/update dependencies
just hooks-install      # install git hooks
just validate           # lint + typecheck + test
just format             # auto-format
just lint               # ruff linter
just typecheck          # mypy strict
just test               # pytest
just new-rule <name>    # scaffold a new signal rule
just new-channel <name> # scaffold a new delivery channel
just new-strategy <name>  # scaffold a new backtest strategy
just new-experiment <name>  # scaffold a new research experiment
just backtest           # interactive backtest run
just backtest-sync      # install backtester dependencies
just dashboard          # start the React dashboard
```

## Do NOT Modify

- `pac.yaml.example` default values — documented in README and relied on by users
- Target allocation logic (deviation thresholds, rebalance calculations) without explicit permission
- The read-only guarantee — this tool must never execute trades

## Learned Patterns

| Pattern | Location | Date |
|---|---|---|
| All signal rules subclass `SignalRule` ABC+Generic[ParamsT] | `src/pac/rules/base.py` | 2026-04 |
| Rules auto-discovered via `discover_rules()` scanning `pac.rules.builtin` | `src/pac/rules/discovery.py` | 2026-04 |
| Configuration loaded from YAML (`pac.yaml`) via `load_config()` | `src/pac/config/loader.py` | 2026-04 |
| Assets are dynamic string IDs (no `AssetClass` enum) | `src/pac/config/models.py` | 2026-04 |
| TR connections are per-request via `tr_session()` context manager | `src/pac/tr/client.py` | 2026-04 |
| Telegram webhook validated via `X-Telegram-Bot-Api-Secret-Token` header | `src/pac/app.py` | 2026-04 |
| `RenderedMessage` is defined in `delivery/base.py`; `templates/engine.py` imports it from there | `src/pac/delivery/base.py` | 2026-04 |
| `Orchestrator.from_settings()` wires config → rules → templates → channels | `src/pac/orchestrator/orchestrator.py` | 2026-04 |
| Dynamic signal routing via `POST /jobs/signal/{signal_name}` | `src/pac/app.py` | 2026-04 |
| All backtest strategies subclass `BacktestStrategy` ABC+Generic[ParamsT] (stateful) | `src/pac/backtester/strategies/base.py` | 2026-04 |
| `BacktestStrategy.reset()` clears per-iteration state (cooldown dates, etc.) | `src/pac/backtester/strategies/base.py` | 2026-04 |
| `BacktestSimulator` runs Monte Carlo (N iterations); price data pre-loaded as `dict[ticker, PriceSeries]` | `src/pac/backtester/engine/simulator.py` | 2026-04 |
| Backtester reuses production `SignalRule` instances against synthetic `PortfolioSnapshot` | `src/pac/backtester/engine/simulator.py` | 2026-04 |
| Assets need `ticker: EUNL.DE` in `pac.yaml` for yfinance; `resolve_tickers()` errors on missing | `src/pac/backtester/data/provider.py` | 2026-04 |
| Backtester is isolated — zero imports from main `pac` app; install with `just backtest-sync` | `src/pac/backtester/` | 2026-04 |
| `ResearchContext.from_config()` is zero-ceremony entry point for research scripts | `src/pac/backtester/research/context.py` | 2026-04 |
| `IndicatorRegistry` starts empty; load packs via `register_pack("tulipy")` or `register_pack("crisis")` | `src/pac/backtester/research/indicators.py` | 2026-04 |
| Proxy tickers (`proxy_ticker`, `proxy_end`) enable 30+ year backtests with pre-ETF data | `src/pac/config/models.py` | 2026-04 |
| `CrisisCompositeRule` uses N-of-M voting (default 3/5); no veto guard by default | `src/pac/rules/builtin/crisis_composite.py` | 2026-04 |
| Pure indicator math lives in `_indicators.py` — rules and composite both call these | `src/pac/rules/builtin/_indicators.py` | 2026-04 |
| `CrisisExploitStrategy` is stateful with cooldown, severity-proportional sell fractions, allocation floors | `src/pac/backtester/strategies/builtin/crisis_exploit.py` | 2026-04 |
| Research API at `/api/research/*` serves experiments, papers, and strategy snapshots | `src/pac/backtester/api/routes/research.py` | 2026-04 |
| `research/` directory holds experiments, papers, and strategy snapshots (not a Python package) | `research/` | 2026-04 |
| Scaffold new experiments via `just new-experiment <name>` | `scripts/scaffold_experiment.py` | 2026-04 |
| `ExperimentManifest` scans `research/experiments/` for all experiments | `src/pac/backtester/research/manifest.py` | 2026-04 |
```

- [ ] **Step 3: Verify the file renders correctly**

```bash
just lint
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: restructure AGENTS.md as hub document with rules references and dependency map"
```

---

### Task 9: Update main module READMEs — models, analysis, config, tr

**Files:**
- Modify: `src/pac/models/README.md`
- Modify: `src/pac/analysis/README.md`
- Modify: `src/pac/config/README.md`
- Modify: `src/pac/tr/README.md`

- [ ] **Step 1: Add `## Dependencies` to `src/pac/models/README.md`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

This module has no internal `pac` imports — it is the foundation layer. All other modules depend on it; it depends on none of them.
```

- [ ] **Step 2: Add `## Dependencies` to `src/pac/analysis/README.md`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Core portfolio and signal types used as function inputs and outputs | `PortfolioSnapshot`, `SignalSeverity` |
| `config` | `pac.config` | Application settings required to extract target allocations and asset metadata | `Settings` |
```

- [ ] **Step 3: Add `## Dependencies` to `src/pac/config/README.md`**

Read the current `src/pac/config/README.md` to find the right insertion point, then add:

```markdown
## Dependencies

This module has no internal `pac` imports — it is the foundation layer. Config models and the loader are self-contained; they depend only on `pydantic` and `pyyaml` (external).
```

- [ ] **Step 4: Add `## Dependencies` to `src/pac/tr/README.md`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Domain types for the portfolio snapshot built from raw WebSocket data | `PortfolioSnapshot`, `Position`, `SavingsPlan` |
```

- [ ] **Step 5: Commit**

```bash
git add src/pac/models/README.md src/pac/analysis/README.md src/pac/config/README.md src/pac/tr/README.md
git commit -m "docs: add dependency tables to models, analysis, config, tr READMEs"
```

---

### Task 10: Update main module READMEs — rules, templates, delivery, orchestrator

**Files:**
- Modify: `src/pac/rules/README.md`
- Modify: `src/pac/templates/README.md`
- Modify: `src/pac/delivery/README.md`
- Modify: `src/pac/orchestrator/README.md`

- [ ] **Step 1: Add `## Dependencies` to `src/pac/rules/README.md`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Input and output types for rule evaluation | `Signal`, `PortfolioSnapshot`, `SignalSeverity` |
| `analysis` | `pac.analysis` | Deviation computation required by most rules' `evaluate()` implementations | `DeviationReport`, `DeviationResult` |
| `market_context` | `pac.market_context` | Protocol for date-aware price access used by crisis rules | `MarketContext` |
```

- [ ] **Step 2: Read `src/pac/templates/README.md` to find the insertion point, then add `## Dependencies`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `delivery` | `pac.delivery` | `RenderedMessage` is the output type of `TemplateEngine.render()` — owned by the delivery layer | `RenderedMessage` |
| `models` | `pac.models` | Signal severity used to classify templates by urgency level | `SignalSeverity` |
```

- [ ] **Step 3: Read `src/pac/delivery/README.md` and add `## Dependencies`**

Insert after the `## Architectural Role` table:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Signal severity used by `DeliveryChannel` to gate sends by urgency | `SignalSeverity` |
```

- [ ] **Step 4: Add `## Dependencies` to `src/pac/orchestrator/README.md`**

Insert after the `## Architectural Role` table (or at the top of the file if no such table exists):

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `analysis` | `pac.analysis` | Deviation calculation and PAC plan computation for signal evaluation | `DeviationReport`, `calculate_deviations`, `compute_pac_plan` |
| `config` | `pac.config` | Application settings required to wire rules, channels, and templates at startup | `Settings` |
| `delivery` | `pac.delivery` | Channel abstraction for routing rendered messages to Telegram and other targets | `DeliveryChannel`, `discover_channels` |
| `models` | `pac.models` | Shared portfolio and signal types passed through the dispatch pipeline | `PortfolioSnapshot`, `Signal` |
| `rules` | `pac.rules` | Signal rule registry and evaluation — core of the dispatch pipeline | `SignalRegistry`, `discover_rules` |
| `templates` | `pac.templates` | Jinja2 rendering engine that converts signal data into formatted messages | `TemplateEngine`, `FormatAdapter` |
| `tr` | `pac.tr` | WebSocket client for fetching live portfolio data on each signal evaluation | `tr_session` |
```

- [ ] **Step 5: Commit**

```bash
git add src/pac/rules/README.md src/pac/templates/README.md src/pac/delivery/README.md src/pac/orchestrator/README.md
git commit -m "docs: add dependency tables to rules, templates, delivery, orchestrator READMEs"
```

---

### Task 11: Create missing backtester submodule READMEs (research/, api/)

**Files:**
- Create: `src/pac/backtester/research/README.md`
- Create: `src/pac/backtester/api/README.md`

- [ ] **Step 1: Create `src/pac/backtester/research/README.md`**

```markdown
# Research Framework

Zero-ceremony research API for backtesting experiments. Provides `ResearchContext` — a single entry point that replaces ~40 lines of boilerplate for data loading, indicator registration, and simulation setup. Also provides `IndicatorRegistry`, `EventCalendar`, and out-of-sample validation helpers.

## Architectural Role

Depends on: [`backtester/data`](../data/), [`backtester/engine`](../engine/), [`backtester/strategies`](../strategies/), [`config`](../../config/), [`models`](../../models/), [`rules`](../../rules/).
Consumed by: research scripts in `research/experiments/`, CLI research commands.

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/data` | `pac.backtester.data` | Fetches and caches historical price series for all assets | `MarketDataProvider`, `PriceSeries` |
| `backtester/engine` | `pac.backtester.engine` | Runs Monte Carlo simulation iterations | `BacktestSimulator`, `SimulationResult` |
| `backtester/strategies` | `pac.backtester.strategies` | Strategy discovery and base class for research variants | `discover_strategies`, `BacktestStrategy` |
| `config` | `pac.config` | Loads and validates the pac.yaml configuration file | `Settings`, `load_config` |
| `models` | `pac.models` | Portfolio and market data types used throughout research computations | `PriceSeries` |
| `rules` | `pac.rules` | Signal rule discovery and registry reused in simulation | `discover_rules`, `SignalRegistry` |

## Key Components

| Component | File | Purpose |
|---|---|---|
| `ResearchContext` | `context.py` | Zero-ceremony facade: load config, fetch data, run simulations, compare variants |
| `IndicatorRegistry` | `indicators.py` | Opt-in indicator registry; empty by default, populated via `register_pack()` |
| `EventCalendar` | `events.py` | Named calendar of market events (recessions, crises) for event-driven analysis |
| `ExperimentManifest` | `manifest.py` | Scans `research/experiments/` and surfaces experiment metadata |
| `Experiment` | `experiment.py` | Single experiment: immutable `experiment.toml` seed + auto-computed state |

## Usage

```python
from pac.backtester.research.context import ResearchContext

ctx = ResearchContext.from_config(
    "backtest/pac-backtest.yaml",
    start_date=date(1996, 1, 1),
    packs=["crisis"],
)

# Run a quick single-iteration simulation
result = ctx.run(strategy="pac_alignment")

# Compare two variants
table = ctx.compare(
    baseline={"strategy": "pac_alignment"},
    variant={"strategy": "crisis_exploit"},
)

# Out-of-sample validation
oos = ctx.walk_forward(strategy="crisis_exploit", folds=5)
```

## Commands

```bash
just new-experiment <name>       # scaffold a new research experiment
just test -k test_research       # run research module tests
just test -k backtester          # run all backtester tests
```

## See Also

- [Backtester README](../README.md) — full architecture and data flow
- [Engine](../engine/) — `BacktestSimulator` and `SimulationResult`
- [Strategies](../strategies/) — `BacktestStrategy` ABC
- [ADR-008: Research Framework](../../../../docs/architecture/ADR-008-research-framework.md)
```

- [ ] **Step 2: Create `src/pac/backtester/api/README.md`**

```markdown
# Backtester API

FastAPI REST API for the backtester dashboard. Serves experiment metadata, saved run results, strategy snapshots, and supports triggering new backtest runs.

## Architectural Role

Depends on: [`backtester/results`](../results/), [`backtester/research`](../research/), [`config`](../../config/).
Consumed by: [`dashboard`](../dashboard/) (React frontend via HTTP).

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/results` | `pac.backtester.results` | Load and list saved backtest run results from the filesystem | `ResultStore`, `RunResult` |
| `backtester/research` | `pac.backtester.research` | Serve experiment metadata and papers from the research directory | `ExperimentManifest` |
| `config` | `pac.config` | Application settings required to locate data directories and validate requests | `Settings` |

## Key Components

| Component | File | Purpose |
|---|---|---|
| `create_app()` | `app.py` | FastAPI app factory with all routes and middleware registered |
| `BacktestManager` | `deps.py` | FastAPI dependency providing `ResultStore` and config to route handlers |
| Research routes | `routes/research.py` | `GET /api/research/experiments`, `/papers`, `/strategies` |
| Run routes | `routes/runs.py` | `GET /api/runs`, `GET /api/runs/{id}` |
| Strategy routes | `routes/strategies.py` | `GET /api/strategies` (available strategy names) |

## Configuration

The API reads the same `pac.yaml` as the main app. Results are served from `.pac/backtests/`. Research artifacts are served from the `research/` directory at the repo root.

## Usage

```bash
just dashboard          # starts both the FastAPI backend and the React frontend
just dashboard --port 9000  # custom port
```

## Commands

```bash
just test -k test_research_routes    # research API route tests
just test -k backtester              # all backtester tests
```

## See Also

- [Dashboard](../dashboard/) — React frontend that consumes this API
- [Results](../results/) — `RunResult` JSON schema and `ResultStore`
- [Research](../research/) — `ExperimentManifest` and experiment metadata
```

- [ ] **Step 3: Commit**

```bash
git add src/pac/backtester/research/README.md src/pac/backtester/api/README.md
git commit -m "docs: create research and api submodule READMEs"
```

---

### Task 12: Update existing backtester submodule READMEs — data, engine, strategies, metrics, results

**Files:**
- Modify: `src/pac/backtester/data/README.md`
- Modify: `src/pac/backtester/engine/README.md`
- Modify: `src/pac/backtester/strategies/README.md`
- Modify: `src/pac/backtester/metrics/README.md`
- Modify: `src/pac/backtester/results/README.md`

- [ ] **Step 1: Add `## Dependencies` to `src/pac/backtester/data/README.md`**

Read the current file to confirm where `## Architectural Role` ends, then insert:

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `config` | `pac.config` | Asset configuration supplies the `ticker` fields used to resolve yfinance symbols | `Settings`, `AssetConfig` |
```

Note: `backtester/data` also defines `PriceSeries` and `PriceBar` in `data/models.py` — these are re-exported from `pac.models.market_data` for use by other modules. The data module has no other internal pac dependencies.

- [ ] **Step 2: Add `## Dependencies` to `src/pac/backtester/engine/README.md`**

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `analysis` | `pac.analysis` | Deviation computation reused on every simulation tick to match production logic | `DeviationReport`, `calculate_deviations` |
| `backtester/data` | `pac.backtester.data` | Price series consumed by the simulation clock and portfolio state machine | `PriceSeries`, `PriceBar` |
| `backtester/results` | `pac.backtester.results` | Result models populated as the simulation progresses | `IterationResult`, `SimulationResult` |
| `backtester/strategies` | `pac.backtester.strategies` | Strategy interface for translating signals into actions each tick | `BacktestStrategy` |
| `config` | `pac.config` | Simulation parameters (dates, contributions, spread) from `BacktestConfig` | `Settings` |
| `rules` | `pac.rules` | Existing production signal rules evaluated on each synthetic snapshot | `SignalRegistry` |
```

- [ ] **Step 3: Add `## Dependencies` to `src/pac/backtester/strategies/README.md`**

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Portfolio and signal types passed to `on_signals()` on each simulation tick | `PortfolioSnapshot`, `Signal` |
| `analysis` | `pac.analysis` | Deviation report passed to `on_signals()` for allocation-aware decision making | `DeviationReport` |
| `backtester/engine` | `pac.backtester.engine` | Action types returned by strategies to the engine | `Action`, `PacAdjustment`, `HardRebalanceOrder` |
```

- [ ] **Step 4: Add `## Dependencies` to `src/pac/backtester/metrics/README.md`**

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/engine` | `pac.backtester.engine` | Per-iteration simulation results aggregated into metric distributions | `IterationResult` |
```

- [ ] **Step 5: Add `## Dependencies` to `src/pac/backtester/results/README.md`**

```markdown
## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Domain model types serialised into the JSON result schema | `PortfolioSnapshot` |
```

- [ ] **Step 6: Commit**

```bash
git add src/pac/backtester/data/README.md src/pac/backtester/engine/README.md
git add src/pac/backtester/strategies/README.md src/pac/backtester/metrics/README.md src/pac/backtester/results/README.md
git commit -m "docs: add dependency tables to backtester submodule READMEs"
```

---

## PHASE 2 — BDD Additions and Module Docstrings

---

### Task 13: Add BDD for `IndicatorRegistry`

**Files:**
- Create: `src/pac/backtester/research/features/indicator_registry.feature`
- Create: `src/pac/backtester/research/tests/test_indicator_registry_bdd.py`

- [ ] **Step 1: Confirm the `features/` directory exists (create if not)**

```bash
ls src/pac/backtester/research/features/ 2>/dev/null || mkdir -p src/pac/backtester/research/features/
```

- [ ] **Step 2: Write the feature file**

Create `src/pac/backtester/research/features/indicator_registry.feature`:

```gherkin
Feature: Indicator Registry

  Background:
    Given an indicator registry with minimal price data

  Scenario: A new registry has no indicators registered
    Then no indicators are registered

  Scenario: Registering the crisis pack makes crisis indicators available
    When the "crisis" indicator pack is registered
    Then the registry contains the "equity_drawdown" indicator
    And the registry contains the "death_cross" indicator

  Scenario: Registering an unknown pack raises a descriptive error
    When the "nonexistent_pack" indicator pack is registered
    Then a ValueError is raised

  Scenario: A custom indicator function can be registered
    When a custom indicator named "my_sma" is registered
    Then the registry contains the "my_sma" indicator
```

- [ ] **Step 3: Run pytest to confirm step definitions are missing (expected failure)**

```bash
just test -k test_indicator_registry_bdd 2>&1 | head -20
```

Expected output: `StepDefinitionNotFoundError` or similar — scenarios are discovered but steps are not implemented yet.

- [ ] **Step 4: Write step definitions**

Create `src/pac/backtester/research/tests/test_indicator_registry_bdd.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from pac.backtester.data.models import PriceBar, PriceSeries
from pac.backtester.research.indicators import IndicatorRegistry

scenarios("../features/indicator_registry.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("an indicator registry with minimal price data")
def given_registry(ctx: dict[str, Any]) -> None:
    bars = [
        PriceBar(
            date=date(2022, 1, d),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("98"),
            close=Decimal("102"),
            volume=1000,
        )
        for d in range(3, 28)
    ]
    price_data = {"stocks": PriceSeries(ticker="EUNL.DE", bars=bars)}
    ctx["registry"] = IndicatorRegistry(price_data)


@then("no indicators are registered")
def then_no_indicators(ctx: dict[str, Any]) -> None:
    assert ctx["registry"].list() == []


@when('the "crisis" indicator pack is registered')
def when_register_crisis(ctx: dict[str, Any]) -> None:
    ctx["registry"].register_pack("crisis")


@when('the "nonexistent_pack" indicator pack is registered')
def when_register_unknown(ctx: dict[str, Any]) -> None:
    try:
        ctx["registry"].register_pack("nonexistent_pack")
        ctx["error"] = None
    except ValueError as e:
        ctx["error"] = e


@when('a custom indicator named "my_sma" is registered')
def when_register_custom(ctx: dict[str, Any]) -> None:
    ctx["registry"].register(
        "my_sma",
        lambda price_data, **_: float(price_data["stocks"].bars[-1].close),
        asset="stocks",
        lookback_days=20,
    )


@then('the registry contains the "equity_drawdown" indicator')
def then_has_equity_drawdown(ctx: dict[str, Any]) -> None:
    assert "equity_drawdown" in ctx["registry"].list()


@then('the registry contains the "death_cross" indicator')
def then_has_death_cross(ctx: dict[str, Any]) -> None:
    assert "death_cross" in ctx["registry"].list()


@then("a ValueError is raised")
def then_value_error(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["error"], ValueError)


@then('the registry contains the "my_sma" indicator')
def then_has_my_sma(ctx: dict[str, Any]) -> None:
    assert "my_sma" in ctx["registry"].list()
```

- [ ] **Step 5: Run tests to verify all scenarios pass**

```bash
just test -k test_indicator_registry_bdd -v
```

Expected: all 4 scenarios pass.

- [ ] **Step 6: Commit**

```bash
git add src/pac/backtester/research/features/indicator_registry.feature
git add src/pac/backtester/research/tests/test_indicator_registry_bdd.py
git commit -m "test: add BDD scenarios for IndicatorRegistry"
```

---

### Task 14: Add BDD for `ResearchContext` (non-IO behaviors)

**Files:**
- Create: `src/pac/backtester/research/features/research_context.feature`
- Create: `src/pac/backtester/research/tests/test_research_context_bdd.py`

These scenarios cover observable behaviors that do not require network calls (indicator pack delegation, event calendar access, date range computation from pre-loaded data).

- [ ] **Step 1: Write the feature file**

Create `src/pac/backtester/research/features/research_context.feature`:

```gherkin
Feature: Research Context

  Scenario: Context exposes the common date range across all loaded assets
    Given a research context with price data for two assets from 2022-01-03 to 2022-01-28
    Then the context data_start is 2022-01-03
    And the context data_end is 2022-01-28

  Scenario: Context provides access to named built-in event calendars
    Given a research context with price data for one asset
    Then the "recessions_us" event calendar is accessible
    And the "financial_crises" event calendar is accessible

  Scenario: Context indicator registry starts empty
    Given a research context with price data for one asset
    Then no indicators are registered in the context

  Scenario: Context delegates indicator pack registration to its registry
    Given a research context with price data for one asset
    When the "crisis" indicator pack is loaded via the context
    Then the context registry contains the "equity_drawdown" indicator
```

- [ ] **Step 2: Run pytest to confirm steps are missing**

```bash
just test -k test_research_context_bdd 2>&1 | head -20
```

Expected: `StepDefinitionNotFoundError` — step definitions not yet implemented.

- [ ] **Step 3: Write step definitions**

Create `src/pac/backtester/research/tests/test_research_context_bdd.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from pac.backtester.data.models import PriceBar, PriceSeries
from pac.backtester.research.indicators import IndicatorRegistry
from pac.config.models import Settings

scenarios("../features/research_context.feature")

# ResearchContext is constructed directly (not via from_config) to avoid network calls.
# This tests the non-IO behaviors: date range computation, calendar access, registry delegation.

from pac.backtester.research.context import ResearchContext  # noqa: E402


def _make_bars(start_day: int, end_day: int) -> list[PriceBar]:
    return [
        PriceBar(
            date=date(2022, 1, d),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("98"),
            close=Decimal("102"),
            volume=1000,
        )
        for d in range(start_day, end_day + 1)
        if date(2022, 1, d).weekday() < 5
    ]


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@pytest.fixture
def minimal_settings(make_settings: Any) -> Settings:
    return make_settings()


@given("a research context with price data for two assets from 2022-01-03 to 2022-01-28")
def given_ctx_two_assets(ctx: dict[str, Any], minimal_settings: Settings) -> None:
    bars = _make_bars(3, 28)
    price_data = {
        "stocks": PriceSeries(ticker="EUNL.DE", bars=bars),
        "gold": PriceSeries(ticker="IGLN.L", bars=bars),
    }
    registry = IndicatorRegistry(price_data)
    ctx["rc"] = ResearchContext(
        settings=minimal_settings,
        price_data=price_data,
        ticker_price_data={"EUNL.DE": price_data["stocks"], "IGLN.L": price_data["gold"]},
        registry=registry,
    )


@given("a research context with price data for one asset")
def given_ctx_one_asset(ctx: dict[str, Any], minimal_settings: Settings) -> None:
    bars = _make_bars(3, 28)
    price_data = {"stocks": PriceSeries(ticker="EUNL.DE", bars=bars)}
    registry = IndicatorRegistry(price_data)
    ctx["rc"] = ResearchContext(
        settings=minimal_settings,
        price_data=price_data,
        ticker_price_data={"EUNL.DE": price_data["stocks"]},
        registry=registry,
    )


@then("the context data_start is 2022-01-03")
def then_data_start(ctx: dict[str, Any]) -> None:
    assert ctx["rc"]._data_start == date(2022, 1, 3)


@then("the context data_end is 2022-01-28")
def then_data_end(ctx: dict[str, Any]) -> None:
    assert ctx["rc"]._data_end == date(2022, 1, 28)


@then('the "recessions_us" event calendar is accessible')
def then_recessions_calendar(ctx: dict[str, Any]) -> None:
    calendar = ctx["rc"].calendars.get("recessions_us")
    assert calendar is not None


@then('the "financial_crises" event calendar is accessible')
def then_crises_calendar(ctx: dict[str, Any]) -> None:
    calendar = ctx["rc"].calendars.get("financial_crises")
    assert calendar is not None


@then("no indicators are registered in the context")
def then_no_indicators(ctx: dict[str, Any]) -> None:
    assert ctx["rc"]._registry.list() == []


@when('the "crisis" indicator pack is loaded via the context')
def when_load_crisis_pack(ctx: dict[str, Any]) -> None:
    ctx["rc"]._registry.register_pack("crisis")


@then('the context registry contains the "equity_drawdown" indicator')
def then_has_equity_drawdown(ctx: dict[str, Any]) -> None:
    assert "equity_drawdown" in ctx["rc"]._registry.list()
```

- [ ] **Step 4: Check that `ResearchContext` has a `calendars` property (read the file if uncertain)**

```bash
grep -n "calendars\|def calendar" src/pac/backtester/research/context.py | head -10
```

If `calendars` is not a property on `ResearchContext`, adjust the step definition to use the correct API (e.g., `ctx["rc"]._calendars` or `ctx["rc"].get_calendar("recessions_us")`).

- [ ] **Step 5: Run tests**

```bash
just test -k test_research_context_bdd -v
```

Expected: all 4 scenarios pass.

- [ ] **Step 6: Commit**

```bash
git add src/pac/backtester/research/features/research_context.feature
git add src/pac/backtester/research/tests/test_research_context_bdd.py
git commit -m "test: add BDD scenarios for ResearchContext non-IO behaviors"
```

---

### Task 15: Module docstrings sweep — research/ and api/

**Files:**
- Modify: `src/pac/backtester/research/__init__.py`
- Modify: `src/pac/backtester/api/__init__.py`
- Modify: `src/pac/backtester/api/app.py` (if `create_app` lacks docstring)
- Modify: `src/pac/backtester/api/deps.py` (if `BacktestManager` lacks docstring)

- [ ] **Step 1: Check `research/__init__.py`**

```bash
cat src/pac/backtester/research/__init__.py
```

If the file is empty or has no module-level docstring, add:

```python
"""Research framework for backtesting experiments.

Provides ResearchContext — a zero-ceremony facade over data loading,
indicator registration, and simulation setup for interactive research scripts.
"""
```

- [ ] **Step 2: Check `api/__init__.py`**

```bash
cat src/pac/backtester/api/__init__.py
```

If empty or missing docstring, add:

```python
"""FastAPI REST API for the backtester dashboard.

Serves experiment metadata, run results, and strategy snapshots.
Use create_app() to build the FastAPI application instance.
"""
```

- [ ] **Step 3: Check `api/app.py` — verify `create_app()` has a Google-style docstring**

```bash
grep -A5 "def create_app" src/pac/backtester/api/app.py
```

If missing, add:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the backtester FastAPI application.

    Args:
        settings: Application settings. Loads from pac.yaml if not provided.

    Returns:
        A fully configured FastAPI app with all routes registered.
    """
```

- [ ] **Step 4: Check `api/deps.py` — verify `BacktestManager` and its key methods have docstrings**

```bash
grep -A3 "class BacktestManager\|def get_manager" src/pac/backtester/api/deps.py
```

Add Google-style docstrings where missing.

- [ ] **Step 5: Check `research/experiment.py` and `research/manifest.py` for missing public docstrings**

```bash
grep -n "^class \|^def " src/pac/backtester/research/experiment.py | head -20
grep -n "^class \|^def " src/pac/backtester/research/manifest.py | head -20
```

For any public class or function without a docstring, add a one-line docstring describing its purpose.

- [ ] **Step 6: Run typecheck and tests to confirm no regressions**

```bash
just validate
```

Expected: all checks pass.

- [ ] **Step 7: Commit**

```bash
git add src/pac/backtester/research/__init__.py src/pac/backtester/api/__init__.py
git add src/pac/backtester/api/app.py src/pac/backtester/api/deps.py
git add src/pac/backtester/research/experiment.py src/pac/backtester/research/manifest.py
git commit -m "docs: add module docstrings to research and api submodules"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| Convert docs to Claude Code rules (.claude/rules/) | Tasks 1–4 |
| Keep docs/ as human-readable guides, update for backtester | Tasks 5–7 |
| AGENTS.md as central hub, Rules & Guidelines section | Task 8 |
| Module Dependency Map in AGENTS.md | Task 8 |
| Dependency tables in all module READMEs | Tasks 9–12 |
| Create missing READMEs (research/, api/) | Task 11 |
| BDD for IndicatorRegistry | Task 13 |
| BDD for ResearchContext (non-IO) | Task 14 |
| Module docstrings sweep (research/, api/) | Task 15 |
| Skip BDD for tr/ (thin boundary adapter) | ✓ no task — correct |
| Skip BDD for analysis/ and models/ (pure math / Pydantic) | ✓ no task — correct |
| Remove feature file inventory table from docs/bdd.md | Task 5 |
| "Why Required" column in dependency tables | Tasks 9–12 |
| Representative exports note (non-exhaustive) | Tasks 9–12 |

All spec requirements are covered. No gaps found.
