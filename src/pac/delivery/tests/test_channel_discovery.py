from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from pydantic import BaseModel

from pac.delivery.base import DeliveryChannel
from pac.delivery.channels.telegram.channel import TelegramChannel
from pac.delivery.discovery import discover_channels


class TestDiscoverChannels:
    def test_discover_finds_telegram(self) -> None:
        channels = discover_channels()
        assert "telegram" in channels
        assert channels["telegram"] is TelegramChannel

    def test_discovered_channel_has_config_model(self) -> None:
        channels = discover_channels()
        for name, cls in channels.items():
            assert hasattr(cls, "config_model"), f"{name} missing config_model"
            assert issubclass(cls.config_model, BaseModel)

    def test_discovered_channels_are_delivery_channel_subclasses(self) -> None:
        channels = discover_channels()
        for name, cls in channels.items():
            assert issubclass(
                cls, DeliveryChannel
            ), f"{name} not a DeliveryChannel subclass"

    def test_empty_package_returns_empty(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "empty_channels"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        sys.path.insert(0, str(tmp_path))
        try:
            channels = discover_channels("empty_channels")
            assert len(channels) == 0
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("empty_channels"):
                    del sys.modules[key]

    def test_abstract_channel_ignored(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "abs_channels"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        sub = pkg_dir / "abstract_ch"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "channel.py").write_text(
            textwrap.dedent(
                """\
            from abc import abstractmethod
            from pydantic import BaseModel
            from pac.delivery.base import DeliveryChannel, RenderedMessage

            class AbstractConfig(BaseModel):
                pass

            class AbstractChannel(DeliveryChannel[AbstractConfig]):
                name = "abstract_ch"

                @property
                def supported_formats(self) -> list[str]:
                    return []

                @abstractmethod
                def extra(self) -> None: ...
            """
            )
        )
        sys.path.insert(0, str(tmp_path))
        try:
            channels = discover_channels("abs_channels")
            assert "abstract_ch" not in channels
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("abs_channels"):
                    del sys.modules[key]

    def test_no_channel_py_ignored(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "nochmod_channels"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        sub = pkg_dir / "no_channel"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "helpers.py").write_text("X = 42\n")
        sys.path.insert(0, str(tmp_path))
        try:
            channels = discover_channels("nochmod_channels")
            assert len(channels) == 0
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("nochmod_channels"):
                    del sys.modules[key]

    def test_duplicate_name_last_wins(self, tmp_path: Path) -> None:
        """When two channels in different subpackages share the same name,
        the last one scanned (alphabetically) overwrites the first."""
        pkg_dir = tmp_path / "dup_channels"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        _channel_src = textwrap.dedent(
            """\
            from pydantic import BaseModel
            from pac.delivery.base import DeliveryChannel, RenderedMessage

            class Cfg(BaseModel):
                tag: str = "{tag}"

            class DupChannel(DeliveryChannel[Cfg]):
                name = "duplicate"

                @property
                def supported_formats(self) -> list[str]:
                    return []

                async def send(self, message: RenderedMessage) -> None:
                    pass
            """
        )
        for subname, tag in [("alpha", "first"), ("beta", "second")]:
            sub = pkg_dir / subname
            sub.mkdir()
            (sub / "__init__.py").write_text("")
            (sub / "channel.py").write_text(_channel_src.format(tag=tag))

        sys.path.insert(0, str(tmp_path))
        try:
            channels = discover_channels("dup_channels")
            assert "duplicate" in channels
            # Last alphabetically (beta) overwrites first (alpha)
            field = channels["duplicate"].config_model.model_fields
            assert field["tag"].default == "second"
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("dup_channels"):
                    del sys.modules[key]
