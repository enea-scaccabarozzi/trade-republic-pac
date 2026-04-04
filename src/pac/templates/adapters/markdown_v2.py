from __future__ import annotations

from pac.templates.adapters.base import FormatAdapter

_SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!"

_SEVERITY_EMOJI: dict[str, str] = {
    "info": "ℹ️",  # noqa: RUF001
    "warning": "⚠️",
    "critical": "🚨",
}


class MarkdownV2Adapter(FormatAdapter):
    """Telegram MarkdownV2 format adapter."""

    @property
    def name(self) -> str:
        return "markdown_v2"

    def escape(self, text: str) -> str:
        text = text.replace("\\", "\\\\")
        result: list[str] = []
        for ch in text:
            if ch in _SPECIAL_CHARS:
                result.append(f"\\{ch}")
            else:
                result.append(ch)
        return "".join(result)

    def literal(self, text: str) -> str:
        return self.escape(text)

    def bold(self, text: str) -> str:
        return f"*{text}*"

    def italic(self, text: str) -> str:
        return f"_{text}_"

    def code(self, text: str) -> str:
        return f"`{text}`"

    def code_block(self, text: str, language: str = "") -> str:
        return f"```{language}\n{text}\n```"

    def link(self, text: str, url: str) -> str:
        return f"[{text}]({url})"

    def heading(self, text: str, level: int = 1) -> str:
        return self.bold(text)

    def list_item(self, text: str) -> str:
        return f"• {text}"

    def separator(self) -> str:
        return "\n———\n"

    def emoji(self, name: str) -> str:
        return _SEVERITY_EMOJI.get(name, name)
