"""BDD step definitions for cli_results_display.feature."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from pac.backtester.cli import app
from pac.backtester.config import BacktestConfig
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

scenarios("../features/cli_results_display.feature")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_equity_curve() -> list[EquityCurvePoint]:
    return [
        EquityCurvePoint(
            date=date(2020, 1, 1) + __import__("datetime").timedelta(days=i * 30),
            p5=9000.0 + i * 100,
            median=10000.0 + i * 200,
            p95=11000.0 + i * 300,
        )
        for i in range(24)
    ]


def _make_allocations() -> list[AllocationPoint]:
    return [
        AllocationPoint(
            date=date(2020, 1, 1) + __import__("datetime").timedelta(days=i * 30),
            assets={
                "stocks": ConfidenceInterval(p5=65.0, median=70.0, p95=75.0),
                "bonds": ConfidenceInterval(p5=10.0, median=15.0, p95=20.0),
                "gold": ConfidenceInterval(p5=10.0, median=15.0, p95=20.0),
            },
        )
        for i in range(24)
    ]


def _make_trades(count: int = 10) -> list[TradeRecord]:
    trades: list[TradeRecord] = []
    for i in range(count):
        trades.append(
            TradeRecord(
                date=date(2020, 1, 1) + __import__("datetime").timedelta(days=i * 15),
                type="pac_execution",
                asset_id="EUNL",
                direction="buy" if i % 3 != 0 else "sell",
                amount_eur=500.0,
                quantity=5.0,
                price=100.0,
                fee=1.0,
                skipped=False,
            )
        )
    return trades


def _make_mock_result(
    *,
    with_equity: bool = True,
    with_allocations: bool = True,
    with_trades: bool = True,
    trade_count: int = 10,
    benchmark: bool = False,
    run_id: str = "test-display-001",
) -> RunResult:
    config = BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2020, 1, 1),
        end_date=date(2021, 12, 31),
        metrics=["sortino", "cagr", "max_drawdown"],
        benchmark=benchmark,
    )
    metrics: dict[str, dict[str, MetricValue]] = {
        "strategy": {
            "sortino": MetricValue(p5=0.5, median=1.0, p95=1.5),
            "cagr": MetricValue(p5=0.05, median=0.08, p95=0.12),
            "max_drawdown": MetricValue(p5=-0.20, median=-0.15, p95=-0.10),
        },
    }
    if benchmark:
        metrics["benchmark"] = {
            "sortino": MetricValue(p5=0.3, median=0.8, p95=1.0),
            "cagr": MetricValue(p5=0.04, median=0.06, p95=0.09),
            "max_drawdown": MetricValue(p5=-0.25, median=-0.20, p95=-0.15),
        }
    return RunResult(
        run_id=run_id,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        config=config,
        monte_carlo=MonteCarloInfo(iterations=100, slippage_range=(0, 3)),
        metrics=metrics,
        equity_curve=_make_equity_curve() if with_equity else [],
        allocations=_make_allocations() if with_allocations else [],
        trades=_make_trades(trade_count) if with_trades else [],
        summary=SummaryStats(
            total_invested=10000.0,
            final_value=ConfidenceInterval(p5=9000.0, median=11000.0, p95=12000.0),
            total_fees=ConfidenceInterval(p5=0.0, median=5.0, p95=10.0),
            total_trades=ConfidenceInterval(p5=0.0, median=3.0, p95=6.0),
            total_pac_executions=24,
        ),
    )


# ── Background steps ─────────────────────────────────────────────────────────


@given("a saved backtest run with equity curve data", target_fixture="ctx")
def _given_run_with_equity() -> dict[str, Any]:
    return {"result": _make_mock_result(), "output": "", "exit_code": None}


@given("the run has trades and metrics")
def _given_trades_and_metrics(ctx: dict[str, Any]) -> None:
    pass  # already set in _make_mock_result


# ── Conditional given steps ───────────────────────────────────────────────────


@given("the run includes benchmark metrics")
def _given_benchmark(ctx: dict[str, Any]) -> None:
    ctx["result"] = _make_mock_result(benchmark=True)


@given("plotext is not installed")
def _given_no_plotext(ctx: dict[str, Any]) -> None:
    ctx["no_plotext"] = True


@given("the run has more than 50 trades")
def _given_many_trades(ctx: dict[str, Any]) -> None:
    ctx["result"] = _make_mock_result(trade_count=75)


# ── When steps ────────────────────────────────────────────────────────────────


@when("I view the backtest result")
def _when_view_result(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    mock_store = MagicMock()
    mock_store.load.return_value = result
    runner = CliRunner()

    patches = [patch("pac.backtester.cli.ResultStore", return_value=mock_store)]
    if ctx.get("no_plotext"):
        # Make plotext import fail inside chart functions
        import builtins

        real_import = builtins.__import__

        def _mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "plotext":
                raise ImportError("plotext not installed")
            return real_import(name, *args, **kwargs)

        patches.append(patch("builtins.__import__", side_effect=_mock_import))

    # Apply all patches
    for p in patches:
        p.start()
    try:
        r = runner.invoke(app, ["show", result.run_id])
    finally:
        for p in patches:
            p.stop()

    ctx["output"] = r.output
    ctx["exit_code"] = r.exit_code


# ── Then steps ────────────────────────────────────────────────────────────────


@then(parsers.parse('the output contains "{text}"'))
def _then_output_contains(ctx: dict[str, Any], text: str) -> None:
    assert text in ctx["output"], f"Expected '{text}' in output:\n{ctx['output'][:500]}"


@then("the output contains a hint to install plotext")
def _then_plotext_hint(ctx: dict[str, Any]) -> None:
    assert "plotext" in ctx["output"].lower(), (
        f"Expected plotext hint in output:\n{ctx['output'][:500]}"
    )
