from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pac.analysis.deviation import DeviationResult
from pac.analysis.rebalance import PacAllocation, PacPlan
from pac.models.signals import Signal, SignalSeverity
from pac.templates.adapters.markdown_v2 import MarkdownV2Adapter
from pac.templates.adapters.plain_text import PlainTextAdapter


@pytest.fixture
def md_adapter() -> MarkdownV2Adapter:
    return MarkdownV2Adapter()


@pytest.fixture
def plain_adapter() -> PlainTextAdapter:
    return PlainTextAdapter()


@pytest.fixture
def sample_signal() -> Signal:
    return Signal(
        name="deviation_check",
        severity=SignalSeverity.WARNING,
        message="Stocks overweight by 4.2%",
        triggered_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_deviations() -> list[DeviationResult]:
    return [
        DeviationResult(
            asset_id="stocks",
            name="FTSE All-World ETF",
            actual_pct=Decimal("74.2"),
            target_pct=Decimal("70.0"),
            deviation_pct=Decimal("4.2"),
            abs_deviation_pct=Decimal("4.2"),
            severity=SignalSeverity.WARNING,
        ),
        DeviationResult(
            asset_id="gold",
            name="Physical Gold ETC",
            actual_pct=Decimal("13.5"),
            target_pct=Decimal("15.0"),
            deviation_pct=Decimal("-1.5"),
            abs_deviation_pct=Decimal("1.5"),
            severity=SignalSeverity.INFO,
        ),
        DeviationResult(
            asset_id="bonds",
            name="Gov Bond ETF",
            actual_pct=Decimal("12.3"),
            target_pct=Decimal("15.0"),
            deviation_pct=Decimal("-2.7"),
            abs_deviation_pct=Decimal("2.7"),
            severity=SignalSeverity.INFO,
        ),
    ]


@pytest.fixture
def sample_pac_plan() -> PacPlan:
    return PacPlan(
        total_budget=Decimal("500.00"),
        allocations={
            "stocks": PacAllocation(
                asset_id="stocks",
                name="FTSE All-World ETF",
                amount=Decimal("350.00"),
                pct_of_budget=Decimal("70.0"),
                target_pct=Decimal("70.0"),
                current_pct=Decimal("68.5"),
            ),
            "gold": PacAllocation(
                asset_id="gold",
                name="Physical Gold ETC",
                amount=Decimal("75.00"),
                pct_of_budget=Decimal("15.0"),
                target_pct=Decimal("15.0"),
                current_pct=Decimal("14.2"),
            ),
            "bonds": PacAllocation(
                asset_id="bonds",
                name="Gov Bond ETF",
                amount=Decimal("75.00"),
                pct_of_budget=Decimal("15.0"),
                target_pct=Decimal("15.0"),
                current_pct=Decimal("17.3"),
            ),
        },
        timestamp=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
    )
