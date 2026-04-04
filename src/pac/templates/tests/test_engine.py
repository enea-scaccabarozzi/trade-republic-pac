from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import jinja2
import pytest

from pac.analysis.deviation import DeviationResult
from pac.analysis.rebalance import PacPlan
from pac.delivery.base import RenderedMessage
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.templates.adapters.markdown_v2 import MarkdownV2Adapter
from pac.templates.adapters.plain_text import PlainTextAdapter
from pac.templates.engine import TemplateEngine


class TestTemplateEngine:
    def test_render_returns_rendered_message(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "threshold_alert",
            {"signal": sample_signal, "deviations": []},
            md_adapter,
            signal_name="deviation_check",
            severity=SignalSeverity.WARNING,
        )
        assert isinstance(result, RenderedMessage)
        assert result.format == "markdown_v2"
        assert result.signal_name == "deviation_check"
        assert result.severity == SignalSeverity.WARNING

    def test_render_content_contains_signal_name(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "threshold_alert",
            {"signal": sample_signal, "deviations": []},
            md_adapter,
            signal_name="deviation_check",
            severity=SignalSeverity.WARNING,
        )
        # Name is escaped in MarkdownV2 (underscores get backslash-escaped)
        assert "deviation" in result.content
        assert "check" in result.content

    def test_render_with_plain_text_adapter(
        self,
        plain_adapter: PlainTextAdapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "threshold_alert",
            {"signal": sample_signal, "deviations": []},
            plain_adapter,
            signal_name="deviation_check",
            severity=SignalSeverity.WARNING,
        )
        assert result.format == "plain_text"
        assert "deviation_check" in result.content

    def test_same_template_different_adapter_different_output(
        self,
        md_adapter: MarkdownV2Adapter,
        plain_adapter: PlainTextAdapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        data: dict[str, object] = {
            "signal": sample_signal,
            "deviations": [],
        }
        md_result = engine.render(
            "threshold_alert",
            data,
            md_adapter,
            signal_name="test",
            severity=SignalSeverity.WARNING,
        )
        plain_result = engine.render(
            "threshold_alert",
            data,
            plain_adapter,
            signal_name="test",
            severity=SignalSeverity.WARNING,
        )
        assert md_result.content != plain_result.content

    def test_render_pac_plan(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_pac_plan: PacPlan,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "pac_plan",
            {"plan": sample_pac_plan},
            md_adapter,
            signal_name="monthly_pac",
            severity=SignalSeverity.INFO,
        )
        assert "Monthly PAC Redistribution" in result.content
        # Name is MarkdownV2-escaped (hyphen becomes \-)
        assert "FTSE" in result.content
        assert "World" in result.content

    def test_render_portfolio_status(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_deviations: list[DeviationResult],
    ) -> None:
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal("200.00"),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        engine = TemplateEngine()
        result = engine.render(
            "portfolio_status",
            {"deviations": sample_deviations, "snapshot": snapshot},
            md_adapter,
            signal_name="portfolio_status",
            severity=SignalSeverity.INFO,
        )
        assert "Portfolio Status" in result.content
        assert "200" in result.content

    def test_unknown_template_raises_error(
        self,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        engine = TemplateEngine()
        with pytest.raises(jinja2.TemplateNotFound):
            engine.render(
                "nonexistent",
                {},
                md_adapter,
                signal_name="x",
                severity=SignalSeverity.INFO,
            )

    def test_missing_variable_raises_error(
        self,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        engine = TemplateEngine()
        with pytest.raises(jinja2.UndefinedError):
            engine.render(
                "threshold_alert",
                {},
                md_adapter,
                signal_name="x",
                severity=SignalSeverity.WARNING,
            )

    def test_has_template_returns_true_for_builtin(self) -> None:
        engine = TemplateEngine()
        assert engine.has_template("threshold_alert") is True

    def test_has_template_returns_false_for_unknown(self) -> None:
        engine = TemplateEngine()
        assert engine.has_template("nonexistent") is False

    def test_custom_template_dir(
        self,
        tmp_path: Path,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        (tmp_path / "test.j2").write_text("{{ bold('hello') }}")
        engine = TemplateEngine(template_dir=tmp_path)
        result = engine.render(
            "test",
            {},
            md_adapter,
            signal_name="test",
            severity=SignalSeverity.INFO,
        )
        assert result.content == "*hello*"

    def test_datefmt_filter(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "threshold_alert",
            {"signal": sample_signal, "deviations": []},
            md_adapter,
            signal_name="test",
            severity=SignalSeverity.WARNING,
        )
        assert "2026" in result.content

    def test_pctfmt_filter(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_deviations: list[DeviationResult],
    ) -> None:
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal("0"),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        engine = TemplateEngine()
        result = engine.render(
            "portfolio_status",
            {"deviations": sample_deviations, "snapshot": snapshot},
            md_adapter,
            signal_name="test",
            severity=SignalSeverity.INFO,
        )
        assert "%" in result.content

    def test_render_cycle_alert(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_signal: Signal,
    ) -> None:
        engine = TemplateEngine()
        result = engine.render(
            "cycle_alert",
            {"signal": sample_signal},
            md_adapter,
            signal_name="cycle_check",
            severity=SignalSeverity.WARNING,
        )
        assert isinstance(result, RenderedMessage)
        # Name is MarkdownV2-escaped (underscore becomes \_)
        assert "deviation" in result.content
        assert "check" in result.content
        assert result.signal_name == "cycle_check"

    def test_render_raises_on_data_key_collision(
        self,
        md_adapter: MarkdownV2Adapter,
    ) -> None:
        engine = TemplateEngine()
        with pytest.raises(ValueError, match="reserved context names"):
            engine.render(
                "threshold_alert",
                {"bold": "shadowed!"},
                md_adapter,
                signal_name="x",
                severity=SignalSeverity.INFO,
            )

    def test_threshold_alert_parity_with_formatting_py(
        self,
        md_adapter: MarkdownV2Adapter,
        sample_signal: Signal,
    ) -> None:
        """Golden test: template output contains same key elements as
        formatting.py's format_signal_alert() for the same signal data.

        Validates that the template produces structurally equivalent output
        to the legacy formatter — same signal name, severity, message, and
        timestamp are present.
        """
        from pac.delivery.channels.telegram.formatting import (
            format_signal_alert,
        )

        engine = TemplateEngine()
        template_result = engine.render(
            "threshold_alert",
            {"signal": sample_signal, "deviations": []},
            md_adapter,
            signal_name=sample_signal.name,
            severity=sample_signal.severity,
        )

        legacy_output = format_signal_alert(sample_signal)

        # Both must contain the same key elements (MarkdownV2-escaped)
        assert "deviation" in template_result.content
        assert "deviation" in legacy_output
        assert "WARNING" in template_result.content
        assert "WARNING" in legacy_output
        assert "2026" in template_result.content
        assert "2026" in legacy_output
