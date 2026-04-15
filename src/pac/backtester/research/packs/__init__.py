"""Indicator pack discovery and IndicatorPack protocol."""

from __future__ import annotations

__all__ = ["IndicatorPack", "discover_packs"]

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pac.backtester.research.indicators import IndicatorRegistry


@runtime_checkable
class IndicatorPack(Protocol):
    """Protocol that indicator packs must implement.

    Each pack is a subpackage under packs/ with an __init__.py
    containing a class that satisfies this protocol.
    """

    @property
    def name(self) -> str:
        """Pack name (e.g., "crisis", "tulipy")."""
        ...

    @property
    def description(self) -> str:
        """What this pack provides."""
        ...

    def register(self, registry: IndicatorRegistry) -> None:
        """Register all indicators from this pack into the registry."""
        ...


def discover_packs(
    package: str = "pac.backtester.research.packs",
) -> dict[str, IndicatorPack]:
    """Scan packs/ subdirectories for IndicatorPack implementations.

    Imports each subpackage's __init__.py, finds classes implementing
    IndicatorPack (excluding IndicatorPack itself), instantiates them,
    and returns a mapping of {pack_name: pack_instance}.

    Import errors are NOT caught — a broken pack will propagate
    the exception and prevent usage. Consistent with discover_rules()
    and discover_channels().

    Args:
        package: Dotted package path to scan. Defaults to builtin packs.

    Returns:
        Dict mapping pack name to its instance.
    """
    pkg = importlib.import_module(package)
    pkg_path = Path(pkg.__file__).parent  # type: ignore[arg-type]
    discovered: dict[str, IndicatorPack] = {}

    for subdir in sorted(pkg_path.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_"):
            continue
        init_file = subdir / "__init__.py"
        if not init_file.exists():
            continue
        module = importlib.import_module(f"{package}.{subdir.name}")
        for obj in vars(module).values():
            if not isinstance(obj, type) or obj is IndicatorPack:
                continue
            try:
                instance = obj()
            except Exception:
                continue
            if isinstance(instance, IndicatorPack):
                discovered[instance.name] = instance

    return discovered
