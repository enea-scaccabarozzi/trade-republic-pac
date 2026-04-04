from __future__ import annotations

from abc import ABC, abstractmethod


class FormatAdapter(ABC):
    """Translates abstract formatting calls into channel-specific markup.

    Injected into Jinja2 templates as globals: bold(), italic(), code(), etc.
    Template authors call format functions without knowing the target channel.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Format identifier (e.g. 'markdown_v2', 'plain_text')."""
        ...

    @abstractmethod
    def escape(self, text: str) -> str:
        """Escape special characters for this format."""
        ...

    @abstractmethod
    def literal(self, text: str) -> str:
        """Escape structural characters that appear as template literals.

        Use for punctuation like (, ), +, -, ., ! that appears in templates
        as fixed text (not user data). In MarkdownV2, escapes special chars.
        In PlainText, returns text as-is (identity).
        """
        ...

    @abstractmethod
    def bold(self, text: str) -> str:
        """Wrap text in bold formatting."""
        ...

    @abstractmethod
    def italic(self, text: str) -> str:
        """Wrap text in italic formatting."""
        ...

    @abstractmethod
    def code(self, text: str) -> str:
        """Inline code."""
        ...

    @abstractmethod
    def code_block(self, text: str, language: str = "") -> str:
        """Multi-line code block."""
        ...

    @abstractmethod
    def link(self, text: str, url: str) -> str:
        """Format a hyperlink."""
        ...

    @abstractmethod
    def heading(self, text: str, level: int = 1) -> str:
        """Format a section heading."""
        ...

    @abstractmethod
    def list_item(self, text: str) -> str:
        """Format a bulleted list item."""
        ...

    @abstractmethod
    def separator(self) -> str:
        """Produce a visual separator line."""
        ...

    def emoji(self, name: str) -> str:
        """Return emoji by name. Default: return name as-is.

        Standard names used in templates:
        - 'info', 'warning', 'critical' (severity indicators)
        """
        return name
