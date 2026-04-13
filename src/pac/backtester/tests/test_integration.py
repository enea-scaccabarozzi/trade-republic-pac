"""End-to-end integration test for phases 2-7 of the backtester.

Bypasses MarketDataProvider (network/yfinance) by injecting synthetic PriceSeries
directly into BacktestSimulator. Proves that data loading → simulation → metrics
→ persistence pipeline works correctly with both builtin strategies.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip(
    "quantstats", reason="backtest extras required: uv sync --group backtest"
)

from pac.backtester.config import BacktestConfig
from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.engine.simulator import BacktestSimulator, SimulationResult
from pac.backtester.metrics.report import compute_report
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.builtin.cycle_exploit import (
    CycleExploitParams,
    CycleExploitStrategy,
)
from pac.backtester.strategies.builtin.pac_alignment import (
    PacAlignmentParams,
    PacAlignmentStrategy,
)
from pac.backtester.strategies.discovery import discover_strategies
from pac.config import Settings
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry

# ---------------------------------------------------------------------------
# Shared settings and config
# ---------------------------------------------------------------------------


def _make_integration_settings() -> Settings:
    """Settings with tickers that match _make_diverging_price_data() keys."""
    return Settings.model_validate(
        {
            "version": 1,
            "broker": {
                "type": "trade_republic",
                "phone_number": "+491234567890",
                "pin": "1234",
            },
            "assets": [
                {
                    "id": "stocks",
                    "name": "Stocks ETF",
                    "isin": "IE00BK5BQT80",
                    "ticker": "EUNL.DE",
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "ticker": "4GLD.DE",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "ticker": "EUN4.DE",
                    "target_pct": 15,
                },
            ],
            "app": {"job_secret": "test-job-secret"},
            "channels": {},
            "signals": [
                {
                    "rule": "threshold_deviation",
                    "name": "threshold",
                    "schedule": "* * * * *",
                    "channels": [],
                    "template": "threshold_alert",
                    "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                },
                {
                    "rule": "cycle_inversion",
                    "name": "cycle",
                    "schedule": "* * * * *",
                    "channels": [],
                    "template": "cycle_alert",
                    "params": {"min_pct": 1.0, "warning_pct": 2.0, "critical_pct": 4.0},
                },
            ],
        }
    )


_INTEGRATION_SETTINGS = _make_integration_settings()

_BASE_CONFIG_KWARGS: dict[str, Any] = dict(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 6, 28),
    initial_cash=Decimal("0"),
    monthly_contribution=Decimal("500"),
    pac_execution_days=[2],
    monte_carlo_iterations=3,
    slippage_days=(0, 0),
    metrics=["sortino", "cagr"],
    benchmark=False,
    seed=42,
)


# ---------------------------------------------------------------------------
# Price data helpers
# ---------------------------------------------------------------------------


def _make_diverging_price_data(
    start_date: date = date(2024, 1, 1),
    n_days: int = 130,
) -> dict[str, PriceSeries]:
    """Generate synthetic price data with stocks rising and gold/bonds flat.

    Returns a dict keyed by Yahoo Finance ticker strings — the same tickers
    defined in _make_integration_settings() assets. The simulator builds its
    internal _price_index by ticker (via _ticker_asset dict), so keys MUST match.

    Price behaviour:
      Stocks: linearly rises 100 → 230 (130% gain over n_days)
      Gold:   flat at 50
      Bonds:  flat at 30

    With pac_execution_days=[2] and initial_cash=0:
      - First PAC on Jan 2 → portfolio exactly at 70/15/15 target.
      - As stocks price rises, stock allocation drifts above 70%.
      - With cycle_inversion min_pct=1.0: signals fire from ~month 2 onward.
    """
    stocks_bars: list[PriceBar] = []
    gold_bars: list[PriceBar] = []
    bonds_bars: list[PriceBar] = []

    current = start_date
    trading_day = 0
    while trading_day < n_days:
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        stocks_price = Decimal("100") + Decimal(str(trading_day))
        gold_price = Decimal("50")
        bonds_price = Decimal("30")

        stocks_bars.append(
            PriceBar(
                date=current,
                open=stocks_price - Decimal("1"),
                high=stocks_price + Decimal("2"),
                low=stocks_price - Decimal("2"),
                close=stocks_price,
                volume=500_000,
            )
        )
        gold_bars.append(
            PriceBar(
                date=current,
                open=gold_price,
                high=gold_price + Decimal("1"),
                low=gold_price - Decimal("1"),
                close=gold_price,
                volume=200_000,
            )
        )
        bonds_bars.append(
            PriceBar(
                date=current,
                open=bonds_price,
                high=bonds_price + Decimal("1"),
                low=bonds_price - Decimal("1"),
                close=bonds_price,
                volume=100_000,
            )
        )

        trading_day += 1
        current += timedelta(days=1)

    return {
        "EUNL.DE": PriceSeries(
            ticker="EUNL.DE", interval=Interval.DAILY, bars=stocks_bars
        ),
        "4GLD.DE": PriceSeries(
            ticker="4GLD.DE", interval=Interval.DAILY, bars=gold_bars
        ),
        "EUN4.DE": PriceSeries(
            ticker="EUN4.DE", interval=Interval.DAILY, bars=bonds_bars
        ),
    }


def _make_registry() -> SignalRegistry:
    registry = SignalRegistry()
    for cls in discover_rules().values():
        registry.register(cls)
    return registry


def _run_full_pipeline(
    config: BacktestConfig,
    strategy: BacktestStrategy[Any],
    tmp_path: Path,
) -> tuple[RunResult, Path]:
    """Run simulator → metrics → store. Returns (RunResult, saved_path)."""
    price_data = _make_diverging_price_data()
    registry = _make_registry()

    sim = BacktestSimulator(
        config=config,
        settings=_INTEGRATION_SETTINGS,
        price_data=price_data,
        signal_registry=registry,
        strategy=strategy,
        rng_seed=42,
    )

    sim_result = SimulationResult(
        config=config,
        iterations=[sim.run_iteration(i) for i in range(config.monte_carlo_iterations)],
    )
    report = compute_report(sim_result, _INTEGRATION_SETTINGS, price_data, rng_seed=42)
    run_result = build_run_result(report)

    store = ResultStore(base_dir=tmp_path / "backtests")
    path = store.save(run_result)
    return run_result, path


# ---------------------------------------------------------------------------
# Discovery verification
# ---------------------------------------------------------------------------


class TestStrategyDiscovery:
    def test_all_strategies_discovered(self) -> None:
        discovered = discover_strategies()
        assert "pac_alignment" in discovered
        assert "cycle_exploit" in discovered
        assert "crisis_exploit" in discovered
        assert len(discovered) == 3


# ---------------------------------------------------------------------------
# PacAlignmentStrategy end-to-end
# ---------------------------------------------------------------------------


class TestPacAlignmentEndToEnd:
    def _make_config(self) -> BacktestConfig:
        return BacktestConfig(strategy="pac_alignment", **_BASE_CONFIG_KWARGS)

    def test_simulation_completes_without_error(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        _run_result, path = _run_full_pipeline(config, strategy, tmp_path)
        assert path.exists()

    def test_result_is_loadable_from_json(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        run_result, _path = _run_full_pipeline(config, strategy, tmp_path)
        store = ResultStore(base_dir=tmp_path / "backtests")
        loaded = store.load(run_result.run_id)
        assert loaded.config.strategy == "pac_alignment"

    def test_equity_curve_has_trading_day_entries(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        assert len(run_result.equity_curve) >= 100

    def test_pac_trades_recorded(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        pac_trades = [t for t in run_result.trades if t.type == "pac_execution"]
        assert len(pac_trades) >= 5

    def test_metrics_are_finite(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        for metric_name in ["sortino", "cagr"]:
            mv = run_result.metrics["strategy"][metric_name]
            assert mv.median == mv.median  # NaN check: NaN != NaN

    def test_pac_volumes_were_adjusted(self, tmp_path: Path) -> None:
        """Strategy adjusts PAC at least once: some trade has different amounts
        than the default 350/75/75 split."""
        config = self._make_config()
        strategy = PacAlignmentStrategy(PacAlignmentParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        pac_trades = [t for t in run_result.trades if t.type == "pac_execution"]
        stocks_amounts = {t.amount_eur for t in pac_trades if t.asset_id == "stocks"}
        # Default always gives 350; alignment gives varied amounts after overweight
        assert len(stocks_amounts) > 1 or min(stocks_amounts) < 350


# ---------------------------------------------------------------------------
# CycleExploitStrategy end-to-end
# ---------------------------------------------------------------------------


class TestCycleExploitEndToEnd:
    def _make_config(self) -> BacktestConfig:
        return BacktestConfig(strategy="cycle_exploit", **_BASE_CONFIG_KWARGS)

    def test_simulation_completes_without_error(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        _run_result, path = _run_full_pipeline(config, strategy, tmp_path)
        assert path.exists()

    def test_result_is_loadable_from_json(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        run_result, _path = _run_full_pipeline(config, strategy, tmp_path)
        store = ResultStore(base_dir=tmp_path / "backtests")
        loaded = store.load(run_result.run_id)
        assert loaded.config.strategy == "cycle_exploit"

    def test_hard_rebalance_trades_appear(self, tmp_path: Path) -> None:
        """Cycle exploitation produces at least one hard rebalance trade."""
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        hr_trades = [t for t in run_result.trades if t.type == "hard_rebalance"]
        assert len(hr_trades) >= 2
        assert any(not t.skipped for t in hr_trades if t.direction == "buy")

    def test_hard_rebalance_trades_have_stocks_sell(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        sell_stocks = [
            t
            for t in run_result.trades
            if t.type == "hard_rebalance"
            and t.direction == "sell"
            and t.asset_id == "stocks"
        ]
        assert len(sell_stocks) >= 1

    def test_metrics_are_finite(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        for metric_name in ["sortino", "cagr"]:
            mv = run_result.metrics["strategy"][metric_name]
            assert mv.median == mv.median  # NaN check

    def test_json_schema_shape(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        _, path = _run_full_pipeline(config, strategy, tmp_path)
        data = json.loads(path.read_text())
        expected_keys = {
            "run_id",
            "created_at",
            "config",
            "metrics",
            "equity_curve",
            "allocations",
            "trades",
            "summary",
        }
        assert expected_keys.issubset(data.keys())

    def test_monte_carlo_info_recorded(self, tmp_path: Path) -> None:
        config = self._make_config()
        strategy = CycleExploitStrategy(CycleExploitParams())
        run_result, _ = _run_full_pipeline(config, strategy, tmp_path)
        assert run_result.monte_carlo.iterations == 3
