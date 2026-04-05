# Developer Setup Scripts

**Source:** Task 004 (April 2026)

## Decision

Provide guided CLI setup scripts under `scripts/` using Typer + Rich, with a `.pac/` JSON cache for idempotent re-runs and a unified `just setup` entry point that chains TR → Telegram → GCP in dependency order.

## Why

- New users must configure three independent external services (Trade Republic, GCP, Telegram) before the app is usable — error-prone when done manually
- Scripts are developer tooling, not runtime code — kept in `scripts/`, excluded from the Docker image via dev-only dependencies
- Idempotent caching (`.pac/`) lets users re-run individual steps without repeating completed work; `--override` forces a fresh run
- Dependency chain (TR → Telegram → GCP) reflects real data dependencies: GCP deploy needs `bot_token`/`chat_id` from Telegram, and webhook registration needs `service_url` from GCP deploy

## Solution

### Script Architecture

```
just setup
  ├── just setup-tr                →  scripts/setup_tr.py
  ├── just setup-telegram --skip-webhook  →  scripts/setup_telegram.py (bot + chat only)
  └── just setup-gcp               →  scripts/setup_gcp.py (deploy + webhook registration)

Standalone:
  just setup-webhook               →  scripts/setup_telegram.py register-webhook

All share:  scripts/setup_utils.py  (cache, Rich helpers, common prompts)
Cache:      .pac/*.json             (gitignored, versioned JSON)
```

### Dependency Chain

```
setup_tr.py          setup_telegram.py         setup_gcp.py
(standalone)    →    (standalone, bot+chat) →  (reads telegram cache)
                     produces bot_token,       deploys Cloud Run,
                     chat_id                   registers webhook with Telegram API,
                                               updates Cloud Run env vars
```

Telegram setup is split into two concerns: **bot creation** (`setup-telegram --skip-webhook`) runs before GCP and needs no external state, while **webhook registration** runs inside `setup-gcp` after deploy produces a `service_url`. A standalone `just setup-webhook` command covers the case where both scripts ran independently and need linking.

Each script is independently runnable with CLI flags for non-interactive use.

## Implementation Phases

| Phase                   | What Changed                                                        |
| ----------------------- | ------------------------------------------------------------------- |
| 1. Foundation           | Added typer/rich/telethon deps, `.pac/` gitignore, `setup_utils.py` |
| 2. Trade Republic setup | `setup_tr.py` — pytr auth flow, credential validation, cache        |
| 3. GCP deploy           | `setup_gcp.py` — gcloud CLI project/deploy/scheduler orchestration  |
| 4. Telegram setup       | `setup_telegram.py` — Telethon BotFather automation, webhook config |
| 5. Unified entry & docs | Justfile recipes (`setup`, `setup-tr`, etc.), README sections       |

## Key Architectural Patterns

### Cache Manager

All scripts share a `CacheManager` for idempotent state persistence:

```python
from scripts.setup_utils import CacheManager

cache = CacheManager("tr")          # reads/writes .pac/tr.json
existing = cache.load()             # dict | None
cache.save({"phone": phone, ...})   # adds _created_at, _version automatically
```

Cache files include `_created_at` and `_version` fields for future compatibility.

### Script CLI Convention

Scripts use Typer with optional CLI flags and an `--override` flag:

```python
import typer
from scripts.setup_utils import CacheManager, console, confirm_or_exit

app = typer.Typer()

@app.command()
def main(
    phone: str = typer.Option("", help="TR phone number"),
    override: bool = typer.Option(False, help="Re-run even if cached"),
) -> None:
    cache = CacheManager("tr")
    if not override and (data := cache.load()):
        print_cached("tr", data)
        return
    confirm_or_exit("This will connect to Trade Republic API.")
    # ... interactive flow ...
```

### Telethon vs python-telegram-bot

Two separate Telegram libraries serve different purposes:

| Library               | Used By             | Purpose                                            |
| --------------------- | ------------------- | -------------------------------------------------- |
| `telethon`            | `setup_telegram.py` | MTProto user client — automates BotFather commands |
| `python-telegram-bot` | Runtime app         | Bot API — receives webhooks, sends messages        |

Telethon is a dev-only dependency. Session files are ephemeral.

## Current Structure

```
scripts/
├── setup_utils.py        # Shared: CacheManager, Rich console/theme, helpers
├── setup_tr.py           # TR auth flow (pytr)
├── setup_gcp.py          # GCP project + Cloud Run + Scheduler + webhook registration
├── setup_telegram.py     # Telethon BotFather + chat_id polling + register-webhook subcommand
├── scaffold_rule.py      # (pre-existing) rule scaffolding
├── scaffold_channel.py   # (pre-existing) channel scaffolding
└── validate_config.py    # (pre-existing) config validation
.pac/                     # gitignored cache directory
├── tr.json
├── gcp.json
└── telegram.json
```

## Updates

| Date       | Task | Summary                                                                                                                        |
| ---------- | ---- | ------------------------------------------------------------------------------------------------------------------------------ |
| April 2026 | 007  | Fixed circular dependency: reordered to TR → Telegram → GCP, split webhook from bot-creation, added `register-webhook` command |
