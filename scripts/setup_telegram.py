"""Telegram bot setup via BotFather automation.

Creates a Telegram bot, configures webhook, and retrieves chat_id.
Uses Telethon (MTProto) to automate BotFather interaction.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import typer  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Prompt  # noqa: E402

from scripts.setup_utils import (  # noqa: E402
    CacheManager,
    confirm_or_exit,
    console,
    fatal_error,
    print_disclaimer,
    print_success,
    update_env_file,
)

app = typer.Typer(
    name="setup-telegram",
    help="Create and configure a Telegram bot with guided setup.",
)

# ── Constants ──────────────────────────────────────────────────────────

CACHE_NAME = "telegram"
SESSION_PATH = ".pac/telethon"
BOT_TOKEN_PATTERN = re.compile(r"\d+:[A-Za-z0-9_-]{35,}")
BOTFATHER = "BotFather"
BOT_API_BASE = "https://api.telegram.org/bot{token}"
POLL_INTERVAL = 3
POLL_TIMEOUT = 120


# ── Telegram Bot API Helper ───────────────────────────────────────────


def _bot_api(
    token: str, method: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Call the Telegram Bot HTTP API.

    Args:
        token: Bot API token.
        method: API method name (e.g. 'getUpdates', 'setWebhook').
        data: JSON body for POST requests.

    Returns:
        Parsed response JSON.

    Raises:
        SystemExit: On API error.
    """
    url = f"{BOT_API_BASE.format(token=token)}/{method}"
    if data is not None:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
        )
    else:
        req = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result: dict[str, Any] = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else "(no body)"
        fatal_error(
            "Telegram API Error",
            f"Method: {method}\nStatus: {exc.code}\nResponse: {error_body}",
        )
    except urllib.error.URLError as exc:
        fatal_error(
            "Telegram API Error",
            f"Could not reach Telegram API: {exc.reason}",
        )

    if not result.get("ok"):
        fatal_error(
            "Telegram API Error",
            f"Method: {method}\nResponse: {result.get('description', 'unknown error')}",
        )

    return result


# ── Telethon Authentication ────────────────────────────────────────────


async def _connect_telethon(
    api_id: int,
    api_hash: str,
    phone: str,
) -> Any:
    """Authenticate user's Telegram account via Telethon.

    Connects using the user's personal Telegram account (MTProto).
    Handles phone -> verification code -> optional 2FA password flow.
    Session is stored in .pac/telethon.session.

    Returns:
        Connected TelegramClient instance.
    """
    from telethon import TelegramClient

    session = Path(SESSION_PATH)
    session.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session), api_id, api_hash)

    def phone_cb() -> str:
        return phone

    def code_cb() -> str:
        return Prompt.ask(
            "Telegram verification code (check your Telegram app)",
            console=console,
        )

    def password_cb() -> str:
        return Prompt.ask(
            "2FA password",
            password=True,
            console=console,
        )

    await client.start(
        phone=phone_cb,
        code_callback=code_cb,
        password=password_cb,
    )

    return client


# ── BotFather Automation ───────────────────────────────────────────────


async def _create_bot(client: Any, bot_name: str, bot_username: str) -> str:
    """Create a new bot via BotFather.

    Sends /newbot to @BotFather, then the bot name and username.
    Parses the response to extract the bot token.

    Args:
        client: Connected TelegramClient.
        bot_name: Display name for the bot.
        bot_username: Username for the bot (must end in 'bot').

    Returns:
        The bot API token.

    Raises:
        SystemExit: If bot creation fails or token cannot be extracted.
    """
    import asyncio as _asyncio

    async def _send_and_wait(text: str, max_wait: float = 10.0) -> str:
        """Send a message to BotFather and wait for the reply."""
        await client.send_message(BOTFATHER, text)
        deadline = _asyncio.get_event_loop().time() + max_wait
        while _asyncio.get_event_loop().time() < deadline:
            await _asyncio.sleep(1.0)
            async for message in client.iter_messages(BOTFATHER, limit=1):
                if not message.out:
                    return str(message.text)
        fatal_error(
            "BotFather Error",
            f"No response from BotFather after {max_wait}s. Sent: {text}",
        )

    with console.status("[info]Creating bot via BotFather...[/info]"):
        # Step 1: /newbot
        resp1 = await _send_and_wait("/newbot")
        if "choose a name" not in resp1.lower():
            fatal_error(
                "BotFather Error",
                f"Unexpected response to /newbot:\n{resp1}",
            )

        # Step 2: send bot display name
        resp2 = await _send_and_wait(bot_name)
        if "username" not in resp2.lower():
            fatal_error(
                "BotFather Error",
                f"Unexpected response to bot name:\n{resp2}",
            )

        # Step 3: send bot username
        resp3 = await _send_and_wait(bot_username)

    # Extract token from response
    token_match = BOT_TOKEN_PATTERN.search(resp3)
    if not token_match:
        fatal_error(
            "Token Extraction Failed",
            f"Could not find bot token in BotFather response:\n{resp3}"
            "\n\nThe username may already be taken."
            " Try again with --override.",
        )

    token = token_match.group(0)
    console.print(f"[success]Bot @{bot_username} created successfully.[/success]")
    return token


