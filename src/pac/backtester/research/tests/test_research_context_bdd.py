"""BDD step definitions for ResearchContext non-IO behaviors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.conftest import make_settings

from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.research.context import ResearchContext
from pac.backtester.research.indicators import IndicatorRegistry

scenarios("../features/research_context.feature")


def _weekday_bars(
    year: int,
    month: int,
    start_day: int,
    end_day: int,
    ticker: str,
) -> list[PriceBar]:
    """Build daily PriceBars for weekdays in a given month range."""
    bars = []
    for day in range(start_day, end_day + 1):
        d = date(year, month, day)
        if d.weekday() < 5:  # Monday-Friday only
            bars.append(
                PriceBar(
                    date=d,
                    open=Decimal("100"),
                    high=Decimal("105"),
                    low=Decimal("98"),
                    close=Decimal("102"),
                    volume=1000,
                )
            )
    return bars


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# ── Background ─────────────────────────────────────────────────────────────


@given("a ResearchContext built from two assets with known bar dates")
def given_research_context(ctx: dict[str, Any]) -> None:
    # stocks: Jan 3 - Jan 28 2022 (weekdays)
    stocks_bars = _weekday_bars(2022, 1, 3, 28, "EUNL.DE")
    # gold: Jan 5 - Jan 26 2022 (narrower window -- forces intersection)
    gold_bars = _weekday_bars(2022, 1, 5, 26, "4GLD.DE")

    price_data = {
        "stocks": PriceSeries(
            ticker="EUNL.DE", interval=Interval.DAILY, bars=stocks_bars
        ),
        "gold": PriceSeries(ticker="4GLD.DE", interval=Interval.DAILY, bars=gold_bars),
    }
    ticker_price_data = {
        "EUNL.DE": price_data["stocks"],
        "4GLD.DE": price_data["gold"],
    }
    settings = make_settings()
    registry = IndicatorRegistry(price_data)

    ctx["rc"] = ResearchContext(settings, price_data, ticker_price_data, registry)
    # Store expected intersection boundaries for assertions
    ctx["expected_start"] = date(2022, 1, 5)  # gold starts later
    ctx["expected_end"] = date(2022, 1, 26)   # gold ends earlier


# ── Date range scenarios ────────────────────────────────────────────────────


@then("the data start date is the latest first bar across all assets")
def then_data_start(ctx: dict[str, Any]) -> None:
    assert ctx["rc"]._data_start == ctx["expected_start"]


@then("the data end date is the earliest last bar across all assets")
def then_data_end(ctx: dict[str, Any]) -> None:
    assert ctx["rc"]._data_end == ctx["expected_end"]


# ── Calendar scenarios ──────────────────────────────────────────────────────


@then('the "crises" calendar is available')
def then_crises_calendar(ctx: dict[str, Any]) -> None:
    assert "crises" in ctx["rc"].calendars


@then('the "bull_runs" calendar is available')
def then_bull_runs_calendar(ctx: dict[str, Any]) -> None:
    assert "bull_runs" in ctx["rc"].calendars


@then('the "corrections" calendar is available')
def then_corrections_calendar(ctx: dict[str, Any]) -> None:
    assert "corrections" in ctx["rc"].calendars


@then('the "rate_regimes" calendar is available')
def then_rate_regimes_calendar(ctx: dict[str, Any]) -> None:
    assert "rate_regimes" in ctx["rc"].calendars


# ── Registry scenarios ──────────────────────────────────────────────────────


@then("no indicators are registered in the context")
def then_no_indicators_in_context(ctx: dict[str, Any]) -> None:
    assert ctx["rc"].indicators.list() == []


@when('the "crisis" pack is registered on the context')
def when_register_crisis_on_context(ctx: dict[str, Any]) -> None:
    ctx["rc"].register_pack("crisis")


@then('the "drawdown" indicator is available in the context')
def then_drawdown_available(ctx: dict[str, Any]) -> None:
    assert "drawdown" in ctx["rc"].indicators.list()
