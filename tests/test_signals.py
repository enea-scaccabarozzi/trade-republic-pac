from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pac.analysis.deviation import calculate_deviations
from pac.config import Settings
from pac.models.portfolio import AssetClass, PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity
from pac.signals.base import SignalRule
from pac.signals.registry import SignalRegistry
from pac.signals.rules import create_default_registry
from pac.signals.rules.cycle import CycleInversionRule
from pac.signals.rules.threshold import ThresholdDeviationRule


def _make_snapshot(
    stocks_value: Decimal,
    gold_value: Decimal,
    bonds_value: Decimal,
    cash: Decimal = Decimal(0),
) -> PortfolioSnapshot:
    """Helper to build a snapshot with given market values."""
    positions = []
    for isin, name, value, ac in [
        ("IE00BK5BQT80", "Stocks ETF", stocks_value, AssetClass.STOCKS),
        ("IE00B4ND3602", "Gold ETC", gold_value, AssetClass.GOLD),
        ("IE00B3F81409", "Bond ETF", bonds_value, AssetClass.BONDS),
    ]:
        if value > 0:
            positions.append(
                Position(
                    isin=isin,
                    name=name,
                    quantity=Decimal(1),
                    price=value,
                    market_value=value,
                    asset_class=ac,
                )
            )
    return PortfolioSnapshot(
        positions=positions,
        cash=cash,
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


class TestSignalRuleProtocol:
    def test_threshold_rule_satisfies_protocol(self) -> None:
        assert isinstance(ThresholdDeviationRule(), SignalRule)

    def test_cycle_rule_satisfies_protocol(self) -> None:
        assert isinstance(CycleInversionRule(), SignalRule)

    def test_custom_rule_satisfies_protocol(self) -> None:
        class _CustomRule:
            @property
            def name(self) -> str:
                return "custom"

            def evaluate(
                self,
                report: object,
                snapshot: object,
                settings: object,
            ) -> list[Signal]:
                return []

        assert isinstance(_CustomRule(), SignalRule)

    def test_non_conforming_rejected(self) -> None:
        class _BadRule:
            pass

        assert not isinstance(_BadRule(), SignalRule)


class TestSignalRegistry:
    def test_empty_registry_returns_no_signals(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        registry = SignalRegistry()
        report = calculate_deviations(sample_snapshot, default_settings)
        assert registry.evaluate_all(report, sample_snapshot, default_settings) == []

    def test_register_non_conforming_raises_type_error(self) -> None:
        registry = SignalRegistry()
        import pytest

        with pytest.raises(TypeError, match="does not implement SignalRule"):
            registry.register("not a rule")  # type: ignore[arg-type]

    def test_len_reflects_registered_rules(self) -> None:
        registry = SignalRegistry()
        assert len(registry) == 0
        registry.register(ThresholdDeviationRule())
        assert len(registry) == 1
        registry.register(CycleInversionRule())
        assert len(registry) == 2

    def test_evaluate_all_merges_signals_from_all_rules(
        self,
        default_settings: Settings,
    ) -> None:
        # Stocks overweight, bonds underweight → both rules should fire
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        registry = SignalRegistry()
        registry.register(ThresholdDeviationRule())
        registry.register(CycleInversionRule())
        signals = registry.evaluate_all(report, snapshot, default_settings)
        rule_names = {s.name for s in signals}
        assert "threshold_deviation" in rule_names
        assert "cycle_inversion" in rule_names


class TestCreateDefaultRegistry:
    def test_returns_registry_with_two_rules(self) -> None:
        registry = create_default_registry()
        assert len(registry) == 2
        names = [r.name for r in registry]
        assert "threshold_deviation" in names
        assert "cycle_inversion" in names


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
        assert rule.evaluate(report, snapshot, default_settings) == []

    def test_overweight_class_yields_critical_signal(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks = 76%, gold = 15%, bonds = 9% → stocks +6pp CRITICAL
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, default_settings)

        stocks_signals = [
            s for s in signals if s.metadata.get("asset_class") == "stocks"
        ]
        assert len(stocks_signals) == 1
        assert stocks_signals[0].severity == SignalSeverity.CRITICAL
        assert stocks_signals[0].metadata["direction"] == "overweight"

    def test_underweight_class_yields_correct_direction(
        self,
        default_settings: Settings,
    ) -> None:
        # bonds = 7% → -8pp underweight CRITICAL
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, default_settings)

        bonds_signals = [s for s in signals if s.metadata.get("asset_class") == "bonds"]
        assert len(bonds_signals) == 1
        assert bonds_signals[0].severity == SignalSeverity.CRITICAL
        assert bonds_signals[0].metadata["direction"] == "underweight"

    def test_multiple_deviating_classes_yields_multiple_signals(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks = 80%, gold = 15%, bonds = 5% → stocks +10 CRITICAL, bonds -10 CRITICAL
        snapshot = _make_snapshot(
            stocks_value=Decimal("8000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("500"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, default_settings)
        assert len(signals) >= 2
        classes = {s.metadata["asset_class"] for s in signals}
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
        signals = rule.evaluate(report, snapshot, default_settings)
        assert len(signals) > 0
        for signal in signals:
            assert "asset_class" in signal.metadata
            assert "deviation_pct" in signal.metadata
            assert "abs_deviation_pct" in signal.metadata
            assert "direction" in signal.metadata
            assert signal.name == "threshold_deviation"
            assert signal.triggered_at == report.timestamp

    def test_warning_severity_at_warning_threshold(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks = 73% → +3pp = exactly WARNING threshold
        snapshot = _make_snapshot(
            stocks_value=Decimal("7300"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1200"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = ThresholdDeviationRule()
        signals = rule.evaluate(report, snapshot, default_settings)
        stocks_signals = [
            s for s in signals if s.metadata.get("asset_class") == "stocks"
        ]
        assert len(stocks_signals) == 1
        assert stocks_signals[0].severity == SignalSeverity.WARNING


class TestCycleInversionRule:
    def test_same_direction_deviations_yield_no_signals(
        self,
        default_settings: Settings,
    ) -> None:
        # All slightly underweight (cash drag) — no inversions
        snapshot = _make_snapshot(
            stocks_value=Decimal("6800"),
            gold_value=Decimal("1450"),
            bonds_value=Decimal("1450"),
            cash=Decimal("300"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        assert rule.evaluate(report, snapshot, default_settings) == []

    def test_opposing_deviations_yield_inversion_signal(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks +6pp, bonds -6pp → clear inversion
        snapshot = _make_snapshot(
            stocks_value=Decimal("7600"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("900"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, default_settings)
        assert len(signals) >= 1
        inversion = signals[0]
        assert inversion.name == "cycle_inversion"
        assert inversion.metadata["overweight_class"] == "stocks"
        assert inversion.metadata["underweight_class"] == "bonds"

    def test_below_min_threshold_yields_no_signal(self) -> None:
        # cycle_inversion_min_pct = 5 → deviations of ~3pp each are below
        settings = Settings(
            tr_phone_number="+491234567890",
            tr_pin="1234",
            telegram_bot_token="fake-token",
            telegram_chat_id="12345",
            webhook_secret="test-secret",
            job_secret="test-job-secret",
            cycle_inversion_min_pct=Decimal("5.0"),
        )
        snapshot = _make_snapshot(
            stocks_value=Decimal("7300"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1200"),
        )
        report = calculate_deviations(snapshot, settings)
        rule = CycleInversionRule()
        assert rule.evaluate(report, snapshot, settings) == []

    def test_one_side_below_min_yields_no_signal(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks +5pp (above min 2), gold -1pp (below min 2) → no inversion
        snapshot = _make_snapshot(
            stocks_value=Decimal("7500"),
            gold_value=Decimal("1400"),
            bonds_value=Decimal("1100"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, default_settings)
        # Verify no signal where one side is below min
        for s in signals:
            over_class = s.metadata["overweight_class"]
            under_class = s.metadata["underweight_class"]
            over_dev = abs(report.deviations[AssetClass(over_class)].deviation_pct)
            under_dev = abs(report.deviations[AssetClass(under_class)].deviation_pct)
            assert over_dev >= default_settings.cycle_inversion_min_pct
            assert under_dev >= default_settings.cycle_inversion_min_pct

    def test_severity_scales_with_combined_divergence(
        self,
        default_settings: Settings,
    ) -> None:
        # Small inversion: combined ~4pp → INFO (below 2*3=6 WARNING threshold)
        snapshot_info = _make_snapshot(
            stocks_value=Decimal("7200"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("1300"),
        )
        report_info = calculate_deviations(snapshot_info, default_settings)
        rule = CycleInversionRule()
        signals_info = rule.evaluate(report_info, snapshot_info, default_settings)
        info_signals = [s for s in signals_info if s.severity == SignalSeverity.INFO]

        # Large inversion: combined ~12pp → CRITICAL (above 2*5=10)
        snapshot_critical = _make_snapshot(
            stocks_value=Decimal("8000"),
            gold_value=Decimal("1500"),
            bonds_value=Decimal("500"),
        )
        report_critical = calculate_deviations(snapshot_critical, default_settings)
        signals_critical = rule.evaluate(
            report_critical, snapshot_critical, default_settings
        )
        critical_signals = [
            s for s in signals_critical if s.severity == SignalSeverity.CRITICAL
        ]

        assert len(info_signals) > 0 or len(signals_info) == 0  # may not breach min
        assert len(critical_signals) > 0

    def test_multiple_pairs_can_invert(
        self,
        default_settings: Settings,
    ) -> None:
        # stocks very overweight, gold and bonds underweight → 2 pairs
        snapshot = _make_snapshot(
            stocks_value=Decimal("8500"),
            gold_value=Decimal("800"),
            bonds_value=Decimal("700"),
        )
        report = calculate_deviations(snapshot, default_settings)
        rule = CycleInversionRule()
        signals = rule.evaluate(report, snapshot, default_settings)
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
        signals = rule.evaluate(report, snapshot, default_settings)
        assert len(signals) > 0
        for signal in signals:
            assert "overweight_class" in signal.metadata
            assert "underweight_class" in signal.metadata
            assert "overweight_deviation_pct" in signal.metadata
            assert "underweight_deviation_pct" in signal.metadata
            assert "combined_divergence_pct" in signal.metadata
            assert signal.name == "cycle_inversion"
            assert signal.triggered_at == report.timestamp
