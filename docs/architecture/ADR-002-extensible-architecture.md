# Extensible Architecture

**Source:** Task 003 (April 2026)
**Status:** Accepted

## Context

ADR-001 established the PAC automation system with a working prototype: Protocol-based signal rules, a single Telegram delivery channel, environment variable configuration, and a monolithic `app.py` that orchestrated everything. While functional, this design had limited extensibility:

- **Hardcoded assets.** A fixed `AssetClass` enum (stocks, gold, bonds) prevented users from customising their portfolio.
- **Protocol-based rules.** `SignalRule` used `typing.Protocol` (structural subtyping). Rules received the entire `Settings` object, not typed params — no IDE autocomplete, no per-rule validation.
- **Single delivery channel.** Telegram was deeply coupled to the application layer. Adding a second channel (Discord, email) would require rewriting the notification pipeline.
- **Environment variable configuration.** All settings came from `PAC_*` env vars via Pydantic `BaseSettings`. Complex structures (asset lists, per-signal params) were awkward to express.
- **No template system.** Message formatting was hardcoded in `telegram/formatting.py`. Adding a channel meant duplicating format logic.
- **Monolithic lifespan.** The Starlette lifespan made network calls (Telegram `set_webhook`) on every cold start, breaking serverless deployment patterns.

## Decision

Adopt an extensible, plugin-like architecture using ABC+Generic base classes, auto-discovery, YAML configuration, and a template engine. The framework handles wiring, discovery, and rendering — contributors add a single file and a config entry.

### Key Design Choices

**ABC + Generic over Protocol.** All extensible base classes use `ABC + Generic[ParamsT/ConfigT]` instead of Protocol. This gives contributors IDE-perfect autocomplete on typed params and mypy enforcement. `__init_subclass__` auto-extracts the Generic type argument into a `params_model` / `config_model` class variable, eliminating registration boilerplate.

**Two-phase config validation.** YAML is parsed into Pydantic models with `channels` and `signal.params` stored as raw dicts. At wiring time, the orchestrator resolves each channel/rule type, finds the corresponding subclass, and calls `config_model.model_validate()` to produce fully typed config objects. This keeps the config schema independent of plugin code.

**Feature-based directory structure.** Each submodule (`config/`, `rules/`, `delivery/`, `templates/`, `analysis/`, `models/`, `tr/`, `orchestrator/`) is autonomous with co-located `tests/`, `features/`, and `README.md`. Dependency inversion via ABCs makes each independently testable.

## Solution

### Architecture

```
pac.yaml (YAML + ${ENV_VAR} interpolation)
       │
       ▼  load_config()
┌──────────────────────────────────────────────────────────────┐
│                        Orchestrator                          │
│  from_settings() wires: config → rules → templates → channels│
│                                                              │
│  dispatch_signal(name)                                       │
│    ├── evaluate: SignalRule[ParamsT].evaluate(report, snap)  │
│    ├── render:   TemplateEngine.render(template, data, fmt)  │
│    └── send:     DeliveryChannel[ConfigT].send(message)      │
└──────────────────────────────────────────────────────────────┘
       ▲                              │
       │ thin HTTP adapter            ▼
┌──────────────┐              ┌──────────────┐
│ Starlette    │              │ Telegram Bot │
│ app.py       │              │ (interactive)│
│ POST /jobs/  │              │ /status etc  │
│ signal/{name}│              └──────────────┘
└──────────────┘
```

### Extensible Base Classes

#### `SignalRule[ParamsT]`

```python
class SignalRule(ABC, Generic[ParamsT]):
    params_model: ClassVar[type[BaseModel]]  # auto-extracted by __init_subclass__

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def evaluate(self, report, snapshot, params: ParamsT) -> list[Signal]: ...

    @classmethod
    def build_template_data(cls, signals, report, snapshot, params) -> dict: ...
```

Rules are stateless. Typed params are validated from YAML at wiring time. Auto-discovered by scanning `pac.rules.builtin`.

#### `DeliveryChannel[ConfigT]`

```python
class DeliveryChannel(ABC, Generic[ConfigT]):
    config_model: ClassVar[type[BaseModel]]  # auto-extracted by __init_subclass__

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]: ...

    @abstractmethod
    async def send(self, message: RenderedMessage) -> None: ...

    async def start(self) -> None: ...    # lifecycle hook
    async def stop(self) -> None: ...     # lifecycle hook
    async def process_update(self, data) -> None: ...  # inbound webhook
```

Interactive features (commands, keyboards) are channel-specific — implemented inside each channel's subpackage, not in the ABC. Channels receive the orchestrator via `set_orchestrator()` for interactive DI.

#### `TemplateEngine` + `FormatAdapter`

```python
class FormatAdapter(ABC):
    @abstractmethod
    def bold(self, text: str) -> str: ...
    @abstractmethod
    def escape(self, text: str) -> str: ...
    @abstractmethod
    def literal(self, text: str) -> str: ...
    # ... italic, code, link, heading, etc.
```

Jinja2 `SandboxedEnvironment` injects adapter methods as globals. Templates call `{{ bold(text) }}` without knowing the target format. Two built-in adapters: `MarkdownV2Adapter` (Telegram) and `PlainTextAdapter`. Custom filters: `datefmt`, `numberfmt`, `pctfmt`, `eurfmt`.

### YAML Configuration

Single `pac.yaml` file replaces environment variables for all structured config. Secrets use `${ENV_VAR}` interpolation — the loader substitutes env var values before Pydantic validation. Dynamic asset list (no enum), per-signal rule params, and channel configs are all declarative.

