"""Unit tests for the backtester CLI (typer commands)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

# get_command() converts typer.Typer → click.BaseCommand, satisfying
# click.testing.CliRunner.invoke's type signature
from typer.main import get_command

from pac.backtester.cli import app
from pac.backtester.config import BacktestConfig
from pac.backtester.results.models import (
    ConfidenceInterval,
    MetricValue,
    MonteCarloInfo,
    RunResult,
    SummaryStats,
)

_cli = get_command(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _make_mock_config() -> BacktestConfig:
    return BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2020, 1, 1),
        end_date=date(2021, 12, 31),
        metrics=["sortino", "cagr"],
        benchmark=False,
    )


def _make_mock_result() -> RunResult:
    config = _make_mock_config()
    return RunResult(
        run_id="2020-01-01T00-00-00Z_pac_alignment",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        config=config,
        monte_carlo=MonteCarloInfo(iterations=100, slippage_range=(0, 3)),
        metrics={
            "strategy": {
                "sortino": MetricValue(p5=0.5, median=1.0, p95=1.5),
                "cagr": MetricValue(p5=0.05, median=0.08, p95=0.12),
            }
        },
        equity_curve=[],
        allocations=[],
        trades=[],
        summary=SummaryStats(
            total_invested=10000.0,
            final_value=ConfidenceInterval(
                p5=9000.0, median=11000.0, p95=12000.0
            ),
            total_fees=ConfidenceInterval(p5=0.0, median=5.0, p95=10.0),
            total_trades=ConfidenceInterval(p5=0.0, median=3.0, p95=6.0),
            total_pac_executions=24,
        ),
    )


@pytest.fixture
def mock_run_result(tmp_path: Path) -> tuple[RunResult, Path]:
    return _make_mock_result(), tmp_path / "result.json"


@pytest.fixture
def mock_run_backtest(
    mock_run_result: tuple[RunResult, Path],
) -> Generator[MagicMock, None, None]:
    result, path = mock_run_result
    with patch(
        "pac.backtester.cli._run_backtest", return_value=(result, path)
    ) as m:
        yield m


class _FakeParams(BaseModel):
    pass


class _FakeStrategy:
    name = "pac_alignment"
    params_model = _FakeParams
    __doc__ = "Fake strategy for testing purposes."


@pytest.fixture
def mock_discover_strategies() -> Generator[MagicMock, None, None]:
    with patch(
        "pac.backtester.cli.discover_strategies",
        return_value={"pac_alignment": _FakeStrategy},
    ) as m:
        yield m


@pytest.fixture
def mock_discover_strategies_empty() -> Generator[MagicMock, None, None]:
    with patch(
        "pac.backtester.cli.discover_strategies", return_value={}
    ) as m:
        yield m


@pytest.fixture
def mock_load_config() -> Generator[MagicMock, None, None]:
    mock_settings = MagicMock()
    mock_settings.assets = []  # empty → no ticker validation, no data fetching
    with patch(
        "pac.backtester.cli.load_config", return_value=mock_settings
    ) as m:
        yield m


@pytest.fixture
def mock_store_with_runs() -> Generator[MagicMock, None, None]:
    mock_result = _make_mock_result()
    mock_store = MagicMock()
    mock_store.list_runs.return_value = [mock_result.run_id]
    mock_store.load.return_value = mock_result
    with patch("pac.backtester.cli.ResultStore", return_value=mock_store):
        yield mock_store


@pytest.fixture
def mock_store_empty() -> Generator[MagicMock, None, None]:
    mock_store = MagicMock()
    mock_store.list_runs.return_value = []
    mock_store.load.side_effect = FileNotFoundError("not found")
    with patch("pac.backtester.cli.ResultStore", return_value=mock_store):
        yield mock_store


@pytest.fixture
def mock_store_with_run() -> Generator[MagicMock, None, None]:
    mock_result = _make_mock_result()
    mock_store = MagicMock()
    mock_store.load.return_value = mock_result
    with patch("pac.backtester.cli.ResultStore", return_value=mock_store):
        yield mock_store


# ── run command tests ─────────────────────────────────────────────────────────


def test_run_command_valid_args_exits_zero(
    runner: CliRunner,
    mock_run_backtest: MagicMock,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "pac_alignment",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
        ],
    )
    assert result.exit_code == 0
    mock_run_backtest.assert_called_once()


def test_run_command_unknown_strategy_exits_one(
    runner: CliRunner,
    mock_discover_strategies_empty: MagicMock,
    mock_load_config: MagicMock,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "nonexistent_strategy",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
        ],
    )
    assert result.exit_code == 1


def test_run_command_invalid_slippage_format_exits_one(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "pac_alignment",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
            "--slippage-days",
            "bad_format",
        ],
    )
    assert result.exit_code != 0


def test_run_command_missing_config_file_exits_one(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "pac_alignment",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
            "--config",
            "/nonexistent/path/pac.yaml",
        ],
    )
    assert result.exit_code == 1


def test_run_command_strategy_params_invalid_json_exits_one(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "pac_alignment",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
            "--strategy-params",
            "not-valid-json{",
        ],
    )
    assert result.exit_code != 0


def test_run_command_defaults_applied(
    runner: CliRunner,
    mock_run_backtest: MagicMock,
) -> None:
    result = runner.invoke(
        _cli,
        [
            "run",
            "--strategy",
            "pac_alignment",
            "--start",
            "2020-01-01",
            "--end",
            "2021-12-31",
        ],
    )
    assert result.exit_code == 0
    call_args: Any = mock_run_backtest.call_args
    bt_config: BacktestConfig = call_args[0][0]
    assert bt_config.monte_carlo_iterations == 100
    assert bt_config.initial_cash == Decimal("10000")
    assert bt_config.benchmark is True
    assert bt_config.slippage_days == (0, 3)


# ── strategies command tests ──────────────────────────────────────────────────


def test_strategies_command_shows_table(
    runner: CliRunner,
    mock_discover_strategies: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["strategies"])
    assert result.exit_code == 0
    assert "pac_alignment" in result.output


def test_strategies_command_empty_shows_message(
    runner: CliRunner,
    mock_discover_strategies_empty: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["strategies"])
    assert result.exit_code == 0
    assert "No strategies" in result.output


# ── results command tests ─────────────────────────────────────────────────────


def test_results_command_shows_table(
    runner: CliRunner,
    mock_store_with_runs: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["results"])
    assert result.exit_code == 0
    assert "pac_alignment" in result.output


def test_results_command_no_runs_shows_message(
    runner: CliRunner,
    mock_store_empty: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["results"])
    assert result.exit_code == 0
    assert "No saved backtest runs" in result.output


# ── show command tests ────────────────────────────────────────────────────────


def test_show_command_valid_run_id_displays_result(
    runner: CliRunner,
    mock_store_with_run: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["show", "2020-01-01T00-00-00Z_pac_alignment"])
    assert result.exit_code == 0
    assert "Backtest Results" in result.output


def test_show_command_unknown_run_id_exits_one(
    runner: CliRunner,
    mock_store_empty: MagicMock,
) -> None:
    result = runner.invoke(_cli, ["show", "nonexistent_run_id"])
    assert result.exit_code == 1


def test_show_command_invalid_run_id_chars_exits_one(
    runner: CliRunner,
) -> None:
    store_mock = MagicMock()
    store_mock.load.side_effect = ValueError("Invalid run_id")
    with patch("pac.backtester.cli.ResultStore", return_value=store_mock):
        result = runner.invoke(_cli, ["show", "../../etc/passwd"])
    assert result.exit_code == 1


# ── interactive mode test ─────────────────────────────────────────────────────


def test_interactive_mode_without_questionary_exits_one(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pac.backtester.cli.questionary", None)
    result = runner.invoke(_cli, [])
    assert result.exit_code == 1
    assert "questionary" in result.output
