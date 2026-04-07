from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pac.backtester.config import BacktestConfig


class TestBacktestConfigDefaults:
    def test_config_default_values(self) -> None:
        config = BacktestConfig(
            strategy="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert config.initial_cash == Decimal("10000")
        assert config.monthly_contribution == Decimal("500")
        assert config.pac_execution_days == [2, 16]
        assert config.settlement_fee == Decimal("1.00")
        assert config.spread_bps == Decimal("10")
        assert config.slippage_days == (0, 3)
        assert config.monte_carlo_iterations == 100
        assert config.benchmark is True
        assert "sortino" in config.metrics


class TestBacktestConfigValidation:
    def test_config_rejects_start_after_end(self) -> None:
        with pytest.raises(ValidationError, match="start_date"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),
            )

    def test_config_rejects_start_equals_end(self) -> None:
        with pytest.raises(ValidationError, match="start_date"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 6, 1),
                end_date=date(2024, 6, 1),
            )

    def test_config_rejects_negative_slippage(self) -> None:
        with pytest.raises(ValidationError, match="slippage_days"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                slippage_days=(-1, 3),
            )

    def test_config_rejects_inverted_slippage(self) -> None:
        with pytest.raises(ValidationError, match="slippage_days"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                slippage_days=(5, 2),
            )

    def test_config_rejects_pac_day_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="PAC execution day"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                pac_execution_days=[0],
            )

        with pytest.raises(ValidationError, match="PAC execution day"):
            BacktestConfig(
                strategy="test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                pac_execution_days=[29],
            )

    def test_config_frozen(self) -> None:
        config = BacktestConfig(
            strategy="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        with pytest.raises(ValidationError):
            config.strategy = "changed"  # type: ignore[misc]
