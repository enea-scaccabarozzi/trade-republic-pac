from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from telegram import Update

from pac.analysis import calculate_deviations, calculate_pac_plan
from pac.config import Settings
from pac.signals import SignalRegistry, create_default_registry
from pac.telegram.bot import (
    create_bot,
    send_pac_notification,
    send_signal_alert,
)
from pac.telegram.keyboards import pac_plan_keyboard
from pac.tr.client import tr_session

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Initialize PTB app at startup, tear down at shutdown."""
    settings = Settings()
    registry = create_default_registry()
    ptb_app = create_bot(settings, registry)

    await ptb_app.initialize()
    await ptb_app.start()

    if settings.webhook_url:
        await ptb_app.bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret,
        )

    app.state.settings = settings
    app.state.ptb_app = ptb_app
    app.state.registry = registry

    yield

    if settings.webhook_url:
        await ptb_app.bot.delete_webhook()
    await ptb_app.stop()
    await ptb_app.shutdown()


async def webhook(request: Request) -> JSONResponse:
    """Handle incoming Telegram webhook updates."""
    settings: Settings = request.app.state.settings
    ptb_app = request.app.state.ptb_app

    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(token, settings.webhook_secret):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return JSONResponse({"ok": True})


async def hourly_check(request: Request) -> JSONResponse:
    """Evaluate signals and send alerts if any fire."""
    settings: Settings = request.app.state.settings
    ptb_app = request.app.state.ptb_app
    registry: SignalRegistry = request.app.state.registry

    secret = request.headers.get("X-Job-Secret", "")
    if not hmac.compare_digest(secret, settings.job_secret):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        async with tr_session(settings) as tr:
            snapshot = await tr.get_portfolio()
        report = calculate_deviations(snapshot, settings)
        signals = registry.evaluate_all(report, snapshot, settings)
        if signals:
            await send_signal_alert(
                ptb_app.bot, settings.telegram_chat_id, signals
            )
        logger.info("hourly_check_done", signal_count=len(signals))
        return JSONResponse({"ok": True, "signals": len(signals)})
    except Exception:
        logger.exception("hourly_check_error")
        return JSONResponse({"error": "internal"}, status_code=500)


async def monthly_pac(request: Request) -> JSONResponse:
    """Calculate PAC plan and send notification."""
    settings: Settings = request.app.state.settings
    ptb_app = request.app.state.ptb_app

    secret = request.headers.get("X-Job-Secret", "")
    if not hmac.compare_digest(secret, settings.job_secret):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        async with tr_session(settings) as tr:
            snapshot = await tr.get_portfolio()
        plan = calculate_pac_plan(snapshot, settings)
        keyboard = pac_plan_keyboard()
        await send_pac_notification(
            ptb_app.bot, settings.telegram_chat_id, plan, keyboard
        )
        logger.info("monthly_pac_done")
        return JSONResponse({"ok": True})
    except Exception:
        logger.exception("monthly_pac_error")
        return JSONResponse({"error": "internal"}, status_code=500)


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/webhook", webhook, methods=["POST"]),
        Route("/jobs/hourly-check", hourly_check, methods=["POST"]),
        Route("/jobs/monthly-pac", monthly_pac, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ],
    lifespan=lifespan,
)
