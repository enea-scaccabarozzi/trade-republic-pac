"""Dashboard entry point — run with ``python -m pac.backtester.dashboard``."""

from __future__ import annotations

import sys


def main() -> None:
    """Start the dashboard server."""
    try:
        from nicegui import ui  # noqa: F401 — import check
    except ImportError:
        print(
            "Dashboard requires extra dependencies.\n"
            "Install them with: uv sync --group dashboard",
            file=sys.stderr,
        )
        sys.exit(1)

    from pac.backtester.dashboard.app import start

    start()


if __name__ == "__main__":
    main()
