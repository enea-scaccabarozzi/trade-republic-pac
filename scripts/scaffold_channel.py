"""Scaffold a new delivery channel subpackage and test file.

Usage:
    python scripts/scaffold_channel.py <channel_name>

Example:
    python scripts/scaffold_channel.py discord
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_SRC_ROOT = Path("src/pac")
_CHANNELS_DIR = _SRC_ROOT / "delivery" / "channels"
_TESTS_DIR = _SRC_ROOT / "delivery" / "tests"


def _to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase: my_channel -> MyChannel."""
    return "".join(part.title() for part in snake.split("_"))


def scaffold_channel(name: str, output_dir: Path | None = None) -> list[Path]:
    """Generate channel subpackage and test file.

    Args:
        name: Channel name in snake_case.
        output_dir: Base directory for output files. Defaults to repo root.

    Returns:
        List of created file paths.

    Raises:
        SystemExit: On validation errors.
    """
    if not _NAME_PATTERN.match(name):
        print(
            f"Error: '{name}' is not a valid channel name. "
            "Use snake_case (e.g. discord)."
        )
        sys.exit(1)

    base = output_dir or Path(".")
    channels_dir = base / _CHANNELS_DIR
    tests_dir = base / _TESTS_DIR
    channel_pkg = channels_dir / name

    # Check directory existence
    if channel_pkg.exists():
        print(f"Error: {channel_pkg} already exists. Aborting.")
        sys.exit(1)

    test_file = tests_dir / f"test_{name}_channel.py"
    if test_file.exists():
        print(f"Error: {test_file} already exists. Aborting.")
        sys.exit(1)

    # Runtime name collision check via discover_channels()
    from pac.delivery.discovery import discover_channels

    existing_channels = discover_channels()
    if name in existing_channels:
        print(
            f"Error: A channel with name '{name}' already exists "
            f"({existing_channels[name].__module__}). Aborting."
        )
        sys.exit(1)

    cls = _to_class_name(name)

    # Ensure directories exist
    channel_pkg.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Generate channel module
    channel_file = channel_pkg / "channel.py"
    channel_content = f'''\
from __future__ import annotations

from pydantic import BaseModel

from pac.delivery.base import DeliveryChannel, RenderedMessage


class {cls}Config(BaseModel):
    """Configuration for the {name} channel. Add your fields here."""


class {cls}Channel(DeliveryChannel[{cls}Config]):
    """TODO: Describe this delivery channel."""

    name = "{name}"

    @property
    def supported_formats(self) -> list[str]:
        return ["plain_text"]

    async def send(self, message: RenderedMessage) -> None:
        # TODO: Implement message delivery
        raise NotImplementedError

    async def start(self) -> None:
        """Called at app startup. Override for setup."""

    async def stop(self) -> None:
        """Called at app shutdown. Override for teardown."""
'''
    channel_file.write_text(channel_content, encoding="utf-8")

    # Generate __init__.py
    init_file = channel_pkg / "__init__.py"
    init_content = f"""\
from __future__ import annotations

from pac.delivery.channels.{name}.channel import (
    {cls}Channel,
    {cls}Config,
)

__all__ = [
    "{cls}Channel",
    "{cls}Config",
]
"""
    init_file.write_text(init_content, encoding="utf-8")

    # Generate test file
    test_content = f"""\
from __future__ import annotations

from pac.delivery.channels.{name}.channel import {cls}Channel, {cls}Config


class TestInit:
    def test_channel_name(self) -> None:
        assert {cls}Channel.name == "{name}"

    def test_config_model_extracted(self) -> None:
        assert {cls}Channel.config_model is {cls}Config
"""
    test_file.write_text(test_content, encoding="utf-8")

    created = [channel_file, init_file, test_file]
    for p in created:
        print(f"  Created: {p}")

    print()
    print(f"Add the channel to pac.yaml under 'channels:' with type: {name}")
    print(
        "If your channel needs a custom format, create a FormatAdapter "
        "subclass in src/pac/templates/adapters/"
    )
    return created


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/scaffold_channel.py <channel_name>")
        sys.exit(1)
    scaffold_channel(sys.argv[1])
