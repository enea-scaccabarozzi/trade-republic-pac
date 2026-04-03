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
- **pydantic / pydantic-settings** — data models and configuration
- **structlog** — structured logging
- **uvicorn** — ASGI server

## Repository Structure

```
src/pac/
├── __main__.py           # Structlog config + uvicorn runner
├── app.py                # Starlette ASGI app (webhook, job, health endpoints)
├── config.py             # Settings (pydantic-settings, PAC_ env prefix)
├── models/               # Pydantic data models (portfolio, signals)
├── tr/                   # TRClient wrapper + tr_session() context manager
├── analysis/             # Deviation calculation, PAC redistribution
├── signals/              # SignalRule Protocol, registry, rules/
└── telegram/             # Bot handlers, message formatting, keyboards
tests/                    # pytest test suite
docs/architecture/        # ADRs
```

## Key Conventions

### Code Style
- **Formatting:** ruff, 88 char line length
- **Linting:** ruff (rule sets: E, F, I, UP, B, SIM, RUF)
- **Type checking:** mypy strict mode — all code must have type hints
- **Commits:** Conventional Commits (`feat(scope): description`)

### Testing
- **Framework:** pytest with `asyncio_mode = "auto"`
- **Location:** `tests/` directory, files prefixed `test_`
- **Run:** `just test` (or `just test -k test_name` for a single test)

### Commands
- `just sync` — install/update dependencies
- `just hooks-install` — install git hooks (pre-commit, commit-msg, pre-push)
- `just validate` — run all checks (lint + typecheck + test)
- `just format` — auto-format code
- `just lint` — run ruff linter
- `just typecheck` — run mypy
- `just test` — run pytest

## Important Patterns

### `tr_session()` Context Manager
All Trade Republic API access goes through `tr_session()` (in `src/pac/tr/client.py`). It opens a WebSocket connection, yields a `TRClient`, and closes the connection on exit. Never hold connections open long-term.

### `SignalRule` Protocol
Signal rules use `typing.Protocol` (structural subtyping), not ABC. Rules are stateless — configuration comes from `Settings`. To add a new rule: implement the `SignalRule` protocol and register it in `SignalRegistry` (see `src/pac/signals/`).

### `Settings` via pydantic-settings
All configuration is loaded from environment variables with `PAC_` prefix. See `src/pac/config.py`. The `Settings` class validates that target allocation percentages sum to 100.

## Do NOT Modify

- `.env.example` default values — these are documented in the README and relied on by users
- Target allocation logic (deviation thresholds, rebalance calculations) without explicit permission from the maintainer
- The read-only guarantee — this tool must never execute trades

## Learned Patterns

| Pattern                                                                      | Location                  | Date    |
| ---------------------------------------------------------------------------- | ------------------------- | ------- |
| All signal rules implement `SignalRule` Protocol (not ABC)                   | `src/pac/signals/base.py` | 2026-04 |
| Configuration uses `PAC_` env prefix via pydantic-settings                   | `src/pac/config.py`       | 2026-04 |
| TR connections are per-request via `tr_session()` context manager            | `src/pac/tr/client.py`    | 2026-04 |
| Telegram webhook validated via `X-Telegram-Bot-Api-Secret-Token` header      | `src/pac/app.py`          | 2026-04 |
| Job endpoints validated via `X-Job-Secret` header with `hmac.compare_digest` | `src/pac/app.py`          | 2026-04 |
