from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest


class TestScaffoldRuleCreatesFiles:
    def test_creates_rule_template_and_test(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        created = scaffold_rule("my_test_rule", output_dir=tmp_path)

        assert len(created) == 3
        rule_file = tmp_path / "src/pac/rules/builtin/my_test_rule.py"
        template_file = tmp_path / "src/pac/templates/builtin/my_test_rule.j2"
        test_file = tmp_path / "src/pac/rules/tests/test_my_test_rule.py"

        assert rule_file.exists()
        assert template_file.exists()
        assert test_file.exists()


class TestScaffoldRuleStructure:
    def test_generated_rule_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        scaffold_rule("sample_rule", output_dir=tmp_path)

        rule_file = tmp_path / "src/pac/rules/builtin/sample_rule.py"
        tree = ast.parse(rule_file.read_text(encoding="utf-8"))

        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "SampleRuleParams" in class_names
        assert "SampleRuleRule" in class_names

    def test_generated_rule_has_required_methods(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        scaffold_rule("check_rule", output_dir=tmp_path)

        rule_file = tmp_path / "src/pac/rules/builtin/check_rule.py"
        tree = ast.parse(rule_file.read_text(encoding="utf-8"))

        rule_class = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "CheckRuleRule"
        )
        method_names = [
            node.name
            for node in ast.walk(rule_class)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "name" in method_names
        assert "evaluate" in method_names
        assert "build_template_data" in method_names

    def test_generated_rule_has_correct_name_property(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        scaffold_rule("my_cool_rule", output_dir=tmp_path)

        rule_file = tmp_path / "src/pac/rules/builtin/my_cool_rule.py"
        content = rule_file.read_text(encoding="utf-8")
        assert 'return "my_cool_rule"' in content

    def test_generated_test_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        scaffold_rule("valid_rule", output_dir=tmp_path)

        test_file = tmp_path / "src/pac/rules/tests/test_valid_rule.py"
        ast.parse(test_file.read_text(encoding="utf-8"))

    def test_generated_template_exists_and_nonempty(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        scaffold_rule("tmpl_rule", output_dir=tmp_path)

        template_file = tmp_path / "src/pac/templates/builtin/tmpl_rule.j2"
        content = template_file.read_text(encoding="utf-8")
        assert "signal" in content
        assert "bold" in content


class TestScaffoldRuleValidation:
    def test_rejects_invalid_name_hyphenated(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        with pytest.raises(SystemExit):
            scaffold_rule("My-Rule", output_dir=tmp_path)

    def test_rejects_invalid_name_starts_with_number(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        with pytest.raises(SystemExit):
            scaffold_rule("123rule", output_dir=tmp_path)

    def test_rejects_invalid_name_uppercase(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        with pytest.raises(SystemExit):
            scaffold_rule("MyRule", output_dir=tmp_path)

    def test_rejects_existing_file(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        # Create the target file first
        rule_file = tmp_path / "src/pac/rules/builtin/existing.py"
        rule_file.parent.mkdir(parents=True, exist_ok=True)
        rule_file.write_text("# existing", encoding="utf-8")

        with pytest.raises(SystemExit):
            scaffold_rule("existing", output_dir=tmp_path)

    def test_rejects_name_collision_with_discovered_rule(self, tmp_path: Path) -> None:
        from scripts.scaffold_rule import scaffold_rule

        # Mock discover_rules to return a known collision
        mock_rules = {"colliding_name": type("FakeRule", (), {})}
        with (
            patch(
                "pac.rules.discovery.discover_rules",
                return_value=mock_rules,
            ),
            pytest.raises(SystemExit),
        ):
            scaffold_rule("colliding_name", output_dir=tmp_path)
