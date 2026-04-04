from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from pac.delivery.base import DeliveryChannel


def discover_channels(
    package: str = "pac.delivery.channels",
) -> dict[str, type[DeliveryChannel[Any]]]:
    """Scan a package for concrete DeliveryChannel subclasses.

    Imports each subpackage that contains a ``channel.py`` module,
    finds all concrete DeliveryChannel subclasses, and returns a
    mapping of {channel_name: channel_class}.

    Import errors are NOT caught — a broken channel module will
    propagate the exception and prevent startup.

    Args:
        package: Dotted package path to scan. Defaults to builtin channels.

    Returns:
        Dict mapping channel name to its class.
    """
    pkg = importlib.import_module(package)
    pkg_path = Path(pkg.__file__).parent  # type: ignore[arg-type]
    discovered: dict[str, type[DeliveryChannel[Any]]] = {}

    for subdir in sorted(pkg_path.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_"):
            continue
        channel_file = subdir / "channel.py"
        if not channel_file.exists():
            continue
        module = importlib.import_module(f"{package}.{subdir.name}.channel")
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, DeliveryChannel)
                and obj is not DeliveryChannel
                and not getattr(obj, "__abstractmethods__", frozenset())
            ):
                discovered[obj.name] = obj

    return discovered
