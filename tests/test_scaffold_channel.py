from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest


class TestScaffoldChannelCreatesFiles:
    def test_creates_channel_package_and_test(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        created = scaffold_channel("my_channel", output_dir=tmp_path)

        assert len(created) == 3
        channel_file = tmp_path / "src/pac/delivery/channels/my_channel/channel.py"
        init_file = tmp_path / "src/pac/delivery/channels/my_channel/__init__.py"
        test_file = tmp_path / "src/pac/delivery/tests/test_my_channel_channel.py"

        assert channel_file.exists()
        assert init_file.exists()
        assert test_file.exists()


class TestScaffoldChannelStructure:
    def test_generated_channel_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        scaffold_channel("sample_ch", output_dir=tmp_path)

        channel_file = tmp_path / "src/pac/delivery/channels/sample_ch/channel.py"
        tree = ast.parse(channel_file.read_text(encoding="utf-8"))

        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "SampleChConfig" in class_names
        assert "SampleChChannel" in class_names

    def test_generated_channel_has_required_methods(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        scaffold_channel("check_ch", output_dir=tmp_path)

        channel_file = tmp_path / "src/pac/delivery/channels/check_ch/channel.py"
        tree = ast.parse(channel_file.read_text(encoding="utf-8"))

        channel_class = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "CheckChChannel"
        )
        method_names = [
            node.name
            for node in ast.walk(channel_class)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "send" in method_names
        assert "supported_formats" in method_names

    def test_generated_channel_has_correct_name(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        scaffold_channel("cool_ch", output_dir=tmp_path)

        channel_file = tmp_path / "src/pac/delivery/channels/cool_ch/channel.py"
        content = channel_file.read_text(encoding="utf-8")
        assert 'name = "cool_ch"' in content

    def test_generated_init_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        scaffold_channel("init_ch", output_dir=tmp_path)

        init_file = tmp_path / "src/pac/delivery/channels/init_ch/__init__.py"
        ast.parse(init_file.read_text(encoding="utf-8"))

    def test_generated_test_is_valid_python(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        scaffold_channel("test_ch", output_dir=tmp_path)

        test_file = tmp_path / "src/pac/delivery/tests/test_test_ch_channel.py"
        ast.parse(test_file.read_text(encoding="utf-8"))


class TestScaffoldChannelValidation:
    def test_rejects_invalid_name_hyphenated(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        with pytest.raises(SystemExit):
            scaffold_channel("My-Channel", output_dir=tmp_path)

    def test_rejects_invalid_name_starts_with_number(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        with pytest.raises(SystemExit):
            scaffold_channel("123channel", output_dir=tmp_path)

    def test_rejects_existing_directory(self, tmp_path: Path) -> None:
        from scripts.scaffold_channel import scaffold_channel

        # Create the target directory first
        channel_dir = tmp_path / "src/pac/delivery/channels/existing"
        channel_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(SystemExit):
            scaffold_channel("existing", output_dir=tmp_path)

    def test_rejects_name_collision_with_discovered_channel(
        self, tmp_path: Path
    ) -> None:
        from scripts.scaffold_channel import scaffold_channel

        mock_channels = {"colliding": type("FakeChannel", (), {})}
        with (
            patch(
                "pac.delivery.discovery.discover_channels",
                return_value=mock_channels,
            ),
            pytest.raises(SystemExit),
        ):
            scaffold_channel("colliding", output_dir=tmp_path)
