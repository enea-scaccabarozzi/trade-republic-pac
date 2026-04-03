from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from pac.analysis import calculate_deviations, calculate_pac_plan
from pac.analysis.rebalance import PacPlan
from pac.config import Settings
from pac.models.signals import Signal
from pac.signals import SignalRegistry, create_default_registry
from pac.telegram.formatting import (
    format_pac_plan,
    format_portfolio_status,
    format_signal_alerts,
)
from pac.telegram.keyboards import (
    CALLBACK_REDISTRIBUTE_RECALC,
    pac_plan_keyboard,
)
from pac.tr.client import TRClient
from pac.tr.exceptions import (
    TRClientError,
    TRConnectionError,
    TRSessionExpiredError,
)

if TYPE_CHECKING:
    from telegram import Bot, InlineKeyboardMarkup

logger = structlog.get_logger()


def _authorized(update: Update, settings: Settings) -> bool:
    """Check if the incoming message is from the authorized chat."""
    chat = update.effective_chat
    if chat is None:
        return False
    return str(chat.id) == settings.telegram_chat_id


async def _handle_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /start — greet and list available commands."""
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        return

    text = (
        "*PAC Bot*\n\n"
        "Available commands:\n"
        "/status — portfolio allocation & deviations\n"
        "/rebalance — evaluate rebalance signals\n"
        "/redistribute — calculate monthly PAC plan\n"
        "/help — show this message"
    )
    await update.message.reply_text(  # type: ignore[union-attr]
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _handle_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /help — alias for /start."""
    await _handle_start(update, context)


async def _handle_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /status — show portfolio allocation and deviations."""
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        return

    tr: TRClient = context.bot_data["tr_client"]
    try:
        snapshot = await tr.get_portfolio()
    except TRSessionExpiredError:
        logger.exception("status_session_expired")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Session expired, please re\\-authenticate\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRConnectionError:
        logger.exception("status_connection_error")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Cannot reach Trade Republic\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRClientError:
        logger.exception("status_fetch_failed")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Unexpected TR error\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    report = calculate_deviations(snapshot, settings)
    text = format_portfolio_status(snapshot, report)
    await update.message.reply_text(  # type: ignore[union-attr]
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _handle_rebalance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /rebalance — run signal evaluation and report results."""
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        return

    tr: TRClient = context.bot_data["tr_client"]
    registry: SignalRegistry = context.bot_data["signal_registry"]
    try:
        snapshot = await tr.get_portfolio()
    except TRSessionExpiredError:
        logger.exception("rebalance_session_expired")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Session expired, please re\\-authenticate\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRConnectionError:
        logger.exception("rebalance_connection_error")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Cannot reach Trade Republic\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRClientError:
        logger.exception("rebalance_fetch_failed")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Unexpected TR error\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    report = calculate_deviations(snapshot, settings)
    signals = registry.evaluate_all(report, snapshot, settings)
    text = format_signal_alerts(signals)
    await update.message.reply_text(  # type: ignore[union-attr]
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _handle_redistribute(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /redistribute — calculate and show PAC plan with keyboard."""
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        return

    tr: TRClient = context.bot_data["tr_client"]
    try:
        snapshot = await tr.get_portfolio()
    except TRSessionExpiredError:
        logger.exception("redistribute_session_expired")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Session expired, please re\\-authenticate\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRConnectionError:
        logger.exception("redistribute_connection_error")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Cannot reach Trade Republic\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRClientError:
        logger.exception("redistribute_fetch_failed")
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Unexpected TR error\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    plan = calculate_pac_plan(snapshot, settings)
    text = format_pac_plan(plan)
    await update.message.reply_text(  # type: ignore[union-attr]
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=pac_plan_keyboard(),
    )


async def _handle_redistribute_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline keyboard callback for PAC recalculation."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        return

    tr: TRClient = context.bot_data["tr_client"]
    try:
        snapshot = await tr.get_portfolio()
    except TRSessionExpiredError:
        logger.exception("redistribute_callback_session_expired")
        await query.edit_message_text(
            "❌ Session expired, please re\\-authenticate\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRConnectionError:
        logger.exception("redistribute_callback_connection_error")
        await query.edit_message_text(
            "❌ Cannot reach Trade Republic\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    except TRClientError:
        logger.exception("redistribute_callback_fetch_failed")
        await query.edit_message_text(
            "❌ Unexpected TR error\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    plan = calculate_pac_plan(snapshot, settings)
    text = format_pac_plan(plan)
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=pac_plan_keyboard(),
    )


def create_bot(
    settings: Settings,
    tr_client: TRClient,
    registry: SignalRegistry | None = None,
) -> Application:  # type: ignore[type-arg]
    """Build and configure the Telegram bot Application.

    Args:
        settings: Application settings with bot token and chat ID.
        tr_client: Connected TRClient instance.
        registry: Signal registry. Defaults to create_default_registry().

    Returns:
        Configured telegram.ext.Application (not yet running).
    """
    if registry is None:
        registry = create_default_registry()

    app = Application.builder().token(settings.telegram_bot_token).build()

    app.bot_data["settings"] = settings
    app.bot_data["tr_client"] = tr_client
    app.bot_data["signal_registry"] = registry

    app.add_handler(CommandHandler("start", _handle_start))
    app.add_handler(CommandHandler("help", _handle_help))
    app.add_handler(CommandHandler("status", _handle_status))
    app.add_handler(CommandHandler("rebalance", _handle_rebalance))
    app.add_handler(CommandHandler("redistribute", _handle_redistribute))

    app.add_handler(
        CallbackQueryHandler(
            _handle_redistribute_callback,
            pattern=f"^{CALLBACK_REDISTRIBUTE_RECALC}$",
        )
    )

    return app


# ── Standalone send functions (for Phase 6 scheduler) ──────────────────


async def send_signal_alert(
    bot: Bot,
    chat_id: str,
    signals: list[Signal],
) -> None:
    """Send signal alert(s) to the given chat. Used by scheduler."""
    text = format_signal_alerts(signals)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def send_pac_notification(
    bot: Bot,
    chat_id: str,
    plan: PacPlan,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Send PAC plan notification to the given chat. Used by scheduler."""
    text = format_pac_plan(plan)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )
