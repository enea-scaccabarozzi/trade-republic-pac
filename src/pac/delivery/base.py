from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar, get_args

from pydantic import BaseModel

from pac.models.signals import SignalSeverity

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class _NoConfig(BaseModel):
    """Sentinel default for config_model — satisfies mypy strict mode."""


class RenderedMessage(BaseModel):
    """Output of template rendering, ready for delivery."""

    content: str
    format: str
    signal_name: str
    severity: SignalSeverity


class DeliveryChannel(ABC, Generic[ConfigT]):
    """Base class for delivery channels.

    Subclass with a concrete Config type:
        class TelegramChannel(DeliveryChannel[TelegramConfig]): ...

    The framework auto-extracts ``config_model`` from the Generic type arg
    via ``__init_subclass__``. Never set config_model manually.
    """

    config_model: ClassVar[type[BaseModel]] = _NoConfig
    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # __orig_bases__ stores the Generic subscriptions as written in class
        # definition (e.g. DeliveryChannel[TelegramConfig]). We traverse them
        # to extract the concrete ConfigT type arg for automatic config_model
        # resolution — this is how Python's typing module preserves type args
        # that are erased at runtime.
        for base in getattr(cls, "__orig_bases__", []):
            origin = getattr(base, "__origin__", None)
            if origin is DeliveryChannel:
                args = get_args(base)
                if (
                    args
                    and isinstance(args[0], type)
                    and issubclass(args[0], BaseModel)
                ):
                    cls.config_model = args[0]
                    return

    def __init__(self, config: ConfigT) -> None:
        """Initialize with validated channel config.

        Args:
            config: Typed config instance validated by Pydantic.
        """
        self._config = config

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Format names this channel can render (e.g. ['markdown_v2'])."""
        ...

    @abstractmethod
    async def send(self, message: RenderedMessage) -> None:
        """Send a rendered message through this channel."""
        ...

    async def set_orchestrator(self, orchestrator: Any) -> None:
        """Receive orchestrator reference before start().

        Override for channels that need the orchestrator for interactive
        features. Default: no-op.
        """

    async def start(self) -> None:
        """Lifecycle: called at app startup. Override for setup."""

    async def stop(self) -> None:
        """Lifecycle: called at app shutdown. Override for teardown."""

    async def process_update(self, data: dict[str, Any]) -> None:
        """Process an inbound webhook update.

        Override for channels that receive inbound interactions.
        Default: no-op.
        """

    @property
    def webhook_secret(self) -> str | None:
        """Secret for validating inbound webhook requests.

        Override for channels that receive webhooks.
        Default: None (no inbound webhook).
        """
        return None
