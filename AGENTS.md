# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Automated portfolio rebalancing assistant for Trade Republic. Reads portfolio positions via the `pytr` library (read-only WebSocket API), detects deviations from a configurable target allocation (default 70/15/15: Stocks/Gold/Bonds), and sends Telegram notifications with rebalancing recommendations. **Never executes trades.** The repository also includes an optional backtesting and research framework for strategy simulation, Monte Carlo analysis, and quantitative research experiments.

## Tech Stack

- **Python 3.11+**
- **uv** — package manager
- **just** — command runner (see `Justfile`)
- **Starlette** — ASGI web framework (webhook + job endpoints)
- **FastAPI** — REST API for backtester and research routes
- **pytr** — Trade Republic WebSocket client (read-only)
- **python-telegram-bot** — Telegram bot API
- **pydantic** — data models and configuration validation
- **pyyaml** — YAML config file parsing
- **Jinja2** — template rendering (SandboxedEnvironment)
- **structlog** — structured logging
- **uvicorn** — ASGI server
- **yfinance** — market price data for backtesting
- **quantstats** — portfolio metrics and tearsheet generation
- **React + Vite** — dashboard frontend (optional, built separately)

## Repository Structure

```
src/pac/
├── __main__.py               # Structlog config + uvicorn runner
├── app.py                    # Thin HTTP adapter over Orchestrator (webhook, signal, health)
├── market_context.py         # MarketContext protocol (date-aware price access)
├── live_market_context.py    # Production MarketContext (yfinance + cache)
├── config/                   # Settings loaded from pac.yaml
│   ├── models.py             # Pydantic config models (AppConfig, BrokerConfig, AssetConfig, etc.)
│   └── loader.py             # YAML loading + ${ENV_VAR} interpolation
├── models/                   # Pydantic data models (portfolio, signals, market_data)
├── tr/                       # TRClient wrapper + tr_session() context manager
├── analysis/                 # Deviation calculation, PAC redistribution
├── rules/                    # SignalRule ABC+Generic, registry, auto-discovery
│   └── builtin/              # Threshold, cycle inversion, PAC plan, crisis detection rules (6 crisis + composite)
├── delivery/                 # DeliveryChannel ABC+Generic, RenderedMessage, auto-discovery
│   ├── base.py               # DeliveryChannel[ConfigT] ABC + RenderedMessage model
│   ├── discovery.py          # discover_channels() scans channels/ subpackages
│   └── channels/telegram/    # TelegramChannel, bot factory, formatting, keyboards
├── templates/                # Template engine + format adapters
│   ├── engine.py             # TemplateEngine — Jinja2 SandboxedEnvironment + adapter injection
│   ├── adapters/             # FormatAdapter ABC + MarkdownV2, PlainText implementations
│   └── builtin/              # .j2 templates (threshold_alert, cycle_alert, pac_plan, portfolio_status, crisis_alert)
└── orchestrator/             # Orchestrator class — framework-agnostic signal dispatch pipeline
src/pac/backtester/
├── data/                     # Price data provider (yfinance, proxy tickers)
├── engine/                   # BacktestSimulator — Monte Carlo runner
├── strategies/               # BacktestStrategy ABC+Generic, auto-discovery, builtin/
├── metrics/                  # MetricsCalculator — quantstats aggregation (P5/median/P95)
├── results/                  # ResultStore — timestamped JSON persistence
├── research/                 # Research framework — ResearchContext, indicators, events, OOS
│   ├── context.py            # ResearchContext zero-ceremony API
│   ├── indicators.py         # IndicatorRegistry + opt-in packs
│   ├── events.py             # EventCalendar + MarketEvent
│   └── packs/                # tulipy_bridge/, crisis/
├── api/                      # FastAPI REST API (research routes, run management)
└── dashboard/                # React + Vite frontend (optional)
tests/                        # Shared fixtures + integration tests
docs/                         # Project documentation + ADRs
scripts/                      # DX scaffolding & validation CLIs (scaffold_rule, scaffold_channel, validate_config)
research/                     # Research experiments, papers, strategy snapshots (not a Python package)
├── experiments/              # Auto-managed experiments (NNN-slug/ dirs)
│   └── _template/            # Scaffold template for new experiments
├── papers/                   # Published research papers
└── strategies/               # Named strategy parameter snapshots
```

Each submodule has co-located `tests/`, `features/`, and `README.md`.

## Rules & Guidelines

