# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Automated portfolio rebalancing assistant for Trade Republic. Reads portfolio positions, detects deviations from a configurable target allocation, and sends notifications with rebalancing recommendations. The repository also includes an optional backtesting and research framework for strategy simulation and quantitative experiments.

**Safety invariant**: this tool is read-only — it must never execute trades.

## Tech Stack

- **Python 3.11+** with modern type hints throughout
- **uv** for dependency management, **just** as command runner
- TDD and BDD are the core development approach
- Prefer modern, well-maintained libraries over legacy alternatives
- See `pyproject.toml` for the full dependency list

## Repository Structure

```
src/pac/
├── app.py                  # Thin HTTP adapter over Orchestrator
├── market_context.py       # MarketContext protocol
├── config/                 # YAML config loading + pydantic models
├── models/                 # Pydantic domain models
├── tr/                     # Trade Republic WebSocket client
├── analysis/               # Deviation calculation, PAC redistribution
├── rules/                  # SignalRule ABC+Generic, auto-discovery
├── delivery/               # DeliveryChannel ABC+Generic, auto-discovery
├── templates/              # Jinja2 template engine + format adapters
├── orchestrator/           # Framework-agnostic signal dispatch pipeline
└── backtester/             # Optional: simulation, research, dashboard
    ├── data/               # Price data provider
    ├── engine/             # BacktestSimulator (Monte Carlo)
    ├── strategies/         # BacktestStrategy ABC+Generic, auto-discovery
    ├── metrics/            # quantstats aggregation
    ├── results/            # Timestamped JSON persistence
    ├── research/           # ResearchContext, indicators, events
    ├── api/                # FastAPI REST API
    └── dashboard/          # React + Vite frontend
tests/                      # Shared fixtures + integration tests
scripts/                    # Scaffolding & validation CLIs
research/                   # Experiments, papers, strategy snapshots (not a Python package)
```

Each submodule has co-located `tests/`, `features/`, and a `README.md` with detailed documentation and its own dependency map. Read the relevant submodule README before modifying that module.

## Guidelines

Before working in a specific area, read the relevant reference:

| Topic                                | Reference                                                                |
| ------------------------------------ | ------------------------------------------------------------------------ |
| BDD feature files & step definitions | [docs/bdd.md](docs/bdd.md)                                               |
| Testing philosophy, DI, mocking      | [docs/testing.md](docs/testing.md)                                       |
| Documentation standards              | [docs/documentation.md](docs/documentation.md)                           |
| Crisis indicators research           | [docs/crisis-indicators-research.md](docs/crisis-indicators-research.md) |
| Research experiments & process       | [research/README.md](research/README.md)                                 |

Module dependencies are declared in each submodule's `README.md` under a `## Dependencies` section. Import direction must follow those declarations — circular imports are not permitted.

## Commands

The `Justfile` contains all development commands, organized into:

- **Setup & dependencies** — install, sync, hooks
- **Code quality** — lint, format, typecheck, validate
- **Testing** — pytest with various filters
- **Scaffolding** — `new-rule`, `new-channel`, `new-strategy`, `new-experiment`
- **Backtester** — sync, run, validate
- **Dashboard** — backend API server, frontend dev/build

Run `just --list` to see all available commands.
