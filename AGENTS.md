# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Automated portfolio rebalancing assistant for Trade Republic. Reads portfolio positions via the `pytr` library (read-only WebSocket API), detects deviations from a configurable target allocation (default 70/15/15: Stocks/Gold/Bonds), and sends Telegram notifications with rebalancing recommendations. **Never executes trades.**

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

## Repository Structure

```
src/pac/
├── __main__.py               # Structlog config + uvicorn runner
├── app.py                    # Thin HTTP adapter over Orchestrator (webhook, signal, health)
├── config/                   # Settings loaded from pac.yaml
│   ├── models.py             # Pydantic config models (AppConfig, BrokerConfig, AssetConfig, etc.)
│   └── loader.py             # YAML loading + ${ENV_VAR} interpolation
├── models/                   # Pydantic data models (portfolio, signals)
├── tr/                       # TRClient wrapper + tr_session() context manager
├── analysis/                 # Deviation calculation, PAC redistribution
├── rules/                    # SignalRule ABC+Generic, registry, auto-discovery
│   └── builtin/              # Threshold, cycle inversion, PAC plan rules
├── delivery/                 # DeliveryChannel ABC+Generic, RenderedMessage, auto-discovery
│   ├── base.py               # DeliveryChannel[ConfigT] ABC + RenderedMessage model
│   ├── discovery.py           # discover_channels() scans channels/ subpackages
│   └── channels/telegram/    # TelegramChannel, bot factory, formatting, keyboards
├── templates/                # Template engine + format adapters
│   ├── engine.py             # TemplateEngine — Jinja2 SandboxedEnvironment + adapter injection
│   └── adapters/             # FormatAdapter ABC + MarkdownV2, PlainText implementations
│   └── builtin/              # .j2 templates (threshold_alert, cycle_alert, pac_plan, portfolio_status)
└── orchestrator/             # Orchestrator class — framework-agnostic signal dispatch pipeline
tests/                        # Shared fixtures + integration tests
docs/                         # Project documentation + ADRs
scripts/                      # DX scaffolding & validation CLIs (scaffold_rule, scaffold_channel, validate_config)
```

Each submodule has co-located `tests/`, `features/`, and `README.md`.

## Key Conventions

### Code Style
- **Formatting:** ruff, 88 char line length
- **Linting:** ruff (rule sets: E, F, I, UP, B, SIM, RUF)
- **Type checking:** mypy strict mode — all code must have type hints
- **Commits:** Conventional Commits (`feat(scope): description`)

### Testing
- **Framework:** pytest with `asyncio_mode = "auto"`
- **Location:** Co-located in each submodule's `tests/` directory; top-level `tests/` for shared fixtures and integration tests
- **Run:** `just test` (or `just test -k test_name` for a single test)
- **BDD:** Feature files in each submodule's `features/` directory

### Commands
- `just sync` — install/update dependencies
- `just hooks-install` — install git hooks (pre-commit, commit-msg, pre-push)
- `just validate` — run all checks (lint + typecheck + test)
- `just format` — auto-format code
- `just lint` — run ruff linter
- `just typecheck` — run mypy
- `just test` — run pytest
- `just new-rule <name>` — scaffold a new signal rule in `src/pac/rules/builtin/`
- `just new-channel <name>` — scaffold a new delivery channel in `src/pac/delivery/channels/`
- `just validate-config` — validate `pac.yaml` against config schema

## Important Patterns

### `tr_session()` Context Manager
All Trade Republic API access goes through `tr_session()` (in `src/pac/tr/client.py`). It opens a WebSocket connection, yields a `TRClient`, and closes the connection on exit. Never hold connections open long-term.

### `SignalRule` ABC + Generic
Signal rules use `ABC + Generic[ParamsT]` (nominal subtyping). Each rule declares a Pydantic params model via its Generic type arg — `__init_subclass__` auto-extracts `params_model`. Rules are stateless; typed params are passed to `evaluate()`. To add a new rule: subclass `SignalRule[YourParams]`, implement `name` and `evaluate()`, and place it in `src/pac/rules/builtin/`. The registry discovers rules automatically via `discover_rules()`.

### `DeliveryChannel` ABC + Generic
Delivery channels use `ABC + Generic[ConfigT]` (same pattern as `SignalRule`). Each channel declares a Pydantic config model via its Generic type arg — `__init_subclass__` auto-extracts `config_model`. Channels implement `name`, `supported_formats`, and `send()`. Optional lifecycle hooks: `start()`, `stop()`, `process_update()`, `webhook_secret`. Interactive features (commands, keyboards) are channel-specific and not part of the ABC. To add a new channel: subclass `DeliveryChannel[YourConfig]`, implement the abstract methods, place a `channel.py` in `src/pac/delivery/channels/<name>/`. Discovery is automatic via `discover_channels()`.

### Template Engine + FormatAdapter
Templates use a Jinja2 `SandboxedEnvironment` (`src/pac/templates/engine.py`). `FormatAdapter` ABC (`adapters/base.py`) defines formatting methods (bold, escape, literal, etc.) injected as Jinja2 globals — templates call `{{ bold(text) }}` without knowing the target format. Two adapters ship built-in: `MarkdownV2Adapter` (Telegram MarkdownV2 escaping) and `PlainTextAdapter` (no markup). `TemplateEngine.render()` takes a template name, data dict, and adapter, returning a `RenderedMessage`. The `literal()` method escapes structural characters (punctuation appearing as fixed text in templates). Four custom filters: `datefmt`, `numberfmt`, `pctfmt`, `eurfmt`.

