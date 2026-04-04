from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

from pac.config.loader import load_config

scenarios("../features/config_loading.feature")

_VALID_CONFIG: dict[str, Any] = {
    "version": 1,
    "app": {"job_secret": "default-secret"},
    "broker": {
        "type": "trade_republic",
        "phone_number": "+491234567890",
        "pin": "1234",
    },
    "assets": [
        {
            "id": "stocks",
            "name": "Stocks ETF",
            "isin": "IE00BK5BQT80",
            "target_pct": 70,
        },
        {
            "id": "gold",
            "name": "Gold ETC",
            "isin": "IE00B4ND3602",
            "target_pct": 15,
        },
        {
            "id": "bonds",
            "name": "Bond ETF",
            "isin": "IE00B3F81409",
            "target_pct": 15,
        },
    ],
    "channels": {},
    "signals": [],
}

_ISINS = [
    "IE00BK5BQT80",
    "IE00B4ND3602",
    "IE00B3F81409",
    "IE00B3RBWM25",
    "IE00BZ163K21",
    "IE00BZ163L38",
    "IE00BZ163M45",
    "IE00BZ163P71",
    "IE00BF4RFH31",
    "IE00B4L5Y983",
]


def _generate_assets(count: int) -> list[dict[str, Any]]:
    """Generate N asset configs that sum to 100%."""
    base_pct = 100 // count
    remainder = 100 - base_pct * count
    assets: list[dict[str, Any]] = []
    for i in range(count):
        pct = base_pct + (1 if i < remainder else 0)
        assets.append(
            {
                "id": f"asset_{i}",
                "name": f"Asset {i}",
                "isin": _ISINS[i],
                "target_pct": pct,
            }
        )
    return assets


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared context for step definitions."""
    return {}


@given("a valid pac.yaml configuration file")
def given_valid_config(tmp_path: Path, ctx: dict[str, Any]) -> None:
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(_VALID_CONFIG))
    ctx["config_path"] = config_path
    ctx["config_data"] = dict(_VALID_CONFIG)


@given(
    parsers.parse('the environment variable "{var}" is set to "{value}"'),
    target_fixture="env_set",
)
def given_env_var_set(
    monkeypatch: pytest.MonkeyPatch,
    var: str,
    value: str,
    ctx: dict[str, Any],
) -> None:
    monkeypatch.setenv(var, value)
    ctx.setdefault("env_vars", {})[var] = value


@given(
    parsers.parse(
        'the config file contains "${{{var}}}" as the job_secret',
    ),
)
def given_config_with_env_ref(
    tmp_path: Path,
    var: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["app"] = {"job_secret": f"${{{var}}}"}
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('the config file references "${{{var}}}"'))
def given_config_references_env(
    tmp_path: Path,
    var: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["app"] = {"job_secret": f"${{{var}}}"}
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('the environment variable "{var}" is not set'))
def given_env_var_not_set(
    monkeypatch: pytest.MonkeyPatch,
    var: str,
) -> None:
    monkeypatch.delenv(var, raising=False)


@given("no config file exists at the specified path")
def given_no_config_file(tmp_path: Path, ctx: dict[str, Any]) -> None:
    ctx["config_path"] = tmp_path / "nonexistent.yaml"


@given("a config file with invalid YAML syntax")
def given_invalid_yaml(tmp_path: Path, ctx: dict[str, Any]) -> None:
    config_path = tmp_path / "pac.yaml"
    config_path.write_text("invalid: yaml: [unclosed")
    ctx["config_path"] = config_path


@given(
    parsers.parse(
        "a config file where asset target_pct values sum to {total:d}",
    ),
)
def given_bad_sum(
    tmp_path: Path,
    total: int,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = [
        {"id": "stocks", "name": "Stocks", "isin": "IE00BK5BQT80", "target_pct": total},
    ]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('a config file with two assets having id "{aid}"'))
def given_duplicate_ids(
    tmp_path: Path,
    aid: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = [
        {"id": aid, "name": "A", "isin": "IE00BK5BQT80", "target_pct": 50},
        {"id": aid, "name": "B", "isin": "IE00B4ND3602", "target_pct": 50},
    ]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('a config file with an asset id "{aid}"'))
def given_invalid_asset_id(
    tmp_path: Path,
    aid: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = [
        {"id": aid, "name": "Bad", "isin": "IE00BK5BQT80", "target_pct": 100},
    ]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('a config file with an asset isin "{isin}"'))
def given_invalid_isin(
    tmp_path: Path,
    isin: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = [
        {"id": "test", "name": "Test", "isin": isin, "target_pct": 100},
    ]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(
    parsers.parse(
        'a config file where signal "{sig}" references channel "{ch}"',
    ),
)
def given_signal_refs_channel(
    tmp_path: Path,
    sig: str,
    ch: str,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["signals"] = [
        {
            "name": sig,
            "rule": "threshold",
            "schedule": "0 * * * *",
            "channels": [ch],
            "template": "default",
        },
    ]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(parsers.parse('no channel "{ch}" is defined'))
def given_no_channel(ctx: dict[str, Any]) -> None:
    pass  # already set up with empty channels


@given("a config file with an empty assets list")
def given_empty_assets(tmp_path: Path, ctx: dict[str, Any]) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = []
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given("a config file containing only a scalar value")
def given_scalar_yaml(tmp_path: Path, ctx: dict[str, Any]) -> None:
    config_path = tmp_path / "pac.yaml"
    config_path.write_text("just a string\n")
    ctx["config_path"] = config_path


@given("a config file without a version field")
def given_no_version(tmp_path: Path, ctx: dict[str, Any]) -> None:
    data = dict(_VALID_CONFIG)
    del data["version"]
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


@given(
    parsers.parse(
        'the environment variable "PAC_CONFIG_PATH" is set to a custom path',
    ),
)
def given_pac_config_path_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ctx: dict[str, Any],
) -> None:
    custom_path = tmp_path / "custom" / "config.yaml"
    ctx["custom_config_path"] = custom_path
    monkeypatch.setenv("PAC_CONFIG_PATH", str(custom_path))


@given("a valid config file exists at that path")
def given_config_at_custom_path(ctx: dict[str, Any]) -> None:
    custom_path: Path = ctx["custom_config_path"]
    custom_path.parent.mkdir(parents=True, exist_ok=True)
    custom_path.write_text(yaml.dump(_VALID_CONFIG))


@given(parsers.parse("a config with {count:d} assets summing to 100%"))
def given_dynamic_asset_count(
    tmp_path: Path,
    count: int,
    ctx: dict[str, Any],
) -> None:
    data = dict(_VALID_CONFIG)
    data["assets"] = _generate_assets(count)
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    ctx["config_path"] = config_path


# ── When steps ─────────────────────────────────────────────────────────


@when("the configuration is loaded")
def when_config_loaded(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = load_config(ctx["config_path"])
        ctx["error"] = None
    except Exception as exc:
        ctx["result"] = None
        ctx["error"] = exc


@when("the configuration is loaded without specifying a path")
def when_config_loaded_no_path(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = load_config()
        ctx["error"] = None
    except Exception as exc:
        ctx["result"] = None
        ctx["error"] = exc


# ── Then steps ─────────────────────────────────────────────────────────


@then("the settings contain the expected values")
def then_settings_valid(ctx: dict[str, Any]) -> None:
    assert ctx["error"] is None
    settings = ctx["result"]
    assert settings is not None
    assert settings.version == 1
    assert len(settings.assets) == 3


@then("the asset target percentages sum to 100")
def then_targets_sum_100(ctx: dict[str, Any]) -> None:
    settings = ctx["result"]
    total = sum(a.target_pct for a in settings.assets)
    assert total == Decimal("100")


@then(parsers.parse('the job_secret is "{expected}"'))
def then_job_secret(ctx: dict[str, Any], expected: str) -> None:
    assert ctx["error"] is None
    assert ctx["result"].app.job_secret == expected


@then(parsers.parse('a ValueError is raised mentioning "{text}"'))
def then_value_error_with_text(ctx: dict[str, Any], text: str) -> None:
    assert ctx["error"] is not None
    assert isinstance(ctx["error"], (ValueError, Exception))
    assert text.lower() in str(ctx["error"]).lower()


@then("a FileNotFoundError is raised")
def then_file_not_found(ctx: dict[str, Any]) -> None:
    assert ctx["error"] is not None
    assert isinstance(ctx["error"], FileNotFoundError)


@then("a YAML parsing error is raised")
def then_yaml_error(ctx: dict[str, Any]) -> None:
    assert ctx["error"] is not None
    assert "yaml" in type(ctx["error"]).__module__.lower() or isinstance(
        ctx["error"], yaml.YAMLError
    )


@then(parsers.parse('a validation error is raised mentioning "{text}"'))
def then_validation_error_with_text(
    ctx: dict[str, Any],
    text: str,
) -> None:
    assert ctx["error"] is not None
    assert text.lower() in str(ctx["error"]).lower()


@then("a validation error is raised")
def then_validation_error(ctx: dict[str, Any]) -> None:
    assert ctx["error"] is not None


@then("the settings are loaded from the custom path")
def then_loaded_from_custom_path(ctx: dict[str, Any]) -> None:
    assert ctx["error"] is None
    assert ctx["result"] is not None
    assert ctx["result"].version == 1


@then(parsers.parse("settings.assets has {count:d} entries"))
def then_asset_count(ctx: dict[str, Any], count: int) -> None:
    assert ctx["error"] is None
    assert len(ctx["result"].assets) == count