# ── Username Validation ────────────────────────────────────────────────


def _validate_bot_username(username: str) -> None:
    """Validate bot username ends with 'bot' (case-insensitive).

    Raises:
        SystemExit: If username is invalid.
    """
    if not username.lower().endswith("bot"):
        fatal_error(
            "Invalid Username",
            f"'{username}' must end with 'bot' (e.g. 'my_pac_bot').",
        )
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]{1,}[Bb][Oo][Tt]$", username):
        fatal_error(
            "Invalid Username",
            f"'{username}' is not a valid bot username.\n"
            "Must start with a letter, contain only"
            " letters/digits/underscores,\n"
            "be at least 5 characters (including 'bot' suffix),"
            " and end with 'bot'.",
        )


# ── Chat ID Polling ───────────────────────────────────────────────────


def _poll_chat_id(token: str) -> str:
    """Poll for /start message to get the user's chat_id.

    After the bot is created, the user must open the bot in Telegram
    and send /start. This function polls getUpdates until it finds
    a /start message, then returns the chat_id.

    Returns:
        The chat_id as a string.

    Raises:
        SystemExit: If polling times out.
    """
    console.print()
    console.print(
        "[info]Now open your new bot in Telegram and send"
        " [bold]/start[/bold].[/info]\n"
        "[dim]You can find the bot by searching for its"
        " username in Telegram.[/dim]"
    )
    console.print()

    # Flush any existing updates and capture last update_id
    flush = _bot_api(token, "getUpdates", {"offset": -1, "limit": 1})
    flush_updates = flush.get("result", [])
    last_update_id = flush_updates[-1]["update_id"] if flush_updates else 0

    deadline = time.monotonic() + POLL_TIMEOUT

    with console.status(
        f"[info]Waiting for /start message (timeout: {POLL_TIMEOUT}s)...[/info]"
    ):
        while time.monotonic() < deadline:
            result = _bot_api(
                token,
                "getUpdates",
                {
                    "offset": last_update_id + 1,
                    "timeout": POLL_INTERVAL,
                },
            )
            updates = result.get("result", [])
            for update in updates:
                last_update_id = update.get("update_id", last_update_id)
                message = update.get("message", {})
                text = message.get("text", "")
                chat = message.get("chat", {})
                chat_id = chat.get("id")

                if text.strip() == "/start" and chat_id:
                    console.print(
                        f"[success]Received /start from chat {chat_id}[/success]"
                    )
                    return str(chat_id)

    fatal_error(
        "Timeout",
        f"No /start message received within {POLL_TIMEOUT}"
        " seconds.\nOpen your bot in Telegram, send /start,"
        " and re-run with --override.",
    )


# ── Webhook ────────────────────────────────────────────────────────────


def _detect_webhook_url() -> str | None:
    """Auto-detect webhook URL from GCP cache if available.

    Returns:
        Webhook URL (service_url + /webhook) or None if not cached.
    """
    gcp_cache = CacheManager("gcp").load()
    if gcp_cache:
        service_url = gcp_cache.get("service_url", "")
        if service_url:
            webhook_url = f"{service_url.rstrip('/')}/webhook"
            console.print(
                f"[info]Detected webhook URL from GCP cache: {webhook_url}[/info]"
            )
            return webhook_url
    return None


def _register_webhook(token: str, webhook_url: str, webhook_secret: str) -> None:
    """Register webhook URL with Telegram Bot API.

    Args:
        token: Bot API token.
        webhook_url: Full webhook URL.
        webhook_secret: Secret token for webhook verification.

    Raises:
        SystemExit: If webhook registration fails.
    """
    with console.status("[info]Registering webhook...[/info]"):
        _bot_api(
            token,
            "setWebhook",
            {
                "url": webhook_url,
                "secret_token": webhook_secret,
            },
        )
    console.print(f"[success]Webhook registered: {webhook_url}[/success]")


