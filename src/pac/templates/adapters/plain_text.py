from __future__ import annotations

from pac.templates.adapters.base import FormatAdapter

_SEVERITY_MARKERS: dict[str, str] = {
    "info": "[INFO]",
    "warning": "[WARNING]",
    "critical": "[CRITICAL]",
}


class PlainTextAdapter(FormatAdapter):
    """Plain-text format adapter — no markup, no escaping."""

    @property
    def name(self) -> str:
        return "plain_text"

    def escape(self, text: str) -> str:
        return text

    def literal(self, text: str) -> str:
        return text

    def bold(self, text: str) -> str:
        return text

    def italic(self, text: str) -> str:
        return text

    def code(self, text: str) -> str:
        return text

    def code_block(self, text: str, language: str = "") -> str:
        return text

    def link(self, text: str, url: str) -> str:
        return f"{text} ({url})"

    def heading(self, text: str, level: int = 1) -> str:
        return text.upper()

    def list_item(self, text: str) -> str:
        return f"- {text}"

    def separator(self) -> str:
        return "\n---\n"

    def emoji(self, name: str) -> str:
        return _SEVERITY_MARKERS.get(name, name)
