from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pac.config import Settings, load_config
from pac.orchestrator import Orchestrator, SignalNotFoundError

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Initialize orchestrator. Zero network calls — fast cold starts."""
    settings = load_config()
    orchestrator = Orchestrator.from_settings(settings)
    await orchestrator.start()

    app.state.settings = settings
    app.state.orchestrator = orchestrator

    yield

    await orchestrator.stop()


async def webhook(request: Request) -> JSONResponse:
    """Handle incoming webhook updates.

    Validates ``X-Telegram-Bot-Api-Secret-Token`` header.
    """
    orchestrator: Orchestrator = request.app.state.orchestrator

    try:
        channel = orchestrator.get_channel("telegram")
    except KeyError:
        return JSONResponse({"error": "no webhook channel"}, status_code=404)

    expected_secret = channel.webhook_secret or ""
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(token, expected_secret):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    await channel.process_update(data)
    return JSONResponse({"ok": True})


async def run_signal(request: Request) -> JSONResponse:
    """Generic signal dispatch — called by external cron scheduler.

    Validates ``X-Job-Secret`` header.
    """
    orchestrator: Orchestrator = request.app.state.orchestrator
    settings: Settings = request.app.state.settings

    secret = request.headers.get("X-Job-Secret", "")
    if not hmac.compare_digest(secret, settings.app.job_secret):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    signal_name = request.path_params["signal_name"]

    try:
        result = await orchestrator.dispatch_signal(signal_name)
        return JSONResponse(
            {
                "ok": True,
                "signal": result.signal_name,
                "signals": result.signal_count,
                "delivered": result.delivered,
            }
        )
    except SignalNotFoundError:
        return JSONResponse(
            {"error": f"unknown signal: {signal_name}"},
            status_code=404,
        )
    except Exception:
        logger.exception("signal_dispatch_error", signal=signal_name)
        return JSONResponse({"error": "internal"}, status_code=500)


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/webhook", webhook, methods=["POST"]),
        Route("/jobs/signal/{signal_name}", run_signal, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ],
    lifespan=lifespan,
)
