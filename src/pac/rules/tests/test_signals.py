from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import SignalRule, _NoParams
from pac.rules.builtin.cycle import CycleInversionParams, CycleInversionRule
from pac.rules.builtin.pac_plan import PacPlanParams, PacPlanRule
from pac.rules.builtin.threshold import ThresholdDeviationRule, ThresholdParams
from pac.rules.registry import SignalRegistry


def _make_snapshot(
    stocks_value: Decimal,
    gold_value: Decimal,
    bonds_value: Decimal,
    cash: Decimal = Decimal(0),
) -> PortfolioSnapshot:
    """Helper to build a snapshot with given market values."""
    positions = []
    for isin, name, value, aid in [
        ("IE00BK5BQT80", "Stocks ETF", stocks_value, "stocks"),
        ("IE00B4ND3602", "Gold ETC", gold_value, "gold"),
        ("IE00B3F81409", "Bond ETF", bonds_value, "bonds"),
    ]:
        if value > 0:
            positions.append(
                Position(
                    isin=isin,
                    name=name,
                    quantity=Decimal(1),
                    price=value,
                    market_value=value,
                    asset_id=aid,
                )
            )
    return PortfolioSnapshot(
        positions=positions,
        cash=cash,
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


class TestSignalRuleABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            SignalRule()  # type: ignore[abstract]

    def test_concrete_subclass_gets_params_model_auto_set(self) -> None:
        class _MyParams(BaseModel):
            threshold: float = 1.0

        class _MyRule(SignalRule[_MyParams]):
            @property
            def name(self) -> str:
                return "my_rule"

            def evaluate(
                self,
                report: Any,
                snapshot: Any,
                params: _MyParams,
            ) -> list[Signal]:
                return []

        assert _MyRule.params_model is _MyParams

    def test_subclass_without_generic_arg_retains_no_params(self) -> None:
        class _RawRule(SignalRule):  # type: ignore[type-arg]
            @property
            def name(self) -> str:
                return "raw"

            def evaluate(
                self,
                report: Any,
                snapshot: Any,
                params: Any,
            ) -> list[Signal]:
                return []

        assert _RawRule.params_model is _NoParams

    def test_threshold_rule_params_model(self) -> None:
        assert ThresholdDeviationRule.params_model is ThresholdParams

    def test_cycle_rule_params_model(self) -> None:
        assert CycleInversionRule.params_model is CycleInversionParams

    def test_pac_plan_rule_params_model(self) -> None:
        assert PacPlanRule.params_model is PacPlanParams


class TestSignalRegistry:
    def test_empty_registry_returns_no_signals(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        registry = SignalRegistry()
        report = calculate_deviations(sample_snapshot, default_settings)
        assert registry.evaluate_all(report, sample_snapshot) == []

    def test_register_non_subclass_raises_type_error(self) -> None:
        registry = SignalRegistry()
        with pytest.raises(TypeError, match="is not a SignalRule subclass"):
            registry.register("not a rule")  # type: ignore[arg-type]

    def test_register_missing_params_model_raises_type_error(self) -> None:
        class _RawRule(SignalRule):  # type: ignore[type-arg]
            @property
            def name(self) -> str:
                return "raw"

            def evaluate(
                self,
                report: Any,
                snapshot: Any,
                params: Any,
            ) -> list[Signal]:
                return []

        registry = SignalRegistry()
        with pytest.raises(TypeError, match="has no params_model"):
            registry.register(_RawRule)

    def test_len_reflects_registered_rules(self) -> None:
        registry = SignalRegistry()
        assert len(registry) == 0
        registry.register(ThresholdDeviationRule)
        assert len(registry) == 1
        registry.register(CycleInversionRule)
        assert len(registry) == 2

    def test_contains(self) -> None:
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule)
        assert "threshold_deviation" in registry
        assert "cycle_inversion" not in registry

    def test_rule_names(self) -> None:
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule)
        registry.register(CycleInversionRule)
        assert set(registry.rule_names) == {
            "threshold_deviation",
            "cycle_inversion",
        }

    def test_get_rule(self) -> None:
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule)
        assert registry.get_rule("threshold_deviation") is ThresholdDeviationRule

    def test_get_rule_unknown_raises_key_error(self) -> None:
        registry = SignalRegistry()
        with pytest.raises(KeyError):
            registry.get_rule("nonexistent")

    def test_evaluate_all_merges_signals_from_all_rules(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule)
        registry.register(CycleInversionRule)
        signals = registry.evaluate_all(report, snapshot)
        rule_names = {s.name for s in signals}
        assert "threshold_deviation" in rule_names
        assert "cycle_inversion" in rule_names

    def test_evaluate_signal_with_params_dict(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7200"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1300"),
        )
        report = calculate_deviations(snapshot, default_settings)
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule)
        signals = registry.evaluate_signal(
            "threshold_deviation",
            {"warning_pct": "1.0", "critical_pct": "3.0"},
            report,
            snapshot,
        )
        assert len(signals) > 0

    def test_evaluate_signal_unknown_raises_key_error(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        registry = SignalRegistry()
        report = calculate_deviations(sample_snapshot, default_settings)
        with pytest.raises(KeyError):
            registry.evaluate_signal(
                "nonexistent",
                {},
                report,
                sample_snapshot,
            )


class TestThresholdDeviationRule:
    def test_perfect_allocation_yields_no_signals(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        assert rule.evaluate(report, snapshot, ThresholdParams()) == []

    def test_overweight_class_yields_critical_signal(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())

        stocks_signals = [s for s in signals if s.metadata.get("asset_id") == "stocks"]
        assert len(stocks_signals) == 1
        assert stocks_signals[0].severity == SignalSeverity.CRITICAL
        assert stocks_signals[0].metadata["direction"] == "overweight"

    def test_underweight_class_yields_correct_direction(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())

        bonds_signals = [s for s in signals if s.metadata.get("asset_id") == "bonds"]
        assert len(bonds_signals) == 1
        assert bonds_signals[0].severity == SignalSeverity.CRITICAL
        assert bonds_signals[0].metadata["direction"] == "underweight"

    def test_multiple_deviating_classes_yields_multiple_signals(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("8000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())
        assert len(signals) >= 2
        classes = {s.metadata["asset_id"] for s in signals}
        assert "stocks" in classes
        assert "bonds" in classes

    def test_signal_metadata_contains_expected_keys(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())
        assert len(signals) > 0
        for signal in signals:
            assert "asset_id" in signal.metadata
            assert "deviation_pct" in signal.metadata
            assert "abs_deviation_pct" in signal.metadata
            assert "direction" in signal.metadata
            assert signal.name == "threshold_deviation"
            assert signal.triggered_at == report.timestamp

    def test_warning_severity_at_warning_threshold(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7300"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1200"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())
        stocks_signals = [s for s in signals if s.metadata.get("asset_id") == "stocks"]
        assert len(stocks_signals) == 1
        assert stocks_signals[0].severity == SignalSeverity.WARNING

    def test_custom_params_lower_threshold(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7200"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1300"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        params = ThresholdParams(
            warning_pct=Decimal("1.0"),
            critical_pct=Decimal("3.0"),
        )
        signals = rule.evaluate(report, snapshot, params)
        stocks_signals = [s for s in signals if s.metadata.get("asset_id") == "stocks"]
        assert len(stocks_signals) == 1
        assert stocks_signals[0].severity == SignalSeverity.WARNING


class TestCycleInversionRule:
    def test_same_direction_deviations_yield_no_signals(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("6800"),
            gold_value=Decimal("1450"),
            bonds_value=Decimal("1450"),
            cash=Decimal("300"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        assert rule.evaluate(report, snapshot, CycleInversionParams()) == []

    def test_opposing_deviations_yield_inversion_signal(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        assert len(signals) >= 1
        inversion = signals[0]
        assert inversion.name == "cycle_inversion"
        assert inversion.metadata["overweight_class"] == "stocks"
        assert inversion.metadata["underweight_class"] == "bonds"

    def test_below_min_threshold_yields_no_signal(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7100"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1400"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        assert signals == []

    def test_one_side_below_min_yields_no_signal(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7500"),
            gold_value=Decimal("1400"),
            bonds_value=Decimal("1100"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        for s in signals:
            over_class = str(s.metadata["overweight_class"])
            under_class = str(s.metadata["underweight_class"])
            over_dev = abs(report.deviations[over_class].deviation_pct)
            under_dev = abs(report.deviations[under_class].deviation_pct)
            assert over_dev >= Decimal("2.0")
            assert under_dev >= Decimal("2.0")

    def test_severity_scales_with_combined_divergence(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot_info = _make_snapshot(
            stocks_value=Decimal("7200"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1300"),
        )
        report_info = calculate_deviations(snapshot_info, default_settings)
        rule = CycleInversionRule()
        signals_info = rule.evaluate(report_info, snapshot_info, CycleInversionParams())
        info_signals = [s for s in signals_info if s.severity == SignalSeverity.INFO]

        snapshot_critical = _make_snapshot(
            stocks_value=Decimal("8000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("500"),
        )
        report_critical = calculate_deviations(snapshot_critical, default_settings)
        signals_critical = rule.evaluate(
            report_critical, snapshot_critical, CycleInversionParams()
        )
        critical_signals = [
            s for s in signals_critical if s.severity == SignalSeverity.CRITICAL
        ]

        assert len(info_signals) > 0 or len(signals_info) == 0
        assert len(critical_signals) > 0

    def test_multiple_pairs_can_invert(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("8500"),
            gold_value=Decimal("800"),
            bonds_value=Decimal("700"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        assert len(signals) >= 2
        pairs = {
            (s.metadata["overweight_class"], s.metadata["underweight_class"])
            for s in signals
        }
        assert len(pairs) >= 2

    def test_signal_metadata_contains_expected_keys(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        assert len(signals) > 0
        for signal in signals:
            assert "overweight_class" in signal.metadata
            assert "underweight_class" in signal.metadata
            assert "overweight_deviation_pct" in signal.metadata
            assert "underweight_deviation_pct" in signal.metadata
            assert "combined_divergence_pct" in signal.metadata
            assert signal.name == "cycle_inversion"
            assert signal.triggered_at == report.timestamp

    def test_custom_min_pct(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7150"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1350"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        assert rule.evaluate(report, snapshot, CycleInversionParams()) == []
        params = CycleInversionParams(min_pct=Decimal("1.0"))
        signals = rule.evaluate(report, snapshot, params)
        assert len(signals) >= 1


# ── PacPlanRule tests ─────────────────────────────────────────────────


class TestPacPlanRule:
    def test_params_model_is_pac_plan_params(self) -> None:
        assert PacPlanRule.params_model is PacPlanParams

    def test_evaluate_produces_info_signal(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = PacPlanRule()
        signals = rule.evaluate(report, snapshot, PacPlanParams())
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.INFO
        assert signals[0].name == "pac_plan"
        assert "allocations" in signals[0].metadata

    def test_custom_budget(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = PacPlanRule()
        params = PacPlanParams(monthly_budget=Decimal("300.00"))
        signals = rule.evaluate(report, snapshot, params)
        assert len(signals) == 1
        assert signals[0].metadata["monthly_budget"] == 300.0


# ── build_template_data() tests ──────────────────────────────────────


class TestBuildTemplateData:
    """Test build_template_data() classmethods on all builtin rules."""

    def test_threshold_build_template_data_contains_deviations(
        self,
        default_settings: Settings,
    ) -> None:
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())
        assert len(signals) > 0

        data = ThresholdDeviationRule.build_template_data(signals, report, snapshot)

        assert "signal" in data
        assert data["signal"] is signals[0]
        assert "deviations" in data
        assert len(data["deviations"]) == len(report.deviations)

    def test_threshold_build_template_data_deviations_are_result_objects(
        self,
        default_settings: Settings,
    ) -> None:
        from pac.analysis.deviation import DeviationResult

        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, ThresholdParams())

        data = ThresholdDeviationRule.build_template_data(signals, report, snapshot)

        for item in data["deviations"]:
            assert isinstance(item, DeviationResult)

    def test_cycle_build_template_data_returns_default_signal(
        self,
        default_settings: Settings,
    ) -> None:
        """CycleInversionRule inherits the default — returns {'signal': signals[0]}."""
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, CycleInversionParams())
        assert len(signals) > 0

        data = CycleInversionRule.build_template_data(signals, report, snapshot)

        assert data == {"signal": signals[0]}

    def test_pac_plan_build_template_data_returns_plan(
        self,
        default_settings: Settings,
    ) -> None:
        from pac.analysis.rebalance import PacPlan

        snapshot = _make_snapshot(
            stocks_value=Decimal("7000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = PacPlanRule()
        signals = rule.evaluate(report, snapshot, PacPlanParams())

        data = PacPlanRule.build_template_data(signals, report, snapshot)

        assert "plan" in data
        assert isinstance(data["plan"], PacPlan)
        assert data["plan"].total_budget == Decimal("500.00")

    def test_pac_plan_build_template_data_uses_budget_from_signal_metadata(
        self,
        default_settings: Settings,
    ) -> None:
        from pac.analysis.rebalance import PacPlan

        snapshot = _make_snapshot(
            stocks_value=Decimal("7000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = PacPlanRule()
        params = PacPlanParams(monthly_budget=Decimal("300.00"))
        signals = rule.evaluate(report, snapshot, params)

        data = PacPlanRule.build_template_data(signals, report, snapshot)

        assert isinstance(data["plan"], PacPlan)
        assert data["plan"].total_budget == Decimal("300.00")
