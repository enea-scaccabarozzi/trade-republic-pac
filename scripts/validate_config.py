"""Validate pac.yaml configuration without starting the server.

Usage:
    python scripts/validate_config.py [--config PATH]

If no --config is given, uses PAC_CONFIG_PATH env var or pac.yaml in CWD.
"""

from __future__ import annotations

import sys
from pathlib import Path

import structlog
import yaml

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
)


def validate_config(config_path: Path | None = None) -> bool:
    """Validate a config file by loading it and wiring the orchestrator.

    Args:
        config_path: Path to the YAML config file (optional).

    Returns:
        True if validation succeeds, False otherwise.
    """
    # 1. Load and parse config
    try:
        from pac.config.loader import load_config

        settings = load_config(config_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return False
    except yaml.YAMLError as e:
        print(f"YAML syntax error: {e}")
        return False
    except ValueError as e:
        print(f"Configuration error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error loading config: {e}")
        return False

    # 2. Validate cross-references via Orchestrator.from_settings()
    try:
        from pac.orchestrator.orchestrator import Orchestrator

        Orchestrator.from_settings(settings)
    except ValueError as e:
        print(f"Validation error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during validation: {e}")
        return False

    # 3. Print success summary
    print("Configuration is valid!")
    print(f"  Assets:   {len(settings.assets)}")
    print(f"  Channels: {len(settings.channels)}")
    print(f"  Signals:  {len(settings.signals)}")
    return True


def _parse_args(argv: list[str]) -> Path | None:
    """Parse CLI arguments for --config PATH."""
    config_path = None
    i = 1
    while i < len(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            config_path = Path(argv[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {argv[i]}")
            print("Usage: python scripts/validate_config.py [--config PATH]")
            sys.exit(1)
    return config_path


if __name__ == "__main__":
    path = _parse_args(sys.argv)
    success = validate_config(path)
    sys.exit(0 if success else 1)
