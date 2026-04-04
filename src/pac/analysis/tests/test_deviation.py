from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from tests.conftest import make_settings

from pac.analysis.deviation import (
    calculate_deviations,
    classify_severity,
    get_target_allocations,
)
from pac.config import Settings
from pac.models.portfolio import (
    PortfolioSnapshot,
    Position,
)
from pac.models.signals import SignalSeverity


class TestGetTargetAllocations:
    def test_returns_decimal_targets(self, default_settings: Settings) -> None:
        targets = get_target_allocations(default_settings)

        assert targets == {
            "stocks": Decimal(70),
            "gold": Decimal(15),
            "bonds": Decimal(15),
        }

    def test_custom_targets(self) -> None:
        settings = make_settings(
            assets=[
                {
                    "id": "stocks",
                    "name": "Stocks ETF",
                    "isin": "IE00BK5BQT80",
                    "target_pct": 50,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "target_pct": 30,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "target_pct": 20,
                },
            ],
        )
        targets = get_target_allocations(settings)

        assert targets["stocks"] == Decimal(50)
        assert targets["gold"] == Decimal(30)
        assert targets["bonds"] == Decimal(20)


class TestClassifySeverity:
    def test_info_below_warning(self) -> None:
        result = classify_severity(Decimal("2.0"), Decimal("3.0"), Decimal("5.0"))
        assert result == SignalSeverity.INFO

    def test_warning_at_threshold(self) -> None:
        result = classify_severity(Decimal("3.0"), Decimal("3.0"), Decimal("5.0"))
        assert result == SignalSeverity.WARNING

    def test_warning_between_thresholds(self) -> None:
        result = classify_severity(Decimal("4.0"), Decimal("3.0"), Decimal("5.0"))
        assert result == SignalSeverity.WARNING

    def test_critical_at_threshold(self) -> None:
        result = classify_severity(Decimal("5.0"), Decimal("3.0"), Decimal("5.0"))
        assert result == SignalSeverity.CRITICAL

    def test_critical_above_threshold(self) -> None:
        result = classify_severity(Decimal("8.0"), Decimal("3.0"), Decimal("5.0"))
        assert result == SignalSeverity.CRITICAL


class TestCalculateDeviations:
    def test_sample_portfolio_deviations(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        """Sample: stocks=1000, gold=200, bonds=100, cash=200 → total=1500.

        actual_pct: stocks≈66.67, gold≈13.33, bonds≈6.67
        deviation: stocks≈-3.33 (WARNING), gold≈-1.67 (INFO), bonds≈-8.33 (CRITICAL)
        """
        report = calculate_deviations(sample_snapshot, default_settings)

        stocks = report.deviations["stocks"]
        assert stocks.deviation_pct < 0  # underweight
        assert stocks.severity == SignalSeverity.WARNING

        gold = report.deviations["gold"]
        assert gold.deviation_pct < 0
        assert gold.severity == SignalSeverity.INFO

        bonds = report.deviations["bonds"]
        assert bonds.deviation_pct < 0
        assert bonds.severity == SignalSeverity.CRITICAL

        assert report.max_severity == SignalSeverity.CRITICAL

    def test_perfect_allocation_all_info(
        self,
        default_settings: Settings,
    ) -> None:
        """Portfolio at exactly 70/15/15 with no cash → all INFO."""
        positions = [
            Position(
                isin="IE00BK5BQT80",
                name="Stocks",
                quantity=Decimal("1"),
                price=Decimal("700"),
                market_value=Decimal("700"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bonds",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="bonds",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions,
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        report = calculate_deviations(snapshot, default_settings)

        for result in report.deviations.values():
            assert result.deviation_pct == 0
            assert result.severity == SignalSeverity.INFO

        assert report.max_severity == SignalSeverity.INFO

    def test_overweight_positive_deviation(
        self,
        default_settings: Settings,
    ) -> None:
        """Stocks at 80% → positive deviation, CRITICAL."""
        positions = [
            Position(
                isin="IE00BK5BQT80",
                name="Stocks",
                quantity=Decimal("1"),
                price=Decimal("800"),
                market_value=Decimal("800"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bonds",
                quantity=Decimal("1"),
                price=Decimal("100"),
                market_value=Decimal("100"),
                asset_id="bonds",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions,
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        report = calculate_deviations(snapshot, default_settings)

        stocks = report.deviations["stocks"]
        assert stocks.deviation_pct == Decimal(10)
        assert stocks.severity == SignalSeverity.CRITICAL

    def test_empty_portfolio(self, default_settings: Settings) -> None:
        """total_value=0 → all deviations = -target_pct."""
        snapshot = PortfolioSnapshot(
            positions=[],
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        report = calculate_deviations(snapshot, default_settings)

        assert report.deviations["stocks"].deviation_pct == Decimal(-70)
        assert report.deviations["gold"].deviation_pct == Decimal(-15)
        assert report.deviations["bonds"].deviation_pct == Decimal(-15)

    def test_timestamp_propagated(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        report = calculate_deviations(sample_snapshot, default_settings)
        assert report.timestamp == sample_snapshot.timestamp

    def test_all_asset_ids_present(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        report = calculate_deviations(sample_snapshot, default_settings)
        assert set(report.deviations.keys()) == {"stocks", "gold", "bonds"}

    def test_deviation_sign_convention(
        self,
        default_settings: Settings,
    ) -> None:
        """Overweight → positive, underweight → negative."""
        positions = [
            Position(
                isin="IE00BK5BQT80",
                name="Stocks",
                quantity=Decimal("1"),
                price=Decimal("900"),
                market_value=Decimal("900"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold",
                quantity=Decimal("1"),
                price=Decimal("50"),
                market_value=Decimal("50"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bonds",
                quantity=Decimal("1"),
                price=Decimal("50"),
                market_value=Decimal("50"),
                asset_id="bonds",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions,
            cash=Decimal(0),
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        report = calculate_deviations(snapshot, default_settings)

        assert report.deviations["stocks"].deviation_pct > 0
        assert report.deviations["gold"].deviation_pct < 0
        assert report.deviations["bonds"].deviation_pct < 0

    def test_abs_deviation_pct_always_positive(
        self,
        sample_snapshot: PortfolioSnapshot,
        default_settings: Settings,
    ) -> None:
        report = calculate_deviations(sample_snapshot, default_settings)

        for result in report.deviations.values():
            assert result.abs_deviation_pct >= 0
            assert result.abs_deviation_pct == abs(result.deviation_pct)
