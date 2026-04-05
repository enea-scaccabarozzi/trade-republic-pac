"""Trade Republic credential setup.

Guides through pytr authentication and validates TR API connectivity.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import typer  # noqa: E402
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
    name="setup-tr",
    help="Set up Trade Republic credentials and validate connectivity.",
)

CACHE_NAME = "tr"
DEFAULT_COOKIES_PATH = ".pac/tr_cookies"
PHONE_PATTERN = re.compile(r"^\+\d{7,15}$")


def _mask_pin(pin: str) -> str:
    """Return masked PIN string for display/cache (never store real PIN)."""
    return "*" * len(pin)


def _validate_phone(phone: str) -> None:
    """Validate phone number format (E.164-like: +<digits>, 7-15 digits).

    Raises:
        SystemExit: If phone number is invalid.
    """
    if not PHONE_PATTERN.match(phone):
        fatal_error(
            "Invalid Phone Number",
            f"'{phone}' is not a valid phone number.\n"
            "Expected format: +<country code><number> (e.g. +491234567890)",
        )


def _authenticate(phone: str, pin: str, cookies_path: str) -> None:
    """Run pytr web login flow: initiate -> 2FA code -> complete.

    Creates the TradeRepublicApi, attempts session resume, and if needed
    runs the interactive 2FA flow. Saves cookies on success.

    All pytr weblogin methods are synchronous (requests.Session-based).

    Raises:
        SystemExit: On authentication failure.
    """
    from pytr.api import TradeRepublicApi

    cookies = Path(cookies_path)
    cookies.parent.mkdir(parents=True, exist_ok=True)

    with console.status("[info]Connecting to Trade Republic...[/info]"):
        try:
            tr = TradeRepublicApi(
                phone_no=phone,
                pin=pin,
                save_cookies=True,
                cookies_file=str(cookies),
            )
        except Exception as exc:
            fatal_error(
                "Connection Failed",
                f"Could not initialize Trade Republic client:\n{exc}",
            )

    # Try to resume existing session
    with console.status("[info]Checking existing session...[/info]"):
        if tr.resume_websession():
            console.print("[success]Existing session is still valid.[/success]")
            return

    # No valid session — start web login (2FA flow)
    console.print("[warning]No valid session found. Starting web login...[/warning]")

    with console.status("[info]Requesting verification code...[/info]"):
        try:
            countdown = tr.initiate_weblogin()
        except ValueError as exc:
            fatal_error(
                "Login Failed",
                f"Could not initiate web login:\n{exc}",
            )

    console.print(
        f"\n[info]A 4-digit verification code has been sent to your "
        f"Trade Republic app.[/info]\n"
        f"[dim]If you don't receive it, wait {countdown}s and press "
        f"Enter with no code to request SMS instead.[/dim]\n"
    )

    # Track time spent waiting for user input so we only sleep the remainder
    t0 = time.monotonic()
    code = Prompt.ask("Verification code", console=console)
    elapsed = time.monotonic() - t0

    if not code.strip():
        # User wants SMS — wait out the remaining countdown
        remaining = max(0, countdown - elapsed)
        if remaining > 0:
            with console.status(
                f"[info]Waiting {remaining:.0f}s before requesting SMS...[/info]"
            ):
                time.sleep(remaining)

        try:
            tr.resend_weblogin()
        except Exception as exc:
            fatal_error("SMS Failed", f"Could not request SMS code:\n{exc}")

        code = Prompt.ask("SMS verification code", console=console)

    if not code.strip():
        fatal_error("No Code", "Verification code is required.")

    with console.status("[info]Completing login...[/info]"):
        try:
            tr.complete_weblogin(code.strip())
        except Exception as exc:
            fatal_error(
                "Verification Failed",
                f"Could not complete login with code '{code.strip()}':\n{exc}",
            )

    console.print("[success]Login successful. Session cookies saved.[/success]")


def _validate_session(phone: str, pin: str, cookies_path: str) -> None:
    """Validate that saved cookies produce a working session.

    Creates a fresh TradeRepublicApi and calls resume_websession()
    to confirm the cookies are valid.

    Raises:
        SystemExit: If validation fails.
    """
    from pytr.api import TradeRepublicApi

    with console.status("[info]Validating session...[/info]"):
        try:
            tr = TradeRepublicApi(
                phone_no=phone,
                pin=pin,
                save_cookies=True,
                cookies_file=str(cookies_path),
            )
            if not tr.resume_websession():
                fatal_error(
                    "Validation Failed",
                    "Session cookies could not be validated.\n"
                    "The login may have failed silently. Please try again.",
                )
        except Exception as exc:
            fatal_error(
                "Validation Failed",
                f"Could not validate session:\n{exc}",
            )


@app.command()
def setup(
    phone: str | None = typer.Option(None, help="TR phone number (e.g. +491234567890)"),
    override: bool = typer.Option(False, "--override", help="Re-run even if cached"),
) -> None:
    """Set up and validate Trade Republic credentials.

    PIN is never accepted as a CLI argument (shell history leak).
    In interactive mode it is prompted with masked input;
    in non-interactive mode set the TR_PIN environment variable.
    """
    cache = CacheManager(CACHE_NAME)

    # ── Check cache ──
    cached = cache.check_cache(override=override)
    if cached is not None:
        return

    # ── Disclaimer ──
    print_disclaimer(
        "Trade Republic Setup",
        "This script will:\n"
        "• Connect to the Trade Republic API (read-only)\n"
        "• Request a 2FA verification code via your TR app or SMS\n"
        "• Save session cookies locally for future API access\n\n"
        "[bold]Your PIN is used only for this login and is NOT stored.[/bold]\n"
        "At runtime, provide it via the TR_PIN environment variable.",
    )
    confirm_or_exit()

    # ── Collect credentials ──
    if phone is None:
        phone = Prompt.ask(
            "Trade Republic phone number (e.g. +491234567890)",
            console=console,
        )

    _validate_phone(phone)

    # PIN: never from CLI args — prompt interactively or read from env var
    pin = os.environ.get("TR_PIN")
    if pin is None:
        pin = Prompt.ask(
            "Trade Republic PIN",
            password=True,
            console=console,
        )

    if not pin:
        fatal_error(
            "Missing Input", "PIN is required. Set TR_PIN or enter interactively."
        )

    cookies_path = DEFAULT_COOKIES_PATH

    # ── Authenticate ──
    _authenticate(phone, pin, cookies_path)

    # ── Validate ──
    _validate_session(phone, pin, cookies_path)

    # ── Save cache ──
    cache.save(
        {
            "phone_number": phone,
            "pin": _mask_pin(pin),
            "cookies_path": cookies_path,
            "validated": True,
        }
    )

    # ── Update .env ──
    update_env_file(
        {
            "TR_PHONE_NUMBER": phone,
            "TR_PIN": pin,
        }
    )

    print_success(
        "Trade Republic Setup Complete",
        f"Phone: {phone}\n"
        f"Cookies: {cookies_path}\n\n"
        "[bold].env updated[/bold] with TR_PHONE_NUMBER and TR_PIN.\n"
        f"Cache saved to [cyan]{cache.path}[/cyan]",
    )


if __name__ == "__main__":
    app()
