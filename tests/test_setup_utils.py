"""Tests for scripts/setup_utils.py shared utilities."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.setup_utils import CACHE_VERSION, CacheManager


class TestCacheManagerRoundTrip:
    def test_save_and_load_round_trips(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        cm.save({"phone": "+49123", "validated": True})

        loaded = cm.load()
        assert loaded is not None
        assert loaded["phone"] == "+49123"
        assert loaded["validated"] is True

    def test_save_adds_metadata(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        cm.save({"key": "value"})

        loaded = cm.load()
        assert loaded is not None
        assert loaded["_version"] == CACHE_VERSION
        assert "_created_at" in loaded

    def test_load_returns_none_when_no_cache(self, tmp_path: Path) -> None:
        cm = CacheManager("missing", cache_dir=tmp_path)
        assert cm.load() is None

    def test_exists_reflects_file_state(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        assert not cm.exists()
        cm.save({"x": 1})
        assert cm.exists()


class TestCacheManagerOverride:
    def test_check_cache_override_true_ignores_cache(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        cm.save({"key": "value"})

        assert cm.check_cache(override=True) is None

    def test_check_cache_override_false_returns_data(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        cm.save({"key": "value"})

        result = cm.check_cache(override=False)
        assert result is not None
        assert result["key"] == "value"

    def test_check_cache_no_cache_returns_none(self, tmp_path: Path) -> None:
        cm = CacheManager("empty", cache_dir=tmp_path)
        assert cm.check_cache(override=False) is None
        assert cm.check_cache(override=True) is None


class TestCacheManagerEdgeCases:
    def test_save_creates_nested_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "sub" / "dir"
        cm = CacheManager("test", cache_dir=nested)
        path = cm.save({"k": "v"})
        assert path.exists()

    def test_save_handles_datetime_values(self, tmp_path: Path) -> None:
        cm = CacheManager("test", cache_dir=tmp_path)
        cm.save({"ts": datetime.now(UTC)})

        loaded = cm.load()
        assert loaded is not None
        assert isinstance(loaded["ts"], str)  # serialized via default=str


class TestUIHelpers:
    def test_print_disclaimer_does_not_raise(self) -> None:
        from scripts.setup_utils import print_disclaimer

        print_disclaimer("Test", "This is a test disclaimer.")

    def test_print_success_does_not_raise(self) -> None:
        from scripts.setup_utils import print_success

        print_success("Done", "Everything worked.")

    def test_confirm_or_exit_exits_on_decline(self) -> None:
        from scripts.setup_utils import confirm_or_exit

        with (
            patch("rich.prompt.Confirm.ask", return_value=False),
            pytest.raises(SystemExit),
        ):
            confirm_or_exit("Continue?")

    def test_fatal_error_always_exits(self) -> None:
        from scripts.setup_utils import fatal_error

        with pytest.raises(SystemExit):
            fatal_error("Fail", "Something went wrong.")


class TestStubScriptHelp:
    @pytest.mark.parametrize(
        "script",
        [
            "scripts/setup_tr.py",
            "scripts/setup_gcp.py",
            "scripts/setup_telegram.py",
        ],
    )
    def test_help_exits_zero(self, script: str) -> None:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


# === update_env_file ===


class TestUpdateEnvFile:
    def test_creates_env_file_if_missing(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        result = update_env_file(
            {"TR_PHONE_NUMBER": "+49123", "TR_PIN": "1234"},
            env_path=env_path,
        )
        assert result == env_path
        content = env_path.read_text()
        assert "TR_PHONE_NUMBER=+49123" in content
        assert "TR_PIN=1234" in content

    def test_updates_existing_keys_in_place(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        env_path.write_text("TR_PHONE_NUMBER=old\nTR_PIN=0000\n")

        update_env_file({"TR_PHONE_NUMBER": "+49999"}, env_path=env_path)

        lines = env_path.read_text().splitlines()
        assert "TR_PHONE_NUMBER=+49999" in lines
        assert "TR_PIN=0000" in lines

    def test_preserves_comments_and_blank_lines(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        env_path.write_text("# This is a comment\n\nTR_PIN=1234\n")

        update_env_file({"TR_PIN": "5678"}, env_path=env_path)

        lines = env_path.read_text().splitlines()
        assert lines[0] == "# This is a comment"
        assert lines[1] == ""
        assert lines[2] == "TR_PIN=5678"

    def test_appends_new_keys_at_end(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        env_path.write_text("A=1\n")

        update_env_file({"B": "2"}, env_path=env_path)

        lines = env_path.read_text().splitlines()
        assert lines[0] == "A=1"
        assert lines[1] == "B=2"

    def test_preserves_unrelated_keys(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        env_path.write_text("OTHER=val\n")

        update_env_file({"TR_PIN": "1234"}, env_path=env_path)

        content = env_path.read_text()
        assert "OTHER=val" in content
        assert "TR_PIN=1234" in content

    def test_sets_restrictive_permissions_on_new_file(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        update_env_file({"KEY": "val"}, env_path=env_path)

        assert oct(env_path.stat().st_mode & 0o777) == oct(0o600)

    def test_sets_restrictive_permissions_on_existing_file(
        self, tmp_path: Path
    ) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        env_path.write_text("KEY=old\n")
        env_path.chmod(0o644)

        update_env_file({"KEY": "new"}, env_path=env_path)

        assert oct(env_path.stat().st_mode & 0o777) == oct(0o600)

    def test_handles_empty_values(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        update_env_file({"PAC_JOB_SECRET": ""}, env_path=env_path)

        content = env_path.read_text()
        assert "PAC_JOB_SECRET=" in content

    def test_returns_env_path(self, tmp_path: Path) -> None:
        from scripts.setup_utils import update_env_file

        env_path = tmp_path / ".env"
        result = update_env_file({"X": "1"}, env_path=env_path)
        assert result == env_path


# === _read_env_value ===


class TestReadEnvValue:
    def test_reads_existing_key(self, tmp_path: Path) -> None:
        from scripts.setup_utils import _read_env_value

        env_path = tmp_path / ".env"
        env_path.write_text("KEY=val\n")

        assert _read_env_value("KEY", env_path=env_path) == "val"

    def test_returns_empty_for_missing_key(self, tmp_path: Path) -> None:
        from scripts.setup_utils import _read_env_value

        env_path = tmp_path / ".env"
        env_path.write_text("OTHER=val\n")

        assert _read_env_value("KEY", env_path=env_path) == ""

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        from scripts.setup_utils import _read_env_value

        env_path = tmp_path / ".env"
        assert _read_env_value("KEY", env_path=env_path) == ""

    def test_ignores_commented_keys(self, tmp_path: Path) -> None:
        from scripts.setup_utils import _read_env_value

        env_path = tmp_path / ".env"
        env_path.write_text("# KEY=val\n")

        assert _read_env_value("KEY", env_path=env_path) == ""


# === collect_env_from_caches ===


class TestCollectEnvFromCaches:
    def _write_cache(self, cache_dir: Path, name: str, data: dict[str, object]) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{name}.json").write_text(json.dumps(data))

    def test_collects_from_tr_cache(self, tmp_path: Path) -> None:
        from scripts.setup_utils import collect_env_from_caches

        self._write_cache(tmp_path, "tr", {"phone_number": "+49123", "pin": "****"})

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=False)
        assert result["TR_PHONE_NUMBER"] == "+49123"

    def test_collects_from_telegram_cache(self, tmp_path: Path) -> None:
        from scripts.setup_utils import collect_env_from_caches

        self._write_cache(
            tmp_path,
            "telegram",
            {
                "bot_token": "123:ABC",
                "chat_id": "999",
                "webhook_url": "https://x.com/webhook",
                "webhook_secret": "sec123",
            },
        )

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=False)
        assert result["TELEGRAM_BOT_TOKEN"] == "123:ABC"
        assert result["TELEGRAM_CHAT_ID"] == "999"
        assert result["TELEGRAM_WEBHOOK_URL"] == "https://x.com/webhook"
        assert result["TELEGRAM_WEBHOOK_SECRET"] == "sec123"

    def test_skips_missing_caches(self, tmp_path: Path) -> None:
        from scripts.setup_utils import collect_env_from_caches

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=True)
        # Only PAC_JOB_SECRET should be present (auto-generated)
        assert "PAC_JOB_SECRET" in result
        assert "TR_PHONE_NUMBER" not in result
        assert "TELEGRAM_BOT_TOKEN" not in result

    def test_generates_job_secret_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts.setup_utils import collect_env_from_caches

        monkeypatch.delenv("PAC_JOB_SECRET", raising=False)

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=True)
        secret = result["PAC_JOB_SECRET"]
        assert len(secret) > 0

    def test_preserves_existing_job_secret_from_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts.setup_utils import collect_env_from_caches

        monkeypatch.setenv("PAC_JOB_SECRET", "my-existing-secret")

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=True)
        assert result["PAC_JOB_SECRET"] == "my-existing-secret"

    def test_preserves_existing_job_secret_from_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts.setup_utils import collect_env_from_caches

        monkeypatch.delenv("PAC_JOB_SECRET", raising=False)
        # Write a .env file in the cwd that collect_env_from_caches will read
        env_path = Path(".env")
        original = env_path.read_text() if env_path.exists() else None
        try:
            env_path.write_text("PAC_JOB_SECRET=from-dot-env\n")
            result = collect_env_from_caches(
                cache_dir=tmp_path, include_job_secret=True
            )
            assert result["PAC_JOB_SECRET"] == "from-dot-env"
        finally:
            if original is not None:
                env_path.write_text(original)
            elif env_path.exists():
                env_path.unlink()

    def test_skips_job_secret_when_disabled(self, tmp_path: Path) -> None:
        from scripts.setup_utils import collect_env_from_caches

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=False)
        assert "PAC_JOB_SECRET" not in result

    def test_skips_empty_cache_values(self, tmp_path: Path) -> None:
        from scripts.setup_utils import collect_env_from_caches

        self._write_cache(
            tmp_path,
            "telegram",
            {
                "bot_token": "",
                "chat_id": "999",
                "webhook_url": "",
                "webhook_secret": "",
            },
        )

        result = collect_env_from_caches(cache_dir=tmp_path, include_job_secret=False)
        assert "TELEGRAM_BOT_TOKEN" not in result
        assert result["TELEGRAM_CHAT_ID"] == "999"
        assert "TELEGRAM_WEBHOOK_URL" not in result
