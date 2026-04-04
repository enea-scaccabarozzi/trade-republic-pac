"""Scaffold a new signal rule module, template, and test file.

Usage:
    python scripts/scaffold_rule.py <rule_name>

Example:
    python scripts/scaffold_rule.py rsi_divergence
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_SRC_ROOT = Path("src/pac")
_RULES_DIR = _SRC_ROOT / "rules" / "builtin"
_TEMPLATES_DIR = _SRC_ROOT / "templates" / "builtin"
_TESTS_DIR = _SRC_ROOT / "rules" / "tests"


def _to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase: rsi_divergence -> RsiDivergence."""
    return "".join(part.title() for part in snake.split("_"))


def scaffold_rule(name: str, output_dir: Path | None = None) -> list[Path]:
    """Generate rule module, template, and test file.

    Args:
        name: Rule name in snake_case.
        output_dir: Base directory for output files. Defaults to repo root.

    Returns:
        List of created file paths.

    Raises:
        SystemExit: On validation errors.
    """
    if not _NAME_PATTERN.match(name):
        print(
            f"Error: '{name}' is not a valid rule name. "
            "Use snake_case (e.g. rsi_divergence)."
        )
        sys.exit(1)

    base = output_dir or Path(".")
    rules_dir = base / _RULES_DIR
    templates_dir = base / _TEMPLATES_DIR
    tests_dir = base / _TESTS_DIR

    rule_file = rules_dir / f"{name}.py"
    template_file = templates_dir / f"{name}.j2"
    test_file = tests_dir / f"test_{name}.py"

    # Check file existence
    for path in [rule_file, template_file, test_file]:
        if path.exists():
            print(f"Error: {path} already exists. Aborting.")
            sys.exit(1)

    # Runtime name collision check via discover_rules()
    from pac.rules.discovery import discover_rules

    existing_rules = discover_rules()
    if name in existing_rules:
        print(
            f"Error: A rule with name '{name}' already exists "
            f"({existing_rules[name].__module__}). Aborting."
        )
        sys.exit(1)

    cls = _to_class_name(name)

    # Ensure directories exist
    for d in [rules_dir, templates_dir, tests_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Generate rule module
    rule_content = f'''\
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.base import SignalRule


class {cls}Params(BaseModel):
    """Parameters for the {name} rule. Add your fields here."""


class {cls}Rule(SignalRule[{cls}Params]):
    """TODO: Describe what this rule detects."""

    @property
    def name(self) -> str:
        return "{name}"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: {cls}Params,
    ) -> list[Signal]:
        signals: list[Signal] = []
        # TODO: Implement evaluation logic
        return signals

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        return {{"signal": signals[0]}}
'''
    rule_file.write_text(rule_content, encoding="utf-8")

    # Generate Jinja2 template
    template_content = """\
{# Expected data: signal (Signal) #}
{{ emoji(signal.severity.value) }} {{ bold("Signal: " ~ escape(signal.name)) }}
Severity{{ literal(":") }} {{ code(signal.severity.value | upper) }}

{{ escape(signal.message) }}

{{ italic(escape(signal.triggered_at | datefmt)) }}
"""
    template_file.write_text(template_content, encoding="utf-8")

    # Generate test file
    test_content = f"""\
from __future__ import annotations

from pac.rules.builtin.{name} import {cls}Params, {cls}Rule


class TestInit:
    def test_rule_name(self) -> None:
        rule = {cls}Rule()
        assert rule.name == "{name}"

    def test_params_model_extracted(self) -> None:
        assert {cls}Rule.params_model is {cls}Params
"""
    test_file.write_text(test_content, encoding="utf-8")

    created = [rule_file, template_file, test_file]
    for p in created:
        print(f"  Created: {p}")

    print()
    print("Optionally add re-exports to " "src/pac/rules/builtin/__init__.py")
    print(
        "Discovery works without re-exports — "
        "discover_rules() scans .py files directly."
    )
    return created


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/scaffold_rule.py <rule_name>")
        sys.exit(1)
    scaffold_rule(sys.argv[1])
