from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from pac.config.loader import (
    _interpolate_env,
    _interpolate_recursive,
    load_config,
)


def _write_config(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a YAML config file and return its path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "pac.yaml"
    config_path.write_text(yaml.dump(data))
    return config_path


_VALID_DATA: dict[str, Any] = {
    "version": 1,
    "app": {"job_secret": "test-secret"},
    "broker": {
        "type": "trade_republic",
        "phone_number": "+491234567890",
        "pin": "1234",
    },
    "assets": [
        {"id": "stocks", "name": "Stocks", "isin": "IE00BK5BQT80", "target_pct": 70},
        {"id": "gold", "name": "Gold", "isin": "IE00B4ND3602", "target_pct": 15},
        {"id": "bonds", "name": "Bonds", "isin": "IE00B3F81409", "target_pct": 15},
    ],
    "channels": {},
    "signals": [],
}


class TestLoadConfig:
    def test_valid_yaml_returns_settings(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, _VALID_DATA)

        settings = load_config(path)

        assert settings.version == 1
        assert len(settings.assets) == 3
        assert settings.app.job_secret == "test-secret"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pac.yaml"
        path.write_text("invalid: yaml: [unclosed")

        with pytest.raises(yaml.YAMLError):
            load_config(path)

    def test_env_var_interpolation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MY_SECRET", "resolved-secret")
        data = dict(_VALID_DATA)
        data["app"] = {"job_secret": "${MY_SECRET}"}
        path = _write_config(tmp_path, data)

        settings = load_config(path)

        assert settings.app.job_secret == "resolved-secret"

    def test_pac_config_path_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = _write_config(tmp_path, _VALID_DATA)
        monkeypatch.setenv("PAC_CONFIG_PATH", str(path))

        settings = load_config()

        assert settings.version == 1

    def test_explicit_path_overrides_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        env_path = _write_config(tmp_path / "env", _VALID_DATA)
        monkeypatch.setenv("PAC_CONFIG_PATH", str(env_path))

        arg_data = dict(_VALID_DATA)
        arg_data["app"] = {"job_secret": "from-arg"}
        arg_path = _write_config(tmp_path / "arg", arg_data)

        settings = load_config(arg_path)

        assert settings.app.job_secret == "from-arg"

    def test_non_dict_root_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pac.yaml"
        path.write_text("just a string\n")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(path)

    def test_null_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pac.yaml"
        path.write_text("# empty file\n")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(path)

    def test_undefined_env_var_in_config_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("UNDEFINED_SECRET_VAR", raising=False)
        data = dict(_VALID_DATA)
        data["app"] = {"job_secret": "${UNDEFINED_SECRET_VAR}"}
        path = _write_config(tmp_path, data)

        with pytest.raises(ValueError, match="UNDEFINED_SECRET_VAR"):
            load_config(path)


class TestInterpolateEnv:
    def test_replaces_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FOO", "bar")

        assert _interpolate_env("${FOO}") == "bar"

    def test_multiple_vars(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")

        assert _interpolate_env("${A}-${B}") == "1-2"

    def test_missing_var_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MISSING", raising=False)

        with pytest.raises(ValueError, match="MISSING"):
            _interpolate_env("${MISSING}")

    def test_no_pattern_unchanged(self) -> None:
        assert _interpolate_env("plain text") == "plain text"


class TestInterpolateRecursive:
    def test_nested_dict(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("X", "resolved")
        obj = {"a": {"b": "${X}"}}

        result = _interpolate_recursive(obj)

        assert result == {"a": {"b": "resolved"}}

    def test_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Y", "val")
        obj = ["${Y}", "plain", 42]

        result = _interpolate_recursive(obj)

        assert result == ["val", "plain", 42]

    def test_non_string_passthrough(self) -> None:
        assert _interpolate_recursive(42) == 42
        assert _interpolate_recursive(True) is True
        assert _interpolate_recursive(None) is None
