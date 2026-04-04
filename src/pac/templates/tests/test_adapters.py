from __future__ import annotations

from pac.templates.adapters.markdown_v2 import MarkdownV2Adapter
from pac.templates.adapters.plain_text import PlainTextAdapter


class TestMarkdownV2Adapter:
    def test_escape_backslash_escaped_first(
        self, md_adapter: MarkdownV2Adapter
    ) -> None:
        """Backslash in input is escaped before special chars."""
        result = md_adapter.escape("a\\b")
        assert result == "a\\\\b"

    def test_escape_special_characters(self, md_adapter: MarkdownV2Adapter) -> None:
        """All MarkdownV2 special chars get backslash-escaped."""
        result = md_adapter.escape("price: $100.00 (50% off)")
        assert "\\." in result
        assert "\\(" in result
        assert "\\)" in result

    def test_bold_wraps_in_asterisks(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.bold("hello") == "*hello*"

    def test_italic_wraps_in_underscores(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.italic("hello") == "_hello_"

    def test_code_wraps_in_backticks(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.code("WARNING") == "`WARNING`"

    def test_code_block_wraps_in_triple_backticks(
        self,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        result = md_adapter.code_block("x = 1", "python")
        assert result == "```python\nx = 1\n```"

    def test_link_produces_markdown_link(self, md_adapter: MarkdownV2Adapter) -> None:
        result = md_adapter.link("docs", "https://x.com")
        assert result == "[docs](https://x.com)"

    def test_heading_uses_bold(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.heading("Title") == "*Title*"

    def test_list_item_uses_bullet(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.list_item("item") == "• item"

    def test_separator_returns_line(self, md_adapter: MarkdownV2Adapter) -> None:
        assert "———" in md_adapter.separator()

    def test_emoji_maps_severity_names(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.emoji("warning") == "⚠️"
        assert md_adapter.emoji("critical") == "🚨"
        assert md_adapter.emoji("info") == "ℹ️"  # noqa: RUF001

    def test_emoji_unknown_returns_name(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.emoji("unknown") == "unknown"

    def test_literal_escapes_special_chars(
        self,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        assert md_adapter.literal("(") == "\\("
        assert md_adapter.literal(")") == "\\)"
        assert md_adapter.literal("+") == "\\+"
        assert md_adapter.literal(".") == "\\."
        assert md_adapter.literal("!") == "\\!"

    def test_name_is_markdown_v2(self, md_adapter: MarkdownV2Adapter) -> None:
        assert md_adapter.name == "markdown_v2"


class TestPlainTextAdapter:
    def test_escape_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.escape("a.b(c)") == "a.b(c)"

    def test_bold_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.bold("hello") == "hello"

    def test_italic_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.italic("hello") == "hello"

    def test_code_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.code("x") == "x"

    def test_link_appends_url(self, plain_adapter: PlainTextAdapter) -> None:
        result = plain_adapter.link("docs", "https://x.com")
        assert result == "docs (https://x.com)"

    def test_heading_uppercases(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.heading("title") == "TITLE"

    def test_list_item_uses_dash(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.list_item("item") == "- item"

    def test_emoji_uses_text_markers(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.emoji("warning") == "[WARNING]"
        assert plain_adapter.emoji("critical") == "[CRITICAL]"
        assert plain_adapter.emoji("info") == "[INFO]"

    def test_code_block_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.code_block("x = 1", "python") == "x = 1"

    def test_literal_is_identity(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.literal("(") == "("
        assert plain_adapter.literal("+") == "+"
        assert plain_adapter.literal(".") == "."

    def test_name_is_plain_text(self, plain_adapter: PlainTextAdapter) -> None:
        assert plain_adapter.name == "plain_text"
