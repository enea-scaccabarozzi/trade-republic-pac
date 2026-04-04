from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import jinja2
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.analysis.deviation import DeviationResult
from pac.analysis.rebalance import PacAllocation, PacPlan
from pac.delivery.base import RenderedMessage
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.templates.adapters.markdown_v2 import MarkdownV2Adapter
from pac.templates.adapters.plain_text import PlainTextAdapter
from pac.templates.engine import TemplateEngine

scenarios("../features/template_rendering.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@given("a template engine with builtin templates", target_fixture="context")
def engine_context() -> dict[str, Any]:
    return {"engine": TemplateEngine()}


@given(parsers.parse("a threshold signal with {severity} severity"))
def threshold_signal(context: dict[str, Any], severity: str) -> None:
    context["signal"] = Signal(
        name="deviation_check",
        severity=SignalSeverity(severity.lower()),
        message="Stocks overweight by 4.2%",
        triggered_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )
    context["data"] = {"signal": context["signal"], "deviations": []}


@given("a MarkdownV2 adapter")
def md_adapter(context: dict[str, Any]) -> None:
    context["adapter"] = MarkdownV2Adapter()


@given("a PlainText adapter")
def plain_adapter(context: dict[str, Any]) -> None:
    context["adapter"] = PlainTextAdapter()


@given("a PAC plan with 3 asset allocations")
def pac_plan_data(context: dict[str, Any]) -> None:
    context["data"] = {
        "plan": PacPlan(
            total_budget=Decimal("500.00"),
            allocations={
                "stocks": PacAllocation(
                    asset_id="stocks",
                    name="FTSE All-World ETF",
                    amount=Decimal("350.00"),
                    pct_of_budget=Decimal("70.0"),
                    target_pct=Decimal("70.0"),
                    current_pct=Decimal("68.5"),
                ),
                "gold": PacAllocation(
                    asset_id="gold",
                    name="Physical Gold ETC",
                    amount=Decimal("75.00"),
                    pct_of_budget=Decimal("15.0"),
                    target_pct=Decimal("15.0"),
                    current_pct=Decimal("14.2"),
                ),
                "bonds": PacAllocation(
                    asset_id="bonds",
                    name="Gov Bond ETF",
                    amount=Decimal("75.00"),
                    pct_of_budget=Decimal("15.0"),
                    target_pct=Decimal("15.0"),
                    current_pct=Decimal("17.3"),
                ),
            },
            timestamp=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        ),
    }


@given("a portfolio with deviations for 3 assets")
def portfolio_deviations(context: dict[str, Any]) -> None:
    context["data"] = {
        "deviations": [
            DeviationResult(
                asset_id="stocks",
                name="FTSE All-World ETF",
                actual_pct=Decimal("74.2"),
                target_pct=Decimal("70.0"),
                deviation_pct=Decimal("4.2"),
                abs_deviation_pct=Decimal("4.2"),
                severity=SignalSeverity.WARNING,
            ),
            DeviationResult(
                asset_id="gold",
                name="Physical Gold ETC",
                actual_pct=Decimal("13.5"),
                target_pct=Decimal("15.0"),
                deviation_pct=Decimal("-1.5"),
                abs_deviation_pct=Decimal("1.5"),
                severity=SignalSeverity.INFO,
            ),
            DeviationResult(
                asset_id="bonds",
                name="Gov Bond ETF",
                actual_pct=Decimal("12.3"),
                target_pct=Decimal("15.0"),
                deviation_pct=Decimal("-2.7"),
                abs_deviation_pct=Decimal("2.7"),
                severity=SignalSeverity.INFO,
            ),
        ],
        "snapshot": PortfolioSnapshot(
            positions=[],
            cash=Decimal("200.00"),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        ),
    }


@given("a threshold signal with CRITICAL severity")
def critical_signal(context: dict[str, Any]) -> None:
    context["signal"] = Signal(
        name="deviation_check",
        severity=SignalSeverity.CRITICAL,
        message="Stocks critically overweight",
        triggered_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )
    context["data"] = {"signal": context["signal"], "deviations": []}


@when(parsers.parse('rendering the "{template_name}" template'))
def render_template(context: dict[str, Any], template_name: str) -> None:
    signal = context.get("signal")
    context["result"] = context["engine"].render(
        template_name,
        context["data"],
        context["adapter"],
        signal_name=signal.name if signal else "test",
        severity=signal.severity if signal else SignalSeverity.INFO,
    )


@when(parsers.parse('rendering "{template_name}" with MarkdownV2 adapter'))
def render_with_md(context: dict[str, Any], template_name: str) -> None:
    signal = context.get("signal")
    context["md_result"] = context["engine"].render(
        template_name,
        context["data"],
        MarkdownV2Adapter(),
        signal_name=signal.name if signal else "test",
        severity=signal.severity if signal else SignalSeverity.INFO,
    )


@when(parsers.parse('rendering "{template_name}" with PlainText adapter'))
def render_with_plain(context: dict[str, Any], template_name: str) -> None:
    signal = context.get("signal")
    context["plain_result"] = context["engine"].render(
        template_name,
        context["data"],
        PlainTextAdapter(),
        signal_name=signal.name if signal else "test",
        severity=signal.severity if signal else SignalSeverity.INFO,
    )


@when(parsers.parse('rendering a template named "{template_name}"'))
def render_unknown(context: dict[str, Any], template_name: str) -> None:
    try:
        context["engine"].render(
            template_name,
            {},
            context["adapter"],
            signal_name="x",
            severity=SignalSeverity.INFO,
        )
        context["error"] = None
    except jinja2.TemplateNotFound as e:
        context["error"] = e


@when(parsers.parse('rendering "{template_name}" with empty data'))
def render_empty_data(context: dict[str, Any], template_name: str) -> None:
    try:
        context["engine"].render(
            template_name,
            {},
            context["adapter"],
            signal_name="x",
            severity=SignalSeverity.WARNING,
        )
        context["error"] = None
    except jinja2.UndefinedError as e:
        context["error"] = e


@when(
    parsers.parse(
        'rendering "{template_name}" '
        "with a data key that shadows a reserved name"
    )
)
def render_with_collision(context: dict[str, Any], template_name: str) -> None:
    try:
        context["engine"].render(
            template_name,
            {"bold": "shadowed!"},
            context["adapter"],
            signal_name="x",
            severity=SignalSeverity.INFO,
        )
        context["error"] = None
    except ValueError as e:
        context["error"] = e


@then("a RenderedMessage is produced")
def result_is_rendered_message(context: dict[str, Any]) -> None:
    assert isinstance(context["result"], RenderedMessage)


@then(parsers.parse('the message format is "{fmt}"'))
def message_format_is(context: dict[str, Any], fmt: str) -> None:
    assert context["result"].format == fmt


@then("the message contains bold signal name")
def message_contains_bold_name(context: dict[str, Any]) -> None:
    assert "*" in context["result"].content
    # Name may be escaped (e.g. underscores) — check each word
    for word in context["signal"].name.split("_"):
        assert word in context["result"].content


@then("the message contains the signal name")
def message_contains_name(context: dict[str, Any]) -> None:
    # Name may be escaped — check each word
    for word in context["signal"].name.split("_"):
        assert word in context["result"].content


@then("the message contains the severity")
def message_contains_severity(context: dict[str, Any]) -> None:
    assert context["signal"].severity.value.upper() in context["result"].content


@then(parsers.parse('the message contains "{text}"'))
def message_contains(context: dict[str, Any], text: str) -> None:
    assert text in context["result"].content


@then("the message contains each asset allocation")
def message_contains_allocations(context: dict[str, Any]) -> None:
    for alloc in context["data"]["plan"].allocations.values():
        # Name may be escaped — check first word (unambiguous identifier)
        first_word = alloc.name.split()[0]
        assert first_word in context["result"].content


@then("the message contains each asset's deviation")
def message_contains_deviations(context: dict[str, Any]) -> None:
    for dev in context["data"]["deviations"]:
        # Name may be escaped — check first word
        first_word = dev.name.split()[0]
        assert first_word in context["result"].content


@then("the two outputs have different content")
def outputs_differ(context: dict[str, Any]) -> None:
    assert context["md_result"].content != context["plain_result"].content


@then("both contain the signal name")
def both_contain_name(context: dict[str, Any]) -> None:
    # Name may be escaped in MarkdownV2 — check each word
    for word in context["signal"].name.split("_"):
        assert word in context["md_result"].content
        assert word in context["plain_result"].content


@then("a template-not-found error is raised")
def template_not_found(context: dict[str, Any]) -> None:
    assert isinstance(context["error"], jinja2.TemplateNotFound)


@then("an undefined-variable error is raised")
def undefined_variable(context: dict[str, Any]) -> None:
    assert isinstance(context["error"], jinja2.UndefinedError)


@then("a data-key-collision error is raised")
def data_key_collision(context: dict[str, Any]) -> None:
    assert isinstance(context["error"], ValueError)
    assert "reserved" in str(context["error"]).lower()
