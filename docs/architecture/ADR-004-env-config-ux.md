# Environment Configuration UX

**Source:** Task 006 (April 2026)

## Decision

Use `.env` as the single canonical surface for runtime secrets, loaded at startup via `python-dotenv`, with setup scripts automatically populating it from `.pac/*.json` caches.

## Why

- Variable names in `.env.example` did not match the `${ENV_VAR}` references in `pac.yaml.example` — users got `ValueError` at startup
- `.env.example` contained 14 stale variables from a pre-YAML config model that were never read
- No `.env` loading at runtime — `just run` ignored `.env` files entirely (only Docker `--env-file` worked)
- Setup scripts wrote to `.pac/*.json` caches but never produced a `.env` — users had to manually transcribe credentials
- `.env` was not gitignored; tracked with empty values, risking accidental secret commits

## Problem Statement

Two disconnected state systems with no bridge:

```
Setup Scripts → .pac/*.json    (caches)
                    ❌ no bridge
pac.yaml ${ENV_VAR} → os.environ ← .env  (but .env never loaded!)
```

Neither the guided path (`just setup`) nor the manual path (copy `.env.example`) produced a working configuration without manual detective work.

## Solution

### Before

```
just setup → .pac/*.json (dead end)
.env.example → wrong variable names → startup crash
just run → os.environ only (no .env loading)
```

### After

```
just setup → .pac/*.json → just generate-env → .env
                                                  ↓
just run → load_dotenv(override=False) → os.environ → pac.yaml ${ENV_VAR}
```

Two working paths:
1. **Guided:** `just setup` → scripts collect credentials → `.env` auto-populated → `just run` works
2. **Manual:** Copy `.env.example` → fill in values → `just run` works

## Implementation Phases

| Phase                    | What Changed                                                                                       |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| 1. Fix .env foundation   | Rewrote `.env.example` with correct names, gitignored `.env`, removed tracked `.env`, added dotenv |
| 2. Bridge scripts → .env | Scripts write `.env` after collecting credentials, added `just generate-env`, updated README       |

## Key Architectural Patterns

### Dotenv Loading in Entry Point

`load_dotenv()` is called in `__main__.py`, not in `loader.py`. This keeps the config loader pure (no side effects) and prevents `.env` files from polluting test runs:

```python
# src/pac/__main__.py
from dotenv import load_dotenv

def main() -> None:
    load_dotenv(override=False)       # .env → os.environ (real env wins)
    from pac.config import load_config
    settings = load_config()
    # ...
```

### Setup Scripts Bridge to .env

Scripts call `update_env_file()` after collecting credentials. `collect_env_from_caches()` reads all `.pac/*.json` caches and maps to canonical env var names:

```python
# scripts/setup_utils.py
def update_env_file(values: dict[str, str], *, env_path: Path = Path(".env")) -> None:
    """Update or create a .env file with the given key-value pairs."""

def collect_env_from_caches() -> dict[str, str]:
    """Read .pac/*.json and return canonical env var dict."""
```

### generate-env Command

Standalone regeneration from caches, also called at the end of `just setup`:

```
just generate-env   # reads .pac/*.json → writes .env
```

## Design Constraints

- `override=False` ensures real environment variables (Docker, Cloud Run) take precedence over `.env` — production deployments are unaffected
- `.env` is gitignored; only `.env.example` is tracked
- `python-dotenv` is an explicit direct dependency (was previously only transitive via uvicorn)
- Config loader (`loader.py`) remains side-effect-free — tests call `load_config()` directly without triggering dotenv
