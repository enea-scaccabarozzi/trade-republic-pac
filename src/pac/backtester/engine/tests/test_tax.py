from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from pac.backtester.engine.tax import (
    AssetTaxMeta,
    ItalianTaxRegime,
    NoTaxRegime,
    TaxResult,
    resolve_tax_regime,
)


class TestTaxResult:
    def test_tax_result_stores_fields(self) -> None:
        result = TaxResult(
            tax_owed=Decimal("26.00"),
            loss_recorded=Decimal("0.00"),
            effective_rate=Decimal("0.26"),
        )
        assert result.tax_owed == Decimal("26.00")
        assert result.loss_recorded == Decimal("0.00")
        assert result.effective_rate == Decimal("0.26")

    def test_tax_result_is_frozen(self) -> None:
        result = TaxResult(
            tax_owed=Decimal("10.00"),
            loss_recorded=Decimal("0.00"),
            effective_rate=Decimal("0.26"),
        )
        with pytest.raises((ValidationError, TypeError)):
            result.tax_owed = Decimal("0.00")  # type: ignore[misc]


class TestAssetTaxMeta:
    def test_government_bond_defaults_to_false(self) -> None:
        meta = AssetTaxMeta()
        assert meta.government_bond is False

    def test_government_bond_can_be_set_true(self) -> None:
        meta = AssetTaxMeta(government_bond=True)
        assert meta.government_bond is True

    def test_asset_tax_meta_is_frozen(self) -> None:
        meta = AssetTaxMeta()
        with pytest.raises((ValidationError, TypeError)):
            meta.government_bond = True  # type: ignore[misc]


class TestNoTaxRegime:
    def test_name_is_none(self) -> None:
        regime = NoTaxRegime()
        assert regime.name == "none"

    def test_zero_tax_on_gain(self) -> None:
        regime = NoTaxRegime()
        meta = AssetTaxMeta()
        result = regime.compute_tax(
            proceeds=Decimal("1260.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0")

    def test_zero_tax_on_loss(self) -> None:
        regime = NoTaxRegime()
        meta = AssetTaxMeta()
        result = regime.compute_tax(
            proceeds=Decimal("800.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0")

    def test_reset_is_noop(self) -> None:
        regime = NoTaxRegime()
        # reset should not raise and calling compute_tax after reset works identically
        regime.reset()
        meta = AssetTaxMeta()
        result = regime.compute_tax(
            proceeds=Decimal("1500.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
        )
        assert result.tax_owed == Decimal("0")


class TestItalianTaxRegime:
    def test_name(self) -> None:
        regime = ItalianTaxRegime()
        assert regime.name == "italian"

    def test_standard_rate_on_gain(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        # gain = 100, tax = 100 * 0.26 = 26.00
        assert result.tax_owed == Decimal("26.00")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0.26")

    def test_government_bond_reduced_rate(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=True)
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        # gain = 100, tax = 100 * 0.125 = 12.50
        assert result.tax_owed == Decimal("12.50")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0.125")

    def test_loss_records_no_tax(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        result = regime.compute_tax(
            proceeds=Decimal("800.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        # loss = 200, no tax, loss recorded
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("200")
        assert result.effective_rate == Decimal("0")

    def test_loss_carryforward_offsets_future_gain(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        # Record a loss of 50 in year 2023
        regime.compute_tax(
            proceeds=Decimal("950.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2023,
        )
        # Gain of 100 in year 2023: only 50 is taxable after offset
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2023,
        )
        # taxable_gain = 100 - 50 = 50, tax = 50 * 0.26 = 13.00
        assert result.tax_owed == Decimal("13.00")
        assert result.loss_recorded == Decimal("0")

    def test_loss_expires_after_4_years(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        # Record a loss in 2020
        regime.compute_tax(
            proceeds=Decimal("900.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2020,
        )
        # In 2025, carryforward_years=4, so 2025-2020=5 > 4 → expired
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2025,
        )
        # full gain of 100 is taxable because 2020 loss has expired
        assert result.tax_owed == Decimal("26.00")

    def test_loss_still_valid_at_4_years(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        # Record a loss of 100 in 2020
        regime.compute_tax(
            proceeds=Decimal("900.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2020,
        )
        # In 2024, 2024-2020=4 which equals carryforward_years → still valid
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        # loss of 100 fully offsets gain of 100 → zero tax
        assert result.tax_owed == Decimal("0.00")

    def test_fifo_loss_consumption(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        # Record 60 loss in 2021
        regime.compute_tax(
            proceeds=Decimal("940.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2021,
        )
        # Record 60 loss in 2022
        regime.compute_tax(
            proceeds=Decimal("940.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2022,
        )
        # Gain of 80 in 2023: FIFO consumes 60 from 2021, then 20 from 2022
        result = regime.compute_tax(
            proceeds=Decimal("1080.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2023,
        )
        # After full offset, taxable_gain = 0 → zero tax
        assert result.tax_owed == Decimal("0.00")
        # Remaining 40 from 2022 should still be available for future use
        result2 = regime.compute_tax(
            proceeds=Decimal("1050.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2023,
        )
        # gain=50, 40 remains from 2022 → taxable=10 → tax=2.60
        assert result2.tax_owed == Decimal("2.60")

    def test_reset_clears_loss_ledger(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        # Record a loss of 200
        regime.compute_tax(
            proceeds=Decimal("800.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        regime.reset()
        # After reset, the full gain is taxable — no prior losses
        result = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        assert result.tax_owed == Decimal("26.00")

    def test_custom_rates(self) -> None:
        regime = ItalianTaxRegime(
            default_rate=Decimal("0.30"),
            government_bond_rate=Decimal("0.10"),
        )
        meta_std = AssetTaxMeta(government_bond=False)
        meta_gov = AssetTaxMeta(government_bond=True)
        result_std = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta_std,
            current_year=2024,
        )
        result_gov = regime.compute_tax(
            proceeds=Decimal("1100.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta_gov,
            current_year=2024,
        )
        assert result_std.tax_owed == Decimal("30.00")
        assert result_gov.tax_owed == Decimal("10.00")

    def test_break_even_trade(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta(government_bond=False)
        result = regime.compute_tax(
            proceeds=Decimal("1000.00"),
            cost_basis=Decimal("1000.00"),
            asset_meta=meta,
            current_year=2024,
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0")


class TestTaxRegimeRegistry:
    def test_resolve_italian(self) -> None:
        regime = resolve_tax_regime("italian", {})
        assert regime.name == "italian"
        assert isinstance(regime, ItalianTaxRegime)

    def test_resolve_none(self) -> None:
        regime = resolve_tax_regime("none", {})
        assert regime.name == "none"
        assert isinstance(regime, NoTaxRegime)

    def test_resolve_italian_with_custom_params(self) -> None:
        regime = resolve_tax_regime(
            "italian",
            {"default_rate": 0.30, "loss_carryforward_years": 2},
        )
        assert isinstance(regime, ItalianTaxRegime)
        # Verify custom rate works
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("30.00")

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tax regime"):
            resolve_tax_regime("unknown", {})