### Orchestrator
The `Orchestrator` class (`src/pac/orchestrator/orchestrator.py`) is the framework-agnostic dispatch pipeline. `Orchestrator.from_settings()` wires config → rules → templates → channels with zero network calls (serverless-safe cold starts). Key methods: `dispatch_signal()` (full pipeline: evaluate → render → send), `evaluate_signal()` (evaluate only, for interactive handlers), `get_portfolio_status()`, `compute_pac_plan()`. `app.py` is a thin HTTP adapter that delegates to `Orchestrator` — it handles auth and request routing only. Dynamic signal routing via `POST /jobs/signal/{signal_name}` replaces hardcoded per-signal routes. Channels receive the orchestrator via `set_orchestrator()` during startup for interactive DI. Rules implement `build_template_data()` to produce template-specific context.

### YAML Config System
All configuration is loaded from a YAML file (`pac.yaml`) via `load_config()` in `src/pac/config/loader.py`. Secrets use `${ENV_VAR}` interpolation — the loader substitutes env var values before pydantic validation. Config models live in `src/pac/config/models.py` (re-exported via `__init__.py`). Assets are dynamic string-based IDs, not a fixed enum.

## Do NOT Modify

- `pac.yaml.example` default values — these are documented in the README and relied on by users
- Target allocation logic (deviation thresholds, rebalance calculations) without explicit permission from the maintainer
- The read-only guarantee — this tool must never execute trades

## Learned Patterns

| Pattern                                                                               | Location                               | Date    |
| ------------------------------------------------------------------------------------- | -------------------------------------- | ------- |
| All signal rules subclass `SignalRule` ABC+Generic[ParamsT] (not Protocol)            | `src/pac/rules/base.py`                | 2026-04 |
| Rules auto-discovered via `discover_rules()` scanning `pac.rules.builtin`             | `src/pac/rules/discovery.py`           | 2026-04 |
| Configuration loaded from YAML (`pac.yaml`) via `load_config()`                       | `src/pac/config/loader.py`             | 2026-04 |
| Assets are dynamic string IDs (no `AssetClass` enum)                                  | `src/pac/config/models.py`             | 2026-04 |
| TR connections are per-request via `tr_session()` context manager                     | `src/pac/tr/client.py`                 | 2026-04 |
| Telegram webhook validated via `X-Telegram-Bot-Api-Secret-Token` header               | `src/pac/app.py`                       | 2026-04 |
| Job endpoints validated via `X-Job-Secret` header with `hmac.compare_digest`          | `src/pac/app.py`                       | 2026-04 |
| Delivery channels subclass `DeliveryChannel` ABC+Generic[ConfigT]                     | `src/pac/delivery/base.py`             | 2026-04 |
| Channels auto-discovered via `discover_channels()` scanning channel packages          | `src/pac/delivery/discovery.py`        | 2026-04 |
| `RenderedMessage` is the channel-agnostic output model for delivery                   | `src/pac/delivery/base.py`             | 2026-04 |
| Interactive features (commands, keyboards) are Telegram-specific, not in ABC          | `src/pac/delivery/channels/telegram/`  | 2026-04 |
| `TemplateEngine` uses Jinja2 `SandboxedEnvironment` with adapter-injected globals     | `src/pac/templates/engine.py`          | 2026-04 |
| `FormatAdapter` ABC defines channel-agnostic formatting (bold, escape, literal, etc.) | `src/pac/templates/adapters/base.py`   | 2026-04 |
| `MarkdownV2Adapter` and `PlainTextAdapter` are the two built-in adapters              | `src/pac/templates/adapters/`          | 2026-04 |
| 4 builtin .j2 templates: threshold_alert, cycle_alert, pac_plan, portfolio_status     | `src/pac/templates/builtin/`           | 2026-04 |
| `literal()` escapes structural characters that appear as fixed text in templates      | `src/pac/templates/adapters/base.py`   | 2026-04 |
| `Orchestrator.from_settings()` wires config → rules → templates → channels            | `src/pac/orchestrator/orchestrator.py` | 2026-04 |
| `app.py` is a thin HTTP adapter; all business logic lives in `Orchestrator`           | `src/pac/app.py`                       | 2026-04 |
| Dynamic signal routing via `POST /jobs/signal/{signal_name}`                          | `src/pac/app.py`                       | 2026-04 |
| `dispatch_signal()` runs the full pipeline: evaluate → render → send                  | `src/pac/orchestrator/orchestrator.py` | 2026-04 |
| `build_template_data()` classmethod on `SignalRule` produces template context         | `src/pac/rules/base.py`                | 2026-04 |
| `set_orchestrator()` on `DeliveryChannel` injects orchestrator for interactive DI     | `src/pac/delivery/base.py`             | 2026-04 |
| Serverless-first lifespan — zero network calls at startup                             | `src/pac/app.py`                       | 2026-04 |
