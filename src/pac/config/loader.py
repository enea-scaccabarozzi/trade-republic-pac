from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from pac.config.models import Settings

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_DEFAULT_CONFIG_PATH = Path("pac.yaml")


def _interpolate_env(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values."""

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            msg = f"Environment variable '{var_name}' is not set"
            raise ValueError(msg)
        return env_value

    return _ENV_PATTERN.sub(_replace, value)


def _interpolate_recursive(obj: Any) -> Any:
    """Recursively interpolate env vars in all string values."""
    if isinstance(obj, str):
        return _interpolate_env(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_recursive(item) for item in obj]
    return obj


def load_config(path: Path | None = None) -> Settings:
    """Load and validate config from a YAML file.

    Args:
        path: Path to the YAML config file.
              Falls back to PAC_CONFIG_PATH env var, then pac.yaml in CWD.

    Returns:
        Validated Settings instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If env var interpolation fails or validation fails.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if path is None:
        env_path = os.environ.get("PAC_CONFIG_PATH")
        path = Path(env_path) if env_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        msg = f"Config file not found: {path}"
        raise FileNotFoundError(msg)

    raw_text = path.read_text(encoding="utf-8")
    raw_data = yaml.safe_load(raw_text)

    if not isinstance(raw_data, dict):
        msg = "Config file must contain a YAML mapping at the top level"
        raise ValueError(msg)

    interpolated = _interpolate_recursive(raw_data)
    return Settings.model_validate(interpolated)