Detailed standards for specific concerns live in `.claude/rules/`. Load the relevant file before working in that area.

| Rule File | Governs |
|---|---|
| `.claude/rules/bdd.md` | When and how to write BDD feature files and step definitions |
| `.claude/rules/testing.md` | Testing philosophy, DI patterns, mocking boundaries, backtester test patterns |
| `.claude/rules/documentation.md` | Doc standards, submodule README template, docstring style |
| `.claude/rules/dependency-injection.md` | Module dependency declarations, DI conventions, import direction rules |

## Module Dependency Map

Quick-reference for understanding what each module depends on and who consumes it. Import direction must follow this map — circular imports are not permitted.

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
All Trade Republic API access goes through `tr_session()` (in `src/pac/tr/client.py`). It opens a WebSocket connection, yields a `TRClient`, and closes the connection on exit. Never hold connections open long-term.

### `SignalRule` ABC + Generic
Signal rules use `ABC + Generic[ParamsT]` (nominal subtyping). Each rule declares a Pydantic params model via its Generic type arg — `__init_subclass__` auto-extracts `params_model`. Rules are stateless; typed params are passed to `evaluate()`. `evaluate()` accepts an optional `market_ctx: MarketContext | None` parameter (defaults to `None`); rules that don't need market data ignore it, while crisis rules use it for historical price indicator calculations. To add a new rule: subclass `SignalRule[YourParams]`, implement `name` and `evaluate()`, and place it in `src/pac/rules/builtin/`. The registry discovers rules automatically via `discover_rules()`. Rules implement `build_template_data()` to produce template-specific context.

### `DeliveryChannel` ABC + Generic
Delivery channels use `ABC + Generic[ConfigT]` (same pattern as `SignalRule`). Each channel declares a Pydantic config model via its Generic type arg — `__init_subclass__` auto-extracts `config_model`. Channels implement `name`, `supported_formats`, and `send()`. Optional lifecycle hooks: `start()`, `stop()`, `process_update()`, `webhook_secret`. Interactive features (commands, keyboards) are channel-specific and not part of the ABC. To add a new channel: subclass `DeliveryChannel[YourConfig]`, implement the abstract methods, place a `channel.py` in `src/pac/delivery/channels/<name>/`. Discovery is automatic via `discover_channels()`.

### Template Engine + FormatAdapter
Templates use a Jinja2 `SandboxedEnvironment` (`src/pac/templates/engine.py`). `FormatAdapter` ABC (`adapters/base.py`) defines formatting methods (bold, escape, literal, etc.) injected as Jinja2 globals — templates call `{{ bold(text) }}` without knowing the target format. Two adapters ship built-in: `MarkdownV2Adapter` (Telegram MarkdownV2 escaping) and `PlainTextAdapter` (no markup). `TemplateEngine.render()` takes a template name, data dict, and adapter, returning a `RenderedMessage`. The `literal()` method escapes structural characters (punctuation appearing as fixed text in templates). Four custom filters: `datefmt`, `numberfmt`, `pctfmt`, `eurfmt`.

### Orchestrator
The `Orchestrator` class (`src/pac/orchestrator/orchestrator.py`) is the framework-agnostic dispatch pipeline. `Orchestrator.from_settings()` wires config → rules → templates → channels with zero network calls (serverless-safe cold starts). Key methods: `dispatch_signal()` (full pipeline: evaluate → render → send), `evaluate_signal()` (evaluate only, for interactive handlers), `get_portfolio_status()`, `compute_pac_plan()`. `app.py` is a thin HTTP adapter that delegates to `Orchestrator` — it handles auth and request routing only. Dynamic signal routing via `POST /jobs/signal/{signal_name}` replaces hardcoded per-signal routes. Channels receive the orchestrator via `set_orchestrator()` during startup for interactive DI.

### YAML Config System
All configuration is loaded from a YAML file (`pac.yaml`) via `load_config()` in `src/pac/config/loader.py`. Secrets use `${ENV_VAR}` interpolation — the loader substitutes env var values before pydantic validation. Config models live in `src/pac/config/models.py` (re-exported via `__init__.py`). Assets are dynamic string-based IDs, not a fixed enum. Assets need a `ticker: EUNL.DE` field for yfinance resolution; proxy tickers (`proxy_ticker`, `proxy_end`) enable 30+ year backtests with pre-ETF data.

