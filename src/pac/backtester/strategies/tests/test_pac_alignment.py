from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pac.analysis.deviation import DeviationReport, DeviationResult
from pac.backtester.engine.actions import PacAdjustment
from pac.backtester.strategies.builtin.pac_alignment import (
    PacAlignmentParams,
    PacAlignmentStrategy,
)
from pac.backtester.strategies.discovery import discover_strategies
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import SignalSeverity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 3, 2, tzinfo=UTC)

_DEFAULT_PAC_VOLUMES: dict[str, Decimal] = {
    "stocks": Decimal("350"),
    "gold": Decimal("75"),
    "bonds": Decimal("75"),
}


def _make_deviation_result(
    asset_id: str,
    actual: float,
    target: float,
) -> DeviationResult:
    actual_d = Decimal(str(actual))
    target_d = Decimal(str(target))
    dev = target_d - actual_d
    return DeviationResult(
        asset_id=asset_id,
        name=asset_id.capitalize(),
        actual_pct=actual_d,
        target_pct=target_d,
        deviation_pct=dev,
        abs_deviation_pct=abs(dev),
        severity=SignalSeverity.INFO,
    )


def _make_report(
    *,
    stocks_actual: float = 70.0,
    gold_actual: float = 15.0,
    bonds_actual: float = 15.0,
) -> DeviationReport:
    deviations = {
        "stocks": _make_deviation_result("stocks", stocks_actual, 70.0),
        "gold": _make_deviation_result("gold", gold_actual, 15.0),
        "bonds": _make_deviation_result("bonds", bonds_actual, 15.0),
    }
    sev = max(
        (d.severity for d in deviations.values()),
        key=lambda s: {"info": 0, "warning": 1, "critical": 2}[s],
    )
    return DeviationReport(
        deviations=deviations,
        max_severity=sev,
        timestamp=_NOW,
    )


def _make_snapshot(*, cash: Decimal = Decimal("0")) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[],
        cash=cash,
        timestamp=_NOW,
    )


def _make_strategy(
    *,
    blend_factor: str = "1.0",
    min_eur_per_asset: str = "1.00",
) -> PacAlignmentStrategy:
    params = PacAlignmentParams(
        blend_factor=Decimal(blend_factor),
        min_eur_per_asset=Decimal(min_eur_per_asset),
    )
    return PacAlignmentStrategy(params)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPacAlignmentRegistration:
    def test_name_is_pac_alignment(self) -> None:
        assert PacAlignmentStrategy.name == "pac_alignment"

    def test_params_model_extracted(self) -> None:
        assert PacAlignmentStrategy.params_model is PacAlignmentParams

    def test_discovered_by_discover_strategies(self) -> None:
        discovered = discover_strategies()
        assert "pac_alignment" in discovered


class TestOnSignalsAlwaysEmpty:
    def test_on_signals_returns_empty_list_always(self) -> None:
        strategy = _make_strategy()
        result = strategy.on_signals(
            signals=[],
            snapshot=_make_snapshot(),
            report=_make_report(),
            current_date=_NOW.date(),
        )
        assert result == []


