from __future__ import annotations

from typing import Any

import structlog
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from pac.delivery.channels.telegram.channel import TelegramConfig
from pac.delivery.channels.telegram.formatting import (
    format_pac_plan,
    format_portfolio_status,
    format_signal_alerts,
)
from pac.delivery.channels.telegram.keyboards import (
    CALLBACK_REDISTRIBUTE_RECALC,
    pac_plan_keyboard,
)
from pac.tr.exceptions import (
    TRClientError,
    TRConnectionError,
    TRSessionExpiredError,
)

logger = structlog.get_logger()


def _authorized(update: Update, config: TelegramConfig) -> bool:
    """Check if the incoming message is from the authorized chat."""
    chat = update.effective_chat
    if chat is None:
        return False
    return str(chat.id) == config.chat_id


async def _handle_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /start — greet and list available commands."""
    config: TelegramConfig = context.bot_data["config"]
    if not _authorized(update, config):
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
    orchestrator: Any = context.bot_data["orchestrator"]
    config: TelegramConfig = context.bot_data["config"]
    if not _authorized(update, config):
        return

    try:
        snapshot, report = await orchestrator.get_portfolio_status()
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
    orchestrator: Any = context.bot_data["orchestrator"]
    config: TelegramConfig = context.bot_data["config"]
    if not _authorized(update, config):
        return

    try:
        snapshot, report = await orchestrator.get_portfolio_status()
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

    signals = orchestrator.registry.evaluate_all(report, snapshot)
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
    orchestrator: Any = context.bot_data["orchestrator"]
    config: TelegramConfig = context.bot_data["config"]
    if not _authorized(update, config):
        return

    try:
        pac_signal = _find_pac_signal(orchestrator)
        if pac_signal is None:
            await update.message.reply_text(  # type: ignore[union-attr]
                "No PAC plan signal configured\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        plan = await orchestrator.compute_pac_plan(pac_signal)
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

    orchestrator: Any = context.bot_data["orchestrator"]
    config: TelegramConfig = context.bot_data["config"]
    if not _authorized(update, config):
        return

    try:
        pac_signal = _find_pac_signal(orchestrator)
        if pac_signal is None:
            await query.edit_message_text(
                "No PAC plan signal configured\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        plan = await orchestrator.compute_pac_plan(pac_signal)
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

    text = format_pac_plan(plan)
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=pac_plan_keyboard(),
    )


def _find_pac_signal(orchestrator: Any) -> str | None:
    """Find the first signal configured with pac_plan rule."""
    for sn in orchestrator.signal_names:
        name: str = str(sn)
        sig_config = orchestrator._signal_map.get(name)
        if sig_config and sig_config.rule == "pac_plan":
            return name
    return None


def create_bot_from_app(
    config: TelegramConfig,
    *,
    orchestrator: Any | None = None,
) -> Application:  # type: ignore[type-arg]
    """Build PTB Application from TelegramConfig.

    Args:
        config: Telegram channel configuration.
        orchestrator: Orchestrator instance for interactive handlers.

    Returns:
        Configured telegram.ext.Application (not yet running).
    """
    app = Application.builder().token(config.bot_token).build()

    app.bot_data["config"] = config
    if orchestrator is not None:
        app.bot_data["orchestrator"] = orchestrator

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