# ── Partial Cache Helper ──────────────────────────────────────────────


def _is_partial_cache(data: dict[str, Any]) -> bool:
    """Check if cache has bot_token but is missing chat_id.

    This indicates bot creation succeeded but chat_id polling was
    interrupted. On re-run we can skip bot creation and resume
    from chat_id polling.
    """
    return bool(data.get("bot_token")) and not data.get("chat_id")


# ── Session Cleanup ───────────────────────────────────────────────────


def _cleanup_session() -> None:
    """Remove Telethon session file from .pac/.

    After bot creation completes, the session file is no longer needed.
    We clean it up to avoid leaving auth material on disk.
    """
    for ext in ("", ".session"):
        path = Path(f"{SESSION_PATH}{ext}")
        if path.exists():
            path.unlink()


# ── Main Async Flow ───────────────────────────────────────────────────


async def _run_setup(
    *,
    bot_name: str,
    bot_username: str,
    phone: str,
    api_id: int,
    api_hash: str,
    skip_webhook: bool = False,
) -> dict[str, str]:
    """Run the full Telegram setup flow (async).

    1. Connect to Telegram as user (Telethon)
    2. Create bot via BotFather
    3. Disconnect Telethon + clean up session
    4. Poll for /start -> chat_id (sync, uses Bot HTTP API)
    5. Register webhook (sync, uses Bot HTTP API)

    Returns:
        Dict with bot_token, bot_username, chat_id,
        webhook_url, webhook_secret.
    """
    # ── Telethon: create bot ──
    client = await _connect_telethon(api_id, api_hash, phone)
    try:
        bot_token = await _create_bot(client, bot_name, bot_username)
    finally:
        await client.disconnect()
        _cleanup_session()

    # ── Save partial cache immediately after bot creation ──
    partial_cache = CacheManager(CACHE_NAME)
    partial_cache.save({"bot_token": bot_token, "bot_username": bot_username})

    # ── Bot API: get chat_id ──
    chat_id = _poll_chat_id(bot_token)

    # ── Webhook ──
    if skip_webhook:
        return {
            "bot_token": bot_token,
            "bot_username": bot_username,
            "chat_id": chat_id,
        }

    webhook_url = _detect_webhook_url()
    if webhook_url is None:
        webhook_url = Prompt.ask(
            "Webhook URL (e.g. https://your-service.run.app/webhook)",
            console=console,
        )

    webhook_secret = secrets.token_hex(32)
    _register_webhook(bot_token, webhook_url, webhook_secret)

    return {
        "bot_token": bot_token,
        "bot_username": bot_username,
        "chat_id": chat_id,
        "webhook_url": webhook_url,
        "webhook_secret": webhook_secret,
    }