class TestOnPacDateNoAdjustmentNeeded:
    def test_returns_none_when_all_at_target(self) -> None:
        strategy = _make_strategy()
        report = _make_report(stocks_actual=70.0, gold_actual=15.0, bonds_actual=15.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert result is None

    def test_returns_none_when_all_overweight(self) -> None:
        # All actual > target → deficits are all 0
        strategy = _make_strategy()
        report = _make_report(stocks_actual=80.0, gold_actual=16.0, bonds_actual=16.0)
        # stocks deficit=0 (over), gold=0 (over), bonds=0 (over)
        # But these don't sum to 100 in a realistic sense; the key is deficit=0
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert result is None


class TestOnPacDateAdjustsVolumes:
    def test_shifts_entirely_toward_underweight_at_blend_1(self) -> None:
        """At blend=1.0, stocks (overweight) gets minimum; gold/bonds get max."""
        strategy = _make_strategy(blend_factor="1.0")
        # stocks at 80% (10pp over) → deficit=0
        # gold at 10% (5pp under) → deficit=5
        # bonds at 10% (5pp under) → deficit=5
        report = _make_report(stocks_actual=80.0, gold_actual=10.0, bonds_actual=10.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert isinstance(result, PacAdjustment)
        assert result.new_volumes["stocks"] == Decimal("1.00")
        assert result.new_volumes["gold"] > Decimal("1.00")
        assert result.new_volumes["bonds"] > Decimal("1.00")

    def test_blend_factor_0_returns_target_proportional(self) -> None:
        """blend=0.0: volumes proportional to target percentages.

        For a 70/15/15 target with €500 PAC: stocks=350, gold=75, bonds=75.
        Asset actual weights do NOT affect the result.
        """
        strategy = _make_strategy(blend_factor="0.0")
        # stocks is overweight, but blend=0 ignores deficit entirely
        report = _make_report(stocks_actual=80.0, gold_actual=10.0, bonds_actual=10.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert isinstance(result, PacAdjustment)
        # 70/100 * 500 = 350, 15/100 * 500 = 75
        assert result.new_volumes["stocks"] == Decimal("350.00")
        assert result.new_volumes["gold"] == Decimal("75.00")
        assert result.new_volumes["bonds"] == Decimal("75.00")

    def test_preserves_total_pac_budget(self) -> None:
        """sum(new_volumes) == sum(current_pac_volumes) within €0.02."""
        strategy = _make_strategy(blend_factor="0.7")
        report = _make_report(stocks_actual=80.0, gold_actual=10.0, bonds_actual=10.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert isinstance(result, PacAdjustment)
        total_input = sum(_DEFAULT_PAC_VOLUMES.values(), Decimal("0"))
        total_output = sum(result.new_volumes.values(), Decimal("0"))
        assert abs(total_output - total_input) <= Decimal("0.02")

    def test_each_asset_gets_at_least_min_eur(self) -> None:
        """With min_eur_per_asset=10, all assets receive ≥ €10."""
        strategy = _make_strategy(blend_factor="1.0", min_eur_per_asset="10.00")
        report = _make_report(stocks_actual=80.0, gold_actual=10.0, bonds_actual=10.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert isinstance(result, PacAdjustment)
        for aid, vol in result.new_volumes.items():
            assert vol >= Decimal("10.00"), f"{aid} got {vol} < 10"

    def test_partial_blend_distributes_proportionally(self) -> None:
        """blend=0.5: result is between pure-target and pure-deficit distributions."""
        strategy = _make_strategy(blend_factor="0.5")
        # gold/bonds both underweight equally
        report = _make_report(stocks_actual=80.0, gold_actual=10.0, bonds_actual=10.0)
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=dict(_DEFAULT_PAC_VOLUMES),
        )
        assert isinstance(result, PacAdjustment)
        # stocks gets less than 350 (it's overweight, blend=0.5 reduces its share)
        assert result.new_volumes["stocks"] < Decimal("350.00")
        # gold and bonds get more than their target-proportional share (75)
        assert result.new_volumes["gold"] > Decimal("75.00")
        assert result.new_volumes["bonds"] > Decimal("75.00")


class TestOnPacDateVolumeTotals:
    def test_total_volumes_match_original_within_cent(self) -> None:
        """Rounding correction step ensures totals are preserved exactly."""
        strategy = _make_strategy(blend_factor="0.6")
        report = _make_report(stocks_actual=75.0, gold_actual=12.0, bonds_actual=13.0)
        pac_volumes = {
            "stocks": Decimal("350"),
            "gold": Decimal("75"),
            "bonds": Decimal("75"),
        }
        result = strategy.on_pac_date(
            snapshot=_make_snapshot(),
            report=report,
            current_date=_NOW.date(),
            current_pac_volumes=pac_volumes,
        )
        assert isinstance(result, PacAdjustment)
        assert sum(result.new_volumes.values()) == sum(pac_volumes.values())
