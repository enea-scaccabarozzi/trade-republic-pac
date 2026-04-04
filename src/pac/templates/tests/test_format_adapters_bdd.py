from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from pac.templates.adapters.markdown_v2 import MarkdownV2Adapter
from pac.templates.adapters.plain_text import PlainTextAdapter

scenarios("../features/format_adapters.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@given("a MarkdownV2 adapter", target_fixture="context")
def md_adapter_context() -> dict[str, Any]:
    return {"adapter": MarkdownV2Adapter()}


@given("a PlainText adapter", target_fixture="context")
def plain_adapter_context() -> dict[str, Any]:
    return {"adapter": PlainTextAdapter()}


@given(parsers.parse("a {adapter} adapter"), target_fixture="context")
def adapter_by_name(adapter: str) -> dict[str, Any]:
    adapters: dict[str, type[MarkdownV2Adapter | PlainTextAdapter]] = {
        "MarkdownV2": MarkdownV2Adapter,
        "PlainText": PlainTextAdapter,
    }
    return {"adapter": adapters[adapter]()}


@when(parsers.parse('escaping the text "{text}"'))
def escape_text(context: dict[str, Any], text: str) -> None:
    context["result"] = context["adapter"].escape(text)


@when(parsers.parse('formatting "{text}" as bold'))
def format_bold(context: dict[str, Any], text: str) -> None:
    context["result"] = context["adapter"].bold(text)


@when(parsers.parse('formatting "{text}" as code'))
def format_code(context: dict[str, Any], text: str) -> None:
    context["result"] = context["adapter"].code(text)


@when(parsers.parse('formatting "{text}" as code_block'))
def format_code_block(context: dict[str, Any], text: str) -> None:
    context["result"] = context["adapter"].code_block(text)


@when(parsers.parse('wrapping "{text}" in literal'))
def wrap_literal(context: dict[str, Any], text: str) -> None:
    context["result"] = context["adapter"].literal(text)


@when(parsers.parse('requesting emoji for "{name}"'))
def request_emoji(context: dict[str, Any], name: str) -> None:
    context["result"] = context["adapter"].emoji(name)


@when(parsers.parse('formatting a link with text "{text}" and URL "{url}"'))
def format_link(context: dict[str, Any], text: str, url: str) -> None:
    context["result"] = context["adapter"].link(text, url)


@then("the result contains backslash-escaped special characters")
def result_contains_escaped(context: dict[str, Any]) -> None:
    result = context["result"]
    assert "\\" in result


@then(parsers.parse('the result is "{expected}"'))
def result_is(context: dict[str, Any], expected: str) -> None:
    assert context["result"] == expected


@then(parsers.parse('the adapter name is "{name}"'))
def adapter_name_is(context: dict[str, Any], name: str) -> None:
    assert context["adapter"].name == name