### Auto-Discovery

Rules and channels are discovered by scanning their package directories at import time — no manual registration required:

```python
def discover_rules(package="pac.rules.builtin") -> dict[str, type[SignalRule]]: ...
def discover_channels(package="pac.delivery.channels") -> dict[str, type[DeliveryChannel]]: ...
```

### Orchestrator

`Orchestrator` is the framework-agnostic dispatch pipeline. `from_settings()` wires config → rules → templates → channels with zero network calls (serverless-safe cold starts). `app.py` is a thin HTTP adapter that delegates to the orchestrator — it handles auth and request routing only.

Dynamic signal routing via `POST /jobs/signal/{signal_name}` replaces hardcoded per-signal routes. The orchestrator resolves signal name → registered rule → dispatches evaluation.

### DX Scaffolding

CLI scripts reduce contributor friction:
- `just new-rule <name>` — scaffolds a new signal rule with typed params, tests, and feature file
- `just new-channel <name>` — scaffolds a new delivery channel with config model, tests, and feature file
- `just validate-config` — validates `pac.yaml` against the config schema

## Implementation Phases

| Phase                        | What Changed                                                                        |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| 1. Project restructure       | Feature-based layout with co-located tests/features/README per submodule            |
| 2. Config system             | YAML config, Pydantic models, dynamic assets, `${ENV_VAR}` interpolation            |
| 3. Rule engine               | `SignalRule[ParamsT]` ABC+Generic, auto-discovery, typed params, BDD tests          |
| 4. Delivery channels         | `DeliveryChannel[ConfigT]` ABC+Generic, Telegram implementation, discovery          |
| 5. Template engine           | Jinja2 `SandboxedEnvironment`, `FormatAdapter` ABC, MarkdownV2 + PlainText adapters |
| 6. Web layer & orchestration | `Orchestrator` dispatch pipeline, thin Starlette adapter, serverless-first lifespan |
| 7. DX scaffolding            | `scaffold_rule`, `scaffold_channel`, `validate_config` CLIs, contributor docs       |

## Current Structure

```
src/pac/
├── __main__.py               # Structlog config + uvicorn runner
├── app.py                    # Thin HTTP adapter over Orchestrator
├── config/
│   ├── models.py             # Pydantic config models (Settings, AssetConfig, etc.)
│   └── loader.py             # YAML loading + ${ENV_VAR} interpolation
├── models/
│   ├── portfolio.py          # Position, PortfolioSnapshot, Allocation
│   └── signals.py            # Signal, RebalanceAction, SignalSeverity
├── tr/
│   ├── client.py             # TRClient wrapper + tr_session() context manager
│   └── exceptions.py         # TR-specific exceptions
├── analysis/
│   ├── deviation.py          # calculate_deviations() → DeviationReport
│   └── rebalance.py          # calculate_pac_plan() → PacPlan
├── rules/
│   ├── base.py               # SignalRule[ParamsT] ABC+Generic
│   ├── registry.py           # SignalRegistry
│   ├── discovery.py          # discover_rules() auto-scanner
│   └── builtin/              # ThresholdDeviation, CycleInversion, PacPlan rules
├── delivery/
│   ├── base.py               # DeliveryChannel[ConfigT] ABC+Generic, RenderedMessage
│   ├── discovery.py          # discover_channels() auto-scanner
│   └── channels/telegram/    # TelegramChannel, bot factory, formatting, keyboards
├── templates/
│   ├── engine.py             # TemplateEngine — Jinja2 SandboxedEnvironment
│   ├── adapters/             # FormatAdapter ABC, MarkdownV2, PlainText
│   └── builtin/              # .j2 templates (threshold_alert, cycle_alert, etc.)
├── orchestrator/
│   └── orchestrator.py       # Orchestrator — framework-agnostic dispatch pipeline
scripts/
├── scaffold_rule.py          # just new-rule <name>
├── scaffold_channel.py       # just new-channel <name>
└── validate_config.py        # just validate-config
```

## Consequences

### Positive

- **Extensibility.** Adding a rule or channel requires one file + one config entry. No framework code changes.
- **Type safety.** Contributors get IDE autocomplete and mypy enforcement on all params and config — typed end-to-end from YAML to `evaluate()`.
- **Testability.** Each submodule is independently testable via DI. BDD feature files serve as living specification.
- **Channel-agnostic rendering.** Templates work across any delivery channel without modification. Adding a channel means implementing one adapter.
- **Serverless-ready.** Zero network calls at startup. Cold starts are fast and idempotent.
- **Contributor UX.** Scaffolding scripts, co-located docs, and typed base classes reduce onboarding friction.

### Negative

- **Complexity.** ABC+Generic, `__init_subclass__` magic, two-phase validation, and auto-discovery add conceptual overhead compared to the original flat architecture.
- **Learning curve.** Contributors must understand the Generic pattern and the template adapter system.
- **YAML coupling.** All configuration moves to a single YAML file — env-var-only deployments are no longer supported.
- **Indirection.** The dispatch pipeline (orchestrator → rule → template → channel) adds layers that can be harder to trace during debugging.

## Supersedes

- ADR-001 `SignalRule` Protocol → replaced by `SignalRule[ParamsT]` ABC+Generic
- ADR-001 environment variable configuration → replaced by YAML config with `${ENV_VAR}` interpolation
- ADR-001 monolithic `app.py` → decomposed into Orchestrator + thin HTTP adapter
- ADR-001 `signals/` directory → renamed to `rules/` with typed params
- ADR-001 `telegram/` directory → generalised to `delivery/channels/telegram/`
