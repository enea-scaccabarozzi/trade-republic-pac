"""Tests for IndicatorRegistry, packs, and discovery."""

from __future__ import annotations

import dataclasses
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pac.backtester.research.indicators import (
    CompositeResult,
    IndicatorRegistry,
    threshold,
)
from pac.backtester.research.indicators import __all__ as indicators_all
from pac.backtester.research.packs import discover_packs
from pac.backtester.research.packs.crisis import CrisisIndicatorDef, CrisisPack
from pac.models.market_data import PriceSeries

# ---------------------------------------------------------------------------
# Registry starts empty
# ---------------------------------------------------------------------------


class TestRegistryEmpty:
    def test_new_registry_has_no_indicators(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        assert reg.list() == []


# ---------------------------------------------------------------------------
# Pack discovery
# ---------------------------------------------------------------------------


class TestPackDiscovery:
    def test_discover_packs_finds_crisis(self) -> None:
        packs = discover_packs()
        assert "crisis" in packs

    def test_discover_packs_crisis_has_correct_name(self) -> None:
        packs = discover_packs()
        assert packs["crisis"].name == "crisis"

    def test_discover_packs_finds_tulipy(self) -> None:
        packs = discover_packs()
        assert "tulipy" in packs


# ---------------------------------------------------------------------------
# Pack registration via discovery
# ---------------------------------------------------------------------------


class TestPackRegistration:
    def test_register_crisis_pack_adds_six_indicators(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        expected = [
            "correlation",
            "death_cross",
            "divergence",
            "drawdown",
            "relative_strength",
            "volatility",
        ]
        assert reg.list() == expected

    def test_register_unknown_pack_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        with pytest.raises(ValueError, match="nonexistent"):
            reg.register_pack("nonexistent")

    def test_register_tulipy_pack_with_mock(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        mock_ti = _make_mock_tulipy()
        with patch.dict(sys.modules, {"tulipy": mock_ti}):
            reg = IndicatorRegistry(price_data)
            reg.register_pack("tulipy")
            assert "sma" in reg.list()

    def test_register_tulipy_raises_when_not_installed(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        with patch.dict(sys.modules, {"tulipy": None}):
            reg = IndicatorRegistry(price_data)
            with pytest.raises(ImportError, match="tulipy is not installed"):
                reg.register_pack("tulipy")


# ---------------------------------------------------------------------------
# Custom indicator registration
# ---------------------------------------------------------------------------


class TestCustomRegistration:
    def test_register_custom_indicator(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        assert "last_close" in reg.list()

    def test_register_duplicate_name_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("x", lambda ps: 0.0, lookback_days=10)
        with pytest.raises(ValueError, match="already registered"):
            reg.register("x", lambda ps: 0.0, lookback_days=10)

    def test_register_multi_asset_custom(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        received: dict[str, PriceSeries] = {}

        def multi_fn(
            data: dict[str, PriceSeries],
        ) -> float:
            received.update(data)
            return 42.0

        reg = IndicatorRegistry(price_data)
        reg.register(
            "multi",
            multi_fn,
            assets=["stocks", "gold"],
            lookback_days=10,
        )
        target = date(2020, 6, 1)
        reg.compute("multi", target)
        assert "stocks" in received
        assert "gold" in received


# ---------------------------------------------------------------------------
# asset_override validation
# ---------------------------------------------------------------------------


class TestAssetOverride:
    def test_compute_with_asset_override_on_single_asset(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        target = date(2020, 12, 1)
        # drawdown is single-asset (stocks), override to gold
        result = reg.compute("drawdown", target, asset="gold")
        assert isinstance(result, float)

    def test_compute_with_asset_override_on_multi_asset_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        target = date(2020, 12, 1)
        with pytest.raises(ValueError, match="multi-asset"):
            reg.compute("divergence", target, asset="bonds")

    def test_series_with_asset_override_on_multi_asset_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        start = date(2020, 11, 1)
        end = date(2020, 12, 1)
        with pytest.raises(ValueError, match="multi-asset"):
            reg.series("divergence", start, end, asset="bonds")


# ---------------------------------------------------------------------------
# compute() — single date
# ---------------------------------------------------------------------------


class TestCompute:
    def test_compute_crisis_drawdown(self, price_data: dict[str, PriceSeries]) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        # At the V-shape trough (~day 250), drawdown should be negative
        target = date(2020, 9, 1)  # ~day 244
        result = reg.compute("drawdown", target)
        assert isinstance(result, float)
        assert result < -0.05  # meaningful drawdown

    def test_compute_crisis_death_cross_returns_bool(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        target = date(2021, 2, 1)  # late enough for 200-day SMA
        result = reg.compute("death_cross", target)
        assert isinstance(result, bool)

    def test_compute_crisis_divergence_uses_two_assets(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        target = date(2020, 12, 1)
        result = reg.compute("divergence", target)
        assert isinstance(result, float)
        # V-shape vs sine should produce non-zero divergence
        assert result != 0.0

    def test_compute_unregistered_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        with pytest.raises(KeyError):
            reg.compute("nonexistent", date(2020, 6, 1))

    def test_compute_custom_indicator(self, price_data: dict[str, PriceSeries]) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        target = date(2020, 6, 1)
        result = reg.compute("last_close", target)
        assert isinstance(result, float)
        assert result > 0.0


# ---------------------------------------------------------------------------
# CrisisIndicatorDef._resolve_args with _param_map
# ---------------------------------------------------------------------------


class TestCrisisResolveArgs:
    def _build_crisis_defs(self) -> dict[str, CrisisIndicatorDef]:
        pack = CrisisPack()
        reg = IndicatorRegistry({})
        pack.register(reg)
        return {
            ind.name: ind
            for ind in [reg.get(n) for n in reg.list()]
            if isinstance(ind, CrisisIndicatorDef)
        }

    def test_crisis_drawdown_resolve_args_maps_stocks_to_equity_series(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        defs = self._build_crisis_defs()
        dd = defs["drawdown"]
        args = dd._resolve_args(price_data, {"lookback_bars": 252})
        assert "equity_series" in args
        assert args["equity_series"] is price_data["stocks"]
        assert args["lookback_bars"] == 252

    def test_crisis_divergence_resolve_args_maps_gold_and_stocks(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        defs = self._build_crisis_defs()
        div = defs["divergence"]
        args = div._resolve_args(price_data, {"lookback_bars": 40})
        assert "gold_series" in args
        assert args["gold_series"] is price_data["gold"]
        assert "equity_series" in args
        assert args["equity_series"] is price_data["stocks"]

    def test_crisis_correlation_resolve_args_maps_bonds_and_stocks(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        defs = self._build_crisis_defs()
        corr = defs["correlation"]
        args = corr._resolve_args(price_data, {"window": 60})
        assert "bond_series" in args
        assert args["bond_series"] is price_data["bonds"]
        assert "equity_series" in args
        assert args["equity_series"] is price_data["stocks"]

    def test_crisis_drawdown_delegates_to_compute_drawdown(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        from pac.rules.builtin._indicators import compute_drawdown

        defs = self._build_crisis_defs()
        dd = defs["drawdown"]

        # Compute via the registry wrapper
        target = date(2020, 9, 1)
        start = target - timedelta(days=dd.lookback_days)
        sliced = {"stocks": price_data["stocks"].slice(start, target)}
        wrapped_result = dd.compute(sliced)

        # Compute directly
        direct_result = compute_drawdown(sliced["stocks"], lookback_bars=252)

        assert wrapped_result == direct_result.drawdown_pct


# ---------------------------------------------------------------------------
# series() — date range
# ---------------------------------------------------------------------------


class TestSeries:
    def test_series_returns_date_result_pairs(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        start = date(2020, 11, 1)
        end = date(2020, 11, 30)
        results = reg.series("drawdown", start, end)
        assert len(results) > 0
        for d, val in results:
            assert isinstance(d, date)
            assert isinstance(val, float)

    def test_series_results_are_non_trivial(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        start = date(2020, 6, 1)
        end = date(2021, 1, 1)
        results = reg.series("drawdown", start, end)
        values = [v for _, v in results]
        assert isinstance(values[0], float)
        # Not all the same — the V-shape produces changing drawdowns
        assert len(set(values)) > 1

    def test_series_only_includes_trading_days(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        start = date(2020, 11, 1)
        end = date(2020, 11, 30)
        results = reg.series("drawdown", start, end)
        bar_dates = {
            bar.date for bar in price_data["stocks"].bars if start <= bar.date <= end
        }
        result_dates = {d for d, _ in results}
        # Result dates must be a subset of actual bar dates
        assert result_dates <= bar_dates

    def test_series_skips_dates_with_insufficient_data(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        def strict_fn(ps: PriceSeries) -> float:
            if len(ps.bars) < 9999:
                msg = "Not enough data"
                raise ValueError(msg)
            return float(ps.bars[-1].close)

        reg = IndicatorRegistry(price_data)
        reg.register("needs_lots", strict_fn, lookback_days=9999)
        start = date(2020, 1, 1)
        end = date(2020, 6, 1)
        results = reg.series("needs_lots", start, end)
        # All dates should be skipped — not enough data
        assert results == []

    def test_series_empty_range_returns_empty(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        future = date(2030, 1, 1)
        results = reg.series("drawdown", future, future)
        assert results == []

    def test_series_custom_indicator(self, price_data: dict[str, PriceSeries]) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        start = date(2020, 6, 1)
        end = date(2020, 6, 10)
        results = reg.series("last_close", start, end)
        assert len(results) > 0
        for _d, val in results:
            assert isinstance(val, float)
            assert val > 0.0


# ---------------------------------------------------------------------------
# Tulipy option filtering
# ---------------------------------------------------------------------------


class TestTulipyOptions:
    def test_tulipy_compute_with_all_options(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        mock_ti = _make_mock_tulipy()
        with patch.dict(sys.modules, {"tulipy": mock_ti}):
            reg = IndicatorRegistry(price_data)
            reg.register_pack("tulipy")
            result = reg.compute("sma", date(2020, 12, 1), period=14)
            assert result is not None

    def test_tulipy_compute_with_no_options(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        mock_ti = _make_mock_tulipy()
        with patch.dict(sys.modules, {"tulipy": mock_ti}):
            reg = IndicatorRegistry(price_data)
            reg.register_pack("tulipy")
            result = reg.compute("sma", date(2020, 12, 1))
            assert result is not None

    def test_tulipy_compute_with_partial_options_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        mock_ti = _make_mock_tulipy(two_options=True)
        with patch.dict(sys.modules, {"tulipy": mock_ti}):
            reg = IndicatorRegistry(price_data)
            reg.register_pack("tulipy")
            with pytest.raises(ValueError, match="provide all options"):
                reg.compute(
                    "macd",
                    date(2020, 12, 1),
                    short_period=12,
                )


# ---------------------------------------------------------------------------
# list() and get()
# ---------------------------------------------------------------------------


class TestListAndGet:
    def test_list_sorted_alphabetically(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("z_indicator", lambda ps: 0.0, lookback_days=10)
        reg.register("a_indicator", lambda ps: 0.0, lookback_days=10)
        reg.register("m_indicator", lambda ps: 0.0, lookback_days=10)
        assert reg.list() == [
            "a_indicator",
            "m_indicator",
            "z_indicator",
        ]

    def test_get_returns_indicator_def(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        defn = reg.get("drawdown")
        assert isinstance(defn, CrisisIndicatorDef)
        assert defn.name == "drawdown"

    def test_get_unknown_raises(self, price_data: dict[str, PriceSeries]) -> None:
        reg = IndicatorRegistry(price_data)
        with pytest.raises(KeyError):
            reg.get("nonexistent")


# ---------------------------------------------------------------------------
# TulipyIndicatorDef unit tests with mock
# ---------------------------------------------------------------------------


class TestTulipyIndicatorDef:
    def test_tulipy_def_extract_inputs_maps_real_to_close(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        from pac.backtester.research.packs.tulipy_bridge import (
            TulipyIndicatorDef,
        )

        defn = TulipyIndicatorDef(
            name="sma",
            full_name="Simple Moving Average",
            inputs=("real",),
            options=("period",),
            outputs=("sma",),
            _ti_func=MagicMock(),
        )
        series = price_data["stocks"]
        arrays = defn._extract_inputs(series)
        assert len(arrays) == 1
        assert len(arrays[0]) == len(series.bars)
        expected_close = float(series.bars[0].close)
        assert arrays[0][0] == pytest.approx(expected_close)

    def test_tulipy_def_extract_inputs_maps_hlc(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        from pac.backtester.research.packs.tulipy_bridge import (
            TulipyIndicatorDef,
        )

        defn = TulipyIndicatorDef(
            name="stoch",
            full_name="Stochastic",
            inputs=("high", "low", "close"),
            options=(),
            outputs=("stoch",),
            _ti_func=MagicMock(),
        )
        series = price_data["stocks"]
        arrays = defn._extract_inputs(series)
        assert len(arrays) == 3
        # First array is highs
        assert arrays[0][0] == pytest.approx(float(series.bars[0].high))
        # Second array is lows
        assert arrays[1][0] == pytest.approx(float(series.bars[0].low))
        # Third array is closes
        assert arrays[2][0] == pytest.approx(float(series.bars[0].close))

    def test_tulipy_def_compute_calls_ti_func(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        import numpy as np

        from pac.backtester.research.packs.tulipy_bridge import (
            TulipyIndicatorDef,
        )

        mock_func = MagicMock(return_value=np.array([1.0, 2.0]))
        defn = TulipyIndicatorDef(
            name="sma",
            full_name="Simple Moving Average",
            inputs=("real",),
            options=("period",),
            outputs=("sma",),
            _ti_func=mock_func,
        )
        sliced = {
            "stocks": price_data["stocks"].slice(date(2020, 6, 1), date(2020, 12, 1))
        }
        defn.compute(sliced, period=14)
        mock_func.assert_called_once()


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_module_all_exports_only_public_api(self) -> None:
        assert indicators_all == [
            "CompositeResult",
            "IndicatorDef",
            "IndicatorRegistry",
            "IndicatorResult",
            "threshold",
        ]


# ---------------------------------------------------------------------------
# CompositeResult
# ---------------------------------------------------------------------------


class TestCompositeResult:
    def test_composite_result_is_frozen_dataclass(self) -> None:
        r = CompositeResult(
            date=date(2020, 6, 1),
            active=True,
            active_count=2,
            total=3,
            min_active=2,
            votes={"a": True, "b": True, "c": False},
            values={"a": 1.0, "b": True, "c": 0.5},
        )
        assert dataclasses.is_dataclass(r)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.active = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# threshold() helper
# ---------------------------------------------------------------------------


class TestThresholdHelper:
    def test_threshold_lt(self) -> None:
        fn = threshold("<", 30)
        assert fn(25) is True
        assert fn(35) is False

    def test_threshold_le(self) -> None:
        fn = threshold("<=", 30)
        assert fn(30) is True
        assert fn(31) is False

    def test_threshold_gt(self) -> None:
        fn = threshold(">", 70)
        assert fn(75) is True
        assert fn(65) is False

    def test_threshold_ge(self) -> None:
        fn = threshold(">=", 70)
        assert fn(70) is True
        assert fn(69) is False

    def test_threshold_invalid_op_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported operator"):
            threshold("!=", 0)


# ---------------------------------------------------------------------------
# composite_series()
# ---------------------------------------------------------------------------


class TestCompositeSeries:
    def test_composite_all_bool_indicators(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("always_true", lambda ps: True, lookback_days=10)
        reg.register("also_true", lambda ps: True, lookback_days=10)
        reg.register("always_false", lambda ps: False, lookback_days=10)

        results = reg.composite_series(
            ["always_true", "also_true", "always_false"],
            min_active=2,
            start=date(2020, 6, 1),
            end=date(2020, 6, 5),
        )
        assert len(results) > 0
        for r in results:
            assert r.active is True
            assert r.active_count == 2

    def test_composite_below_min_active_is_inactive(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("always_true", lambda ps: True, lookback_days=10)
        reg.register("also_true", lambda ps: True, lookback_days=10)
        reg.register("always_false", lambda ps: False, lookback_days=10)

        results = reg.composite_series(
            ["always_true", "also_true", "always_false"],
            min_active=3,
            start=date(2020, 6, 1),
            end=date(2020, 6, 5),
        )
        assert len(results) > 0
        for r in results:
            assert r.active is False

    def test_composite_with_threshold_on_numeric(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )
        reg.register("always_true", lambda ps: True, lookback_days=10)

        results = reg.composite_series(
            ["last_close", "always_true"],
            min_active=1,
            start=date(2020, 6, 1),
            end=date(2020, 6, 5),
            thresholds={"last_close": threshold("<", 80)},
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r.active, bool)
            assert isinstance(r.votes["last_close"], bool)

    def test_composite_numeric_without_threshold_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register(
            "last_close",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )

        with pytest.raises(ValueError, match="returns a numeric value"):
            reg.composite_series(
                ["last_close"],
                min_active=1,
                start=date(2020, 6, 1),
                end=date(2020, 6, 5),
            )

    def test_composite_mixed_sources_crisis_and_custom(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")
        reg.register("bull", lambda ps: True, lookback_days=10)

        results = reg.composite_series(
            ["drawdown", "death_cross", "bull"],
            min_active=1,
            start=date(2020, 11, 1),
            end=date(2020, 11, 10),
            thresholds={"drawdown": threshold("<", -0.10)},
        )
        assert len(results) > 0
        for r in results:
            assert "drawdown" in r.votes
            assert "death_cross" in r.votes
            assert "bull" in r.votes

    def test_composite_with_kwargs_tuple_form(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        received_kwargs: dict[str, object] = {}

        def capture_fn(ps: PriceSeries, **kwargs: object) -> float:
            received_kwargs.update(kwargs)
            return float(ps.bars[-1].close)

        reg = IndicatorRegistry(price_data)
        reg.register("custom", capture_fn, lookback_days=10)

        reg.composite_series(
            [("custom", {"period": 14})],
            min_active=1,
            start=date(2020, 6, 1),
            end=date(2020, 6, 3),
            thresholds={"custom": threshold(">", 0)},
        )
        assert received_kwargs.get("period") == 14

    def test_composite_skips_dates_with_insufficient_data(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        def strict_fn(ps: PriceSeries) -> bool:
            if len(ps.bars) < 9999:
                raise ValueError("Not enough data")
            return True

        reg = IndicatorRegistry(price_data)
        reg.register("needs_lots", strict_fn, lookback_days=9999)
        reg.register("always_true", lambda ps: True, lookback_days=10)

        results = reg.composite_series(
            ["needs_lots", "always_true"],
            min_active=2,
            start=date(2020, 6, 1),
            end=date(2020, 6, 5),
        )
        # needs_lots votes False (insufficient data), so active_count <= 1
        for r in results:
            assert r.votes["needs_lots"] is False
            assert r.active is False

    def test_composite_result_has_per_indicator_votes(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("a", lambda ps: True, lookback_days=10)
        reg.register("b", lambda ps: False, lookback_days=10)

        results = reg.composite_series(
            ["a", "b"],
            min_active=1,
            start=date(2020, 6, 1),
            end=date(2020, 6, 3),
        )
        for r in results:
            assert r.votes == {"a": True, "b": False}

    def test_composite_result_has_per_indicator_values(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("a", lambda ps: True, lookback_days=10)
        reg.register(
            "b",
            lambda ps: float(ps.bars[-1].close),
            lookback_days=10,
        )

        results = reg.composite_series(
            ["a", "b"],
            min_active=1,
            start=date(2020, 6, 1),
            end=date(2020, 6, 3),
            thresholds={"b": threshold(">", 0)},
        )
        for r in results:
            assert "a" in r.values
            assert "b" in r.values
            assert r.values["a"] is True
            assert isinstance(r.values["b"], float)

    def test_composite_min_active_validation(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("a", lambda ps: True, lookback_days=10)

        with pytest.raises(ValueError, match="min_active must be between"):
            reg.composite_series(
                ["a"],
                min_active=0,
                start=date(2020, 6, 1),
                end=date(2020, 6, 5),
            )

        with pytest.raises(ValueError, match="min_active must be between"):
            reg.composite_series(
                ["a"],
                min_active=2,
                start=date(2020, 6, 1),
                end=date(2020, 6, 5),
            )

    def test_composite_unregistered_indicator_raises(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        with pytest.raises(KeyError, match="not_registered"):
            reg.composite_series(
                ["not_registered"],
                min_active=1,
                start=date(2020, 6, 1),
                end=date(2020, 6, 5),
            )

    def test_composite_empty_range_returns_empty(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register("a", lambda ps: True, lookback_days=10)

        results = reg.composite_series(
            ["a"],
            min_active=1,
            start=date(2030, 1, 1),
            end=date(2030, 1, 31),
        )
        assert results == []

    def test_composite_bool_indicator_no_threshold_needed(
        self, price_data: dict[str, PriceSeries]
    ) -> None:
        reg = IndicatorRegistry(price_data)
        reg.register_pack("crisis")

        # death_cross returns bool — no threshold entry needed
        results = reg.composite_series(
            ["death_cross"],
            min_active=1,
            start=date(2021, 2, 1),
            end=date(2021, 2, 5),
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r.votes["death_cross"], bool)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_tulipy(*, two_options: bool = False) -> MagicMock:
    """Create a mock tulipy module with a fake 'sma' indicator."""
    import numpy as np

    mock_ti = MagicMock()

    fake_sma = MagicMock()
    fake_sma.inputs = ["real"]
    fake_sma.options = ["period"]
    fake_sma.outputs = ["sma"]
    fake_sma.full_name = "Simple Moving Average"
    fake_sma.return_value = np.array([1.0, 2.0, 3.0])

    attrs = {"sma": fake_sma}

    if two_options:
        fake_macd = MagicMock()
        fake_macd.inputs = ["real"]
        fake_macd.options = ["short_period", "long_period"]
        fake_macd.outputs = ["macd", "signal"]
        fake_macd.full_name = "Moving Average Convergence/Divergence"
        fake_macd.return_value = (
            np.array([1.0]),
            np.array([2.0]),
        )
        attrs["macd"] = fake_macd

    type(mock_ti).__dir__ = lambda self: list(attrs.keys())  # type: ignore[method-assign]
    for name, obj in attrs.items():
        setattr(mock_ti, name, obj)

    return mock_ti
