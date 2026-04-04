from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from pac.config.models import AppConfig, AssetConfig, BrokerConfig, Settings


def _base_settings_data(**overrides: Any) -> dict[str, Any]:
    """Build base settings dict with test defaults."""
    data: dict[str, Any] = {
        "version": 1,
        "app": {"job_secret": "test-secret"},
        "broker": {
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
        },
        "assets": [
            {
                "id": "stocks",
                "name": "Stocks",
                "isin": "IE00BK5BQT80",
                "target_pct": 70,
            },
            {
                "id": "gold",
                "name": "Gold",
                "isin": "IE00B4ND3602",
                "target_pct": 15,
            },
            {
                "id": "bonds",
                "name": "Bonds",
                "isin": "IE00B3F81409",
                "target_pct": 15,
            },
        ],
        "channels": {},
        "signals": [],
    }
    data.update(overrides)
    return data


class TestSettings:
    def test_valid_construction(self) -> None:
        settings = Settings.model_validate(_base_settings_data())

        assert settings.version == 1
        assert len(settings.assets) == 3
        assert settings.app.job_secret == "test-secret"

    def test_allocation_sum_must_be_100(self) -> None:
        data = _base_settings_data(
            assets=[
                {"id": "a", "name": "A", "isin": "IE00BK5BQT80", "target_pct": 50},
                {"id": "b", "name": "B", "isin": "IE00B4ND3602", "target_pct": 30},
            ],
        )

        with pytest.raises(ValidationError, match="sum to 100"):
            Settings.model_validate(data)

    def test_unique_asset_ids(self) -> None:
        data = _base_settings_data(
            assets=[
                {"id": "same", "name": "A", "isin": "IE00BK5BQT80", "target_pct": 50},
                {"id": "same", "name": "B", "isin": "IE00B4ND3602", "target_pct": 50},
            ],
        )

        with pytest.raises(ValidationError, match="unique"):
            Settings.model_validate(data)

    def test_signal_channels_must_exist(self) -> None:
        data = _base_settings_data(
            signals=[
                {
                    "name": "test",
                    "rule": "threshold",
                    "schedule": "0 * * * *",
                    "channels": ["nonexistent"],
                    "template": "default",
                },
            ],
        )

        with pytest.raises(ValidationError, match="unknown channel"):
            Settings.model_validate(data)

    def test_signal_with_valid_channel(self) -> None:
        data = _base_settings_data(
            channels={"telegram": {"type": "telegram", "bot_token": "t"}},
            signals=[
                {
                    "name": "test",
                    "rule": "threshold",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "template": "default",
                },
            ],
        )

        settings = Settings.model_validate(data)

        assert len(settings.signals) == 1

    def test_asset_map_property(self) -> None:
        settings = Settings.model_validate(_base_settings_data())

        am = settings.asset_map

        assert "stocks" in am
        assert am["stocks"].isin == "IE00BK5BQT80"

    def test_isin_to_asset_id_property(self) -> None:
        settings = Settings.model_validate(_base_settings_data())

        mapping = settings.isin_to_asset_id

        assert mapping["IE00BK5BQT80"] == "stocks"
        assert mapping["IE00B4ND3602"] == "gold"

    def test_target_allocations_property(self) -> None:
        settings = Settings.model_validate(_base_settings_data())

        targets = settings.target_allocations

        assert targets["stocks"] == Decimal("70")
        assert targets["gold"] == Decimal("15")
        assert targets["bonds"] == Decimal("15")

    def test_missing_version_rejected(self) -> None:
        data = _base_settings_data()
        del data["version"]

        with pytest.raises(ValidationError, match="version"):
            Settings.model_validate(data)

    def test_empty_signals_and_channels_by_default(self) -> None:
        data = _base_settings_data()
        del data["channels"]
        del data["signals"]

        settings = Settings.model_validate(data)

        assert settings.channels == {}
        assert settings.signals == []


