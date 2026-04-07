from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest


class TestScaffoldStrategyCreatesFiles:
    def test_creates_strategy_and_test(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        created = scaffold_strategy("my_test_strategy", output_dir=tmp_path)

        assert len(created) == 2
        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/my_test_strategy.py"
        )
        test_file = (
            tmp_path
            / "src/pac/backtester/strategies/tests/test_my_test_strategy.py"
        )

        assert strategy_file.exists()
        assert test_file.exists()


class TestScaffoldStrategyStructure:
    def test_generated_strategy_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        scaffold_strategy("sample_strategy", output_dir=tmp_path)

        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/sample_strategy.py"
        )
        ast.parse(strategy_file.read_text(encoding="utf-8"))

    def test_generated_strategy_has_required_class_names(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        scaffold_strategy("sample_strategy", output_dir=tmp_path)

        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/sample_strategy.py"
        )
        tree = ast.parse(strategy_file.read_text(encoding="utf-8"))

        class_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        assert "SampleStrategyParams" in class_names
        assert "SampleStrategyStrategy" in class_names

    def test_generated_strategy_has_on_signals_method(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        scaffold_strategy("check_strategy", output_dir=tmp_path)

        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/check_strategy.py"
        )
        tree = ast.parse(strategy_file.read_text(encoding="utf-8"))

        strategy_class = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and node.name == "CheckStrategyStrategy"
        )
        method_names = [
            node.name
            for node in ast.walk(strategy_class)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "on_signals" in method_names

    def test_generated_strategy_has_correct_name_attribute(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        scaffold_strategy("my_cool_strategy", output_dir=tmp_path)

        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/my_cool_strategy.py"
        )
        content = strategy_file.read_text(encoding="utf-8")
        assert 'name = "my_cool_strategy"' in content

    def test_generated_test_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        scaffold_strategy("valid_strategy", output_dir=tmp_path)

        test_file = (
            tmp_path
            / "src/pac/backtester/strategies/tests/test_valid_strategy.py"
        )
        ast.parse(test_file.read_text(encoding="utf-8"))


class TestScaffoldStrategyValidation:
    def test_rejects_invalid_name_hyphenated(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        with pytest.raises(SystemExit):
            scaffold_strategy("My-Strategy", output_dir=tmp_path)

    def test_rejects_invalid_name_starts_with_number(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        with pytest.raises(SystemExit):
            scaffold_strategy("123strategy", output_dir=tmp_path)

    def test_rejects_invalid_name_uppercase(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        with pytest.raises(SystemExit):
            scaffold_strategy("MyStrategy", output_dir=tmp_path)

    def test_rejects_existing_file(self, tmp_path: Path) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        # Create the target file first
        strategy_file = (
            tmp_path
            / "src/pac/backtester/strategies/builtin/existing.py"
        )
        strategy_file.parent.mkdir(parents=True, exist_ok=True)
        strategy_file.write_text("# existing", encoding="utf-8")

        with pytest.raises(SystemExit):
            scaffold_strategy("existing", output_dir=tmp_path)

    def test_rejects_name_collision_with_discovered_strategy(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_strategy import scaffold_strategy

        mock_strategies = {"colliding_name": type("FakeStrategy", (), {})}
        with (
            patch(
                "pac.backtester.strategies.discovery.discover_strategies",
                return_value=mock_strategies,
            ),
            pytest.raises(SystemExit),
        ):
            scaffold_strategy("colliding_name", output_dir=tmp_path)