# ── Typer Command ─────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def setup(
    ctx: typer.Context,
    bot_name: str | None = typer.Option(None, "--bot-name", help="Bot display name"),
    bot_username: str | None = typer.Option(
        None,
        "--bot-username",
        help="Bot username (must end in 'bot')",
    ),
    override: bool = typer.Option(False, "--override", help="Re-run even if cached"),
    skip_webhook: bool = typer.Option(
        False,
        "--skip-webhook",
        help="Skip webhook registration (done later by GCP deploy)",
    ),
) -> None:
    """Create a Telegram bot and configure webhook.

    Bot token and webhook secret are sensitive — they are never accepted
    as CLI flags. api_id/api_hash can be provided via TELEGRAM_API_ID
    and TELEGRAM_API_HASH environment variables.
    """
    if ctx is not None and ctx.invoked_subcommand is not None:
        return

    cache = CacheManager(CACHE_NAME)

    # ── Check cache ──
    cached = cache.load()
    if cached and not override:
        # ── Partial recovery ──
        if _is_partial_cache(cached):
            console.print(
                "[warning]Partial cache detected — bot was created"
                " but chat_id is missing."
                " Resuming from chat_id polling...[/warning]"
            )
            bot_token = cached["bot_token"]
            bot_username_cached: str = cached["bot_username"]
            chat_id = _poll_chat_id(bot_token)

            result: dict[str, str] = {
                "bot_token": bot_token,
                "bot_username": bot_username_cached,
                "chat_id": chat_id,
            }

            if not skip_webhook:
                webhook_url = _detect_webhook_url()
                if webhook_url is None:
                    webhook_url = Prompt.ask(
                        "Webhook URL (e.g. https://your-service.run.app/webhook)",
                        console=console,
                    )
                webhook_secret = secrets.token_hex(32)
                _register_webhook(bot_token, webhook_url, webhook_secret)
                result["webhook_url"] = webhook_url
                result["webhook_secret"] = webhook_secret

            cache.save(result)
            env_updates: dict[str, str] = {
                "TELEGRAM_BOT_TOKEN": bot_token,
                "TELEGRAM_CHAT_ID": chat_id,
            }
            if "webhook_url" in result:
                env_updates["TELEGRAM_WEBHOOK_URL"] = result["webhook_url"]
                env_updates["TELEGRAM_WEBHOOK_SECRET"] = result["webhook_secret"]
            update_env_file(env_updates)

            if skip_webhook:
                print_success(
                    "Telegram Bot Setup Complete (recovered, webhook pending)",
                    f"Bot:      @{bot_username_cached}\n"
                    f"Chat ID:  {chat_id}\n\n"
                    "[bold].env updated[/bold] with"
                    " TELEGRAM_BOT_TOKEN and"
                    " TELEGRAM_CHAT_ID.\n"
                    "[dim]Webhook registration will happen"
                    " during GCP deploy.[/dim]\n\n"
                    f"Cache saved to [cyan]{cache.path}[/cyan]",
                )
            else:
                print_success(
                    "Telegram Bot Setup Complete (recovered)",
                    f"Bot:      @{bot_username_cached}\n"
                    f"Chat ID:  {chat_id}\n"
                    f"Webhook:  {result['webhook_url']}\n\n"
                    "[bold].env updated[/bold] with"
                    " TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,\n"
                    "TELEGRAM_WEBHOOK_URL, and"
                    " TELEGRAM_WEBHOOK_SECRET.\n\n"
                    f"Cache saved to [cyan]{cache.path}[/cyan]",
                )
            return

        # ── Full cache hit — nothing to do ──
        cache.check_cache(override=override)
        return

    # ── Disclaimer ──
    print_disclaimer(
        "Telegram Bot Setup",
        "This script will:\n"
        "\u2022 Log into your personal Telegram account"
        " (via Telethon MTProto)\n"
        "\u2022 Send messages to @BotFather to create a new bot\n"
        "\u2022 Poll for your /start message to get your chat_id\n"
        "\u2022 Register a webhook URL with the Telegram Bot API"
        "\n\n"
        "[bold]Requirements:[/bold]\n"
        "\u2022 A Telegram account\n"
        "\u2022 API credentials from https://my.telegram.org\n\n"
        "[bold]Your Telegram session is temporary[/bold] — the"
        " session\nfile is deleted after bot creation completes.",
    )
    confirm_or_exit()

    # ── Guide through my.telegram.org ──
    console.print()
    console.print(
        Panel(
            "To automate bot creation, this script needs your"
            " Telegram API\ncredentials (api_id and api_hash)."
            " These are different from\nthe bot token.\n\n"
            "[bold]Steps:[/bold]\n"
            "1. Go to [link=https://my.telegram.org]"
            "https://my.telegram.org[/link]\n"
            "2. Log in with your phone number\n"
            "3. Click 'API development tools'\n"
            "4. Create an application (any name/URL is fine)\n"
            "5. Copy the [bold]api_id[/bold] (number) and"
            " [bold]api_hash[/bold] (string)\n\n"
            "[dim]You can also set TELEGRAM_API_ID and"
            " TELEGRAM_API_HASH\n"
            "environment variables to skip these prompts.[/dim]",
            title="\U0001f4f1 Telegram API Credentials",
            border_style="info",
        )
    )
    console.print()

    # ── Collect api_id / api_hash (env var fallback) ──
    api_id_str = os.environ.get("TELEGRAM_API_ID") or Prompt.ask(
        "Telegram API ID (number)", console=console
    )
    try:
        api_id = int(api_id_str)
    except ValueError:
        fatal_error(
            "Invalid API ID",
            f"'{api_id_str}' is not a valid integer.",
        )

    api_hash = os.environ.get("TELEGRAM_API_HASH") or Prompt.ask(
        "Telegram API hash (string)", console=console
    )
    if not api_hash.strip():
        fatal_error("Missing Input", "API hash is required.")

    # ── Collect phone number ──
    phone = Prompt.ask(
        "Your Telegram phone number (e.g. +491234567890)",
        console=console,
    )

    # ── Collect bot details ──
    if bot_name is None:
        bot_name = Prompt.ask(
            "Bot display name (e.g. 'My PAC Bot')",
            console=console,
        )

    if bot_username is None:
        bot_username = Prompt.ask(
            "Bot username (must end in 'bot', e.g. 'my_pac_bot')",
            console=console,
        )

    _validate_bot_username(bot_username)

    # ── Run async setup ──
    result = asyncio.run(
        _run_setup(
            bot_name=bot_name,
            bot_username=bot_username,
            phone=phone,
            api_id=api_id,
            api_hash=api_hash,
            skip_webhook=skip_webhook,
        )
    )

    # ── Save cache ──
    cache.save(result)

    # ── Update .env ──
    env_vars: dict[str, str] = {
        "TELEGRAM_BOT_TOKEN": result["bot_token"],
        "TELEGRAM_CHAT_ID": result["chat_id"],
    }
    if "webhook_url" in result:
        env_vars["TELEGRAM_WEBHOOK_URL"] = result["webhook_url"]
        env_vars["TELEGRAM_WEBHOOK_SECRET"] = result["webhook_secret"]
    update_env_file(env_vars)

    if skip_webhook:
        print_success(
            "Telegram Bot Setup Complete (webhook pending)",
            f"Bot:      @{result['bot_username']}\n"
            f"Chat ID:  {result['chat_id']}\n\n"
            "[bold].env updated[/bold] with"
            " TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.\n"
            "[dim]Webhook registration will happen"
            " during GCP deploy.[/dim]\n\n"
            f"Cache saved to [cyan]{cache.path}[/cyan]",
        )
    else:
        print_success(
            "Telegram Bot Setup Complete",
            f"Bot:      @{result['bot_username']}\n"
            f"Chat ID:  {result['chat_id']}\n"
            f"Webhook:  {result['webhook_url']}\n\n"
            "[bold].env updated[/bold] with TELEGRAM_BOT_TOKEN,"
            " TELEGRAM_CHAT_ID,\n"
            "TELEGRAM_WEBHOOK_URL, and"
            " TELEGRAM_WEBHOOK_SECRET.\n\n"
            f"Cache saved to [cyan]{cache.path}[/cyan]",
        )