class TestAppConfig:
    def test_defaults(self) -> None:
        cfg = AppConfig(job_secret="s")

        assert cfg.log_level == "INFO"
        assert cfg.dev_mode is False
        assert cfg.port == 8080

    def test_job_secret_required(self) -> None:
        with pytest.raises(ValidationError, match="job_secret"):
            AppConfig.model_validate({})


class TestBrokerConfig:
    def test_defaults(self) -> None:
        cfg = BrokerConfig(phone_number="+49", pin="1234")

        assert cfg.type == "trade_republic"
        assert cfg.cookies_path == "/tmp/tr_cookies"

    def test_phone_and_pin_required(self) -> None:
        with pytest.raises(ValidationError):
            BrokerConfig.model_validate({})


class TestAssetConfig:
    def test_valid_id(self) -> None:
        cfg = AssetConfig(
            id="stocks_etf",
            name="S",
            isin="IE00BK5BQT80",
            target_pct=Decimal("50"),
        )
        assert cfg.id == "stocks_etf"

    @pytest.mark.parametrize(
        "bad_id",
        ["Invalid", "has-dash", "1starts_num", "HAS_UPPER", ""],
    )
    def test_invalid_id_rejected(self, bad_id: str) -> None:
        with pytest.raises(ValidationError):
            AssetConfig(
                id=bad_id,
                name="X",
                isin="IE00BK5BQT80",
                target_pct=Decimal("50"),
            )

    def test_valid_isin(self) -> None:
        cfg = AssetConfig(
            id="a",
            name="A",
            isin="IE00BK5BQT80",
            target_pct=Decimal("50"),
        )
        assert cfg.isin == "IE00BK5BQT80"

    @pytest.mark.parametrize("bad_isin", ["INVALID", "ie00bk5bqt80", "123"])
    def test_invalid_isin_rejected(self, bad_isin: str) -> None:
        with pytest.raises(ValidationError):
            AssetConfig(
                id="a",
                name="A",
                isin=bad_isin,
                target_pct=Decimal("50"),
            )

    def test_target_pct_range(self) -> None:
        with pytest.raises(ValidationError):
            AssetConfig(
                id="a",
                name="A",
                isin="IE00BK5BQT80",
                target_pct=Decimal("-1"),
            )

        with pytest.raises(ValidationError):
            AssetConfig(
                id="a",
                name="A",
                isin="IE00BK5BQT80",
                target_pct=Decimal("101"),
            )


class TestSignalConfig:
    def test_signal_config_empty_name_accepted(self) -> None:
        from pac.config.models import SignalConfig

        cfg = SignalConfig(
            name="",
            rule="threshold",
            schedule="0 * * * *",
            channels=["telegram"],
            template="default",
        )
        assert cfg.name == ""

    def test_signal_config_empty_channels_accepted(self) -> None:
        from pac.config.models import SignalConfig

        cfg = SignalConfig(
            name="test",
            rule="threshold",
            schedule="0 * * * *",
            channels=[],
            template="default",
        )
        assert cfg.channels == []


class TestSettingsEdgeCases:
    def test_duplicate_signal_names_accepted(self) -> None:
        data = _base_settings_data(
            channels={"telegram": {"type": "telegram", "bot_token": "t"}},
            signals=[
                {
                    "name": "same_name",
                    "rule": "threshold",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "template": "default",
                },
                {
                    "name": "same_name",
                    "rule": "cycle",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "template": "default",
                },
            ],
        )
        settings = Settings.model_validate(data)
        assert len(settings.signals) == 2

    def test_broker_custom_cookies_path(self) -> None:
        cfg = BrokerConfig(
            phone_number="+49",
            pin="1234",
            cookies_path="/custom/path",
        )
        assert cfg.cookies_path == "/custom/path"

    def test_allocation_over_100_rejected(self) -> None:
        data = _base_settings_data(
            assets=[
                {"id": "a", "name": "A", "isin": "IE00BK5BQT80", "target_pct": 60},
                {"id": "b", "name": "B", "isin": "IE00B4ND3602", "target_pct": 60},
            ],
        )
        with pytest.raises(ValidationError, match="sum to 100"):
            Settings.model_validate(data)
