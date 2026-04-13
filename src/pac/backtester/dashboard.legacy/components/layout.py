"""Shared layout shell — header, sidebar, dark mode toggle."""

from __future__ import annotations

from nicegui import ui

# Navigation items: (label, icon, route)
NAV_ITEMS: list[tuple[str, str, str]] = [
    ("Results", "list", "/"),
    ("Run Backtest", "play_arrow", "/run"),
    ("Compare", "compare_arrows", "/compare"),
]


def render_layout(*, active: str = "/") -> None:
    """Render the shared app shell (header + sidebar).

    Call this at the top of every @ui.page function.

    Args:
        active: The route path of the current page (for highlighting).
    """
    dark = ui.dark_mode()

    with ui.header(elevated=True).classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("science").classes("text-2xl")
            ui.label("PAC Backtester").classes("text-h6 font-bold")

        ui.switch(
            "Dark mode",
            value=True,
            on_change=lambda e: dark.set_value(e.value),
        )

    with ui.left_drawer(top_corner=True, bottom_corner=True).classes(
        "bg-slate-50 dark:bg-slate-800"
    ):
        ui.label("Navigation").classes("text-caption text-grey q-mb-sm")
        for label, icon, route in NAV_ITEMS:
            is_active = route == active
            with ui.item(
                on_click=lambda r=route: ui.navigate.to(r),
            ).classes("rounded-lg" + (" bg-primary text-white" if is_active else "")):
                with ui.item_section().props("avatar"):
                    ui.icon(icon)
                with ui.item_section():
                    ui.label(label)
