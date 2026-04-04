from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.constants import ParseMode

from pac.delivery.base import RenderedMessage
from pac.delivery.channels.telegram.channel import (
    TelegramChannel,
    TelegramConfig,
    WebhookConfig,
)
from pac.models.signals import SignalSeverity


@pytest.fixture
def telegram_config() -> TelegramConfig:
    return TelegramConfig(bot_token="test-token", chat_id="12345")


@pytest.fixture
def sample_message() -> RenderedMessage:
    return RenderedMessage(
        content="*Alert*: threshold breached",
        format="markdown_v2",
        signal_name="threshold_deviation",
        severity=SignalSeverity.WARNING,
    )


class TestTelegramChannelProperties:
    def test_name_is_telegram(self) -> None:
        assert TelegramChannel.name == "telegram"

    def test_supported_formats(self, telegram_config: TelegramConfig) -> None:
        channel = TelegramChannel(telegram_config)
        assert channel.supported_formats == ["markdown_v2"]

    def test_config_model_is_telegram_config(self) -> None:
        assert TelegramChannel.config_model is TelegramConfig

    def test_webhook_secret_with_webhook(self) -> None:
        config = TelegramConfig(
            bot_token="t",
            chat_id="1",
            webhook=WebhookConfig(url="https://example.com", secret="s3cret"),
        )
        channel = TelegramChannel(config)
        assert channel.webhook_secret == "s3cret"

    def test_webhook_secret_without_webhook(
        self,
        telegram_config: TelegramConfig,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        assert channel.webhook_secret is None

    def test_webhook_secret_empty_string_is_none(self) -> None:
        config = TelegramConfig(
            bot_token="t",
            chat_id="1",
            webhook=WebhookConfig(url="https://example.com", secret=""),
        )
        channel = TelegramChannel(config)
        assert channel.webhook_secret is None


class TestTelegramChannelSend:
    async def test_send_calls_bot_send_message(
        self,
        telegram_config: TelegramConfig,
        sample_message: RenderedMessage,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        channel._ptb_app = mock_app

        await channel.send(sample_message)

        mock_bot.send_message.assert_awaited_once_with(
            chat_id="12345",
            text="*Alert*: threshold breached",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def test_send_before_start_raises(
        self,
        telegram_config: TelegramConfig,
        sample_message: RenderedMessage,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        with pytest.raises(RuntimeError, match="not started"):
            await channel.send(sample_message)

    async def test_send_after_stop_raises(
        self,
        telegram_config: TelegramConfig,
        sample_message: RenderedMessage,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        # Simulate started state
        mock_app = MagicMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        channel._ptb_app = mock_app

        await channel.stop()

        with pytest.raises(RuntimeError, match="not started"):
            await channel.send(sample_message)


class TestTelegramChannelProcessUpdate:
    async def test_process_update_delegates_to_ptb(
        self,
        telegram_config: TelegramConfig,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        mock_app = MagicMock()
        mock_app.process_update = AsyncMock()
        mock_app.bot = MagicMock()
        channel._ptb_app = mock_app

        with patch(
            "pac.delivery.channels.telegram.channel.Update.de_json",
        ) as mock_de_json:
            mock_update = MagicMock()
            mock_de_json.return_value = mock_update
            await channel.process_update({"update_id": 1})

        mock_app.process_update.assert_awaited_once_with(mock_update)

    async def test_process_update_before_start_logs_warning(
        self,
        telegram_config: TelegramConfig,
    ) -> None:
        channel = TelegramChannel(telegram_config)
        # Should not raise — just logs warning
        await channel.process_update({"update_id": 1})
