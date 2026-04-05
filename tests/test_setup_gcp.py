"""Tests for scripts/setup_gcp.py — GCP Cloud Run deploy."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml


def _completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Helper to create CompletedProcess for mocking."""
    return subprocess.CompletedProcess(
        args=["gcloud"],
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
    )


# === _run_gcloud ===


class TestRunGcloud:
    def setup_method(self) -> None:
        import scripts.setup_gcp as gcp

        self._orig = gcp._ACTIVE_ACCOUNT
        gcp._ACTIVE_ACCOUNT = None

    def teardown_method(self) -> None:
        import scripts.setup_gcp as gcp

        gcp._ACTIVE_ACCOUNT = self._orig

    @patch("subprocess.run", return_value=_completed(stdout="ok"))
    def test_returns_result_on_success(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _run_gcloud

        result = _run_gcloud(["projects", "list"])
        assert result.stdout == "ok"
        mock_run.assert_called_once()

    @patch(
        "subprocess.run",
        return_value=_completed(returncode=1, stderr="error msg"),
    )
    def test_exits_on_failure_when_check_true(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _run_gcloud

        with pytest.raises(SystemExit):
            _run_gcloud(["bad", "command"], check=True)

    @patch("subprocess.run", return_value=_completed(returncode=1))
    def test_returns_on_failure_when_check_false(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _run_gcloud

        result = _run_gcloud(["bad", "command"], check=False)
        assert result.returncode == 1

    @patch("subprocess.run", return_value=_completed(stdout="ok"))
    def test_prepends_gcloud_to_args(self, mock_run: MagicMock) -> None:
        import scripts.setup_gcp as gcp

        orig = gcp._ACTIVE_ACCOUNT
        gcp._ACTIVE_ACCOUNT = None
        try:
            gcp._run_gcloud(["projects", "list"])
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "gcloud"
            assert cmd[1:] == ["projects", "list"]
        finally:
            gcp._ACTIVE_ACCOUNT = orig

    @patch("subprocess.run", return_value=_completed(stdout="ok"))
    def test_injects_account_flag_when_active_account_set(
        self, mock_run: MagicMock
    ) -> None:
        import scripts.setup_gcp as gcp

        orig = gcp._ACTIVE_ACCOUNT
        gcp._ACTIVE_ACCOUNT = "user@example.com"
        try:
            gcp._run_gcloud(["projects", "list"])
            cmd = mock_run.call_args[0][0]
            assert cmd[:4] == ["gcloud", "--account", "user@example.com", "projects"]
        finally:
            gcp._ACTIVE_ACCOUNT = orig


# === Account selection ===


class TestSelectAccount:
    def setup_method(self) -> None:
        import scripts.setup_gcp as gcp

        self._orig = gcp._ACTIVE_ACCOUNT
        gcp._ACTIVE_ACCOUNT = None

    def teardown_method(self) -> None:
        import scripts.setup_gcp as gcp

        gcp._ACTIVE_ACCOUNT = self._orig

    def test_uses_provided_account_directly(self) -> None:
        import scripts.setup_gcp as gcp

        result = gcp._select_account("user@example.com")
        assert result == "user@example.com"
        assert gcp._ACTIVE_ACCOUNT == "user@example.com"

    @patch("scripts.setup_gcp._run_gcloud")
    def test_auto_selects_single_account(self, mock_gcloud: MagicMock) -> None:
        import scripts.setup_gcp as gcp

        mock_gcloud.return_value = _completed(stdout="only@example.com\n")
        result = gcp._select_account(None)
        assert result == "only@example.com"
        assert gcp._ACTIVE_ACCOUNT == "only@example.com"

    @patch("scripts.setup_gcp.Prompt.ask", return_value="2")
    @patch("scripts.setup_gcp._run_gcloud")
    def test_prompts_when_multiple_accounts(
        self, mock_gcloud: MagicMock, mock_prompt: MagicMock
    ) -> None:
        import scripts.setup_gcp as gcp

        mock_gcloud.return_value = _completed(stdout="a@example.com\nb@example.com\n")
        result = gcp._select_account(None)
        assert result == "b@example.com"
        assert gcp._ACTIVE_ACCOUNT == "b@example.com"

    @patch("scripts.setup_gcp._run_gcloud")
    def test_returns_none_when_no_accounts(self, mock_gcloud: MagicMock) -> None:
        import scripts.setup_gcp as gcp

        mock_gcloud.return_value = _completed(stdout="")
        result = gcp._select_account(None)
        assert result is None
        assert gcp._ACTIVE_ACCOUNT is None

    @patch("scripts.setup_gcp.Prompt.ask", return_value="freeform@example.com")
    @patch("scripts.setup_gcp._run_gcloud")
    def test_accepts_freeform_account_input(
        self, mock_gcloud: MagicMock, mock_prompt: MagicMock
    ) -> None:
        import scripts.setup_gcp as gcp

        mock_gcloud.return_value = _completed(stdout="a@example.com\nb@example.com\n")
        result = gcp._select_account(None)
        assert result == "freeform@example.com"
        assert gcp._ACTIVE_ACCOUNT == "freeform@example.com"


# === Prerequisite checks ===


class TestCheckGcloudInstalled:
    @patch("subprocess.run", return_value=_completed(returncode=1))
    def test_exits_if_missing(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _check_gcloud_installed

        with pytest.raises(SystemExit):
            _check_gcloud_installed()

    @patch("subprocess.run", return_value=_completed(returncode=0))
    def test_succeeds_if_found(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _check_gcloud_installed

        _check_gcloud_installed()  # no error


class TestCheckDockerInstalled:
    @patch("subprocess.run", return_value=_completed(returncode=1))
    def test_exits_if_missing(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _check_docker_installed

        with pytest.raises(SystemExit):
            _check_docker_installed()

    @patch("subprocess.run", return_value=_completed(returncode=0))
    def test_succeeds_if_found(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _check_docker_installed

        _check_docker_installed()  # no error


class TestLoadPacConfigRaw:
    def test_exits_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        from scripts.setup_gcp import _load_pac_config_raw

        with pytest.raises(SystemExit):
            _load_pac_config_raw()

    def test_returns_raw_dict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = {"version": 1, "signals": [], "broker": {"pin": "${TR_PIN}"}}
        (tmp_path / "pac.yaml").write_text(yaml.safe_dump(config))

        from scripts.setup_gcp import _load_pac_config_raw

        raw = _load_pac_config_raw()
        assert raw["version"] == 1
        # Env vars NOT interpolated — raw string preserved
        assert raw["broker"]["pin"] == "${TR_PIN}"

    def test_exits_on_invalid_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pac.yaml").write_text("just a string")

        from scripts.setup_gcp import _load_pac_config_raw

        with pytest.raises(SystemExit):
            _load_pac_config_raw()


# === Project setup ===


class TestEnsureProject:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_validates_cli_flag_project(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _ensure_project

        mock_gcloud.return_value = _completed(stdout="my-project")
        result = _ensure_project("my-project")
        assert result == "my-project"

    @patch("scripts.setup_gcp._run_gcloud")
    def test_exits_if_cli_project_not_found(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _ensure_project

        mock_gcloud.return_value = _completed(returncode=1)
        with pytest.raises(SystemExit):
            _ensure_project("bad-project")

    @patch("scripts.setup_gcp.Prompt.ask", return_value="1")
    @patch("scripts.setup_gcp._run_gcloud")
    def test_interactive_selects_from_list(
        self, mock_gcloud: MagicMock, mock_prompt: MagicMock
    ) -> None:
        from scripts.setup_gcp import _ensure_project

        mock_gcloud.return_value = _completed(stdout="proj-a\nproj-b\n")
        result = _ensure_project(None)
        assert result == "proj-a"

    @patch("scripts.setup_gcp._create_project", return_value="new-proj")
    @patch("scripts.setup_gcp.Prompt.ask", return_value="new-proj")
    @patch("scripts.setup_gcp._run_gcloud")
    def test_interactive_creates_new_project(
        self,
        mock_gcloud: MagicMock,
        mock_prompt: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        from scripts.setup_gcp import _ensure_project

        # No projects listed
        mock_gcloud.return_value = _completed(stdout="")
        result = _ensure_project(None)
        assert result == "new-proj"
        mock_create.assert_called_once_with("new-proj")


class TestCreateProject:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_creates_and_returns_id(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _create_project

        mock_gcloud.return_value = _completed()
        result = _create_project("test-proj")
        assert result == "test-proj"
        # Verify gcloud projects create was called
        create_call = mock_gcloud.call_args_list[0]
        assert "create" in create_call[0][0]


class TestCheckBilling:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_exits_if_no_billing(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _check_billing

        mock_gcloud.return_value = _completed(stdout="", returncode=0)
        with pytest.raises(SystemExit):
            _check_billing("my-project")

    @patch("scripts.setup_gcp._run_gcloud")
    def test_succeeds_with_billing(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _check_billing

        mock_gcloud.return_value = _completed(stdout="billingAccounts/ABC123")
        _check_billing("my-project")  # no error


class TestEnableApis:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_enables_all_required_apis(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import REQUIRED_APIS, _enable_apis

        mock_gcloud.return_value = _completed()
        _enable_apis()
        args = mock_gcloud.call_args[0][0]
        for api in REQUIRED_APIS:
            assert api in args
        assert "artifactregistry.googleapis.com" not in args

    @patch("scripts.setup_gcp._run_gcloud")
    def test_enables_extra_apis_when_provided(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _enable_apis

        mock_gcloud.return_value = _completed()
        _enable_apis(extra_apis=["artifactregistry.googleapis.com"])
        args = mock_gcloud.call_args[0][0]
        assert "artifactregistry.googleapis.com" in args
        assert "run.googleapis.com" in args


# === Artifact Registry ===


class TestEnsureArtifactRepo:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_creates_repo_if_missing(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _ensure_artifact_repo

        # First call (describe) fails, subsequent succeed
        mock_gcloud.side_effect = [
            _completed(returncode=1),  # describe fails
            _completed(),  # create succeeds
            _completed(),  # configure-docker
        ]
        result = _ensure_artifact_repo("my-proj", "europe-west1")
        assert "my-proj" in result
        assert "europe-west1" in result
        assert mock_gcloud.call_count == 3

    @patch("scripts.setup_gcp._run_gcloud")
    def test_skips_creation_if_exists(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _ensure_artifact_repo

        mock_gcloud.side_effect = [
            _completed(stdout="projects/p/locations/r/repositories/pac"),
            _completed(),  # configure-docker
        ]
        result = _ensure_artifact_repo("my-proj", "europe-west1")
        assert "my-proj" in result
        # Only 2 calls: describe + configure-docker (no create)
        assert mock_gcloud.call_count == 2


# === Build & push ===


class TestBuildAndPush:
    @patch("subprocess.run")
    def test_returns_image_uri_on_success(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _build_and_push

        mock_run.return_value = _completed()
        result = _build_and_push("europe-west1-docker.pkg.dev/proj/pac")
        assert result.endswith(":latest")
        assert "trade-republic-pac" in result

    @patch("subprocess.run")
    def test_exits_on_build_failure(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _build_and_push

        mock_run.return_value = _completed(returncode=1)
        with pytest.raises(SystemExit):
            _build_and_push("europe-west1-docker.pkg.dev/proj/pac")

    @patch("subprocess.run")
    def test_exits_on_push_failure(self, mock_run: MagicMock) -> None:
        from scripts.setup_gcp import _build_and_push

        # Build succeeds, push fails
        mock_run.side_effect = [
            _completed(),  # docker build
            _completed(returncode=1),  # docker push
        ]
        with pytest.raises(SystemExit):
            _build_and_push("europe-west1-docker.pkg.dev/proj/pac")


# === Environment variable file ===


class TestWriteEnvFile:
    def test_creates_valid_yaml(self) -> None:
        from scripts.setup_gcp import _write_env_file

        env = {"KEY_A": "value_a", "KEY_B": "value_b"}
        path = _write_env_file(env)
        try:
            loaded = yaml.safe_load(path.read_text())
            assert loaded == env
        finally:
            path.unlink(missing_ok=True)

    def test_cleans_up_on_write_error(self) -> None:
        from scripts.setup_gcp import _write_env_file

        with (
            patch("yaml.safe_dump", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            _write_env_file({"K": "V"})


# === Deploy Cloud Run ===


class TestDeployCloudRun:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_returns_service_url(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _deploy_cloud_run

        mock_gcloud.side_effect = [
            _completed(),  # deploy
            _completed(stdout="https://svc-abc.run.app"),  # describe
        ]
        url = _deploy_cloud_run("svc", "img:latest", "europe-west1", {"K": "V"})
        assert url == "https://svc-abc.run.app"

    @patch("scripts.setup_gcp._run_gcloud")
    def test_passes_env_vars_file_in_args(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _deploy_cloud_run

        mock_gcloud.side_effect = [
            _completed(),
            _completed(stdout="https://svc.run.app"),
        ]
        _deploy_cloud_run("svc", "img:latest", "eu", {"K": "V"})
        deploy_args = mock_gcloud.call_args_list[0][0][0]
        assert any(a.startswith("--env-vars-file=") for a in deploy_args)

    @patch("scripts.setup_gcp._run_gcloud")
    def test_cleans_up_env_file_on_deploy_failure(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _deploy_cloud_run

        mock_gcloud.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            _deploy_cloud_run("svc", "img:latest", "eu", {"K": "V"})
        # Temp file should be cleaned up (no leftover pac-env-*.yaml)

    @patch("scripts.setup_gcp._run_gcloud")
    def test_exits_if_url_empty(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _deploy_cloud_run

        mock_gcloud.side_effect = [
            _completed(),  # deploy ok
            _completed(stdout=""),  # empty URL
        ]
        with pytest.raises(SystemExit):
            _deploy_cloud_run("svc", "img:latest", "eu", {"K": "V"})


# === Webhook URL update ===


class TestUpdateWebhookEnv:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_merges_env_vars_with_webhook(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _update_webhook_env

        mock_gcloud.return_value = _completed()
        env = {"PAC_JOB_SECRET": "s", "TR_PIN": "1234"}
        _update_webhook_env("svc", "https://svc.run.app", "eu", env)

        # Check the env-vars-file arg was passed
        update_args = mock_gcloud.call_args[0][0]
        env_file_arg = [a for a in update_args if a.startswith("--env-vars-file=")]
        assert len(env_file_arg) == 1

    @patch("scripts.setup_gcp.secrets.token_urlsafe", return_value="gen")
    @patch("scripts.setup_gcp._run_gcloud")
    def test_generates_secret_if_missing(
        self,
        mock_gcloud: MagicMock,
        mock_token: MagicMock,
    ) -> None:
        from scripts.setup_gcp import _update_webhook_env

        mock_gcloud.return_value = _completed()
        _update_webhook_env("svc", "https://svc.run.app", "eu", {})
        mock_token.assert_called_once_with(32)

    @patch("scripts.setup_gcp._run_gcloud")
    def test_cleans_up_on_failure(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _update_webhook_env

        mock_gcloud.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            _update_webhook_env("svc", "https://svc.run.app", "eu", {})


# === Cloud Scheduler ===


class TestSetupScheduler:
    @patch("scripts.setup_gcp._run_gcloud")
    def test_creates_job_for_each_signal(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _setup_scheduler

        mock_gcloud.return_value = _completed()
        config: dict[str, Any] = {
            "signals": [
                {"name": "hourly-check", "schedule": "0 * * * *"},
                {"name": "monthly-pac", "schedule": "0 0 1 * *"},
            ]
        }
        jobs = _setup_scheduler("https://svc.run.app", "europe-west1", "secret", config)
        assert len(jobs) == 2
        assert "pac-signal-hourly-check" in jobs
        assert "pac-signal-monthly-pac" in jobs

    def test_returns_empty_for_no_signals(self) -> None:
        from scripts.setup_gcp import _setup_scheduler

        jobs = _setup_scheduler("https://svc.run.app", "eu", "secret", {"signals": []})
        assert jobs == []

    def test_returns_empty_when_signals_key_missing(self) -> None:
        from scripts.setup_gcp import _setup_scheduler

        jobs = _setup_scheduler("https://svc.run.app", "eu", "secret", {})
        assert jobs == []

    @patch("scripts.setup_gcp._run_gcloud")
    def test_deletes_before_creating(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _setup_scheduler

        mock_gcloud.return_value = _completed()
        config: dict[str, Any] = {
            "signals": [{"name": "test", "schedule": "* * * * *"}]
        }
        _setup_scheduler("https://svc.run.app", "eu", "secret", config)
        # First call should be delete with check=False
        first_call = mock_gcloud.call_args_list[0]
        assert "delete" in first_call[0][0]
        assert first_call[1].get("check") is False

    @patch("scripts.setup_gcp._run_gcloud")
    def test_skips_signal_missing_name(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _setup_scheduler

        mock_gcloud.return_value = _completed()
        config: dict[str, Any] = {"signals": [{"schedule": "* * * * *"}]}
        jobs = _setup_scheduler("https://svc.run.app", "eu", "secret", config)
        assert jobs == []
        mock_gcloud.assert_not_called()

    @patch("scripts.setup_gcp._run_gcloud")
    def test_skips_signal_missing_schedule(self, mock_gcloud: MagicMock) -> None:
        from scripts.setup_gcp import _setup_scheduler

        mock_gcloud.return_value = _completed()
        config: dict[str, Any] = {"signals": [{"name": "test"}]}
        jobs = _setup_scheduler("https://svc.run.app", "eu", "secret", config)
        assert jobs == []
        mock_gcloud.assert_not_called()


# === Collect env vars ===


class TestCollectEnvVars:
    @patch("scripts.setup_gcp.Prompt.ask")
    @patch("scripts.setup_gcp.CacheManager")
    def test_reads_tr_phone_from_cache(
        self,
        mock_cache_cls: MagicMock,
        mock_prompt: MagicMock,
    ) -> None:
        from scripts.setup_gcp import _collect_env_vars

        # TR cache has phone
        tr_instance = MagicMock()
        tr_instance.load.return_value = {"phone_number": "+49123"}
        # Telegram cache empty
        tg_instance = MagicMock()
        tg_instance.load.return_value = None

        mock_cache_cls.side_effect = [tr_instance, tg_instance]
        mock_prompt.side_effect = [
            "job-secret",  # PAC_JOB_SECRET
            "1234",  # TR_PIN
            "bot-token",  # TELEGRAM_BOT_TOKEN
            "chat-id",  # TELEGRAM_CHAT_ID
        ]

        env = _collect_env_vars()
        assert env["TR_PHONE_NUMBER"] == "+49123"
        assert env["PAC_JOB_SECRET"] == "job-secret"
        assert env["TELEGRAM_BOT_TOKEN"] == "bot-token"

    @patch("scripts.setup_gcp.Prompt.ask")
    @patch("scripts.setup_gcp.CacheManager")
    def test_prompts_when_no_cache(
        self,
        mock_cache_cls: MagicMock,
        mock_prompt: MagicMock,
    ) -> None:
        from scripts.setup_gcp import _collect_env_vars

        # Both caches empty
        tr_instance = MagicMock()
        tr_instance.load.return_value = None
        tg_instance = MagicMock()
        tg_instance.load.return_value = None

        mock_cache_cls.side_effect = [tr_instance, tg_instance]
        mock_prompt.side_effect = [
            "job-secret",  # PAC_JOB_SECRET
            "+49999",  # TR_PHONE_NUMBER
            "1234",  # TR_PIN
            "bot-tok",  # TELEGRAM_BOT_TOKEN
            "chat-42",  # TELEGRAM_CHAT_ID
        ]

        env = _collect_env_vars()
        assert env["TR_PHONE_NUMBER"] == "+49999"
        assert env["TELEGRAM_CHAT_ID"] == "chat-42"


# === Cache integrity ===


class TestCacheIntegrity:
    def test_cache_contains_expected_fields(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("gcp", cache_dir=tmp_path)
        cache.save(
            {
                "project_id": "my-project",
                "region": "europe-west1",
                "service_name": "trade-republic-pac",
                "service_url": "https://example.run.app",
                "image_uri": "europe-west1-docker.pkg.dev/p/pac/img:latest",
                "artifact_repo": "pac",
                "scheduler_jobs": ["pac-signal-test"],
            }
        )
        loaded = cache.load()
        assert loaded is not None
        assert loaded["project_id"] == "my-project"
        assert loaded["service_url"].startswith("https://")
        assert isinstance(loaded["scheduler_jobs"], list)

    def test_incremental_cache_after_docker_push(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("gcp", cache_dir=tmp_path)
        # After docker push — no service_url yet
        cache.save(
            {
                "project_id": "proj",
                "region": "eu",
                "service_name": "svc",
                "image_uri": "img:latest",
                "artifact_repo": "pac",
            }
        )
        loaded = cache.load()
        assert loaded is not None
        assert "service_url" not in loaded
        assert loaded["image_uri"] == "img:latest"


# === Disclaimer decline ===


class TestDisclaimerDecline:
    @patch("scripts.setup_gcp.confirm_or_exit", side_effect=SystemExit(1))
    @patch("scripts.setup_gcp.print_disclaimer")
    @patch("scripts.setup_gcp._load_pac_config_raw", return_value={"signals": []})
    @patch("scripts.setup_gcp._check_gcloud_installed")
    def test_exits_before_any_gcloud_calls(
        self,
        mock_gcloud_check: MagicMock,
        mock_config: MagicMock,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        from scripts.setup_gcp import setup

        with pytest.raises(SystemExit):
            setup(
                project="p",
                region="eu",
                service_name="svc",
                override=True,
                registry="ghcr",
            )

        mock_disclaimer.assert_called_once()


# === Cache hit ===


class TestCacheHit:
    def test_returns_early_on_cache_hit(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("gcp", cache_dir=tmp_path)
        cache.save({"project_id": "cached-proj"})

        with (
            patch(
                "scripts.setup_gcp.CacheManager",
                return_value=cache,
            ),
            patch("subprocess.run") as mock_run,
        ):
            from scripts.setup_gcp import setup

            setup(
                project="p",
                region="eu",
                service_name="svc",
                override=False,
                registry="ghcr",
            )
            # No subprocess calls — cached
            mock_run.assert_not_called()


# === GHCR image constant ===


class TestGhcrImage:
    def test_ghcr_constant_defined(self) -> None:
        from scripts.setup_gcp import GHCR_IMAGE

        assert GHCR_IMAGE == "ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest"

    def test_artifact_registry_not_in_required_apis(self) -> None:
        from scripts.setup_gcp import REQUIRED_APIS

        assert "artifactregistry.googleapis.com" not in REQUIRED_APIS


# === Registry flag behavior ===


class TestRegistryFlag:
    @patch("scripts.setup_gcp._setup_scheduler", return_value=[])
    @patch("scripts.setup_gcp._register_telegram_webhook")
    @patch(
        "scripts.setup_gcp._deploy_cloud_run",
        return_value="https://svc.run.app",
    )
    @patch("scripts.setup_gcp._collect_env_vars", return_value={"PAC_JOB_SECRET": "s"})
    @patch("scripts.setup_gcp._enable_apis")
    @patch("scripts.setup_gcp._check_billing")
    @patch("scripts.setup_gcp._ensure_project", return_value="proj")
    @patch("scripts.setup_gcp.confirm_or_exit")
    @patch("scripts.setup_gcp.print_disclaimer")
    @patch(
        "scripts.setup_gcp._load_pac_config_raw",
        return_value={"signals": [{"name": "s1", "schedule": "* * * * *"}]},
    )
    @patch("scripts.setup_gcp._check_gcloud_installed")
    @patch("scripts.setup_gcp._check_docker_installed")
    @patch("scripts.setup_gcp.print_success")
    def test_ghcr_skips_docker_build(
        self,
        mock_success: MagicMock,
        mock_docker: MagicMock,
        mock_gcloud: MagicMock,
        mock_config: MagicMock,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
        mock_project: MagicMock,
        mock_billing: MagicMock,
        mock_apis: MagicMock,
        mock_env: MagicMock,
        mock_deploy: MagicMock,
        mock_webhook: MagicMock,
        mock_scheduler: MagicMock,
    ) -> None:
        from scripts.setup_gcp import GHCR_IMAGE, setup

        setup(
            project="proj",
            region="eu",
            service_name="svc",
            override=True,
            registry="ghcr",
        )
        # Docker check NOT called for ghcr
        mock_docker.assert_not_called()
        # Deploy called with GHCR image
        mock_deploy.assert_called_once()
        assert mock_deploy.call_args[0][1] == GHCR_IMAGE
        # enable_apis called without artifact registry extra
        mock_apis.assert_called_once_with()

    @patch("scripts.setup_gcp._setup_scheduler", return_value=[])
    @patch("scripts.setup_gcp._register_telegram_webhook")
    @patch(
        "scripts.setup_gcp._deploy_cloud_run",
        return_value="https://svc.run.app",
    )
    @patch("scripts.setup_gcp._collect_env_vars", return_value={"PAC_JOB_SECRET": "s"})
    @patch("scripts.setup_gcp._build_and_push", return_value="img:latest")
    @patch(
        "scripts.setup_gcp._ensure_artifact_repo",
        return_value="eu-docker.pkg.dev/proj/pac",
    )
    @patch("scripts.setup_gcp._enable_apis")
    @patch("scripts.setup_gcp._check_billing")
    @patch("scripts.setup_gcp._ensure_project", return_value="proj")
    @patch("scripts.setup_gcp.confirm_or_exit")
    @patch("scripts.setup_gcp.print_disclaimer")
    @patch(
        "scripts.setup_gcp._load_pac_config_raw",
        return_value={"signals": [{"name": "s1", "schedule": "* * * * *"}]},
    )
    @patch("scripts.setup_gcp._check_gcloud_installed")
    @patch("scripts.setup_gcp._check_docker_installed")
    @patch("scripts.setup_gcp.print_success")
    def test_artifact_registry_does_full_build(
        self,
        mock_success: MagicMock,
        mock_docker: MagicMock,
        mock_gcloud: MagicMock,
        mock_config: MagicMock,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
        mock_project: MagicMock,
        mock_billing: MagicMock,
        mock_apis: MagicMock,
        mock_ar_repo: MagicMock,
        mock_build: MagicMock,
        mock_env: MagicMock,
        mock_deploy: MagicMock,
        mock_webhook: MagicMock,
        mock_scheduler: MagicMock,
    ) -> None:
        from scripts.setup_gcp import setup

        setup(
            project="proj",
            region="eu",
            service_name="svc",
            override=True,
            registry="artifact-registry",
        )
        # Docker check IS called for artifact-registry
        mock_docker.assert_called_once()
        # AR repo + build/push called
        mock_ar_repo.assert_called_once()
        mock_build.assert_called_once()
        # enable_apis called WITH artifact registry extra
        mock_apis.assert_called_once_with(
            extra_apis=["artifactregistry.googleapis.com"]
        )


# === Dynamic cost disclaimer ===


class TestBuildCostDisclaimer:
    def test_ghcr_mode_mentions_ghcr(self) -> None:
        from scripts.setup_gcp import _build_cost_disclaimer

        text = _build_cost_disclaimer("ghcr", 2)
        assert "GHCR" in text
        assert "Pull pre-built Docker image" in text
        assert "Artifact Registry: 0.5 GB" not in text

    def test_artifact_registry_mode_mentions_ar(self) -> None:
        from scripts.setup_gcp import _build_cost_disclaimer

        text = _build_cost_disclaimer("artifact-registry", 2)
        assert "Artifact Registry" in text
        assert "Build and push a Docker image" in text
        assert "0.5 GB free storage" in text

    def test_signal_count_within_free_tier(self) -> None:
        from scripts.setup_gcp import _build_cost_disclaimer

        text = _build_cost_disclaimer("ghcr", 2)
        assert "2 signal(s) detected" in text
        assert "$0.00/month" in text

    def test_signal_count_above_free_tier(self) -> None:
        from scripts.setup_gcp import _build_cost_disclaimer

        text = _build_cost_disclaimer("ghcr", 5)
        assert "5 signal(s) detected" in text
        # 5 - 3 = 2 paid, 2 * 0.10 = $0.20
        assert "$0.20/month" in text

    def test_zero_signals(self) -> None:
        from scripts.setup_gcp import _build_cost_disclaimer

        text = _build_cost_disclaimer("ghcr", 0)
        assert "0 signal(s) detected" in text
        assert "$0.00/month" in text


# === Register Telegram webhook ===


class TestRegisterTelegramWebhook:
    @patch("scripts.setup_gcp._update_webhook_env")
    @patch("scripts.setup_gcp.update_env_file")
    @patch("scripts.setup_telegram._bot_api")
    @patch("scripts.setup_gcp.CacheManager")
    def test_registers_webhook_when_telegram_cache_exists(
        self,
        mock_cache_cls: MagicMock,
        mock_bot_api: MagicMock,
        mock_update_env: MagicMock,
        mock_webhook_env: MagicMock,
        tmp_path: Path,
    ) -> None:
        from scripts.setup_gcp import _register_telegram_webhook

        # Telegram CacheManager
        tg_instance = MagicMock()
        tg_instance.load.return_value = {
            "_version": 1,
            "bot_token": "tok123",
            "bot_username": "my_bot",
            "chat_id": "42",
        }
        mock_cache_cls.return_value = tg_instance

        mock_bot_api.return_value = {"ok": True, "result": True}

        _register_telegram_webhook(
            "svc",
            "https://svc.run.app",
            "eu",
            {"PAC_JOB_SECRET": "s"},
        )

        # Verify setWebhook was called
        mock_bot_api.assert_called_once()
        call_args = mock_bot_api.call_args
        assert call_args[0][0] == "tok123"
        assert call_args[0][1] == "setWebhook"
        assert call_args[0][2]["url"] == "https://svc.run.app/webhook"

        # Verify telegram cache updated
        tg_instance.save.assert_called_once()
        saved = tg_instance.save.call_args[0][0]
        assert saved["webhook_url"] == "https://svc.run.app/webhook"
        assert "webhook_secret" in saved
        assert saved["bot_token"] == "tok123"
        assert saved["chat_id"] == "42"

        # Verify .env updated
        mock_update_env.assert_called_once()
        env_call = mock_update_env.call_args[0][0]
        assert "TELEGRAM_WEBHOOK_URL" in env_call
        assert "TELEGRAM_WEBHOOK_SECRET" in env_call

        # Verify Cloud Run env updated
        mock_webhook_env.assert_called_once()

    @patch("scripts.setup_gcp._update_webhook_env")
    @patch("scripts.setup_gcp.CacheManager")
    def test_skips_webhook_when_no_telegram_cache(
        self,
        mock_cache_cls: MagicMock,
        mock_webhook_env: MagicMock,
    ) -> None:
        from scripts.setup_gcp import _register_telegram_webhook

        tg_instance = MagicMock()
        tg_instance.load.return_value = None
        mock_cache_cls.return_value = tg_instance

        with patch("scripts.setup_telegram._bot_api") as mock_api:
            _register_telegram_webhook(
                "svc",
                "https://svc.run.app",
                "eu",
                {},
            )
            mock_api.assert_not_called()

        # Still updates Cloud Run env
        mock_webhook_env.assert_called_once()

    @patch("scripts.setup_gcp._register_telegram_webhook")
    @patch("scripts.setup_gcp._setup_scheduler", return_value=[])
    @patch(
        "scripts.setup_gcp._deploy_cloud_run",
        return_value="https://svc.run.app",
    )
    @patch(
        "scripts.setup_gcp._collect_env_vars",
        return_value={"PAC_JOB_SECRET": "s"},
    )
    @patch("scripts.setup_gcp._enable_apis")
    @patch("scripts.setup_gcp._check_billing")
    @patch("scripts.setup_gcp._ensure_project", return_value="proj")
    @patch("scripts.setup_gcp.confirm_or_exit")
    @patch("scripts.setup_gcp.print_disclaimer")
    @patch(
        "scripts.setup_gcp._load_pac_config_raw",
        return_value={"signals": []},
    )
    @patch("scripts.setup_gcp._check_gcloud_installed")
    @patch("scripts.setup_gcp.print_success")
    def test_setup_calls_register_webhook_after_deploy(
        self,
        mock_success: MagicMock,
        mock_gcloud: MagicMock,
        mock_config: MagicMock,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
        mock_project: MagicMock,
        mock_billing: MagicMock,
        mock_apis: MagicMock,
        mock_env: MagicMock,
        mock_deploy: MagicMock,
        mock_scheduler: MagicMock,
        mock_register_webhook: MagicMock,
    ) -> None:
        from scripts.setup_gcp import setup

        setup(
            project="proj",
            region="eu",
            service_name="svc",
            override=True,
            registry="ghcr",
        )

        mock_register_webhook.assert_called_once_with(
            "svc",
            "https://svc.run.app",
            "eu",
            {"PAC_JOB_SECRET": "s"},
        )
