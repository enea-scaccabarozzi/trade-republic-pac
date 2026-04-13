"""Dashboard test fixtures."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from pac.backtester.config import BacktestConfig
from pac.backtester.dashboard.state import DashboardState
from pac.backtester.results.models import (
    AllocationPoint,
    ConfidenceInterval,
    EquityCurvePoint,
    MetricValue,
    MonteCarloInfo,
    RunResult,
    SummaryStats,
    TradeRecord,
)
from pac.backtester.results.store import ResultStore


@pytest.fixture()
def sample_run_result() -> RunResult:
    """A RunResult with multi-point data for chart and filter testing.

    Contains 6 equity curve points, 3 allocation points (2 assets),
    5 trade records, and both strategy + benchmark metrics.
    Backwards-compatible: strategy="pac_alignment", final_value
    median=52000, iterations=50.
    """
    return RunResult(
        run_id="20260401_120000_pac_alignment",
        created_at=datetime(2026, 4, 1, 12, 0, 0),
        config=BacktestConfig(
            strategy="pac_alignment",
            start_date=date(2020, 1, 1),
            end_date=date(2025, 12, 31),
            monte_carlo_iterations=50,
        ),
        monte_carlo=MonteCarloInfo(iterations=50, slippage_range=(0, 3)),
        metrics={
            "strategy": {
                "cagr": MetricValue(p5=0.05, median=0.08, p95=0.11),
                "sharpe": MetricValue(p5=0.5, median=0.8, p95=1.1),
            },
            "benchmark": {
                "cagr": MetricValue(p5=0.06, median=0.06, p95=0.06),
                "sharpe": MetricValue(p5=0.6, median=0.6, p95=0.6),
            },
        },
        equity_curve=[
            EquityCurvePoint(
                date=date(2020, 1, 2),
                p5=9800,
                median=10000,
                p95=10200,
            ),
            EquityCurvePoint(
                date=date(2021, 1, 2),
                p5=15000,
                median=18000,
                p95=21000,
            ),
            EquityCurvePoint(
                date=date(2022, 1, 2),
                p5=17000,
                median=22000,
                p95=27000,
            ),
            EquityCurvePoint(
                date=date(2023, 1, 2),
                p5=16000,
                median=20000,
                p95=24000,
            ),
            EquityCurvePoint(
                date=date(2024, 1, 2),
                p5=25000,
                median=35000,
                p95=45000,
            ),
            EquityCurvePoint(
                date=date(2025, 6, 1),
                p5=38000,
                median=52000,
                p95=66000,
            ),
        ],
        allocations=[
            AllocationPoint(
                date=date(2020, 1, 2),
                assets={
                    "stocks": ConfidenceInterval(p5=68, median=70, p95=72),
                    "gold": ConfidenceInterval(p5=28, median=30, p95=32),
                },
            ),
            AllocationPoint(
                date=date(2022, 1, 2),
                assets={
                    "stocks": ConfidenceInterval(p5=65, median=68, p95=71),
                    "gold": ConfidenceInterval(p5=29, median=32, p95=35),
                },
            ),
            AllocationPoint(
                date=date(2025, 6, 1),
                assets={
                    "stocks": ConfidenceInterval(p5=70, median=73, p95=76),
                    "gold": ConfidenceInterval(p5=24, median=27, p95=30),
                },
            ),
        ],
        trades=[
            TradeRecord(
                date=date(2020, 1, 2),
                type="pac_execution",
                asset_id="stocks",
                direction="buy",
                amount_eur=350.0,
                quantity=3.5,
                price=100.0,
                fee=1.0,
            ),
            TradeRecord(
                date=date(2020, 1, 2),
                type="pac_execution",
                asset_id="gold",
                direction="buy",
                amount_eur=150.0,
                quantity=1.0,
                price=150.0,
                fee=1.0,
            ),
            TradeRecord(
                date=date(2022, 6, 15),
                type="hard_rebalance",
                asset_id="stocks",
                direction="sell",
                amount_eur=500.0,
                quantity=2.0,
                price=250.0,
                fee=1.0,
            ),
            TradeRecord(
                date=date(2023, 3, 1),
                type="pac_execution",
                asset_id="gold",
                direction="buy",
                amount_eur=200.0,
                quantity=0.8,
                price=250.0,
                fee=1.0,
                skipped=True,
            ),
            TradeRecord(
                date=date(2025, 1, 10),
                type="pac_execution",
                asset_id="stocks",
                direction="buy",
                amount_eur=500.0,
                quantity=1.5,
                price=333.33,
                fee=1.0,
            ),
        ],
        summary=SummaryStats(
            total_invested=40000.0,
            final_value=ConfidenceInterval(p5=45000, median=52000, p95=59000),
            total_fees=ConfidenceInterval(p5=50, median=72, p95=95),
            total_trades=ConfidenceInterval(p5=10, median=15, p95=20),
            total_pac_executions=144,
        ),
    )


@pytest.fixture()
def sample_run_result_b() -> RunResult:
    """A second RunResult with different values for comparison tests.

    Uses a different strategy name, date range, and final values,
    but the same structural shape (6 equity points, 3 allocation points).
    """
    return RunResult(
        run_id="20260402_140000_buy_and_hold",
        created_at=datetime(2026, 4, 2, 14, 0, 0),
        config=BacktestConfig(
            strategy="buy_and_hold",
            start_date=date(2019, 1, 1),
            end_date=date(2024, 12, 31),
            monte_carlo_iterations=30,
            metrics=["sortino", "calmar", "max_drawdown", "cagr", "sharpe"],
        ),
        monte_carlo=MonteCarloInfo(iterations=30, slippage_range=(0, 2)),
        metrics={
            "strategy": {
                "cagr": MetricValue(p5=0.06, median=0.09, p95=0.12),
                "sharpe": MetricValue(p5=0.4, median=0.7, p95=1.0),
                "max_drawdown": MetricValue(p5=-0.25, median=-0.18, p95=-0.12),
            },
        },
        equity_curve=[
            EquityCurvePoint(
                date=date(2019, 1, 2),
                p5=9700,
                median=10000,
                p95=10300,
            ),
            EquityCurvePoint(
                date=date(2020, 1, 2),
                p5=13000,
                median=16000,
                p95=19000,
            ),
            EquityCurvePoint(
                date=date(2021, 1, 2),
                p5=18000,
                median=24000,
                p95=30000,
            ),
            EquityCurvePoint(
                date=date(2022, 1, 2),
                p5=15000,
                median=19000,
                p95=23000,
            ),
            EquityCurvePoint(
                date=date(2023, 1, 2),
                p5=22000,
                median=30000,
                p95=38000,
            ),
            EquityCurvePoint(
                date=date(2024, 6, 1),
                p5=30000,
                median=42000,
                p95=54000,
            ),
        ],
        allocations=[
            AllocationPoint(
                date=date(2019, 1, 2),
                assets={
                    "stocks": ConfidenceInterval(p5=90, median=95, p95=100),
                    "bonds": ConfidenceInterval(p5=0, median=5, p95=10),
                },
            ),
            AllocationPoint(
                date=date(2021, 1, 2),
                assets={
                    "stocks": ConfidenceInterval(p5=88, median=93, p95=98),
                    "bonds": ConfidenceInterval(p5=2, median=7, p95=12),
                },
            ),
            AllocationPoint(
                date=date(2024, 6, 1),
                assets={
                    "stocks": ConfidenceInterval(p5=85, median=90, p95=95),
                    "bonds": ConfidenceInterval(p5=5, median=10, p95=15),
                },
            ),
        ],
        trades=[
            TradeRecord(
                date=date(2019, 1, 2),
                type="pac_execution",
                asset_id="stocks",
                direction="buy",
                amount_eur=500.0,
                quantity=5.0,
                price=100.0,
                fee=1.0,
            ),
            TradeRecord(
                date=date(2021, 6, 15),
                type="pac_execution",
                asset_id="bonds",
                direction="buy",
                amount_eur=100.0,
                quantity=2.0,
                price=50.0,
                fee=1.0,
            ),
        ],
        summary=SummaryStats(
            total_invested=35000.0,
            final_value=ConfidenceInterval(p5=38000, median=42000, p95=46000),
            total_fees=ConfidenceInterval(p5=30, median=45, p95=60),
            total_trades=ConfidenceInterval(p5=8, median=12, p95=16),
            total_pac_executions=120,
        ),
    )


@pytest.fixture()
def populated_store(tmp_path: Path, sample_run_result: RunResult) -> ResultStore:
    """A ResultStore with one saved run in a temp directory."""
    store = ResultStore(base_dir=tmp_path / "backtests")
    store.save(sample_run_result)
    return store


@pytest.fixture()
def dashboard_state(populated_store: ResultStore) -> DashboardState:
    """A DashboardState wired to the populated temp store."""
    return DashboardState(store=populated_store)
