from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.research.indicators import IndicatorRegistry

scenarios("../features/indicator_registry.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("an indicator registry with minimal price data")
def given_registry(ctx: dict[str, Any]) -> None:
    bars = [
        PriceBar(
            date=date(2022, 1, d),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("98"),
            close=Decimal("102"),
            volume=1000,
        )
        for d in range(3, 28)
        if date(2022, 1, d).weekday() < 5
    ]
    price_data = {
        "stocks": PriceSeries(ticker="EUNL.DE", interval=Interval.DAILY, bars=bars)
    }
    ctx["registry"] = IndicatorRegistry(price_data)


@then("no indicators are registered")
def then_no_indicators(ctx: dict[str, Any]) -> None:
    assert ctx["registry"].list() == []


@when('the "crisis" indicator pack is registered')
def when_register_crisis(ctx: dict[str, Any]) -> None:
    ctx["registry"].register_pack("crisis")


@when('the "nonexistent_pack" indicator pack is registered')
def when_register_unknown(ctx: dict[str, Any]) -> None:
    try:
        ctx["registry"].register_pack("nonexistent_pack")
        ctx["error"] = None
    except ValueError as e:
        ctx["error"] = e


@when('a custom indicator named "my_sma" is registered')
def when_register_custom(ctx: dict[str, Any]) -> None:
    ctx["registry"].register(
        "my_sma",
        lambda price_data, **_: float(price_data.bars[-1].close),
        asset="stocks",
        lookback_days=20,
    )


@then('the registry contains the "drawdown" indicator')
def then_has_drawdown(ctx: dict[str, Any]) -> None:
    assert "drawdown" in ctx["registry"].list()


@then('the registry contains the "death_cross" indicator')
def then_has_death_cross(ctx: dict[str, Any]) -> None:
    assert "death_cross" in ctx["registry"].list()


@then("a ValueError is raised")
def then_value_error(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["error"], ValueError)


@then('the registry contains the "my_sma" indicator')
def then_has_my_sma(ctx: dict[str, Any]) -> None:
    assert "my_sma" in ctx["registry"].list()
