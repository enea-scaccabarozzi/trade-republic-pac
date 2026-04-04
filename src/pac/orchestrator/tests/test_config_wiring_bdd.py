from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from pac.config import Settings
from pac.orchestrator import Orchestrator

# ── Scenarios ───────────────────────────────────────────────────────────


@scenario(
    "../features/config_wiring.feature",
    "Valid config wires successfully",
)
def test_valid_wiring() -> None:
    pass


@scenario(
    "../features/config_wiring.feature",
    "Config references unknown rule",
)
def test_unknown_rule() -> None:
    pass


@scenario(
    "../features/config_wiring.feature",
    "Config references unknown channel type",
)
def test_unknown_channel_type() -> None:
    pass


@scenario(
    "../features/config_wiring.feature",
    "Config references unknown template",
)
def test_unknown_template() -> None:
    pass


# ── Shared fixtures ────────────────────────────────────────────────────

_BASE_KWARGS: dict[str, Any] = {
    "version": 1,
    "app": {"job_secret": "test"},
    "broker": {"type": "trade_republic", "phone_number": "+49", "pin": "1234"},
    "assets": [
        {
            "id": "stocks",
            "name": "Stocks ETF",
            "isin": "IE00BK5BQT80",
            "target_pct": 70,
        },
        {"id": "gold", "name": "Gold ETC", "isin": "IE00B4ND3602", "target_pct": 15},
        {"id": "bonds", "name": "Bond ETF", "isin": "IE00B3F81409", "target_pct": 15},
    ],
}


@pytest.fixture()
def wiring_context() -> dict[str, Any]:
    return {}


# ── Steps ───────────────────────────────────────────────────────────────


@given("a config with valid signals, rules, and channels", target_fixture="settings")
def valid_settings() -> Settings:
    return Settings.model_validate(
        {
            **_BASE_KWARGS,
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [
                {
                    "name": "deviation_check",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                    "template": "threshold_alert",
                }
            ],
        }
    )


@given(
    parsers.parse('a config with signal referencing rule "{rule_name}"'),
    target_fixture="settings",
)
def settings_unknown_rule(rule_name: str) -> Settings:
    return Settings.model_validate(
        {
            **_BASE_KWARGS,
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [
                {
                    "name": "test",
                    "rule": rule_name,
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": "threshold_alert",
                }
            ],
        }
    )


@given(
    parsers.parse('a config with channel type "{ch_type}" not discovered'),
    target_fixture="settings",
)
def settings_unknown_channel_type(ch_type: str) -> Settings:
    return Settings.model_validate(
        {
            **_BASE_KWARGS,
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                },
                "my_channel": {"type": ch_type},
            },
            "signals": [],
        }
    )


@given(
    parsers.parse('a config with signal referencing template "{tpl_name}"'),
    target_fixture="settings",
)
def settings_unknown_template(tpl_name: str) -> Settings:
    return Settings.model_validate(
        {
            **_BASE_KWARGS,
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [
                {
                    "name": "test",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": tpl_name,
                }
            ],
        }
    )


@when(
    "the orchestrator is created from settings",
    target_fixture="wiring_result",
)
def create_orchestrator(
    settings: Settings, wiring_context: dict[str, Any]
) -> dict[str, Any]:
    try:
        orch = Orchestrator.from_settings(settings)
        wiring_context["orchestrator"] = orch
        wiring_context["error"] = None
    except ValueError as e:
        wiring_context["orchestrator"] = None
        wiring_context["error"] = e
    return wiring_context


@then("all rules are registered")
def rules_registered(wiring_context: dict[str, Any]) -> None:
    orch = wiring_context["orchestrator"]
    assert orch is not None
    assert "threshold_deviation" in orch.registry


@then("all channels are instantiated with typed config")
def channels_instantiated(wiring_context: dict[str, Any]) -> None:
    orch = wiring_context["orchestrator"]
    assert orch is not None
    assert "telegram" in orch._channels


@then(parsers.parse('a validation error is raised mentioning "{text}"'))
def validation_error_raised(wiring_context: dict[str, Any], text: str) -> None:
    err = wiring_context["error"]
    assert err is not None, "Expected a ValueError but none was raised"
    assert text in str(err)
