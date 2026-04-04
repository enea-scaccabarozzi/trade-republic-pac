from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from telegram.constants import ParseMode

from pac.delivery.base import RenderedMessage
from pac.delivery.channels.telegram.channel import (
    TelegramChannel,
    TelegramConfig,
    WebhookConfig,
)
from pac.models.signals import SignalSeverity

scenarios("../features/telegram_delivery.feature")


def _make_message() -> RenderedMessage:
    return RenderedMessage(
        content="*Test*: alert triggered",
        format="markdown_v2",
        signal_name="test_signal",
        severity=SignalSeverity.WARNING,
    )


def _make_config(
    *,
    webhook: WebhookConfig | None = None,
) -> TelegramConfig:
    return TelegramConfig(
        bot_token="test-token",
        chat_id="12345",
        webhook=webhook,
    )


def _mock_ptb_app() -> MagicMock:
    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    mock_app.stop = AsyncMock()
    mock_app.shutdown = AsyncMock()
    return mock_app


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


# ── Given steps ──────────────────────────────────────────────────────


@given("a started Telegram channel", target_fixture="context")
def started_channel() -> dict[str, Any]:
    config = _make_config()
    channel = TelegramChannel(config)
    channel._ptb_app = _mock_ptb_app()
    return {"channel": channel, "message": _make_message()}


@given("an unstarted Telegram channel", target_fixture="context")
def unstarted_channel() -> dict[str, Any]:
    config = _make_config()
    channel = TelegramChannel(config)
    return {"channel": channel, "message": _make_message()}


@given(
    "a started Telegram channel that has been stopped",
    target_fixture="context",
)
def stopped_channel() -> dict[str, Any]:
    import asyncio

    config = _make_config()
    channel = TelegramChannel(config)
    mock_app = _mock_ptb_app()
    channel._ptb_app = mock_app
    asyncio.get_event_loop().run_until_complete(channel.stop())
    return {
        "channel": channel,
        "message": _make_message(),
    }


@given("a Telegram channel configuration", target_fixture="context")
def channel_config() -> dict[str, Any]:
    config = _make_config()
    return {"config": config}


@given("a Telegram channel with webhook configured", target_fixture="context")
def channel_with_webhook() -> dict[str, Any]:
    config = _make_config(
        webhook=WebhookConfig(url="https://example.com", secret="s3cret"),
    )
    return {"config": config}


@given(
    "a Telegram channel without webhook configured",
    target_fixture="context",
)
def channel_without_webhook() -> dict[str, Any]:
    config = _make_config()
    return {"config": config}


# ── When steps ──────────────────────────────────────────────────────


@when("a rendered message is sent through the channel")
def send_message(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    message: RenderedMessage = context["message"]
    try:
        import asyncio

        asyncio.get_event_loop().run_until_complete(channel.send(message))
        context["send_error"] = None
    except RuntimeError as exc:
        context["send_error"] = exc


@when("the channel is created")
def create_channel(context: dict[str, Any]) -> None:
    context["channel"] = TelegramChannel(context["config"])


@when("the channel is started")
def start_channel(context: dict[str, Any]) -> None:
    channel = TelegramChannel(context["config"])
    channel._ptb_app = _mock_ptb_app()
    context["channel"] = channel


@when("a rendered message is sent")
def send_lifecycle_message(context: dict[str, Any]) -> None:
    import asyncio

    channel: TelegramChannel = context["channel"]
    msg = _make_message()
    context["message"] = msg
    asyncio.get_event_loop().run_until_complete(channel.send(msg))


@when("the channel is stopped")
def stop_channel(context: dict[str, Any]) -> None:
    import asyncio

    channel: TelegramChannel = context["channel"]
    if context.get("needs_stop"):
        asyncio.get_event_loop().run_until_complete(channel.stop())
        context["needs_stop"] = False
    else:
        asyncio.get_event_loop().run_until_complete(channel.stop())


# ── Then steps ──────────────────────────────────────────────────────


@then("the message is delivered to the configured chat")
def message_delivered(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    assert context["send_error"] is None
    channel._ptb_app.bot.send_message.assert_awaited_once()  # type: ignore[union-attr]


@then("the message uses MarkdownV2 parse mode")
def message_uses_markdown_v2(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    call_kwargs = channel._ptb_app.bot.send_message.call_args  # type: ignore[union-attr]
    assert call_kwargs.kwargs.get("parse_mode") == ParseMode.MARKDOWN_V2


@then("a RuntimeError is raised")
def runtime_error_raised(context: dict[str, Any]) -> None:
    assert isinstance(context["send_error"], RuntimeError)


@then(parsers.parse('the supported formats include "{fmt}"'))
def formats_include(context: dict[str, Any], fmt: str) -> None:
    channel: TelegramChannel = context["channel"]
    assert fmt in channel.supported_formats


@then(parsers.parse('the channel name is "{name}"'))
def channel_name_is(context: dict[str, Any], name: str) -> None:
    channel: TelegramChannel = context["channel"]
    assert channel.name == name


@then("the webhook secret matches the configured value")
def webhook_secret_matches(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    assert channel.webhook_secret == "s3cret"


@then("the webhook secret is None")
def webhook_secret_none(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    assert channel.webhook_secret is None


@then("the message was delivered successfully")
def message_delivered_lifecycle(context: dict[str, Any]) -> None:
    # No error was raised during send — verified by successful step execution
    assert context.get("send_error") is None or "send_error" not in context


@then("the channel is no longer running")
def channel_not_running(context: dict[str, Any]) -> None:
    channel: TelegramChannel = context["channel"]
    assert channel._ptb_app is None
