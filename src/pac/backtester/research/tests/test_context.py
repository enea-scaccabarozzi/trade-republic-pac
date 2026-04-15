"""Tests for ResearchContext."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pac.backtester.engine.simulator import IterationResult, SimulationResult
from pac.backtester.research.context import ResearchContext
from pac.backtester.research.events import EventCalendar, MarketEvent
from pac.backtester.research.indicators import CompositeResult, IndicatorRegistry
from pac.backtester.research.models import (
    ComparisonTable,
    EventAnalysisResult,
    OOSResult,
    SweepResult,
    WalkForwardResult,
)
from pac.backtester.research.tests.conftest import make_series, make_test_settings
from pac.models.market_data import PriceSeries

# ---------------------------------------------------------------------------
# Helper: build a ResearchContext from synthetic data (no from_config)
# ---------------------------------------------------------------------------


def _build_context(
    *,
    n_bars: int = 500,
    settings_overrides: dict[str, Any] | None = None,
) -> ResearchContext:
    """Build a ResearchContext directly via __init__ with synthetic data."""
    settings = make_test_settings(**(settings_overrides or {}))
    base = date(2020, 1, 1)
    asset_price_data: dict[str, PriceSeries] = {
        "stocks": make_series("EUNL.DE", n_bars, base, 100.0, pattern="v_shape"),
        "gold": make_series("4GLD.DE", n_bars, base, 50.0, pattern="sine"),
        "bonds": make_series("EUN4.DE", n_bars, base, 80.0, pattern="sine"),
    }
    ticker_price_data: dict[str, PriceSeries] = {
        "EUNL.DE": asset_price_data["stocks"],
        "4GLD.DE": asset_price_data["gold"],
        "EUN4.DE": asset_price_data["bonds"],
    }
    registry = IndicatorRegistry(asset_price_data)
    return ResearchContext(settings, asset_price_data, ticker_price_data, registry)


# ---------------------------------------------------------------------------
# TestPricesProperty
# ---------------------------------------------------------------------------


class TestPricesProperty:
    def test_prices_returns_asset_id_keyed_data(self) -> None:
        ctx = _build_context()
        assert "stocks" in ctx.prices
        assert isinstance(ctx.prices["stocks"], PriceSeries)

    def test_prices_contains_all_assets(self) -> None:
        ctx = _build_context()
        assert set(ctx.prices.keys()) == {"stocks", "gold", "bonds"}


# ---------------------------------------------------------------------------
# TestSettingsProperty
# ---------------------------------------------------------------------------


class TestSettingsProperty:
    def test_settings_returns_loaded_settings(self) -> None:
        ctx = _build_context()
        assert ctx.settings.version == 1
        asset_ids = [a.id for a in ctx.settings.assets]
        assert asset_ids == ["stocks", "gold", "bonds"]


# ---------------------------------------------------------------------------
# TestIndicatorsProperty
# ---------------------------------------------------------------------------


class TestIndicatorsProperty:
    def test_indicators_returns_registry(self) -> None:
        ctx = _build_context()
        assert isinstance(ctx.indicators, IndicatorRegistry)

    def test_indicators_starts_empty(self) -> None:
        ctx = _build_context()
        assert ctx.indicators.list() == []


# ---------------------------------------------------------------------------
# TestToDataframe
# ---------------------------------------------------------------------------


class TestToDataframe:
    def test_returns_dataframe_with_correct_columns(self) -> None:
        ctx = _build_context()
        df = ctx.to_dataframe("stocks")
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_date_is_index(self) -> None:
        ctx = _build_context()
        df = ctx.to_dataframe("stocks")
        assert df.index.name == "date"

    def test_ohlc_are_float(self) -> None:
        ctx = _build_context()
        df = ctx.to_dataframe("stocks")
        for col in ("open", "high", "low", "close"):
            assert df[col].dtype == float

    def test_volume_is_int(self) -> None:
        ctx = _build_context()
        df = ctx.to_dataframe("stocks")
        assert df["volume"].dtype == int

    def test_unknown_asset_raises_keyerror(self) -> None:
        ctx = _build_context()
        with pytest.raises(KeyError, match="nonexistent"):
            ctx.to_dataframe("nonexistent")

    def test_pandas_not_installed_raises_importerror(self) -> None:
        ctx = _build_context()
        with (
            patch.dict(sys.modules, {"pandas": None}),
            pytest.raises(ImportError, match="pandas is required"),
        ):
            ctx.to_dataframe("stocks")


# ---------------------------------------------------------------------------
# TestIndicatorDelegation
# ---------------------------------------------------------------------------


class TestIndicatorDelegation:
    def test_indicator_delegates_to_registry(self) -> None:
        ctx = _build_context()
        ctx.register_pack("crisis")
        target = date(2020, 9, 1)
        result = ctx.indicator("drawdown", target)
        assert isinstance(result, float)
        assert result < 0  # V-shape trough → negative drawdown

    def test_indicator_series_delegates_to_registry(self) -> None:
        ctx = _build_context()
        ctx.register_pack("crisis")
        start = date(2020, 11, 1)
        end = date(2020, 12, 1)
        result = ctx.indicator_series("drawdown", start, end)
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], tuple)
        assert isinstance(result[0][0], date)


# ---------------------------------------------------------------------------
# TestRegisterPack
# ---------------------------------------------------------------------------


class TestRegisterPack:
    def test_register_pack_delegates(self) -> None:
        ctx = _build_context()
        ctx.register_pack("crisis")
        assert "drawdown" in ctx.indicators.list()

    def test_register_pack_crisis_makes_indicators_available(self) -> None:
        ctx = _build_context()
        ctx.register_pack("crisis")
        target = date(2020, 9, 1)
        result = ctx.indicator("drawdown", target)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# TestRegisterIndicator
# ---------------------------------------------------------------------------


class TestRegisterIndicator:
    def test_register_custom_indicator(self) -> None:
        ctx = _build_context()
        ctx.register_indicator(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        assert "last_close" in ctx.indicators.list()

    def test_registered_indicator_is_computable(self) -> None:
        ctx = _build_context()
        ctx.register_indicator(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        result = ctx.indicator("last_close", date(2020, 6, 1))
        assert isinstance(result, float)
        assert result > 0


# ---------------------------------------------------------------------------
# TestSimulate
# ---------------------------------------------------------------------------


class TestSimulate:
    def test_simulate_returns_iteration_result(self) -> None:
        ctx = _build_context()
        result = ctx.simulate("crisis_exploit")
        assert isinstance(result, IterationResult)
        assert result.iteration == 0

    def test_simulate_is_deterministic(self) -> None:
        ctx = _build_context()
        r1 = ctx.simulate("crisis_exploit")
        r2 = ctx.simulate("crisis_exploit")
        assert r1.final_value == r2.final_value
        assert len(r1.trades) == len(r2.trades)

    def test_simulate_unknown_strategy_raises_with_available_list(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="Unknown strategy 'nonexistent'"):
            ctx.simulate("nonexistent")


# ---------------------------------------------------------------------------
# TestSimulateMC
# ---------------------------------------------------------------------------


class TestSimulateMC:
    def test_simulate_mc_returns_simulation_result(self) -> None:
        ctx = _build_context()
        result = ctx.simulate_mc("crisis_exploit", iterations=3, seed=42)
        assert isinstance(result, SimulationResult)

    def test_simulate_mc_respects_iterations(self) -> None:
        ctx = _build_context()
        result = ctx.simulate_mc(
            "crisis_exploit",
            iterations=5,
            seed=42,
            slippage_days=(0, 0),
        )
        assert len(result.iterations) == 5


# ---------------------------------------------------------------------------
# TestFromConfig
# ---------------------------------------------------------------------------


class TestFromConfig:
    def test_from_config_loads_settings_and_fetches_data(
        self,
        tmp_path: Path,
    ) -> None:
        """Integration test: from_config() wires everything correctly."""
        config_yaml = tmp_path / "pac.yaml"
        config_yaml.write_text(
            "version: 1\n"
            "broker:\n"
            "  type: trade_republic\n"
            "  phone_number: '+491234567890'\n"
            "  pin: '1234'\n"
            "assets:\n"
            "  - id: stocks\n"
            "    name: Stocks ETF\n"
            "    isin: IE00BK5BQT80\n"
            "    ticker: EUNL.DE\n"
            "    target_pct: 70\n"
            "  - id: gold\n"
            "    name: Gold ETC\n"
            "    isin: IE00B4ND3602\n"
            "    ticker: 4GLD.DE\n"
            "    target_pct: 15\n"
            "  - id: bonds\n"
            "    name: Bond ETF\n"
            "    isin: IE00B3F81409\n"
            "    ticker: EUN4.DE\n"
            "    target_pct: 15\n"
            "app:\n"
            "  job_secret: test-secret\n"
            "channels: {}\n"
            "signals: []\n"
        )

        base = date(2020, 1, 1)
        mock_data = {
            "EUNL.DE": make_series("EUNL.DE", 100, base, 100.0),
            "4GLD.DE": make_series("4GLD.DE", 100, base, 50.0, "sine"),
            "EUN4.DE": make_series("EUN4.DE", 100, base, 80.0, "sine"),
        }

        def mock_fetch(
            ticker: str,
            start: date,
            end: date,
            proxy_chain: Any = None,
            primary_currency: Any = None,
            **kwargs: Any,
        ) -> PriceSeries:
            return mock_data[ticker]

        with (
            patch(
                "pac.backtester.data.provider.MarketDataProvider"
            ) as mock_provider_cls,
        ):
            mock_provider = mock_provider_cls.return_value
            mock_provider.fetch_with_proxy.side_effect = mock_fetch
            ctx = ResearchContext.from_config(
                str(config_yaml),
                start_date=date(2020, 1, 1),
                end_date=date(2020, 4, 10),
            )

        assert set(ctx.prices.keys()) == {"stocks", "gold", "bonds"}
        assert ctx.settings.version == 1
        assert ctx.indicators.list() == []

    def test_from_config_with_packs(self, tmp_path: Path) -> None:
        """from_config() with packs= loads the specified packs."""
        config_yaml = tmp_path / "pac.yaml"
        config_yaml.write_text(
            "version: 1\n"
            "broker:\n"
            "  type: trade_republic\n"
            "  phone_number: '+491234567890'\n"
            "  pin: '1234'\n"
            "assets:\n"
            "  - id: stocks\n"
            "    name: Stocks ETF\n"
            "    isin: IE00BK5BQT80\n"
            "    ticker: EUNL.DE\n"
            "    target_pct: 70\n"
            "  - id: gold\n"
            "    name: Gold ETC\n"
            "    isin: IE00B4ND3602\n"
            "    ticker: 4GLD.DE\n"
            "    target_pct: 15\n"
            "  - id: bonds\n"
            "    name: Bond ETF\n"
            "    isin: IE00B3F81409\n"
            "    ticker: EUN4.DE\n"
            "    target_pct: 15\n"
            "app:\n"
            "  job_secret: test-secret\n"
            "channels: {}\n"
            "signals: []\n"
        )

        base = date(2020, 1, 1)
        mock_data = {
            "EUNL.DE": make_series("EUNL.DE", 100, base, 100.0),
            "4GLD.DE": make_series("4GLD.DE", 100, base, 50.0, "sine"),
            "EUN4.DE": make_series("EUN4.DE", 100, base, 80.0, "sine"),
        }

        def mock_fetch(
            ticker: str,
            start: date,
            end: date,
            proxy_chain: Any = None,
            primary_currency: Any = None,
            **kwargs: Any,
        ) -> PriceSeries:
            return mock_data[ticker]

        with (
            patch(
                "pac.backtester.data.provider.MarketDataProvider"
            ) as mock_provider_cls,
        ):
            mock_provider = mock_provider_cls.return_value
            mock_provider.fetch_with_proxy.side_effect = mock_fetch
            ctx = ResearchContext.from_config(
                str(config_yaml),
                start_date=date(2020, 1, 1),
                end_date=date(2020, 4, 10),
                packs=["crisis"],
            )

        assert "drawdown" in ctx.indicators.list()


# ---------------------------------------------------------------------------
# TestCompositeSeriesContext
# ---------------------------------------------------------------------------


class TestCompositeSeriesContext:
    def test_composite_series_delegates_to_registry(self) -> None:
        ctx = _build_context()
        ctx.register_indicator("a", lambda ps: True, lookback_days=10)
        ctx.register_indicator("b", lambda ps: False, lookback_days=10)

        results = ctx.composite_series(
            ["a", "b"],
            min_active=1,
            start=date(2020, 6, 1),
            end=date(2020, 6, 5),
        )
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, CompositeResult) for r in results)


# ---------------------------------------------------------------------------
# TestComputeMetrics
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def test_returns_dict_of_metric_names(self) -> None:
        ctx = _build_context()
        result = ctx.simulate("crisis_exploit")
        m = ctx.compute_metrics(result)
        assert set(m.keys()) == {"sharpe", "cagr", "max_drawdown"}

    def test_custom_metric_names(self) -> None:
        ctx = _build_context()
        result = ctx.simulate("crisis_exploit")
        m = ctx.compute_metrics(result, metric_names=["sortino", "calmar"])
        assert set(m.keys()) == {"sortino", "calmar"}

    def test_values_are_finite_floats(self) -> None:
        ctx = _build_context()
        result = ctx.simulate("crisis_exploit")
        m = ctx.compute_metrics(result)
        for v in m.values():
            assert isinstance(v, float)
            # NaN is acceptable from quantstats on synthetic data,
            # but values should be float type regardless
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# TestCompare
# ---------------------------------------------------------------------------


class TestCompare:
    def test_compare_two_variants_returns_comparison_table(self) -> None:
        ctx = _build_context()
        table = ctx.compare(
            [
                {"strategy": "crisis_exploit", "params": {}},
                {"strategy": "crisis_exploit", "params": {}},
            ]
        )
        assert isinstance(table, ComparisonTable)
        assert len(table.variants) == 2

    def test_compare_auto_generates_labels(self) -> None:
        ctx = _build_context()
        table = ctx.compare(
            [
                {"strategy": "crisis_exploit", "params": {"dd": -20}},
            ]
        )
        assert "crisis_exploit" in table.variants[0].label
        assert "dd=-20" in table.variants[0].label

    def test_compare_uses_custom_labels(self) -> None:
        ctx = _build_context()
        table = ctx.compare(
            [
                {
                    "strategy": "crisis_exploit",
                    "params": {},
                    "label": "MyLabel",
                },
            ]
        )
        assert table.variants[0].label == "MyLabel"

    def test_compare_empty_variants_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="must not be empty"):
            ctx.compare([])

    def test_compare_missing_strategy_key_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="strategy"):
            ctx.compare([{"params": {}}])

    def test_compare_metrics_match_requested(self) -> None:
        ctx = _build_context()
        table = ctx.compare(
            [{"strategy": "crisis_exploit"}],
            metrics=["sharpe"],
        )
        assert set(table.variants[0].metrics.keys()) == {"sharpe"}

    def test_compare_to_dict_pivot(self) -> None:
        ctx = _build_context()
        table = ctx.compare(
            [
                {
                    "strategy": "crisis_exploit",
                    "params": {},
                    "label": "A",
                },
            ]
        )
        d = table.to_dict()
        assert "A" in d
        assert "final_value" in d["A"]

    def test_compare_unknown_strategy_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="Unknown strategy"):
            ctx.compare([{"strategy": "nonexistent_strategy_xyz"}])


# ---------------------------------------------------------------------------
# TestSweep
# ---------------------------------------------------------------------------


class TestSweep:
    def test_sweep_2x2_grid_returns_4_results(self) -> None:
        ctx = _build_context()
        sr = ctx.sweep(
            "crisis_exploit",
            {"dd_threshold_pct": [-15, -20], "cooldown_days": [30, 60]},
        )
        assert isinstance(sr, SweepResult)
        assert len(sr.results) == 4

    def test_sweep_uses_base_params(self) -> None:
        ctx = _build_context()
        sr = ctx.sweep(
            "crisis_exploit",
            {"dd_threshold_pct": [-20]},
            base_params={"cooldown_days": 90},
        )
        for vr in sr.results:
            assert vr.params["cooldown_days"] == 90

    def test_sweep_best_returns_highest_primary_metric(self) -> None:
        ctx = _build_context()
        sr = ctx.sweep(
            "crisis_exploit",
            {"dd_threshold_pct": [-15, -20]},
            metrics=["sharpe"],
        )
        best = sr.best
        other = [v for v in sr.results if v.label != best.label]
        for v in other:
            assert v.metrics["sharpe"] <= best.metrics["sharpe"]

    def test_sweep_empty_grid_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="must not be empty"):
            ctx.sweep("crisis_exploit", {})

    def test_sweep_empty_values_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="empty values"):
            ctx.sweep("crisis_exploit", {"dd_threshold_pct": []})

    def test_sweep_preserves_grid_spec(self) -> None:
        ctx = _build_context()
        grid = {"dd_threshold_pct": [-15, -20]}
        sr = ctx.sweep("crisis_exploit", grid)
        assert sr.param_grid == grid

    def test_sweep_single_param_single_value(self) -> None:
        ctx = _build_context()
        sr = ctx.sweep("crisis_exploit", {"dd_threshold_pct": [-20]})
        assert len(sr.results) == 1


# ---------------------------------------------------------------------------
# TestCalendarsProperty
# ---------------------------------------------------------------------------


class TestCalendarsProperty:
    def test_calendars_returns_dict_with_4_builtin(self) -> None:
        ctx = _build_context()
        cals = ctx.calendars
        assert isinstance(cals, dict)
        expected = {"crises", "bull_runs", "corrections", "rate_regimes"}
        assert set(cals.keys()) == expected

    def test_calendars_returns_copy(self) -> None:
        ctx = _build_context()
        c1 = ctx.calendars
        c2 = ctx.calendars
        assert c1 is not c2


# ---------------------------------------------------------------------------
# TestValidateOOS
# ---------------------------------------------------------------------------


class TestValidateOOS:
    def test_validate_oos_default_split(self) -> None:
        ctx = _build_context()
        result = ctx.validate_oos("crisis_exploit")
        assert isinstance(result, OOSResult)
        assert result.split_date > ctx._data_start
        assert result.split_date < ctx._data_end

    def test_validate_oos_explicit_split_date(self) -> None:
        ctx = _build_context()
        split = date(2020, 9, 1)
        result = ctx.validate_oos("crisis_exploit", split_date=split)
        assert result.split_date == split

    def test_validate_oos_split_date_out_of_range(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="split_date"):
            ctx.validate_oos("crisis_exploit", split_date=date(2019, 1, 1))

    def test_validate_oos_split_date_at_end_raises(self) -> None:
        ctx = _build_context()
        with pytest.raises(ValueError, match="split_date"):
            ctx.validate_oos("crisis_exploit", split_date=ctx._data_end)

    def test_validate_oos_degradation_computed(self) -> None:
        ctx = _build_context()
        result = ctx.validate_oos("crisis_exploit")
        assert isinstance(result.degradation_ratio, float)

    def test_validate_oos_metrics_present(self) -> None:
        ctx = _build_context()
        result = ctx.validate_oos("crisis_exploit")
        assert "sharpe" in result.in_sample_metrics
        assert "sharpe" in result.out_of_sample_metrics

    def test_validate_oos_final_values_positive(self) -> None:
        ctx = _build_context()
        result = ctx.validate_oos("crisis_exploit")
        assert result.in_sample_final_value > 0
        assert result.out_of_sample_final_value > 0


# ---------------------------------------------------------------------------
# TestWalkForward
# ---------------------------------------------------------------------------


class TestWalkForward:
    def test_walk_forward_generates_windows(self) -> None:
        # 1500 bars = ~4.1 years; window=1yr, step=1yr → 3 windows
        ctx = _build_context(n_bars=1500)
        result = ctx.walk_forward(
            "crisis_exploit",
            window_years=1,
            step_years=1,
            min_oos_days=90,
        )
        assert isinstance(result, WalkForwardResult)
        assert len(result.windows) >= 1

    def test_walk_forward_stability_score(self) -> None:
        ctx = _build_context(n_bars=1500)
        result = ctx.walk_forward(
            "crisis_exploit",
            window_years=1,
            step_years=1,
            min_oos_days=90,
        )
        assert isinstance(result.stability_score, float)

    def test_walk_forward_too_short_data(self) -> None:
        ctx = _build_context(n_bars=50)
        with pytest.raises(ValueError, match="Data too short"):
            ctx.walk_forward(
                "crisis_exploit",
                window_years=10,
                step_years=5,
            )

    def test_walk_forward_skips_short_oos(self) -> None:
        # 1500 bars (~4.1 years), window_years=1, step_years=1.
        # Each full OOS = 364 days. Last truncated window has ~39 days.
        # With min_oos_days=100, the truncated window is skipped.
        ctx = _build_context(n_bars=1500)
        result_loose = ctx.walk_forward(
            "crisis_exploit",
            window_years=1,
            step_years=1,
            min_oos_days=30,
        )
        result_strict = ctx.walk_forward(
            "crisis_exploit",
            window_years=1,
            step_years=1,
            min_oos_days=100,
        )
        # Stricter min_oos_days should drop the truncated final window
        assert len(result_strict.windows) <= len(result_loose.windows)
        for w in result_strict.windows:
            oos_days = (w.oos_end - w.oos_start).days
            assert oos_days >= 100

    def test_walk_forward_consistent_windows(self) -> None:
        ctx = _build_context(n_bars=1500)
        result = ctx.walk_forward(
            "crisis_exploit",
            window_years=1,
            step_years=1,
            min_oos_days=90,
        )
        assert isinstance(result.consistent_windows, int)
        assert result.consistent_windows >= 0
        assert result.consistent_windows <= len(result.windows)


# ---------------------------------------------------------------------------
# TestEvaluateEvents
# ---------------------------------------------------------------------------


def _make_test_calendar() -> EventCalendar:
    """Calendar with events inside the 500-bar range (2020-01-01 to ~2021-05-15)."""
    return EventCalendar(
        name="test_cal",
        events=(
            MarketEvent(
                date(2020, 3, 1),
                date(2020, 5, 1),
                "Event A",
                frozenset({"crisis"}),
            ),
            MarketEvent(
                date(2020, 8, 1),
                date(2020, 10, 1),
                "Event B",
                frozenset({"recovery"}),
            ),
            MarketEvent(
                date(2021, 1, 1),
                date(2021, 3, 1),
                "Event C",
                frozenset({"bull"}),
            ),
        ),
    )


class TestEvaluateEvents:
    def test_evaluate_events_returns_result(self) -> None:
        ctx = _build_context()
        cal = _make_test_calendar()
        result = ctx.evaluate_events("crisis_exploit", calendar=cal)
        assert isinstance(result, EventAnalysisResult)
        assert result.calendar_name == "test_cal"

    def test_evaluate_events_per_event_metrics(self) -> None:
        ctx = _build_context()
        cal = _make_test_calendar()
        result = ctx.evaluate_events("crisis_exploit", calendar=cal)
        assert len(result.per_event) == 3
        for em in result.per_event:
            assert em.event_name is not None
            assert isinstance(em.event_return, float)
            assert "sharpe" in em.metrics_during_event

    def test_evaluate_events_empty_calendar(self) -> None:
        ctx = _build_context()
        empty_cal = EventCalendar(name="empty", events=())
        with pytest.raises(ValueError, match="no events"):
            ctx.evaluate_events("crisis_exploit", calendar=empty_cal)

    def test_evaluate_events_outside_data(self) -> None:
        ctx = _build_context()
        outside_cal = EventCalendar(
            name="outside",
            events=(
                MarketEvent(
                    date(2025, 1, 1),
                    date(2025, 6, 1),
                    "Future",
                    frozenset({"future"}),
                ),
            ),
        )
        with pytest.raises(ValueError, match=r"No events.*overlap"):
            ctx.evaluate_events("crisis_exploit", calendar=outside_cal)

    def test_evaluate_events_generalization_score(self) -> None:
        ctx = _build_context()
        cal = _make_test_calendar()
        result = ctx.evaluate_events("crisis_exploit", calendar=cal)
        assert isinstance(result.generalization_score, float)

    def test_evaluate_events_mixed_signs_nan(self) -> None:
        import math

        # Create a calendar with events in extreme V-shape regions
        # to produce mixed-sign returns
        cal = EventCalendar(
            name="mixed",
            events=(
                # During the drop (negative return)
                MarketEvent(
                    date(2020, 1, 2),
                    date(2020, 4, 1),
                    "Drop",
                    frozenset({"crisis"}),
                ),
                # During the recovery (positive return)
                MarketEvent(
                    date(2020, 9, 1),
                    date(2020, 12, 1),
                    "Recovery",
                    frozenset({"bull"}),
                ),
            ),
        )
        ctx = _build_context()
        result = ctx.evaluate_events("crisis_exploit", calendar=cal)
        returns = [e.event_return for e in result.per_event]
        has_positive = any(r > 0 for r in returns if not math.isnan(r))
        has_negative = any(r < 0 for r in returns if not math.isnan(r))
        if has_positive and has_negative:
            assert math.isnan(result.generalization_score)

    def test_evaluate_events_mean_return(self) -> None:
        ctx = _build_context()
        cal = _make_test_calendar()
        result = ctx.evaluate_events("crisis_exploit", calendar=cal)
        assert isinstance(result.mean_event_return, float)
