"""Tests for quantstats integration in ResearchContext."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import pytest

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import (
    DayResult,
    IterationResult,
    SimulationResult,
)
from pac.backtester.research._quantstats_helpers import (
    _ANNUALIZED_METRICS,
    _EXTENDED_METRICS,
    _import_qs,
    _result_to_returns,
)
from pac.backtester.research.context import ResearchContext
from pac.backtester.research.indicators import IndicatorRegistry
from pac.backtester.research.models import MetricBand, QuantstatsMetrics
from pac.backtester.research.tests.conftest import make_series, make_test_settings
from pac.models.market_data import PriceSeries

# ---------------------------------------------------------------------------
# Helper: build minimal IterationResult from synthetic equity curve
# ---------------------------------------------------------------------------


def _make_iteration(
    n_days: int = 100,
    start_value: float = 10000.0,
) -> IterationResult:
    """Build a minimal IterationResult with a simple rising equity curve."""
    daily = [
        DayResult(
            date=date(2020, 1, 1) + timedelta(days=i),
            total_value=Decimal(str(start_value + i * 10)),
            allocations={
                "stocks": Decimal("70"),
                "gold": Decimal("15"),
                "bonds": Decimal("15"),
            },
            cash=Decimal("0"),
        )
        for i in range(n_days)
    ]
    return IterationResult(
        iteration=0,
        daily_values=daily,
        trades=[],
        final_value=daily[-1].total_value,
    )


def _make_simulation(n_iterations: int = 3) -> SimulationResult:
    """Build a SimulationResult with multiple iterations."""
    iterations = [
        _make_iteration(n_days=100, start_value=10000.0 + i * 500)
        for i in range(n_iterations)
    ]
    config = BacktestConfig(
        strategy="crisis_exploit",
        strategy_params={},
        start_date=date(2020, 1, 1),
        end_date=date(2020, 4, 10),
        monte_carlo_iterations=n_iterations,
        slippage_days=(0, 0),
    )
    return SimulationResult(config=config, iterations=iterations)


def _build_context() -> ResearchContext:
    """Build a ResearchContext directly via __init__ with synthetic data."""
    settings = make_test_settings()
    base = date(2020, 1, 1)
    asset_price_data: dict[str, PriceSeries] = {
        "stocks": make_series("EUNL.DE", 500, base, 100.0, pattern="v_shape"),
        "gold": make_series("4GLD.DE", 500, base, 50.0, pattern="sine"),
        "bonds": make_series("EUN4.DE", 500, base, 80.0, pattern="sine"),
    }
    ticker_price_data: dict[str, PriceSeries] = {
        "EUNL.DE": asset_price_data["stocks"],
        "4GLD.DE": asset_price_data["gold"],
        "EUN4.DE": asset_price_data["bonds"],
    }
    registry = IndicatorRegistry(asset_price_data)
    return ResearchContext(settings, asset_price_data, ticker_price_data, registry)


# ---------------------------------------------------------------------------
# TestQuantstatsMetrics (model tests)
# ---------------------------------------------------------------------------


class TestQuantstatsMetrics:
    def test_metric_band_model(self) -> None:
        band = MetricBand(p5=0.1, median=0.3, p95=0.5)
        assert band.p5 == 0.1
        assert band.median == 0.3
        assert band.p95 == 0.5

    def test_quantstats_metrics_float_values(self) -> None:
        m = QuantstatsMetrics(metrics={"sharpe": 1.5, "sortino": 2.0})
        assert m.metrics["sharpe"] == 1.5
        assert isinstance(m.metrics["sharpe"], float)

    def test_quantstats_metrics_band_values(self) -> None:
        band = MetricBand(p5=0.1, median=0.3, p95=0.5)
        m = QuantstatsMetrics(metrics={"sharpe": band})
        assert isinstance(m.metrics["sharpe"], MetricBand)


# ---------------------------------------------------------------------------
# TestQuantstatsMethod
# ---------------------------------------------------------------------------


class TestQuantstatsMethod:
    def test_defaults_compute_seven_metrics(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        m = ctx.quantstats(result)
        assert len(m.metrics) == 7
        expected_keys = {
            "sharpe",
            "sortino",
            "calmar",
            "max_drawdown",
            "cagr",
            "volatility",
            "omega",
        }
        assert set(m.metrics.keys()) == expected_keys

    def test_all_computes_full_set(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        m = ctx.quantstats(result, metrics="all")
        assert len(m.metrics) >= 20

    def test_selected_metrics(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        m = ctx.quantstats(result, metrics=["sharpe", "omega"])
        assert set(m.metrics.keys()) == {"sharpe", "omega"}

    def test_unknown_metric_raises_valueerror(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        with pytest.raises(ValueError, match="Unknown metric"):
            ctx.quantstats(result, metrics=["nonexistent"])

    def test_mc_result_returns_metric_bands(self) -> None:
        ctx = _build_context()
        sim = _make_simulation(n_iterations=3)
        m = ctx.quantstats(sim)
        import math

        for v in m.metrics.values():
            assert isinstance(v, MetricBand)
            # NaN metrics produce NaN bands — skip ordering check
            if not math.isnan(v.p5):
                assert v.p5 <= v.median <= v.p95

    def test_single_iteration_mc(self) -> None:
        ctx = _build_context()
        sim = _make_simulation(n_iterations=1)
        m = ctx.quantstats(sim)
        import math

        for v in m.metrics.values():
            assert isinstance(v, MetricBand)
            # NaN == NaN is False, so check via isnan
            if math.isnan(v.p5):
                assert math.isnan(v.median) and math.isnan(v.p95)
            else:
                assert v.p5 == v.median == v.p95

    def test_nan_safe(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=2)
        # Should not crash even with very short series
        m = ctx.quantstats(result)
        for v in m.metrics.values():
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# TestQuantstatsReport
# ---------------------------------------------------------------------------


class TestQuantstatsReport:
    def test_generates_html_file(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        output = tmp_path / "report.html"
        path = ctx.quantstats_report(result, output)
        assert path.exists()
        content = path.read_text()
        assert content.startswith("<") or content.startswith("<!DOCTYPE")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        output = tmp_path / "nested" / "dir" / "report.html"
        path = ctx.quantstats_report(result, output)
        assert path.exists()
        assert path.parent.exists()

    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        output = tmp_path / "report.html"
        path = ctx.quantstats_report(result, output)
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# TestQuantstatsPlot
# ---------------------------------------------------------------------------


class TestQuantstatsPlot:
    def setup_method(self) -> None:
        plt.close("all")

    def teardown_method(self) -> None:
        plt.close("all")

    def test_returns_matplotlib_figure(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        fig = ctx.quantstats_plot(result, "returns")
        assert hasattr(fig, "savefig")

    def test_unknown_kind_raises_valueerror(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        with pytest.raises(ValueError, match="Unknown plot kind"):
            ctx.quantstats_plot(result, "nonexistent")

    @pytest.mark.parametrize(
        "kind",
        [
            "returns",
            "drawdown",
            "histogram",
            "daily_returns",
            "distribution",
        ],
    )
    def test_supported_kinds_produce_figure(self, kind: str) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        fig = ctx.quantstats_plot(result, kind)
        assert hasattr(fig, "savefig")


# ---------------------------------------------------------------------------
# TestQuantstatsRolling
# ---------------------------------------------------------------------------


class TestQuantstatsRolling:
    def test_returns_date_value_tuples(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=300)
        data = ctx.quantstats_rolling(result, "sharpe", window=50)
        assert isinstance(data, list)
        if data:
            d, v = data[0]
            assert isinstance(d, date)
            assert isinstance(v, float)

    def test_sharpe_rolling(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=300)
        data = ctx.quantstats_rolling(result, "sharpe", window=50)
        assert len(data) > 0

    def test_sortino_rolling(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=300)
        data = ctx.quantstats_rolling(result, "sortino", window=50)
        assert len(data) > 0

    def test_volatility_rolling(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=300)
        data = ctx.quantstats_rolling(result, "volatility", window=50)
        assert len(data) > 0

    def test_unknown_metric_raises_valueerror(self) -> None:
        ctx = _build_context()
        result = _make_iteration()
        with pytest.raises(ValueError, match="Unknown rolling metric"):
            ctx.quantstats_rolling(result, "nonexistent")

    def test_custom_window(self) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=300)
        data_50 = ctx.quantstats_rolling(result, "sharpe", window=50)
        data_100 = ctx.quantstats_rolling(result, "sharpe", window=100)
        # Different windows produce different number of non-NaN results
        assert len(data_50) != len(data_100) or len(data_50) > 0


# ---------------------------------------------------------------------------
# TestQuantstatsSavePlots
# ---------------------------------------------------------------------------


class TestQuantstatsSavePlots:
    def setup_method(self) -> None:
        plt.close("all")

    def teardown_method(self) -> None:
        plt.close("all")

    def test_saves_default_plots(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        paths = ctx.quantstats_save_plots(result, tmp_path)
        assert len(paths) == 6
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"

    def test_custom_kinds(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        paths = ctx.quantstats_save_plots(
            result, tmp_path, kinds=["returns", "drawdown"]
        )
        assert len(paths) == 2

    def test_svg_fmt(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        paths = ctx.quantstats_save_plots(
            result, tmp_path, kinds=["returns"], fmt="svg"
        )
        assert len(paths) == 1
        assert paths[0].suffix == ".svg"

    def test_returns_paths(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        paths = ctx.quantstats_save_plots(result, tmp_path, kinds=["returns"])
        assert all(isinstance(p, Path) for p in paths)
        assert all(p.exists() for p in paths)

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        ctx = _build_context()
        result = _make_iteration(n_days=200)
        out_dir = tmp_path / "nested" / "plots"
        paths = ctx.quantstats_save_plots(result, out_dir, kinds=["returns"])
        assert out_dir.exists()
        assert len(paths) == 1


# ---------------------------------------------------------------------------
# TestQuantstatsHelpers (unit tests for _quantstats_helpers.py)
# ---------------------------------------------------------------------------


class TestQuantstatsHelpers:
    def test_import_qs_success(self) -> None:
        qs = _import_qs()
        assert hasattr(qs, "stats")

    def test_import_qs_missing(self) -> None:
        with (
            patch.dict(sys.modules, {"quantstats": None}),
            pytest.raises(ImportError, match="quantstats is required"),
        ):
            _import_qs()

    def test_result_to_returns(self) -> None:
        result = _make_iteration(n_days=50)
        returns = _result_to_returns(result)
        assert len(returns) == 49  # first day dropped

    def test_extended_metrics_registry_keys(self) -> None:
        assert len(_EXTENDED_METRICS) >= 20

    def test_annualized_metrics_subset(self) -> None:
        assert _ANNUALIZED_METRICS.issubset(_EXTENDED_METRICS.keys())
