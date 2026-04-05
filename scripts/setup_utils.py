"""Shared utilities for setup scripts.

Provides cache management, Rich UI helpers, and common Typer patterns
used by setup_tr.py, setup_gcp.py, and setup_telegram.py.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# ── Constants ──────────────────────────────────────────────────────────

CACHE_DIR = Path(".pac")
CACHE_VERSION = 1

# ── Console ────────────────────────────────────────────────────────────

_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
    }
)

console = Console(theme=_THEME)

# ── Cache Manager ──────────────────────────────────────────────────────


class CacheManager:
    """Read/write JSON caches under .pac/ with versioning and override support."""

    def __init__(self, name: str, *, cache_dir: Path = CACHE_DIR) -> None:
        self._name = name
        self._path = cache_dir / f"{name}.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any] | None:
        """Load cached data. Returns None if cache doesn't exist."""
        if not self._path.exists():
            return None
        text = self._path.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(text)
        return data

    def save(self, data: dict[str, Any]) -> Path:
        """Save data to cache with metadata. Returns cache file path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_version": CACHE_VERSION,
            "_created_at": datetime.now(UTC).isoformat(),
            **data,
        }
        self._path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        return self._path

    def exists(self) -> bool:
        """Check if cache file exists."""
        return self._path.exists()

    def check_cache(self, *, override: bool) -> dict[str, Any] | None:
        """Load cache and handle override logic.

        Returns cached data if it exists and override is False.
        Returns None if no cache or override is True.
        If cache exists and override is False, also prints cached state.
        """
        if override:
            return None
        data = self.load()
        if data is not None:
            print_cached(self._name, data)
        return data


# ── Rich UI Helpers ────────────────────────────────────────────────────


def print_disclaimer(title: str, message: str) -> None:
    """Display a warning/disclaimer panel before a destructive or external action."""
    console.print()
    console.print(
        Panel(
            message,
            title=f"⚠️  {title}",
            border_style="warning",
            padding=(1, 2),
        )
    )
    console.print()


def confirm_or_exit(message: str = "Do you want to continue?") -> None:
    """Prompt user for confirmation. Exits with code 1 if declined."""
    from rich.prompt import Confirm

    if not Confirm.ask(message, console=console):
        console.print("[warning]Aborted.[/warning]")
        sys.exit(1)


def print_success(title: str, message: str) -> None:
    """Display a success panel."""
    console.print()
    console.print(
        Panel(
            message,
            title=f"✅  {title}",
            border_style="success",
            padding=(1, 2),
        )
    )
    console.print()


def fatal_error(title: str, message: str) -> NoReturn:
    """Display an error panel and exit."""
    console.print()
    console.print(
        Panel(
            message,
            title=f"❌  {title}",
            border_style="error",
            padding=(1, 2),
        )
    )
    console.print()
    sys.exit(1)


def print_cached(name: str, data: dict[str, Any]) -> None:
    """Display cached state as a Rich table."""
    created = data.get("_created_at", "unknown")

    console.print()
    console.print(f"[info]Found cached {name} setup (created: {created})[/info]")

    table = Table(title=f"Cached: {name}", show_lines=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, value in data.items():
        if key.startswith("_"):
            continue
        table.add_row(key, str(value))

    console.print(table)
    console.print()
    console.print("[info]Run with --override to re-run this setup step.[/info]")


# ── .env File Helpers ──────────────────────────────────────────────────

_ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _read_env_value(key: str, *, env_path: Path = Path(".env")) -> str:
    """Read a single value from a .env file without loading into os.environ.

    Returns the value string, or "" if the key is not found or the file
    does not exist.
    """
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        m = _ENV_LINE_RE.match(line)
        if m and m.group(1) == key:
            return m.group(2)
    return ""


def update_env_file(
    updates: dict[str, str],
    *,
    env_path: Path = Path(".env"),
) -> Path:
    """Update or create a .env file with the given key-value pairs.

    - Preserves comments and blank lines
    - Updates existing keys in-place (preserves position)
    - Appends new keys at the end
    - Sets file permissions to 0o600 (owner read/write only)
    - Returns the path to the written file
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    handled: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        m = _ENV_LINE_RE.match(line)
        if m and m.group(1) in updates:
            key = m.group(1)
            new_lines.append(f"{key}={updates[key]}")
            handled.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in handled:
            new_lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    env_path.chmod(0o600)

    updated_keys = ", ".join(updates.keys())
    console.print(f"[info]Updated .env: {updated_keys}[/info]")

    return env_path


def collect_env_from_caches(
    *,
    cache_dir: Path = CACHE_DIR,
    include_job_secret: bool = True,
) -> dict[str, str]:
    """Build env var dict from cached setup results.

    Reads .pac/tr.json and .pac/telegram.json. Generates PAC_JOB_SECRET
    if include_job_secret is True and no existing value is found in
    os.environ or the current .env file.

    Returns:
        Dict of env var name -> value. Only includes keys that have
        non-empty values (skips missing caches gracefully).
    """
    env_vars: dict[str, str] = {}

    # ── TR cache ──
    tr_cache = CacheManager("tr", cache_dir=cache_dir)
    tr_data = tr_cache.load()
    if tr_data:
        phone = tr_data.get("phone_number", "")
        if phone:
            env_vars["TR_PHONE_NUMBER"] = phone

    # ── Telegram cache ──
    tg_cache = CacheManager("telegram", cache_dir=cache_dir)
    tg_data = tg_cache.load()
    if tg_data:
        mapping = {
            "bot_token": "TELEGRAM_BOT_TOKEN",
            "chat_id": "TELEGRAM_CHAT_ID",
            "webhook_url": "TELEGRAM_WEBHOOK_URL",
            "webhook_secret": "TELEGRAM_WEBHOOK_SECRET",
        }
        for cache_key, env_key in mapping.items():
            val = str(tg_data.get(cache_key, ""))
            if val:
                env_vars[env_key] = val

    # ── PAC_JOB_SECRET ──
    if include_job_secret:
        existing = os.environ.get("PAC_JOB_SECRET", "")
        if not existing:
            existing = _read_env_value("PAC_JOB_SECRET")
        if existing:
            env_vars["PAC_JOB_SECRET"] = existing
        else:
            env_vars["PAC_JOB_SECRET"] = secrets.token_urlsafe(32)

    # ── Warn if TR_PIN missing ──
    if "TR_PIN" not in env_vars:
        existing_pin = _read_env_value("TR_PIN")
        if not existing_pin:
            console.print(
                "[yellow]⚠️  TR_PIN is not in caches — set it manually "
                "in .env or via environment[/yellow]"
            )

    return env_vars
