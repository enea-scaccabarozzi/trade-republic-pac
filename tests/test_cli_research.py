"""CLI integration tests for quick, compare, sweep subcommands."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pac.backtester.cli import app
from pac.backtester.research.context import ResearchContext
from pac.backtester.research.indicators import IndicatorRegistry
from pac.backtester.research.tests.conftest import make_series, make_test_settings
from pac.models.market_data import PriceSeries

runner = CliRunner()


def _mock_context() -> ResearchContext:
    """Build a ResearchContext from synthetic data (no network)."""
    settings = make_test_settings()
    base = date(2020, 1, 1)
    asset_data: dict[str, PriceSeries] = {
        "stocks": make_series("EUNL.DE", 500, base, 100.0, "v_shape"),
        "gold": make_series("4GLD.DE", 500, base, 50.0, "sine"),
        "bonds": make_series("EUN4.DE", 500, base, 80.0, "sine"),
    }
    ticker_data: dict[str, PriceSeries] = {
        "EUNL.DE": asset_data["stocks"],
        "4GLD.DE": asset_data["gold"],
        "EUN4.DE": asset_data["bonds"],
    }
    registry = IndicatorRegistry(asset_data)
    return ResearchContext(settings, asset_data, ticker_data, registry)


@pytest.fixture(autouse=True)
def _patch_build_context() -> Any:
    """Patch _build_research_context to avoid real data fetching."""
    ctx = _mock_context()
    with patch(
        "pac.backtester.cli._build_research_context",
        return_value=ctx,
    ):
        yield


class TestQuickCommand:
    def test_quick_displays_metrics(self) -> None:
        result = runner.invoke(
            app,
            ["quick", "-s", "crisis_exploit"],
        )
        assert result.exit_code == 0
        assert "Quick Test" in result.output
        assert "Sharpe" in result.output
        assert "Cagr" in result.output

    def test_quick_unknown_strategy_exits_1(self) -> None:
        result = runner.invoke(
            app,
            ["quick", "-s", "nonexistent"],
        )
        assert result.exit_code == 1


class TestCompareCommand:
    def test_compare_two_variants(self) -> None:
        result = runner.invoke(
            app,
            [
                "compare",
                "-v",
                "crisis_exploit:{}",
                "-v",
                "crisis_exploit:{}",
            ],
        )
        assert result.exit_code == 0
        assert "Comparison" in result.output

    def test_compare_no_variants_exits_1(self) -> None:
        result = runner.invoke(app, ["compare"])
        assert result.exit_code == 1


class TestSweepCommand:
    def test_sweep_displays_grid_results(self) -> None:
        result = runner.invoke(
            app,
            [
                "sweep",
                "-s",
                "crisis_exploit",
                "-g",
                '{"dd_threshold_pct": [-15, -20]}',
            ],
        )
        assert result.exit_code == 0
        assert "Sweep" in result.output

    def test_sweep_invalid_json_exits_1(self) -> None:
        result = runner.invoke(
            app,
            [
                "sweep",
                "-s",
                "crisis_exploit",
                "-g",
                "not-json",
            ],
        )
        assert result.exit_code == 1
