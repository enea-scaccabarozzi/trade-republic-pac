from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from pac.delivery.base import (
    DeliveryChannel,
    RenderedMessage,
    _NoConfig,
)
from pac.models.signals import SignalSeverity


class DummyConfig(BaseModel):
    token: str = "test"


class DummyChannel(DeliveryChannel[DummyConfig]):
    name = "dummy"

    @property
    def supported_formats(self) -> list[str]:
        return ["plain_text"]

    async def send(self, message: RenderedMessage) -> None:
        pass


class FailingChannel(DeliveryChannel[DummyConfig]):
    name = "failing"

    @property
    def supported_formats(self) -> list[str]:
        return ["plain_text"]

    async def send(self, message: RenderedMessage) -> None:
        raise ConnectionError("send failed")


class BareChannel(DeliveryChannel[Any]):
    """Channel without a concrete BaseModel type arg."""

    name = "bare"

    @property
    def supported_formats(self) -> list[str]:
        return []

    async def send(self, message: RenderedMessage) -> None:
        pass


class TestDeliveryChannelABC:
    def test_config_model_auto_extracted(self) -> None:
        assert DummyChannel.config_model is DummyConfig

    def test_no_config_sentinel_on_bare_subclass(self) -> None:
        assert BareChannel.config_model is _NoConfig

    def test_config_stored_on_init(self) -> None:
        config = DummyConfig(token="secret")
        channel = DummyChannel(config)
        assert channel._config is config

    def test_name_is_classvar(self) -> None:
        # Accessible on the class — no instance needed
        assert DummyChannel.name == "dummy"

    async def test_default_start_stop_are_noop(self) -> None:
        channel = DummyChannel(DummyConfig())
        await channel.start()
        await channel.stop()

    async def test_default_process_update_is_noop(self) -> None:
        channel = DummyChannel(DummyConfig())
        await channel.process_update({})

    def test_default_webhook_secret_is_none(self) -> None:
        channel = DummyChannel(DummyConfig())
        assert channel.webhook_secret is None

    def test_abstract_methods_enforced(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):

            class IncompleteChannel(DeliveryChannel[DummyConfig]):
                name = "incomplete"

            IncompleteChannel(DummyConfig())  # type: ignore[abstract]


class TestRenderedMessage:
    def test_rendered_message_fields(self) -> None:
        msg = RenderedMessage(
            content="hello",
            format="markdown_v2",
            signal_name="threshold_deviation",
            severity=SignalSeverity.WARNING,
        )
        assert msg.content == "hello"
        assert msg.format == "markdown_v2"
        assert msg.signal_name == "threshold_deviation"
        assert msg.severity == SignalSeverity.WARNING

    def test_rendered_message_severity_type(self) -> None:
        msg = RenderedMessage(
            content="test",
            format="plain_text",
            signal_name="test_signal",
            severity=SignalSeverity.CRITICAL,
        )
        assert isinstance(msg.severity, SignalSeverity)

    def test_rendered_message_requires_all_fields(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RenderedMessage.model_validate({"content": "hi"})  # missing fields


class TestChannelSendFailure:
    async def test_failing_channel_raises_on_send(self) -> None:
        channel = FailingChannel(DummyConfig())
        msg = RenderedMessage(
            content="test",
            format="plain_text",
            signal_name="test",
            severity=SignalSeverity.INFO,
        )
        with pytest.raises(ConnectionError, match="send failed"):
            await channel.send(msg)
