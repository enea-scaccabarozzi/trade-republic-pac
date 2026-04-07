from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pac.backtester.engine.actions import ExecutedTrade
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
from pac.backtester.results.tests.conftest import _make_config


def _make_run_result() -> RunResult:
    """Build a minimal RunResult for serialization tests."""
    config = _make_config()
    return RunResult(
        run_id="2024-01-02T10-00-00_test_strategy",
        created_at=datetime(2024, 1, 2, 10, 0, 0),
        config=config,
        monte_carlo=MonteCarloInfo(iterations=3, slippage_range=(0, 3)),
        metrics={
            "strategy": {
                "sharpe": MetricValue(p5=0.3, median=0.5, p95=0.7),
            },
            "benchmark": {
                "sharpe": MetricValue(p5=0.4, median=0.4, p95=0.4),
            },
        },
        equity_curve=[
            EquityCurvePoint(
                date=date(2024, 1, 2), p5=9800.0, median=10000.0, p95=10200.0,
            ),
        ],
        allocations=[
            AllocationPoint(
                date=date(2024, 1, 2),
                assets={
                    "stocks": ConfidenceInterval(
                        p5=68.0, median=70.0, p95=72.0,
                    ),
                    "cash": ConfidenceInterval(
                        p5=0.0, median=0.0, p95=0.0,
                    ),
                },
            ),
        ],
        trades=[
            TradeRecord(
                date=date(2024, 1, 2),
                type="pac_execution",
                asset_id="stocks",
                direction="buy",
                amount_eur=175.0,
                quantity=1.75,
                price=100.0,
                fee=0.0,
            ),
        ],
        summary=SummaryStats(
            total_invested=11000.0,
            final_value=ConfidenceInterval(
                p5=10500.0, median=11000.0, p95=11800.0,
            ),
            total_fees=ConfidenceInterval(p5=1.0, median=2.0, p95=3.0),
            total_trades=ConfidenceInterval(p5=1.0, median=1.0, p95=2.0),
            total_pac_executions=12,
        ),
    )


class TestRunResultRoundTrip:
    def test_run_result_round_trip(self) -> None:
        result = _make_run_result()
        data = result.model_dump(mode="json")
        restored = RunResult.model_validate(data)
        assert restored == result

    def test_confidence_interval_json_shape(self) -> None:
        ci = ConfidenceInterval(p5=1.0, median=2.0, p95=3.0)
        data = ci.model_dump(mode="json")
        assert set(data.keys()) == {"p5", "median", "p95"}

    def test_equity_curve_point_date_serialized(self) -> None:
        point = EquityCurvePoint(
            date=date(2024, 1, 2), p5=100.0, median=110.0, p95=120.0,
        )
        data = point.model_dump(mode="json")
        assert data["date"] == "2024-01-02"

    def test_metric_value_uniform_shape(self) -> None:
        # Strategy with spread
        strategy_mv = MetricValue(p5=0.3, median=0.5, p95=0.7)
        # Benchmark with uniform (p5 = p95 = median)
        bench_mv = MetricValue(p5=0.4, median=0.4, p95=0.4)

        for mv in [strategy_mv, bench_mv]:
            data = mv.model_dump(mode="json")
            assert set(data.keys()) == {"p5", "median", "p95"}

    def test_trade_record_from_executed_trade(self) -> None:
        et = ExecutedTrade(
            date=date(2024, 1, 2),
            type="pac_execution",
            asset_id="stocks",
            direction="buy",
            amount_eur=Decimal("175.00"),
            quantity=Decimal("1.75"),
            price=Decimal("100.00"),
            fee=Decimal("0"),
        )
        tr = TradeRecord(
            date=et.date,
            type=et.type,
            asset_id=et.asset_id,
            direction=et.direction,
            amount_eur=float(et.amount_eur),
            quantity=float(et.quantity),
            price=float(et.price),
            fee=float(et.fee),
            skipped=et.skipped,
        )
        assert isinstance(tr.amount_eur, float)
        assert isinstance(tr.quantity, float)
        assert tr.amount_eur == 175.0
        assert tr.quantity == 1.75

    def test_allocation_point_has_cash(self) -> None:
        result = _make_run_result()
        alloc = result.allocations[0]
        assert "cash" in alloc.assets
