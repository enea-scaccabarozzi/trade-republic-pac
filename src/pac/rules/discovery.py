from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from pac.rules.base import SignalRule


def discover_rules(
    package: str = "pac.rules.builtin",
) -> dict[str, type[SignalRule[Any]]]:
    """Scan a package for concrete SignalRule subclasses.

    Imports each .py file (excluding _ prefixed) in the package directory,
    finds all concrete SignalRule subclasses, and returns a mapping of
    {rule_name: rule_class}.

    Import errors are NOT caught — a broken rule module will propagate
    the exception and prevent startup. This is deliberate: a broken rule
    file should fail fast, not silently disappear from the registry.

    Args:
        package: Dotted package path to scan. Defaults to builtin rules.

    Returns:
        Dict mapping rule name to its class.
    """
    pkg = importlib.import_module(package)
    pkg_path = Path(pkg.__file__).parent  # type: ignore[arg-type]
    discovered: dict[str, type[SignalRule[Any]]] = {}

    for path in sorted(pkg_path.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{path.stem}")
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, SignalRule)
                and obj is not SignalRule
                and not getattr(obj, "__abstractmethods__", frozenset())
            ):
                instance = obj()
                discovered[instance.name] = obj

    return discovered
