"""Tests for scripts/setup_tr.py — Trade Republic setup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMaskPin:
    def test_masks_four_digit_pin(self) -> None:
        from scripts.setup_tr import _mask_pin

        assert _mask_pin("1234") == "****"

    def test_masks_six_digit_pin(self) -> None:
        from scripts.setup_tr import _mask_pin

        assert _mask_pin("123456") == "******"


class TestValidatePhone:
    def test_accepts_valid_e164(self) -> None:
        from scripts.setup_tr import _validate_phone

        _validate_phone("+491234567890")  # no error

    def test_accepts_short_valid(self) -> None:
        from scripts.setup_tr import _validate_phone

        _validate_phone("+1234567")  # 7 digits, minimum

    def test_rejects_missing_plus(self) -> None:
        from scripts.setup_tr import _validate_phone

        with pytest.raises(SystemExit):
            _validate_phone("491234567890")

    def test_rejects_letters(self) -> None:
        from scripts.setup_tr import _validate_phone

        with pytest.raises(SystemExit):
            _validate_phone("+49abc")

    def test_rejects_too_short(self) -> None:
        from scripts.setup_tr import _validate_phone

        with pytest.raises(SystemExit):
            _validate_phone("+12345")  # 5 digits, below minimum


class TestAuthenticate:
    def _make_mock_api(
        self,
        *,
        resume: bool = False,
        countdown: int = 30,
        weblogin_error: Exception | None = None,
        complete_error: Exception | None = None,
    ) -> MagicMock:
        """Create a MagicMock for TradeRepublicApi (all methods are sync)."""
        mock = MagicMock()
        mock.resume_websession.return_value = resume
        if weblogin_error:
            mock.initiate_weblogin.side_effect = weblogin_error
        else:
            mock.initiate_weblogin.return_value = countdown
        if complete_error:
            mock.complete_weblogin.side_effect = complete_error
        return mock

    @patch("pytr.api.TradeRepublicApi")
    def test_resumes_existing_session(
        self, mock_api_cls: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _authenticate

        mock_api = self._make_mock_api(resume=True)
        mock_api_cls.return_value = mock_api

        _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))

        mock_api.resume_websession.assert_called_once()
        mock_api.initiate_weblogin.assert_not_called()

    @patch("scripts.setup_tr.Prompt.ask", return_value="1234")
    @patch("pytr.api.TradeRepublicApi")
    def test_runs_2fa_on_expired_session(
        self, mock_api_cls: MagicMock, mock_prompt: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _authenticate

        mock_api = self._make_mock_api(resume=False, countdown=30)
        mock_api_cls.return_value = mock_api

        _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))

        mock_api.resume_websession.assert_called_once()
        mock_api.initiate_weblogin.assert_called_once()
        mock_api.complete_weblogin.assert_called_once_with("1234")

    @patch("scripts.setup_tr.Prompt.ask", side_effect=["", "5678"])
    @patch("scripts.setup_tr.time")
    @patch("pytr.api.TradeRepublicApi")
    def test_sms_fallback_on_empty_code(
        self,
        mock_api_cls: MagicMock,
        mock_time: MagicMock,
        mock_prompt: MagicMock,
        tmp_path: Path,
    ) -> None:
        from scripts.setup_tr import _authenticate

        mock_api = self._make_mock_api(resume=False, countdown=30)
        mock_api_cls.return_value = mock_api
        mock_time.monotonic.side_effect = [0.0, 5.0]  # 5s elapsed

        _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))

        mock_api.resend_weblogin.assert_called_once()
        mock_api.complete_weblogin.assert_called_once_with("5678")
        # Should sleep remaining countdown: max(0, 30 - 5) = 25
        mock_time.sleep.assert_called_once_with(25.0)

    @patch("pytr.api.TradeRepublicApi", side_effect=RuntimeError("WAF"))
    def test_exits_on_init_failure(
        self, mock_api_cls: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _authenticate

        with pytest.raises(SystemExit):
            _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))

    @patch("pytr.api.TradeRepublicApi")
    def test_exits_on_weblogin_failure(
        self, mock_api_cls: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _authenticate

        mock_api = self._make_mock_api(
            resume=False, weblogin_error=ValueError("bad creds")
        )
        mock_api_cls.return_value = mock_api

        with pytest.raises(SystemExit):
            _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))

    @patch("scripts.setup_tr.Prompt.ask", return_value="9999")
    @patch("pytr.api.TradeRepublicApi")
    def test_exits_on_verification_failure(
        self, mock_api_cls: MagicMock, mock_prompt: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _authenticate

        mock_api = self._make_mock_api(
            resume=False, complete_error=RuntimeError("bad code")
        )
        mock_api_cls.return_value = mock_api

        with pytest.raises(SystemExit):
            _authenticate("+491234567890", "1234", str(tmp_path / "cookies"))


class TestValidateSession:
    @patch("pytr.api.TradeRepublicApi")
    def test_exits_when_resume_fails(
        self, mock_api_cls: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _validate_session

        mock_api = MagicMock()
        mock_api.resume_websession.return_value = False
        mock_api_cls.return_value = mock_api

        with pytest.raises(SystemExit):
            _validate_session("+491234567890", "1234", str(tmp_path / "cookies"))

    @patch("pytr.api.TradeRepublicApi")
    def test_succeeds_when_resume_works(
        self, mock_api_cls: MagicMock, tmp_path: Path
    ) -> None:
        from scripts.setup_tr import _validate_session

        mock_api = MagicMock()
        mock_api.resume_websession.return_value = True
        mock_api_cls.return_value = mock_api

        _validate_session("+491234567890", "1234", str(tmp_path / "cookies"))
        mock_api.resume_websession.assert_called_once()


class TestDisclaimerDecline:
    @patch("scripts.setup_tr.confirm_or_exit", side_effect=SystemExit(1))
    @patch("scripts.setup_tr.print_disclaimer")
    @patch("scripts.setup_tr.CacheManager")
    def test_exits_before_collecting_credentials(
        self,
        mock_cache_cls: MagicMock,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        mock_cache = MagicMock()
        mock_cache.check_cache.return_value = None
        mock_cache_cls.return_value = mock_cache

        from scripts.setup_tr import setup

        with pytest.raises(SystemExit):
            setup(phone="+491234567890", override=False)

        mock_disclaimer.assert_called_once()


class TestPinFromEnvVar:
    @patch("pytr.api.TradeRepublicApi")
    @patch("scripts.setup_tr.confirm_or_exit")
    @patch("scripts.setup_tr.print_disclaimer")
    def test_uses_tr_pin_env_var(
        self,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
        mock_api_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("TR_PIN", "9999")

        mock_api = MagicMock()
        mock_api.resume_websession.return_value = True
        mock_api_cls.return_value = mock_api

        # Redirect cache to tmp_path so we don't pollute the workspace
        with patch(
            "scripts.setup_tr.CacheManager",
            return_value=CacheManagerStub(tmp_path),
        ):
            from scripts.setup_tr import setup

            setup(phone="+491234567890", override=True)

        # PIN came from env var, not from Prompt.ask
        mock_api_cls.assert_called()


class TestCacheIntegrity:
    def test_cache_never_stores_real_pin(self, tmp_path: Path) -> None:
        from scripts.setup_tr import _mask_pin
        from scripts.setup_utils import CacheManager

        cache = CacheManager("tr", cache_dir=tmp_path)
        cache.save(
            {
                "phone_number": "+49123",
                "pin": _mask_pin("5678"),
                "cookies_path": ".pac/tr_cookies",
                "validated": True,
            }
        )

        loaded = cache.load()
        assert loaded is not None
        assert loaded["pin"] == "****"
        user_data = {k: v for k, v in loaded.items() if not k.startswith("_")}
        assert "5678" not in str(user_data)

    def test_cache_contains_expected_fields(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("tr", cache_dir=tmp_path)
        cache.save(
            {
                "phone_number": "+491234567890",
                "pin": "****",
                "cookies_path": ".pac/tr_cookies",
                "validated": True,
            }
        )

        loaded = cache.load()
        assert loaded is not None
        assert "phone_number" in loaded
        assert "pin" in loaded
        assert "cookies_path" in loaded
        assert "validated" in loaded


# ── Test helpers ───────────────────────────────────────────────────────


class CacheManagerStub:
    """Minimal CacheManager stand-in that redirects to tmp_path."""

    def __init__(self, tmp_path: Path) -> None:
        self._path = tmp_path / "tr.json"
        self._cm = _real_cache_manager("tr", cache_dir=tmp_path)

    @property
    def path(self) -> Path:
        return self._path

    def check_cache(self, *, override: bool) -> dict[str, object] | None:
        return self._cm.check_cache(override=override)

    def save(self, data: dict[str, object]) -> Path:
        return self._cm.save(data)  # type: ignore[arg-type]


def _real_cache_manager(name: str, *, cache_dir: Path) -> object:
    from scripts.setup_utils import CacheManager

    return CacheManager(name, cache_dir=cache_dir)


class TestSetupWritesEnv:
    @patch("pytr.api.TradeRepublicApi")
    @patch("scripts.setup_tr.confirm_or_exit")
    @patch("scripts.setup_tr.print_disclaimer")
    def test_writes_phone_and_pin_to_env(
        self,
        mock_disclaimer: MagicMock,
        mock_confirm: MagicMock,
        mock_api_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("TR_PIN", "9999")

        mock_api = MagicMock()
        mock_api.resume_websession.return_value = True
        mock_api_cls.return_value = mock_api

        with (
            patch(
                "scripts.setup_tr.CacheManager",
                return_value=CacheManagerStub(tmp_path),
            ),
            patch(
                "scripts.setup_tr.update_env_file",
            ) as mock_update_env,
        ):
            from scripts.setup_tr import setup

            setup(phone="+491234567890", override=True)

        mock_update_env.assert_called_once_with(
            {
                "TR_PHONE_NUMBER": "+491234567890",
                "TR_PIN": "9999",
            }
        )