# ── Register Webhook Command ─────────────────────────────────────────


@app.command(name="register-webhook")
def register_webhook(
    override: bool = typer.Option(
        False,
        "--override",
        help="Re-register even if webhook is already cached",
    ),
) -> None:
    """Register Telegram webhook using cached setup results.

    Reads bot_token from .pac/telegram.json and service_url from
    .pac/gcp.json. Generates a webhook_secret, calls setWebhook,
    then updates both caches and .env.

    Use this after running 'setup-telegram --skip-webhook' and
    'setup-gcp' separately.
    """
    cache = CacheManager(CACHE_NAME)
    cached = cache.load()

    if not cached or not cached.get("bot_token"):
        fatal_error(
            "No Telegram Cache",
            "No bot_token found in .pac/telegram.json.\n"
            "Run 'just setup-telegram' first.",
        )

    bot_token: str = cached["bot_token"]

    if not override and cached.get("webhook_url") and cached.get("webhook_secret"):
        console.print(
            f"[info]Webhook already registered:"
            f" {cached['webhook_url']}[/info]\n"
            "[dim]Use --override to re-register.[/dim]"
        )
        return

    webhook_url = _detect_webhook_url()
    if webhook_url is None:
        fatal_error(
            "No GCP Cache",
            "Could not detect webhook URL from .pac/gcp.json.\n"
            "Run 'just setup-gcp' first.",
        )

    webhook_secret = secrets.token_hex(32)
    _register_webhook(bot_token, webhook_url, webhook_secret)

    # Update telegram cache with webhook keys
    updated = {k: v for k, v in cached.items() if not k.startswith("_")}
    updated["webhook_url"] = webhook_url
    updated["webhook_secret"] = webhook_secret
    cache.save(updated)

    update_env_file(
        {
            "TELEGRAM_WEBHOOK_URL": webhook_url,
            "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
        }
    )

    print_success(
        "Webhook Registered",
        f"Webhook URL: {webhook_url}\n\n"
        "[bold].env updated[/bold] with"
        " TELEGRAM_WEBHOOK_URL and"
        " TELEGRAM_WEBHOOK_SECRET.\n\n"
        f"Cache saved to [cyan]{cache.path}[/cyan]",
    )

    console.print(
        "\n[warning]⚠️  Cloud Run env vars"
        " (TELEGRAM_WEBHOOK_SECRET) were NOT updated.\n"
        "If you need them in sync, re-deploy with"
        " 'just setup-gcp --override'\n"
        "or run 'gcloud run services update'"
        " manually.[/warning]"
    )


if __name__ == "__main__":
    app()
