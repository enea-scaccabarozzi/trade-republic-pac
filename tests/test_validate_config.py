from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def valid_config(tmp_path: Path) -> Path:
    """Create a minimal valid pac.yaml (no env var interpolation needed)."""
    config = tmp_path / "pac.yaml"
    config.write_text(
        """\
version: 1
app:
  job_secret: test-secret
broker:
  type: trade_republic
  phone_number: "+491234567890"
  pin: "1234"
assets:
  - id: stocks
    name: Stocks ETF
    isin: IE00BK5BQT80
    target_pct: 70
  - id: gold
    name: Gold ETC
    isin: IE00B4ND3602
    target_pct: 15
  - id: bonds
    name: Bond ETF
    isin: IE00B3F81409
    target_pct: 15
channels:
  telegram:
    type: telegram
    bot_token: fake-token
    chat_id: "12345"
    webhook:
      url: ""
      secret: test-secret
signals: []
""",
        encoding="utf-8",
    )
    return config


class TestValidateConfigCLI:
    def test_valid_config_exits_zero(self, valid_config: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_config.py",
                "--config",
                str(valid_config),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Configuration is valid" in result.stdout

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_config.py",
                "--config",
                str(tmp_path / "nonexistent.yaml"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error" in result.stdout

    def test_invalid_yaml_exits_one(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(
            "{{{{not valid yaml:::::",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_config.py",
                "--config",
                str(bad_yaml),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_unknown_rule_reference_exits_one(self, tmp_path: Path) -> None:
        config = tmp_path / "bad_rule.yaml"
        config.write_text(
            """\
version: 1
app:
  job_secret: test-secret
broker:
  type: trade_republic
  phone_number: "+491234567890"
  pin: "1234"
assets:
  - id: stocks
    name: Stocks ETF
    isin: IE00BK5BQT80
    target_pct: 100
channels:
  telegram:
    type: telegram
    bot_token: fake-token
    chat_id: "12345"
signals:
  - name: bad_signal
    rule: nonexistent_rule
    schedule: "0 * * * *"
    channels: [telegram]
    params: {}
    template: threshold_alert
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_config.py",
                "--config",
                str(config),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_unknown_arg_exits_one(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_config.py",
                "--unknown-flag",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage" in result.stdout
