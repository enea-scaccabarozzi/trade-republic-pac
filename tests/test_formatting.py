from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pac.analysis.deviation import DeviationReport, DeviationResult
from pac.analysis.rebalance import PacAllocation, PacPlan
from pac.models.portfolio import AssetClass, PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.telegram.formatting import (
    _escape,
    format_pac_plan,
    format_portfolio_status,
    format_signal_alert,
    format_signal_alerts,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _make_signal(
    *,
    name: str = "Test Signal",
    severity: SignalSeverity = SignalSeverity.INFO,
    message: str = "Something happened",
) -> Signal:
    return Signal(
        name=name,
        severity=severity,
        message=message,
        triggered_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )


def _make_deviation_report(
    *,
    stocks_dev: Decimal = Decimal("0.0"),
    gold_dev: Decimal = Decimal("0.0"),
    bonds_dev: Decimal = Decimal("0.0"),
    stocks_severity: SignalSeverity = SignalSeverity.INFO,
    gold_severity: SignalSeverity = SignalSeverity.INFO,
    bonds_severity: SignalSeverity = SignalSeverity.INFO,
) -> DeviationReport:
    deviations = {
        AssetClass.STOCKS: DeviationResult(
            asset_class=AssetClass.STOCKS,
            actual_pct=Decimal("70") + stocks_dev,
            target_pct=Decimal("70"),
            deviation_pct=stocks_dev,
            abs_deviation_pct=abs(stocks_dev),
            severity=stocks_severity,
        ),
        AssetClass.GOLD: DeviationResult(
            asset_class=AssetClass.GOLD,
            actual_pct=Decimal("15") + gold_dev,
            target_pct=Decimal("15"),
            deviation_pct=gold_dev,
            abs_deviation_pct=abs(gold_dev),
            severity=gold_severity,
        ),
        AssetClass.BONDS: DeviationResult(
            asset_class=AssetClass.BONDS,
            actual_pct=Decimal("15") + bonds_dev,
            target_pct=Decimal("15"),
            deviation_pct=bonds_dev,
            abs_deviation_pct=abs(bonds_dev),
            severity=bonds_severity,
        ),
    }
    max_sev = max(
        [stocks_severity, gold_severity, bonds_severity],
        key=lambda s: ["info", "warning", "critical"].index(s.value),
    )
    return DeviationReport(
        deviations=deviations,
        max_severity=max_sev,
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


def _make_pac_plan(budget: Decimal = Decimal("500.00")) -> PacPlan:
    return PacPlan(
        total_budget=budget,
        allocations={
            AssetClass.STOCKS: PacAllocation(
                asset_class=AssetClass.STOCKS,
                amount=Decimal("350.00"),
                pct_of_budget=Decimal("70.0"),
                target_pct=Decimal("70"),
                current_pct=Decimal("66.7"),
            ),
            AssetClass.GOLD: PacAllocation(
                asset_class=AssetClass.GOLD,
                amount=Decimal("75.00"),
                pct_of_budget=Decimal("15.0"),
                target_pct=Decimal("15"),
                current_pct=Decimal("13.3"),
            ),
            AssetClass.BONDS: PacAllocation(
                asset_class=AssetClass.BONDS,
                amount=Decimal("75.00"),
                pct_of_budget=Decimal("15.0"),
                target_pct=Decimal("15"),
                current_pct=Decimal("6.7"),
            ),
        },
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


# ── _escape tests ─────────────────────────────────────────────────────


class TestEscape:
    def test_special_chars_escaped(self) -> None:
        raw = "_*[]()~`>#+-=|{}.!"
        escaped = _escape(raw)
        for ch in raw:
            assert f"\\{ch}" in escaped

    def test_backslash_escaped_first(self) -> None:
        result = _escape("a\\b")
        assert result == "a\\\\b"
        # Ensure no triple backslash (double-escaping)
        assert "\\\\\\\\" not in result

    def test_plain_text_unchanged(self) -> None:
        assert _escape("hello world") == "hello world"


# ── format_signal_alert tests ─────────────────────────────────────────


class TestFormatSignalAlert:
    def test_info_severity_contains_emoji(self) -> None:
        sig = _make_signal(severity=SignalSeverity.INFO)
        text = format_signal_alert(sig)
        assert "ℹ️" in text  # noqa: RUF001
        assert "*Signal:" in text

    def test_critical_severity_contains_emoji(self) -> None:
        sig = _make_signal(severity=SignalSeverity.CRITICAL)
        text = format_signal_alert(sig)
        assert "🚨" in text

    def test_warning_severity_contains_emoji(self) -> None:
        sig = _make_signal(severity=SignalSeverity.WARNING)
        text = format_signal_alert(sig)
        assert "⚠️" in text

    def test_special_chars_in_message_escaped(self) -> None:
        sig = _make_signal(message="Buy 100.5% of ETF-1")
        text = format_signal_alert(sig)
        assert "100\\.5" in text
        assert "ETF\\-1" in text

    def test_severity_in_backticks(self) -> None:
        sig = _make_signal(severity=SignalSeverity.WARNING)
        text = format_signal_alert(sig)
        assert "`WARNING`" in text

    def test_timestamp_in_italics(self) -> None:
        sig = _make_signal()
        text = format_signal_alert(sig)
        assert "_2026\\-04\\-01 12:00 UTC_" in text


# ── format_signal_alerts tests ────────────────────────────────────────


class TestFormatSignalAlerts:
    def test_empty_list_returns_no_active(self) -> None:
        text = format_signal_alerts([])
        assert "No active signals" in text

    def test_multiple_signals_separated_by_divider(self) -> None:
        sigs = [
            _make_signal(name="Alpha"),
            _make_signal(name="Beta"),
        ]
        text = format_signal_alerts(sigs)
        assert "———" in text
        assert "Alpha" in text
        assert "Beta" in text


# ── format_portfolio_status tests ─────────────────────────────────────


class TestFormatPortfolioStatus:
    def test_all_asset_classes_listed(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        report = _make_deviation_report()
        text = format_portfolio_status(sample_snapshot, report)
        assert "Stocks" in text
        assert "Gold" in text
        assert "Bonds" in text
        assert "*Portfolio Status*" in text

    def test_cash_and_total_shown(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        report = _make_deviation_report()
        text = format_portfolio_status(sample_snapshot, report)
        assert "Cash:" in text
        assert "Total:" in text

    def test_severity_emojis_match_deviations(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        report = _make_deviation_report(
            stocks_dev=Decimal("6.0"),
            stocks_severity=SignalSeverity.CRITICAL,
            gold_dev=Decimal("-3.5"),
            gold_severity=SignalSeverity.WARNING,
        )
        text = format_portfolio_status(sample_snapshot, report)
        # CRITICAL stocks line should have 🚨
        lines = text.split("\n")
        stocks_line = next(line for line in lines if "Stocks" in line)
        assert "🚨" in stocks_line
        # WARNING gold line should have ⚠️
        gold_line = next(line for line in lines if "Gold" in line)
        assert "⚠️" in gold_line

    def test_positive_deviation_has_plus_sign(
        self,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        report = _make_deviation_report(stocks_dev=Decimal("2.5"))
        text = format_portfolio_status(sample_snapshot, report)
        lines = text.split("\n")
        stocks_line = next(line for line in lines if "Stocks" in line)
        assert "\\+" in stocks_line


# ── format_pac_plan tests ─────────────────────────────────────────────


class TestFormatPacPlan:
    def test_standard_plan_has_header_and_budget(self) -> None:
        plan = _make_pac_plan()
        text = format_pac_plan(plan)
        assert "*Monthly PAC Redistribution*" in text
        assert "Budget:" in text

    def test_all_asset_classes_shown(self) -> None:
        plan = _make_pac_plan()
        text = format_pac_plan(plan)
        assert "Stocks" in text
        assert "Gold" in text
        assert "Bonds" in text

    def test_current_and_target_shown(self) -> None:
        plan = _make_pac_plan()
        text = format_pac_plan(plan)
        assert "Current:" in text
        assert "Target:" in text

    def test_zero_budget_shows_zero_amounts(self) -> None:
        plan = PacPlan(
            total_budget=Decimal("0.00"),
            allocations={
                ac: PacAllocation(
                    asset_class=ac,
                    amount=Decimal("0.00"),
                    pct_of_budget=Decimal("0.0"),
                    target_pct=Decimal("0"),
                    current_pct=Decimal("0"),
                )
                for ac in AssetClass
            },
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
        )
        text = format_pac_plan(plan)
        assert "€0\\.00" in text