### `MarketContext` Protocol
`MarketContext` (`src/pac/market_context.py`) provides date-aware price access. Two implementations: `LiveMarketContext` (production, yfinance + cache) and `BacktestMarketContext` (injected by the simulator). Crisis rules require `MarketContext` — they return an empty list when `market_ctx is None` (graceful degradation). Pure indicator math lives in `_indicators.py`; both rules and composites call these functions directly.

### `BacktestStrategy` ABC + Generic
Backtest strategies use `ABC + Generic[ParamsT]` (stateful, unlike `SignalRule`). Strategies are auto-discovered via `discover_strategies()` scanning `pac.backtester.strategies.builtin`. The `BacktestStrategy.reset()` hook clears per-iteration state (e.g., cooldown dates) between Monte Carlo runs. The simulator reuses production `SignalRule` instances against synthetic `PortfolioSnapshot` — rules never know they're being backtested. `BacktestSimulator` runs Monte Carlo (N iterations); price data must be pre-loaded as `dict[ticker, PriceSeries]`.

### `ResearchContext` API
`ResearchContext.from_config()` (`src/pac/backtester/research/context.py`) is the zero-ceremony entry point for all research scripts. Quick-test mode (N=1, deterministic, ~10s) is the default. Key methods: `ctx.compare()` and `ctx.sweep()` for variant comparison and parameter sweeps; `ctx.holdout()`, `ctx.walk_forward()`, `ctx.leave_one_event_out()` for OOS validation; `ctx.quantstats()` and `ctx.quantstats_report()` for tearsheets. `IndicatorRegistry` starts empty — load packs via `register_pack("tulipy")` or `register_pack("crisis")`. `EventCalendar` is accessed via `ctx.calendars`.

## Commands

### Core
- `just sync` — install/update dependencies
- `just hooks-install` — install git hooks (pre-commit, commit-msg, pre-push)
- `just validate` — run all checks (lint + typecheck + test)
- `just format` — auto-format code
- `just lint` — run ruff linter
- `just typecheck` — run mypy
- `just test` — run pytest

### Scaffolding
- `just new-rule <name>` — scaffold a new signal rule in `src/pac/rules/builtin/`
- `just new-channel <name>` — scaffold a new delivery channel in `src/pac/delivery/channels/`
- `just new-strategy <name>` — scaffold a new backtest strategy in `src/pac/backtester/strategies/builtin/`
- `just new-experiment <name>` — scaffold a new research experiment in `research/experiments/`
- `just validate-config` — validate `pac.yaml` against config schema

### Backtester
- `just backtest-sync` — install backtester optional dependencies
- `just backtest` — run backtester CLI
- `just backtest-validate` — validate backtester configuration
- `just backtest-validate-quick` — quick validation (no network calls)

### Dashboard
- `just dashboard-sync` — install dashboard backend dependencies
- `just dashboard` — start dashboard backend API server
- `just dashboard-dev` — start dashboard backend in dev/reload mode
- `just dashboard-ui-sync` — install dashboard frontend dependencies
- `just dashboard-ui-dev` — start Vite dev server
- `just dashboard-ui-build` — build frontend for production
- `just dashboard-ui-validate` — lint + typecheck frontend

## Do NOT Modify

- `pac.yaml.example` default values — these are documented in the README and relied on by users
- Target allocation logic (deviation thresholds, rebalance calculations) without explicit permission from the maintainer
- The read-only guarantee — this tool must never execute trades

## Learned Patterns

