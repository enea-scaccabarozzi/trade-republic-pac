"""Unit tests for the framework-agnostic backtest pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pydantic
import pytest
import yaml

from pac.backtester.config import BacktestConfig
from pac.backtester.runner import PipelineError, run_pipeline
from pac.config import Settings

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_settings() -> Settings:
    """Build a Settings instance with tickers for all assets."""
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
            "signals": [],
        }
    )


def _make_settings_no_tickers() -> Settings:
    """Build a Settings instance where assets have no ticker field."""
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
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "target_pct": 15,
                },
            ],
            "app": {"job_secret": "test-job-secret"},
            "channels": {},
            "signals": [],
        }
    )


def _make_config(iterations: int = 3) -> BacktestConfig:
    return BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        monte_carlo_iterations=iterations,
    )


def _make_mock_strategy_cls() -> MagicMock:
    """Create a mock strategy class with a params_model."""
    strategy_cls = MagicMock()
    strategy_cls.params_model = MagicMock()
    strategy_cls.params_model.model_validate = MagicMock(
        return_value=MagicMock(),
    )
    strategy_cls.return_value = MagicMock()  # strategy instance
    return strategy_cls


# ── Patch target prefix ──────────────────────────────────────────────────────

_MOD = "pac.backtester.runner"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRunPipelineHappyPath:
    """Verify the full pipeline returns (RunResult, Path) and calls progress."""

    @patch(f"{_MOD}.ResultStore")
    @patch(f"{_MOD}.build_run_result")
    @patch(f"{_MOD}.compute_report")
    @patch(f"{_MOD}.SimulationResult")
    @patch(f"{_MOD}.BacktestSimulator")
    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_run_pipeline_happy_path(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
        mock_sim_cls: MagicMock,
        mock_sim_result_cls: MagicMock,
        mock_report: MagicMock,
        mock_build: MagicMock,
        mock_store_cls: MagicMock,
    ) -> None:
        config = _make_config(iterations=3)
        config_path = Path("pac.yaml")
        settings = _make_settings()
        mock_load.return_value = settings

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}

        strategy_cls = _make_mock_strategy_cls()
        mock_disc_strats.return_value = {"pac_alignment": strategy_cls}

        mock_iteration = MagicMock()
        mock_sim = MagicMock()
        mock_sim.run_iteration.return_value = mock_iteration
        mock_sim_cls.return_value = mock_sim

        expected_report = MagicMock()
        mock_report.return_value = expected_report

        expected_result = MagicMock()
        mock_build.return_value = expected_result

        expected_path = Path(".pac/backtests/run.json")
        mock_store = MagicMock()
        mock_store.save.return_value = expected_path
        mock_store_cls.return_value = mock_store

        progress_calls: list[tuple[int, int]] = []

        def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        result, path = run_pipeline(
            config,
            config_path,
            seed=42,
            on_progress=on_progress,
        )

        assert result is expected_result
        assert path is expected_path
        assert progress_calls == [(1, 3), (2, 3), (3, 3)]
        assert mock_sim.run_iteration.call_count == 3
        mock_store.save.assert_called_once_with(expected_result)

    @patch(f"{_MOD}.ResultStore")
    @patch(f"{_MOD}.build_run_result")
    @patch(f"{_MOD}.compute_report")
    @patch(f"{_MOD}.SimulationResult")
    @patch(f"{_MOD}.BacktestSimulator")
    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_run_pipeline_no_progress_callback(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
        mock_sim_cls: MagicMock,
        mock_sim_result_cls: MagicMock,
        mock_report: MagicMock,
        mock_build: MagicMock,
        mock_store_cls: MagicMock,
    ) -> None:
        config = _make_config(iterations=2)
        settings = _make_settings()
        mock_load.return_value = settings

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}

        strategy_cls = _make_mock_strategy_cls()
        mock_disc_strats.return_value = {"pac_alignment": strategy_cls}

        mock_sim = MagicMock()
        mock_sim.run_iteration.return_value = MagicMock()
        mock_sim_cls.return_value = mock_sim

        mock_report.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        mock_store = MagicMock()
        mock_store.save.return_value = Path("out.json")
        mock_store_cls.return_value = mock_store

        # Should not raise when on_progress is None
        result, _path = run_pipeline(
            config,
            Path("pac.yaml"),
            on_progress=None,
        )

        assert result is not None
        assert mock_sim.run_iteration.call_count == 2


class TestRunPipelineConfigErrors:
    """Verify PipelineError(step='config') on config load failures."""

    @patch(f"{_MOD}.load_config")
    def test_config_not_found(self, mock_load: MagicMock) -> None:
        mock_load.side_effect = FileNotFoundError("pac.yaml not found")
        config = _make_config()

        with pytest.raises(PipelineError, match="config") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "config"
        assert "not found" in exc_info.value.detail

    @patch(f"{_MOD}.load_config")
    def test_config_yaml_error(self, mock_load: MagicMock) -> None:
        mock_load.side_effect = yaml.YAMLError("bad yaml")
        config = _make_config()

        with pytest.raises(PipelineError, match="config") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "config"
        assert "YAML" in exc_info.value.detail

    @patch(f"{_MOD}.load_config")
    def test_config_validation_error(self, mock_load: MagicMock) -> None:
        mock_load.side_effect = ValueError("missing required field")
        config = _make_config()

        with pytest.raises(PipelineError, match="config") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "config"
        assert "invalid" in exc_info.value.detail.lower()


class TestRunPipelineTickerErrors:
    """Verify PipelineError(step='tickers') on missing ticker fields."""

    @patch(f"{_MOD}.load_config")
    def test_missing_tickers(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_settings_no_tickers()
        config = _make_config()

        with pytest.raises(PipelineError, match="tickers") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "tickers"
        assert "stocks" in exc_info.value.detail


class TestRunPipelineStrategyErrors:
    """Verify PipelineError(step='strategy') on strategy failures."""

    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_unknown_strategy(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}
        mock_disc_strats.return_value = {"other_strategy": MagicMock()}

        config = _make_config()  # strategy="pac_alignment"

        with pytest.raises(PipelineError, match="strategy") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "strategy"
        assert "pac_alignment" in exc_info.value.detail

    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_invalid_strategy_params(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}

        strategy_cls = MagicMock()
        strategy_cls.params_model = MagicMock()
        strategy_cls.params_model.model_validate = MagicMock(
            side_effect=pydantic.ValidationError.from_exception_data(
                title="Params",
                line_errors=[
                    {
                        "type": "missing",
                        "loc": ("blend_factor",),
                        "input": {},
                    },
                ],
            ),
        )
        mock_disc_strats.return_value = {"pac_alignment": strategy_cls}

        config = _make_config()

        with pytest.raises(PipelineError, match="strategy") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "strategy"
        assert "Invalid strategy params" in exc_info.value.detail


class TestRunPipelineMarketDataErrors:
    """Verify PipelineError(step='market_data') on fetch failures."""

    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_market_data_failure(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()

        mock_provider = MagicMock()
        mock_provider.fetch_with_proxy.side_effect = RuntimeError("network error")
        mock_provider_cls.return_value = mock_provider

        config = _make_config()

        with pytest.raises(PipelineError, match="market_data") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "market_data"
        assert "network" in exc_info.value.detail.lower()

    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_market_data_import_error(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()
        mock_provider_cls.side_effect = ImportError("yfinance not installed")

        config = _make_config()

        with pytest.raises(PipelineError, match="market_data") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "market_data"


class TestRunPipelineMetricsErrors:
    """Verify PipelineError(step='metrics') on report computation failure."""

    @patch(f"{_MOD}.compute_report")
    @patch(f"{_MOD}.SimulationResult")
    @patch(f"{_MOD}.BacktestSimulator")
    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_metrics_failure(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
        mock_sim_cls: MagicMock,
        mock_sim_result_cls: MagicMock,
        mock_report: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}

        strategy_cls = _make_mock_strategy_cls()
        mock_disc_strats.return_value = {"pac_alignment": strategy_cls}

        mock_sim = MagicMock()
        mock_sim.run_iteration.return_value = MagicMock()
        mock_sim_cls.return_value = mock_sim

        mock_report.side_effect = RuntimeError("quantstats crash")

        config = _make_config(iterations=1)

        with pytest.raises(PipelineError, match="metrics") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "metrics"
        assert "quantstats" in exc_info.value.detail.lower()


class TestRunPipelineAggregationErrors:
    """Verify PipelineError(step='aggregation') on empty iterations."""

    @patch(f"{_MOD}.build_run_result")
    @patch(f"{_MOD}.compute_report")
    @patch(f"{_MOD}.SimulationResult")
    @patch(f"{_MOD}.BacktestSimulator")
    @patch(f"{_MOD}.discover_strategies")
    @patch(f"{_MOD}.discover_rules")
    @patch(f"{_MOD}.MarketDataProvider")
    @patch(f"{_MOD}.load_config")
    def test_empty_iterations(
        self,
        mock_load: MagicMock,
        mock_provider_cls: MagicMock,
        mock_disc_rules: MagicMock,
        mock_disc_strats: MagicMock,
        mock_sim_cls: MagicMock,
        mock_sim_result_cls: MagicMock,
        mock_report: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_load.return_value = _make_settings()

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = MagicMock()
        mock_provider_cls.return_value = mock_provider

        mock_disc_rules.return_value = {}

        strategy_cls = _make_mock_strategy_cls()
        mock_disc_strats.return_value = {"pac_alignment": strategy_cls}

        mock_sim = MagicMock()
        mock_sim.run_iteration.return_value = MagicMock()
        mock_sim_cls.return_value = mock_sim

        mock_report.return_value = MagicMock()
        mock_build.side_effect = ValueError(
            "Cannot build RunResult from empty iterations list",
        )

        config = _make_config(iterations=1)

        with pytest.raises(PipelineError, match="aggregation") as exc_info:
            run_pipeline(config, Path("pac.yaml"))

        assert exc_info.value.step == "aggregation"
        assert "empty" in exc_info.value.detail.lower()
