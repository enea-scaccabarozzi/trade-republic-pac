"""Scaffold a new backtest strategy module and test file.

Usage:
    python scripts/scaffold_strategy.py <strategy_name>

Example:
    python scripts/scaffold_strategy.py momentum_shift
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_SRC_ROOT = Path("src/pac")
_STRATEGIES_DIR = _SRC_ROOT / "backtester" / "strategies" / "builtin"
_TESTS_DIR = _SRC_ROOT / "backtester" / "strategies" / "tests"


def _to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase: momentum_shift -> MomentumShift."""
    return "".join(part.title() for part in snake.split("_"))


def scaffold_strategy(name: str, output_dir: Path | None = None) -> list[Path]:
    """Generate strategy module and test file.

    Args:
        name: Strategy name in snake_case.
        output_dir: Base directory for output files. Defaults to repo root.

    Returns:
        List of created file paths.

    Raises:
        SystemExit: On validation errors.
    """
    if not _NAME_PATTERN.match(name):
        print(
            f"Error: '{name}' is not a valid strategy name. "
            "Use snake_case (e.g. momentum_shift)."
        )
        sys.exit(1)

    base = output_dir or Path(".")
    strategies_dir = base / _STRATEGIES_DIR
    tests_dir = base / _TESTS_DIR

    strategy_file = strategies_dir / f"{name}.py"
    test_file = tests_dir / f"test_{name}.py"

    # Check file existence
    for path in [strategy_file, test_file]:
        if path.exists():
            print(f"Error: {path} already exists. Aborting.")
            sys.exit(1)

    # Runtime name collision check via discover_strategies()
    from pac.backtester.strategies.discovery import discover_strategies

    existing_strategies = discover_strategies()
    if name in existing_strategies:
        print(
            f"Error: A strategy with name '{name}' already exists "
            f"({existing_strategies[name].__module__}). Aborting."
        )
        sys.exit(1)

    cls = _to_class_name(name)

    # Ensure directories exist
    for d in [strategies_dir, tests_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Generate strategy module
    strategy_content = f'''\
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class {cls}Params(BaseModel):
    """Parameters for the {name} strategy. Add your fields here."""


class {cls}Strategy(BacktestStrategy[{cls}Params]):
    """TODO: Describe what this strategy does."""

    name = "{name}"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        actions: list[Action] = []
        # TODO: Implement signal translation logic
        return actions

    # def on_pac_date(
    #     self,
    #     snapshot: PortfolioSnapshot,
    #     report: DeviationReport,
    #     current_date: date,
    #     current_pac_volumes: dict[str, Decimal],
    # ) -> PacAdjustment | None:
    #     return None  # override to dynamically adjust PAC volumes on execution dates
'''
    strategy_file.write_text(strategy_content, encoding="utf-8")

    # Generate test file
    test_content = f"""\
from __future__ import annotations

from pac.backtester.strategies.builtin.{name} import {cls}Params, {cls}Strategy


class TestInit:
    def test_strategy_name(self) -> None:
        assert {cls}Strategy.name == "{name}"

    def test_params_model_extracted(self) -> None:
        assert {cls}Strategy.params_model is {cls}Params
"""
    test_file.write_text(test_content, encoding="utf-8")

    created = [strategy_file, test_file]
    for p in created:
        print(f"  Created: {p}")

    print()
    print(
        "Discovery is automatic — "
        "discover_strategies() scans .py files directly."
    )
    return created


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/scaffold_strategy.py <strategy_name>")
        sys.exit(1)
    scaffold_strategy(sys.argv[1])