| Pattern                                                                                                                                            | Location                                                      | Date    |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------- |
| All signal rules subclass `SignalRule` ABC+Generic[ParamsT] (not Protocol)                                                                         | `src/pac/rules/base.py`                                       | 2026-04 |
| Rules auto-discovered via `discover_rules()` scanning `pac.rules.builtin`                                                                          | `src/pac/rules/discovery.py`                                  | 2026-04 |
| Configuration loaded from YAML (`pac.yaml`) via `load_config()`                                                                                    | `src/pac/config/loader.py`                                    | 2026-04 |
| Assets are dynamic string IDs (no `AssetClass` enum)                                                                                               | `src/pac/config/models.py`                                    | 2026-04 |
| TR connections are per-request via `tr_session()` context manager                                                                                  | `src/pac/tr/client.py`                                        | 2026-04 |
| Telegram webhook validated via `X-Telegram-Bot-Api-Secret-Token` header                                                                            | `src/pac/app.py`                                              | 2026-04 |
| Job endpoints validated via `X-Job-Secret` header with `hmac.compare_digest`                                                                       | `src/pac/app.py`                                              | 2026-04 |
| Delivery channels subclass `DeliveryChannel` ABC+Generic[ConfigT]                                                                                  | `src/pac/delivery/base.py`                                    | 2026-04 |
| Channels auto-discovered via `discover_channels()` scanning channel packages                                                                       | `src/pac/delivery/discovery.py`                               | 2026-04 |
| `RenderedMessage` is the channel-agnostic output model for delivery                                                                                | `src/pac/delivery/base.py`                                    | 2026-04 |
| Interactive features (commands, keyboards) are Telegram-specific, not in ABC                                                                       | `src/pac/delivery/channels/telegram/`                         | 2026-04 |
| `TemplateEngine` uses Jinja2 `SandboxedEnvironment` with adapter-injected globals                                                                  | `src/pac/templates/engine.py`                                 | 2026-04 |
| `FormatAdapter` ABC defines channel-agnostic formatting (bold, escape, literal, etc.)                                                              | `src/pac/templates/adapters/base.py`                          | 2026-04 |
| `MarkdownV2Adapter` and `PlainTextAdapter` are the two built-in adapters                                                                           | `src/pac/templates/adapters/`                                 | 2026-04 |
| 5 builtin .j2 templates: threshold_alert, cycle_alert, pac_plan, portfolio_status, crisis_alert                                                    | `src/pac/templates/builtin/`                                  | 2026-04 |
| `literal()` escapes structural characters that appear as fixed text in templates                                                                   | `src/pac/templates/adapters/base.py`                          | 2026-04 |
| `Orchestrator.from_settings()` wires config → rules → templates → channels                                                                         | `src/pac/orchestrator/orchestrator.py`                        | 2026-04 |
| `app.py` is a thin HTTP adapter; all business logic lives in `Orchestrator`                                                                        | `src/pac/app.py`                                              | 2026-04 |
| Dynamic signal routing via `POST /jobs/signal/{signal_name}`                                                                                       | `src/pac/app.py`                                              | 2026-04 |
| `dispatch_signal()` runs the full pipeline: evaluate → render → send                                                                               | `src/pac/orchestrator/orchestrator.py`                        | 2026-04 |
| `build_template_data()` classmethod on `SignalRule` produces template context                                                                      | `src/pac/rules/base.py`                                       | 2026-04 |
| `set_orchestrator()` on `DeliveryChannel` injects orchestrator for interactive DI                                                                  | `src/pac/delivery/base.py`                                    | 2026-04 |
| Serverless-first lifespan — zero network calls at startup                                                                                          | `src/pac/app.py`                                              | 2026-04 |
| All backtest strategies subclass `BacktestStrategy` ABC+Generic[ParamsT] (stateful, unlike SignalRule)                                             | `src/pac/backtester/strategies/base.py`                       | 2026-04 |
| Strategies auto-discovered via `discover_strategies()` scanning `pac.backtester.strategies.builtin`                                                | `src/pac/backtester/strategies/discovery.py`                  | 2026-04 |
| `BacktestSimulator` runs Monte Carlo (N iterations); price data must be pre-loaded as `dict[ticker, PriceSeries]`                                  | `src/pac/backtester/engine/simulator.py`                      | 2026-04 |
| Backtester reuses production `SignalRule` instances against synthetic `PortfolioSnapshot` — rules never know they're being backtested              | `src/pac/backtester/engine/simulator.py`                      | 2026-04 |
| Results persisted as timestamped JSON to `.pac/backtests/` via `ResultStore`; schema includes equity curve bands (P5/median/P95)                   | `src/pac/backtester/results/store.py`                         | 2026-04 |
| Metrics computed via quantstats per MC iteration, aggregated to P5/median/P95 via `MetricsCalculator`                                              | `src/pac/backtester/metrics/calculator.py`                    | 2026-04 |
| Assets need `ticker: EUNL.DE` field in `pac.yaml` for yfinance resolution; `resolve_tickers()` errors on missing tickers                           | `src/pac/backtester/data/provider.py`                         | 2026-04 |
| Backtester is an optional isolated module — zero imports from main `pac` app; install with `just backtest-sync`                                    | `src/pac/backtester/`                                         | 2026-04 |
| Dashboard uses React + Vite with TanStack Router file-based route registration                                                                     | `src/pac/backtester/dashboard/`                               | 2026-04 |
| Dashboard is optional — React app built separately; backend API in `backtester.api`                                                                | `src/pac/backtester/api/`                                     | 2026-04 |
| `run_pipeline()` in `runner.py` is the shared backtest pipeline (CLI + API)                                                                        | `src/pac/backtester/runner.py`                                | 2026-04 |
| `MarketContext` protocol provides date-aware price access; production (`LiveMarketContext`) and backtest (`BacktestMarketContext`) implementations | `src/pac/market_context.py`, `src/pac/live_market_context.py` | 2026-04 |
| Crisis rules require `MarketContext` — return empty list when `market_ctx is None` (graceful degradation)                                          | `src/pac/rules/builtin/`                                      | 2026-04 |
| Pure indicator math lives in `_indicators.py` — rules and composite both call these functions                                                      | `src/pac/rules/builtin/_indicators.py`                        | 2026-04 |
| `CrisisCompositeRule` uses N-of-M voting (default 3/5); no veto guard                                                                              | `src/pac/rules/builtin/crisis_composite.py`                   | 2026-04 |
| `CrisisExploitStrategy` is stateful with cooldown, severity-proportional sell fractions, allocation floors                                         | `src/pac/backtester/strategies/builtin/crisis_exploit.py`     | 2026-04 |
| `BacktestStrategy.reset()` hook clears per-iteration state (e.g., cooldown dates)                                                                  | `src/pac/backtester/strategies/base.py`                       | 2026-04 |
| Proxy tickers (`proxy_ticker`, `proxy_end`) on `AssetConfig` enable 30+ year backtests with pre-ETF data                                           | `src/pac/config/models.py`                                    | 2026-04 |
| `PriceSeries`/`PriceBar`/`Interval` are shared vocabulary in `pac.models.market_data`, re-exported from `pac.backtester.data.models`               | `src/pac/models/market_data.py`                               | 2026-04 |
| `ResearchContext.from_config()` is the zero-ceremony entry point for all research scripts                                                          | `src/pac/backtester/research/context.py`                      | 2026-04 |
| `IndicatorRegistry` starts empty; load packs via `register_pack("tulipy")` or `register_pack("crisis")`                                            | `src/pac/backtester/research/indicators.py`                   | 2026-04 |
| Indicator packs use `IndicatorPack` ABC; tulipy and crisis are built-in                                                                            | `src/pac/backtester/research/packs/`                          | 2026-04 |
| `EventCalendar` system with built-in calendars; accessed via `ctx.calendars`                                                                       | `src/pac/backtester/research/events.py`                       | 2026-04 |
| Experiment state auto-computed from directory contents; `experiment.toml` is immutable seed                                                        | `src/pac/backtester/research/experiment.py`                   | 2026-04 |
| `ExperimentManifest` scans `research/experiments/` for all experiments                                                                             | `src/pac/backtester/research/manifest.py`                     | 2026-04 |
| Quick-test mode (N=1, deterministic, ~10s) is the default research mode                                                                            | `src/pac/backtester/research/context.py`                      | 2026-04 |
| `ctx.compare()` and `ctx.sweep()` for variant comparison and parameter sweeps                                                                      | `src/pac/backtester/research/context.py`                      | 2026-04 |
| OOS validation: `ctx.holdout()`, `ctx.walk_forward()`, `ctx.leave_one_event_out()`                                                                 | `src/pac/backtester/research/context.py`                      | 2026-04 |
| Quantstats integration: `ctx.quantstats()` and `ctx.quantstats_report()` for tearsheets                                                            | `src/pac/backtester/research/context.py`                      | 2026-04 |
| ResultStore now supports `label`, `tags`, `experiment_id` for searchable runs                                                                      | `src/pac/backtester/results/store.py`                         | 2026-04 |
| Research API at `/api/research/*` serves experiments, papers, and strategy files                                                                   | `src/pac/backtester/api/routes/research.py`                   | 2026-04 |
| Dashboard research browser renders experiments, papers, and quantstats reports                                                                     | `src/pac/backtester/dashboard/`                               | 2026-04 |
| `research/` directory holds experiments, papers, and strategy snapshots (not a Python package)                                                     | `research/`                                                   | 2026-04 |
| Scaffold new experiments via `just new-experiment <name>` (uses `scripts/scaffold_experiment.py`)                                                  | `scripts/scaffold_experiment.py`                              | 2026-04 |
