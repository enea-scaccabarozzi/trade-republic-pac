from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from pac.backtester.strategies.base import BacktestStrategy


def discover_strategies(
    package: str = "pac.backtester.strategies.builtin",
) -> dict[str, type[BacktestStrategy[Any]]]:
    """Scan a package for concrete BacktestStrategy subclasses.

    Imports each .py file (excluding _ prefixed) in the package directory,
    finds all concrete BacktestStrategy subclasses, and returns a mapping
    of {strategy_name: strategy_class}.

    Import errors are NOT caught — a broken strategy module will propagate
    the exception and prevent startup.

    Args:
        package: Dotted package path to scan. Defaults to builtin strategies.

    Returns:
        Dict mapping strategy name to its class.
    """
    pkg = importlib.import_module(package)
    pkg_path = Path(pkg.__file__).parent  # type: ignore[arg-type]
    discovered: dict[str, type[BacktestStrategy[Any]]] = {}

    for path in sorted(pkg_path.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{path.stem}")
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BacktestStrategy)
                and obj is not BacktestStrategy
                and not getattr(obj, "__abstractmethods__", frozenset())
            ):
                # Read name directly from class attribute — no instantiation needed
                discovered[obj.name] = obj

    return discovered
