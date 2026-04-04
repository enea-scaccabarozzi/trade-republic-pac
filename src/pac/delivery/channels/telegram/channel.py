from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel
from telegram import Update
from telegram.constants import ParseMode

from pac.delivery.base import DeliveryChannel, RenderedMessage

if TYPE_CHECKING:
    from telegram.ext import Application

logger = structlog.get_logger()


class WebhookConfig(BaseModel):
    """Telegram webhook endpoint configuration."""

    url: str = ""
    secret: str = ""


class TelegramConfig(BaseModel):
    """Configuration for the Telegram delivery channel."""

    bot_token: str
    chat_id: str
    webhook: WebhookConfig | None = None


class TelegramChannel(DeliveryChannel[TelegramConfig]):
    """Telegram delivery channel — sends messages via PTB."""

    name = "telegram"

    def __init__(self, config: TelegramConfig) -> None:
        super().__init__(config)
        self._ptb_app: Application | None = None  # type: ignore[type-arg]
        self._orchestrator: Any = None

    @property
    def supported_formats(self) -> list[str]:
        return ["markdown_v2"]

    async def send(self, message: RenderedMessage) -> None:
        """Send a rendered message to the configured Telegram chat.

        Raises:
            RuntimeError: If the channel has not been started.
        """
        if self._ptb_app is None:
            msg = "TelegramChannel not started — call start() first"
            raise RuntimeError(msg)
        await self._ptb_app.bot.send_message(
            chat_id=self._config.chat_id,
            text=message.content,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def set_orchestrator(self, orchestrator: Any) -> None:
        """Store orchestrator for interactive command handlers."""
        self._orchestrator = orchestrator

    async def start(self) -> None:
        """Create the PTB Application, register handlers, and initialize."""
        from pac.delivery.channels.telegram.bot import create_bot_from_app

        self._ptb_app = create_bot_from_app(
            self._config,
            orchestrator=self._orchestrator,
        )
        await self._ptb_app.initialize()
        await self._ptb_app.start()

    async def stop(self) -> None:
        """Shut down the PTB Application and release resources."""
        if self._ptb_app is not None:
            await self._ptb_app.stop()
            await self._ptb_app.shutdown()
            self._ptb_app = None

    async def process_update(self, data: dict[str, Any]) -> None:
        """Process an incoming Telegram webhook update.

        Args:
            data: Raw Telegram update JSON deserialized to a dict.
        """
        if self._ptb_app is None:
            logger.warning("telegram_update_before_start")
            return
        update = Update.de_json(data, self._ptb_app.bot)
        await self._ptb_app.process_update(update)

    @property
    def webhook_secret(self) -> str | None:
        """Return the webhook secret from config, if configured."""
        if self._config.webhook is None:
            return None
        return self._config.webhook.secret or None

    @property
    def ptb_app(self) -> Application | None:  # type: ignore[type-arg]
        """Access the underlying PTB Application (for Telegram-specific use)."""
        return self._ptb_app
