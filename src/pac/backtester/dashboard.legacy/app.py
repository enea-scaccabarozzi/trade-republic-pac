"""NiceGUI application setup and server lifecycle."""

from __future__ import annotations

from nicegui import ui

# ruff: noqa: F401 — page module imports register @ui.page routes as side effects.
import pac.backtester.dashboard.pages.compare
import pac.backtester.dashboard.pages.result_detail
import pac.backtester.dashboard.pages.results_list
import pac.backtester.dashboard.pages.run


def start(
    *,
    host: str = "127.0.0.1",
    port: int = 8090,
    reload: bool = False,
    title: str = "PAC Backtester",
) -> None:
    """Start the NiceGUI server.

    Args:
        host: Bind address.
        port: Bind port.
        reload: Enable hot-reload for development.
        title: Browser tab title.
    """
    import structlog

    _log = structlog.get_logger()
    _log.info("dashboard_started", url=f"http://{host}:{port}")

    ui.run(
        host=host,
        port=port,
        reload=reload,
        title=title,
        dark=True,
        favicon="🔬",
    )
