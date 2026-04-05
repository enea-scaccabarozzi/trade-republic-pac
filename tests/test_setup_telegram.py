"""Tests for scripts/setup_telegram.py — Telegram bot setup."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# === Helpers ===


def _no_subcommand_ctx() -> MagicMock:
    """Create a mock typer.Context with no invoked subcommand."""
    ctx = MagicMock()
    ctx.invoked_subcommand = None
    return ctx


# === _validate_bot_username ===


class TestValidateBotUsername:
    def test_accepts_valid_username(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        _validate_bot_username("my_pac_bot")  # no error

    def test_accepts_uppercase_bot_suffix(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        _validate_bot_username("MyPacBot")  # no error

    def test_accepts_5char_username(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        _validate_bot_username("a_bot")  # 5 chars, minimum valid

    def test_rejects_no_bot_suffix(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        with pytest.raises(SystemExit):
            _validate_bot_username("my_pac")

    def test_rejects_too_short(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        with pytest.raises(SystemExit):
            _validate_bot_username("abot")  # 4 chars, no separator

    def test_rejects_starts_with_digit(self) -> None:
        from scripts.setup_telegram import _validate_bot_username

        with pytest.raises(SystemExit):
            _validate_bot_username("1bot")


# === _bot_api ===


def _mock_urlopen_response(data: dict[str, Any]) -> MagicMock:
    """Create a mock for urllib.request.urlopen context manager."""
    body = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestBotApi:
    @patch("scripts.setup_telegram.urllib.request.urlopen")
    def test_get_request_returns_parsed_json(self, mock_urlopen: MagicMock) -> None:
        from scripts.setup_telegram import _bot_api

        mock_urlopen.return_value = _mock_urlopen_response({"ok": True, "result": []})
        result = _bot_api("tok123", "getUpdates")
        assert result == {"ok": True, "result": []}

    @patch("scripts.setup_telegram.urllib.request.urlopen")
    def test_post_request_sends_json_body(self, mock_urlopen: MagicMock) -> None:
        from scripts.setup_telegram import _bot_api

        mock_urlopen.return_value = _mock_urlopen_response({"ok": True, "result": {}})
        _bot_api("tok123", "setWebhook", {"url": "https://x.com"})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"
        assert b'"url"' in req.data

    @patch("scripts.setup_telegram.urllib.request.urlopen")
    def test_exits_on_http_error(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        from scripts.setup_telegram import _bot_api

        exc = urllib.error.HTTPError(
            url="https://api.telegram.org/bot/test",
            code=400,
            msg="Bad Request",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=io.BytesIO(b"bad request body"),
        )
        mock_urlopen.side_effect = exc

        with pytest.raises(SystemExit):
            _bot_api("tok", "getMe")

    @patch("scripts.setup_telegram.urllib.request.urlopen")
    def test_exits_on_url_error(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        from scripts.setup_telegram import _bot_api

        mock_urlopen.side_effect = urllib.error.URLError("DNS fail")
        with pytest.raises(SystemExit):
            _bot_api("tok", "getMe")

    @patch("scripts.setup_telegram.urllib.request.urlopen")
    def test_exits_on_not_ok_response(self, mock_urlopen: MagicMock) -> None:
        from scripts.setup_telegram import _bot_api

        mock_urlopen.return_value = _mock_urlopen_response(
            {"ok": False, "description": "Unauthorized"}
        )
        with pytest.raises(SystemExit):
            _bot_api("tok", "getMe")


# === _connect_telethon ===


class TestConnectTelethon:
    @patch("scripts.setup_telegram.Prompt.ask", return_value="12345")
    @patch("telethon.TelegramClient")
    async def test_creates_client_and_starts(
        self,
        mock_client_cls: MagicMock,
        _mock_prompt: MagicMock,
    ) -> None:
        from scripts.setup_telegram import _connect_telethon

        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        result = await _connect_telethon(123, "hash", "+49123")

        mock_client.start.assert_awaited_once()
        assert result is mock_client

    @patch("scripts.setup_telegram.Prompt.ask", return_value="12345")
    @patch("telethon.TelegramClient")
    async def test_session_path_in_pac_dir(
        self,
        mock_client_cls: MagicMock,
        _mock_prompt: MagicMock,
    ) -> None:
        from scripts.setup_telegram import _connect_telethon

        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        await _connect_telethon(123, "hash", "+49123")

        session_arg = mock_client_cls.call_args[0][0]
        assert ".pac/telethon" in session_arg


# === _create_bot ===


class TestCreateBot:
    def _make_message(self, text: str, *, out: bool = False) -> MagicMock:
        msg = MagicMock()
        msg.text = text
        msg.out = out
        return msg

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_extracts_token_from_botfather(self, _mock_sleep: AsyncMock) -> None:
        from scripts.setup_telegram import _create_bot

        client = AsyncMock()
        token_str = "123456:ABCdefGHIjklMNOpqrsTUVwxyz0123456789a"

        responses = [
            self._make_message(
                "Alright, a new bot. How are we going to call it?"
                " Please choose a name for your bot."
            ),
            self._make_message("Good. Now let's choose a username for your bot."),
            self._make_message(
                f"Done! Use this token to access the HTTP API:\n"
                f"{token_str}\nKeep your token secure."
            ),
        ]
        call_count = 0

        async def iter_messages_side_effect(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            msg = responses[call_count]
            call_count += 1
            yield msg

        client.iter_messages = iter_messages_side_effect

        result = await _create_bot(client, "My Bot", "my_pac_bot")
        assert result == token_str

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_exits_on_unexpected_newbot_response(
        self, _mock_sleep: AsyncMock
    ) -> None:
        from scripts.setup_telegram import _create_bot

        client = AsyncMock()

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            msg = MagicMock()
            msg.text = "Something unexpected"
            msg.out = False
            yield msg

        client.iter_messages = iter_msg

        with pytest.raises(SystemExit):
            await _create_bot(client, "Bot", "my_bot")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_exits_on_unexpected_name_response(
        self, _mock_sleep: AsyncMock
    ) -> None:
        from scripts.setup_telegram import _create_bot

        client = AsyncMock()
        responses = [
            self._make_message("Please choose a name for your bot."),
            self._make_message("Error: something went wrong"),
        ]
        call_count = 0

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            nonlocal call_count
            msg = responses[call_count]
            call_count += 1
            yield msg

        client.iter_messages = iter_msg

        with pytest.raises(SystemExit):
            await _create_bot(client, "Bot", "my_bot")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_exits_on_missing_token(self, _mock_sleep: AsyncMock) -> None:
        from scripts.setup_telegram import _create_bot

        client = AsyncMock()
        responses = [
            self._make_message("Please choose a name"),
            self._make_message("Now choose a username"),
            self._make_message("No token here whatsoever!"),
        ]
        call_count = 0

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            nonlocal call_count
            msg = responses[call_count]
            call_count += 1
            yield msg

        client.iter_messages = iter_msg

        with pytest.raises(SystemExit):
            await _create_bot(client, "Bot", "my_bot")

    @patch("asyncio.get_event_loop")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_exits_on_timeout_no_response(
        self, _mock_sleep: AsyncMock, mock_get_loop: MagicMock
    ) -> None:
        from scripts.setup_telegram import _create_bot

        # Simulate time advancing past the 10s deadline after one iteration
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0, 0, 11]  # deadline=10, enter loop, then expire
        mock_get_loop.return_value = mock_loop

        client = AsyncMock()

        async def iter_empty(*_a: Any, **_kw: Any) -> Any:
            # yield only outgoing messages
            msg = MagicMock()
            msg.out = True
            msg.text = "outgoing"
            yield msg

        client.iter_messages = iter_empty

        with pytest.raises(SystemExit):
            await _create_bot(client, "Bot", "my_bot")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_until_incoming_message(self, _mock_sleep: AsyncMock) -> None:
        from scripts.setup_telegram import _create_bot

        client = AsyncMock()
        token_str = "123456:ABCdefGHIjklMNOpqrsTUVwxyz0123456789a"

        # For each _send_and_wait call, iter_messages may be called
        # multiple times: first returning an outgoing msg, then incoming.
        step = 0
        incoming_responses = [
            self._make_message("Please choose a name for your bot."),
            self._make_message("Now choose a username for your bot."),
            self._make_message(f"Done! Use this token:\n{token_str}\nKeep it secure."),
        ]

        call_count = 0

        async def iter_messages_side_effect(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count, step
            # On even calls: return outgoing message (should be skipped)
            # On odd calls: return the real incoming response
            if call_count % 2 == 0:
                call_count += 1
                yield self._make_message("outgoing", out=True)
            else:
                msg = incoming_responses[step]
                step += 1
                call_count += 1
                yield msg

        client.iter_messages = iter_messages_side_effect

        result = await _create_bot(client, "My Bot", "my_pac_bot")
        assert result == token_str


# === _poll_chat_id ===


class TestPollChatId:
    @patch("scripts.setup_telegram._bot_api")
    def test_returns_chat_id_on_start_message(self, mock_api: MagicMock) -> None:
        from scripts.setup_telegram import _poll_chat_id

        mock_api.side_effect = [
            # flush call
            {"ok": True, "result": []},
            # poll call with /start
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "text": "/start",
                            "chat": {"id": 987654},
                        },
                    }
                ],
            },
        ]
        assert _poll_chat_id("tok") == "987654"

    @patch("scripts.setup_telegram.time")
    @patch("scripts.setup_telegram._bot_api")
    def test_exits_on_timeout(self, mock_api: MagicMock, mock_time: MagicMock) -> None:
        from scripts.setup_telegram import _poll_chat_id

        # flush
        mock_api.return_value = {"ok": True, "result": []}
        # monotonic: first call sets deadline, second exceeds it
        mock_time.monotonic.side_effect = [0, 0, 200]

        with pytest.raises(SystemExit):
            _poll_chat_id("tok")

    @patch("scripts.setup_telegram._bot_api")
    def test_ignores_non_start_messages(self, mock_api: MagicMock) -> None:
        from scripts.setup_telegram import _poll_chat_id

        mock_api.side_effect = [
            # flush
            {"ok": True, "result": []},
            # poll with /help (not /start)
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "text": "/help",
                            "chat": {"id": 111},
                        },
                    }
                ],
            },
            # poll with /start
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 2,
                        "message": {
                            "text": "/start",
                            "chat": {"id": 222},
                        },
                    }
                ],
            },
        ]
        assert _poll_chat_id("tok") == "222"

    @patch("scripts.setup_telegram._bot_api")
    def test_flush_captures_last_update_id(self, mock_api: MagicMock) -> None:
        from scripts.setup_telegram import _poll_chat_id

        mock_api.side_effect = [
            # flush with existing update
            {"ok": True, "result": [{"update_id": 50}]},
            # poll with /start — offset should be 51
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 51,
                        "message": {
                            "text": "/start",
                            "chat": {"id": 999},
                        },
                    }
                ],
            },
        ]
        _poll_chat_id("tok")

        # Second call should use offset = 51
        second_call = mock_api.call_args_list[1]
        assert second_call[0][2]["offset"] == 51

    @patch("scripts.setup_telegram.time.sleep")
    @patch("scripts.setup_telegram._bot_api")
    def test_no_double_sleep(self, mock_api: MagicMock, mock_sleep: MagicMock) -> None:
        from scripts.setup_telegram import _poll_chat_id

        mock_api.side_effect = [
            # flush
            {"ok": True, "result": []},
            # first poll: empty
            {"ok": True, "result": []},
            # second poll: /start arrives
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "text": "/start",
                            "chat": {"id": 42},
                        },
                    }
                ],
            },
        ]
        assert _poll_chat_id("tok") == "42"
        # Long poll via getUpdates timeout param is sufficient;
        # no explicit time.sleep should be called.
        mock_sleep.assert_not_called()


# === _detect_webhook_url ===


class TestDetectWebhookUrl:
    @patch("scripts.setup_telegram.CacheManager")
    def test_returns_url_from_gcp_cache(self, mock_cache_cls: MagicMock) -> None:
        from scripts.setup_telegram import _detect_webhook_url

        instance = MagicMock()
        instance.load.return_value = {"service_url": "https://svc.run.app"}
        mock_cache_cls.return_value = instance

        assert _detect_webhook_url() == "https://svc.run.app/webhook"

    @patch("scripts.setup_telegram.CacheManager")
    def test_returns_none_without_cache(self, mock_cache_cls: MagicMock) -> None:
        from scripts.setup_telegram import _detect_webhook_url

        instance = MagicMock()
        instance.load.return_value = None
        mock_cache_cls.return_value = instance

        assert _detect_webhook_url() is None

    @patch("scripts.setup_telegram.CacheManager")
    def test_returns_none_with_empty_service_url(
        self, mock_cache_cls: MagicMock
    ) -> None:
        from scripts.setup_telegram import _detect_webhook_url

        instance = MagicMock()
        instance.load.return_value = {"service_url": ""}
        mock_cache_cls.return_value = instance

        assert _detect_webhook_url() is None

    @patch("scripts.setup_telegram.CacheManager")
    def test_strips_trailing_slash(self, mock_cache_cls: MagicMock) -> None:
        from scripts.setup_telegram import _detect_webhook_url

        instance = MagicMock()
        instance.load.return_value = {"service_url": "https://svc.run.app/"}
        mock_cache_cls.return_value = instance

        assert _detect_webhook_url() == "https://svc.run.app/webhook"


# === _register_webhook ===


class TestRegisterWebhook:
    @patch("scripts.setup_telegram._bot_api")
    def test_calls_set_webhook_api(self, mock_api: MagicMock) -> None:
        from scripts.setup_telegram import _register_webhook

        mock_api.return_value = {"ok": True, "result": True}
        _register_webhook("tok", "https://x.com/webhook", "sec123")
        mock_api.assert_called_once_with(
            "tok",
            "setWebhook",
            {
                "url": "https://x.com/webhook",
                "secret_token": "sec123",
            },
        )

    @patch("scripts.setup_telegram._bot_api")
    def test_exits_on_api_failure(self, mock_api: MagicMock) -> None:
        from scripts.setup_telegram import _register_webhook

        mock_api.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            _register_webhook("tok", "https://x.com/wh", "sec")


# === _cleanup_session ===


class TestCleanupSession:
    def test_removes_session_files(self, tmp_path: Path) -> None:
        from scripts.setup_telegram import _cleanup_session

        with patch(
            "scripts.setup_telegram.SESSION_PATH",
            str(tmp_path / "telethon"),
        ):
            (tmp_path / "telethon").touch()
            (tmp_path / "telethon.session").touch()
            _cleanup_session()
            assert not (tmp_path / "telethon").exists()
            assert not (tmp_path / "telethon.session").exists()

    def test_no_error_if_files_missing(self, tmp_path: Path) -> None:
        from scripts.setup_telegram import _cleanup_session

        with patch(
            "scripts.setup_telegram.SESSION_PATH",
            str(tmp_path / "telethon"),
        ):
            _cleanup_session()  # no error


# === Cache integrity ===


class TestCacheIntegrity:
    def test_cache_contains_expected_fields(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("telegram", cache_dir=tmp_path)
        cache.save(
            {
                "bot_token": "123:ABC",
                "bot_username": "test_bot",
                "chat_id": "999",
                "webhook_url": "https://x.com/webhook",
                "webhook_secret": "secret123",
            }
        )
        loaded = cache.load()
        assert loaded is not None
        assert loaded["bot_token"] == "123:ABC"
        assert loaded["bot_username"] == "test_bot"
        assert loaded["chat_id"] == "999"
        assert loaded["webhook_url"] == "https://x.com/webhook"
        assert loaded["webhook_secret"] == "secret123"

    def test_cache_bot_token_present(self, tmp_path: Path) -> None:
        from scripts.setup_utils import CacheManager

        cache = CacheManager("telegram", cache_dir=tmp_path)
        cache.save({"bot_token": "123:ABC"})
        loaded = cache.load()
        assert loaded is not None
        assert "bot_token" in loaded


# === Partial cache recovery ===


class TestPartialCacheRecovery:
    def test_partial_cache_detected(self) -> None:
        from scripts.setup_telegram import _is_partial_cache

        assert _is_partial_cache({"bot_token": "t", "bot_username": "u"})

    def test_full_cache_not_partial(self) -> None:
        from scripts.setup_telegram import _is_partial_cache

        assert not _is_partial_cache(
            {
                "bot_token": "t",
                "bot_username": "u",
                "chat_id": "123",
            }
        )

    def test_empty_cache_not_partial(self) -> None:
        from scripts.setup_telegram import _is_partial_cache

        assert not _is_partial_cache({})

    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value="https://x.com/webhook",
    )
    @patch(
        "scripts.setup_telegram._poll_chat_id",
        return_value="42",
    )
    def test_recovery_skips_bot_creation(
        self,
        mock_poll: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        tmp_path: Path,
    ) -> None:
        from scripts.setup_telegram import setup

        # Prepare partial cache
        cache_dir = tmp_path / ".pac"
        cache_dir.mkdir()
        cache_file = cache_dir / "telegram.json"
        cache_file.write_text(
            json.dumps(
                {
                    "_version": 1,
                    "_created_at": "2026-01-01",
                    "bot_token": "123:ABC",
                    "bot_username": "test_bot",
                }
            )
        )

        with (
            patch("scripts.setup_telegram.CacheManager") as mock_cache_cls,
            patch("scripts.setup_telegram._create_bot") as mock_create,
        ):
            # Make the CacheManager instance use the real cache
            from scripts.setup_utils import CacheManager

            real_cache = CacheManager("telegram", cache_dir=cache_dir)
            mock_cache_cls.return_value = real_cache

            setup(ctx=_no_subcommand_ctx(), override=False, skip_webhook=False)

            mock_create.assert_not_called()
            mock_poll.assert_called_once()

            # Verify final cache has all fields
            loaded = real_cache.load()
            assert loaded is not None
            assert loaded["chat_id"] == "42"
            assert loaded["webhook_url"] == "https://x.com/webhook"


# === Env var fallbacks ===


class TestEnvVarFallbacks:
    @patch("scripts.setup_telegram.asyncio.run")
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.Prompt.ask")
    def test_api_id_from_env(
        self,
        mock_prompt: MagicMock,
        _mock_confirm: MagicMock,
        mock_async_run: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from scripts.setup_telegram import setup

        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")

        mock_prompt.side_effect = [
            "+491234567890",  # phone
            "My Bot",  # bot_name
            "my_pac_bot",  # bot_username
        ]
        mock_async_run.return_value = {
            "bot_token": "t",
            "bot_username": "my_pac_bot",
            "chat_id": "1",
            "webhook_url": "https://x.com/wh",
            "webhook_secret": "s",
        }

        with patch("scripts.setup_telegram.CacheManager") as mock_cache:
            instance = MagicMock()
            instance.load.return_value = None
            mock_cache.return_value = instance
            setup(
                ctx=_no_subcommand_ctx(),
                bot_name=None,
                bot_username=None,
                override=True,
            )

        # Prompt.ask should NOT have been called for api_id
        for call in mock_prompt.call_args_list:
            assert "API ID" not in call[0][0]

    @patch("scripts.setup_telegram.asyncio.run")
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.Prompt.ask")
    def test_api_hash_from_env(
        self,
        mock_prompt: MagicMock,
        _mock_confirm: MagicMock,
        mock_async_run: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from scripts.setup_telegram import setup

        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")

        mock_prompt.side_effect = [
            "+491234567890",  # phone
            "My Bot",  # bot_name
            "my_pac_bot",  # bot_username
        ]
        mock_async_run.return_value = {
            "bot_token": "t",
            "bot_username": "my_pac_bot",
            "chat_id": "1",
            "webhook_url": "https://x.com/wh",
            "webhook_secret": "s",
        }

        with patch("scripts.setup_telegram.CacheManager") as mock_cache:
            instance = MagicMock()
            instance.load.return_value = None
            mock_cache.return_value = instance
            setup(
                ctx=_no_subcommand_ctx(),
                bot_name=None,
                bot_username=None,
                override=True,
            )

        # Prompt.ask should NOT have been called for api_hash
        for call in mock_prompt.call_args_list:
            assert "API hash" not in call[0][0]

    @patch("scripts.setup_telegram.asyncio.run")
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.Prompt.ask")
    def test_prompt_when_env_empty(
        self,
        mock_prompt: MagicMock,
        _mock_confirm: MagicMock,
        mock_async_run: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from scripts.setup_telegram import setup

        monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
        monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)

        mock_prompt.side_effect = [
            "12345",  # api_id
            "abc123",  # api_hash
            "+491234567890",  # phone
            "My Bot",  # bot_name
            "my_pac_bot",  # bot_username
        ]
        mock_async_run.return_value = {
            "bot_token": "t",
            "bot_username": "my_pac_bot",
            "chat_id": "1",
            "webhook_url": "https://x.com/wh",
            "webhook_secret": "s",
        }

        with patch("scripts.setup_telegram.CacheManager") as mock_cache:
            instance = MagicMock()
            instance.load.return_value = None
            mock_cache.return_value = instance
            setup(
                ctx=_no_subcommand_ctx(),
                bot_name=None,
                bot_username=None,
                override=True,
            )

        prompts = [c[0][0] for c in mock_prompt.call_args_list]
        assert any("API ID" in p for p in prompts)
        assert any("API hash" in p for p in prompts)


# === Typer command integration ===


class TestTyperCommandIntegration:
    @patch("scripts.setup_telegram.secrets.token_hex", return_value="s3cr3t")
    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value="https://svc.run.app/webhook",
    )
    @patch("scripts.setup_telegram._poll_chat_id", return_value="999")
    @patch("scripts.setup_telegram._cleanup_session")
    @patch("scripts.setup_telegram._connect_telethon")
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.Prompt.ask")
    def test_full_flow_mocked(
        self,
        mock_prompt: MagicMock,
        _mock_confirm: MagicMock,
        mock_connect: MagicMock,
        mock_cleanup: MagicMock,
        mock_poll: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        mock_token_hex: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from scripts.setup_telegram import app
        from typer.testing import CliRunner

        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")

        mock_prompt.side_effect = [
            "+491234567890",  # phone
            "My PAC Bot",  # bot_name
            "my_pac_bot",  # bot_username
        ]

        # Mock Telethon client
        mock_client = AsyncMock()
        mock_connect.return_value = mock_client

        token_str = "123456:ABCdefGHIjklMNOpqrsTUVwxyz0123456789a"

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            msg = MagicMock()
            msg.out = False
            msg.text = f"Done! Token:\n{token_str}\nKeep it safe."
            yield msg

        # Configure mock for _create_bot's three calls
        msgs = [
            "Please choose a name for your bot.",
            "Now choose a username for your bot.",
            f"Done! Token:\n{token_str}\nKeep it safe.",
        ]
        call_idx = 0

        async def iter_side(*_a: Any, **_kw: Any) -> Any:
            nonlocal call_idx
            msg = MagicMock()
            msg.out = False
            msg.text = msgs[call_idx]
            call_idx += 1
            yield msg

        mock_client.iter_messages = iter_side

        # Use real CacheManager writing to tmp_path
        with patch("scripts.setup_telegram.CacheManager") as mock_cache_cls:
            from scripts.setup_utils import CacheManager

            real_cache = CacheManager("telegram", cache_dir=tmp_path)
            mock_cache_cls.return_value = real_cache

            runner = CliRunner()
            result = runner.invoke(app, ["--override"])

        assert result.exit_code == 0, result.output
        loaded = real_cache.load()
        assert loaded is not None
        assert loaded["bot_token"] == token_str
        assert loaded["chat_id"] == "999"
        assert loaded["webhook_url"] == "https://svc.run.app/webhook"
        assert loaded["webhook_secret"] == "s3cr3t"


# === Disclaimer decline ===


class TestDisclaimerDecline:
    @patch(
        "scripts.setup_telegram.confirm_or_exit",
        side_effect=SystemExit(1),
    )
    def test_exits_before_collecting_credentials(
        self, _mock_confirm: MagicMock
    ) -> None:
        from scripts.setup_telegram import setup

        with (
            patch("scripts.setup_telegram.CacheManager") as mock_cache_cls,
            patch("scripts.setup_telegram._connect_telethon") as mock_connect,
        ):
            instance = MagicMock()
            instance.load.return_value = None
            mock_cache_cls.return_value = instance

            with pytest.raises(SystemExit):
                setup(ctx=_no_subcommand_ctx(), override=True)

            mock_connect.assert_not_called()


class TestSetupWritesEnv:
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.print_disclaimer")
    def test_writes_telegram_vars_to_env(
        self,
        _mock_disclaimer: MagicMock,
        _mock_confirm: MagicMock,
    ) -> None:
        result_data = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "999",
            "webhook_url": "https://x.com/webhook",
            "webhook_secret": "sec123",
        }

        cache_instance = MagicMock()
        cache_instance.load.return_value = None
        cache_instance.path = Path(".pac/telegram.json")

        with (
            patch("scripts.setup_telegram.CacheManager", return_value=cache_instance),
            patch("scripts.setup_telegram._run_setup", return_value=result_data),
            patch("scripts.setup_telegram.update_env_file") as mock_update_env,
            patch(
                "scripts.setup_telegram.Prompt.ask",
                side_effect=[
                    "12345",  # api_id
                    "abc123hash",  # api_hash
                    "+49123",  # phone
                    "My Bot",  # bot_name
                    "my_pac_bot",  # bot_username
                ],
            ),
        ):
            from scripts.setup_telegram import setup

            setup(
                ctx=_no_subcommand_ctx(),
                override=True,
                bot_name=None,
                bot_username=None,
            )

        mock_update_env.assert_called_once_with(
            {
                "TELEGRAM_BOT_TOKEN": "123:ABC",
                "TELEGRAM_CHAT_ID": "999",
                "TELEGRAM_WEBHOOK_URL": "https://x.com/webhook",
                "TELEGRAM_WEBHOOK_SECRET": "sec123",
            }
        )


# === Skip webhook flag ===


class TestSkipWebhookFlag:
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.print_disclaimer")
    def test_skip_webhook_omits_webhook_keys_from_env(
        self,
        _mock_disclaimer: MagicMock,
        _mock_confirm: MagicMock,
    ) -> None:
        """setup(skip_webhook=True) writes .env without webhook keys."""
        result_data = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "999",
        }

        cache_instance = MagicMock()
        cache_instance.load.return_value = None
        cache_instance.path = Path(".pac/telegram.json")

        with (
            patch(
                "scripts.setup_telegram.CacheManager",
                return_value=cache_instance,
            ),
            patch(
                "scripts.setup_telegram._run_setup",
                return_value=result_data,
            ) as mock_run,
            patch(
                "scripts.setup_telegram.update_env_file",
            ) as mock_update_env,
            patch(
                "scripts.setup_telegram.Prompt.ask",
                side_effect=[
                    "12345",
                    "abc123hash",
                    "+49123",
                    "My Bot",
                    "my_pac_bot",
                ],
            ),
        ):
            from scripts.setup_telegram import setup

            setup(
                ctx=_no_subcommand_ctx(),
                override=True,
                bot_name=None,
                bot_username=None,
                skip_webhook=True,
            )

        mock_run.assert_called_once()
        assert mock_run.call_args[1]["skip_webhook"] is True

        mock_update_env.assert_called_once_with(
            {
                "TELEGRAM_BOT_TOKEN": "123:ABC",
                "TELEGRAM_CHAT_ID": "999",
            }
        )

        # Cache saved without webhook keys
        cache_instance.save.assert_called_once_with(result_data)

    @patch("scripts.setup_telegram._cleanup_session")
    @patch("scripts.setup_telegram._poll_chat_id", return_value="42")
    @patch("scripts.setup_telegram._connect_telethon")
    async def test_run_setup_skip_webhook_returns_no_webhook(
        self,
        mock_connect: MagicMock,
        mock_poll: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        """_run_setup(skip_webhook=True) returns dict without webhook."""
        mock_client = AsyncMock()
        mock_connect.return_value = mock_client

        token = "123456:ABCdefGHIjklMNOpqrsTUVwxyz0123456789a"

        call_idx = 0
        msgs = [
            "Please choose a name for your bot.",
            "Now choose a username for your bot.",
            f"Done! Token:\n{token}\nKeep it safe.",
        ]

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            nonlocal call_idx
            msg = MagicMock()
            msg.out = False
            msg.text = msgs[call_idx]
            call_idx += 1
            yield msg

        mock_client.iter_messages = iter_msg

        from scripts.setup_telegram import _run_setup

        result = await _run_setup(
            bot_name="Bot",
            bot_username="my_pac_bot",
            phone="+49123",
            api_id=123,
            api_hash="hash",
            skip_webhook=True,
        )

        assert result == {
            "bot_token": token,
            "bot_username": "my_pac_bot",
            "chat_id": "42",
        }
        assert "webhook_url" not in result
        assert "webhook_secret" not in result

    @patch("scripts.setup_telegram._register_webhook")
    @patch("scripts.setup_telegram._detect_webhook_url")
    @patch("scripts.setup_telegram._poll_chat_id", return_value="42")
    def test_partial_recovery_skip_webhook_omits_webhook(
        self,
        mock_poll: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Partial cache + --skip-webhook: polls chat_id, no webhook."""
        cache_dir = tmp_path / ".pac"
        cache_dir.mkdir()
        (cache_dir / "telegram.json").write_text(
            json.dumps(
                {
                    "_version": 1,
                    "_created_at": "2026-01-01",
                    "bot_token": "123:ABC",
                    "bot_username": "test_bot",
                }
            )
        )

        with (
            patch(
                "scripts.setup_telegram.CacheManager",
            ) as mock_cache_cls,
            patch(
                "scripts.setup_telegram._create_bot",
            ) as mock_create,
        ):
            from scripts.setup_utils import CacheManager

            real_cache = CacheManager("telegram", cache_dir=cache_dir)
            mock_cache_cls.return_value = real_cache

            from scripts.setup_telegram import setup

            setup(ctx=_no_subcommand_ctx(), override=False, skip_webhook=True)

        mock_create.assert_not_called()
        mock_poll.assert_called_once()
        mock_detect.assert_not_called()
        mock_register.assert_not_called()

        loaded = real_cache.load()
        assert loaded is not None
        assert loaded["chat_id"] == "42"
        assert "webhook_url" not in loaded
        assert "webhook_secret" not in loaded

    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value=None,
    )
    @patch("scripts.setup_telegram._poll_chat_id", return_value="42")
    @patch("scripts.setup_telegram._cleanup_session")
    @patch("scripts.setup_telegram._connect_telethon")
    @patch("scripts.setup_telegram.confirm_or_exit")
    @patch("scripts.setup_telegram.Prompt.ask")
    def test_standalone_no_gcp_cache_prompts_url(
        self,
        mock_prompt: MagicMock,
        _mock_confirm: MagicMock,
        mock_connect: MagicMock,
        mock_cleanup: MagicMock,
        mock_poll: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Standalone run (skip_webhook=False), no GCP cache → prompts."""
        monkeypatch.setenv("TELEGRAM_API_ID", "123")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")

        mock_client = AsyncMock()
        mock_connect.return_value = mock_client
        token = "123456:ABCdefGHIjklMNOpqrsTUVwxyz0123456789a"

        msgs = [
            "Please choose a name for your bot.",
            "Now choose a username for your bot.",
            f"Done! Token:\n{token}\nKeep it safe.",
        ]
        call_idx = 0

        async def iter_msg(*_a: Any, **_kw: Any) -> Any:
            nonlocal call_idx
            msg = MagicMock()
            msg.out = False
            msg.text = msgs[call_idx]
            call_idx += 1
            yield msg

        mock_client.iter_messages = iter_msg

        mock_prompt.side_effect = [
            "+49123",  # phone
            "My Bot",  # bot_name
            "my_pac_bot",  # bot_username
            "https://manual.run.app/webhook",  # webhook URL prompt
        ]

        cache_instance = MagicMock()
        cache_instance.load.return_value = None
        cache_instance.path = Path(".pac/telegram.json")

        with patch(
            "scripts.setup_telegram.CacheManager",
            return_value=cache_instance,
        ):
            from scripts.setup_telegram import setup

            setup(
                ctx=_no_subcommand_ctx(),
                override=True,
                bot_name=None,
                bot_username=None,
                skip_webhook=False,
            )

        mock_detect.assert_called_once()
        mock_register.assert_called_once()
        # Webhook URL was prompted
        saved = cache_instance.save.call_args[0][0]
        assert saved["webhook_url"] == "https://manual.run.app/webhook"


# === Register webhook subcommand ===


class TestRegisterWebhookCommand:
    """Tests for the register-webhook subcommand."""

    @patch("scripts.setup_telegram.update_env_file")
    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value="https://svc.run.app/webhook",
    )
    @patch("scripts.setup_telegram.secrets.token_hex", return_value="wh_secret")
    def test_registers_webhook_from_caches(
        self,
        _mock_hex: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        mock_update_env: MagicMock,
    ) -> None:
        """Both telegram + gcp caches present → registers webhook."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {
            "_version": 1,
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "42",
        }
        cache_instance.path = Path(".pac/telegram.json")

        with patch(
            "scripts.setup_telegram.CacheManager",
            return_value=cache_instance,
        ):
            register_webhook(override=True)

        mock_detect.assert_called_once()
        mock_register.assert_called_once_with(
            "123:ABC", "https://svc.run.app/webhook", "wh_secret"
        )
        mock_update_env.assert_called_once_with(
            {
                "TELEGRAM_WEBHOOK_URL": "https://svc.run.app/webhook",
                "TELEGRAM_WEBHOOK_SECRET": "wh_secret",
            }
        )
        saved = cache_instance.save.call_args[0][0]
        assert saved["webhook_url"] == "https://svc.run.app/webhook"
        assert saved["webhook_secret"] == "wh_secret"
        assert saved["bot_token"] == "123:ABC"
        # Internal keys (_version) stripped
        assert "_version" not in saved

    def test_exits_when_no_telegram_cache(self) -> None:
        """No .pac/telegram.json → SystemExit."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = None

        with (
            patch(
                "scripts.setup_telegram.CacheManager",
                return_value=cache_instance,
            ),
            pytest.raises(SystemExit),
        ):
            register_webhook()

    def test_exits_when_no_bot_token(self) -> None:
        """Telegram cache exists but no bot_token → SystemExit."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {"bot_username": "bot"}

        with (
            patch(
                "scripts.setup_telegram.CacheManager",
                return_value=cache_instance,
            ),
            pytest.raises(SystemExit),
        ):
            register_webhook()

    @patch("scripts.setup_telegram._detect_webhook_url", return_value=None)
    def test_exits_when_detect_webhook_url_returns_none(
        self,
        mock_detect: MagicMock,
    ) -> None:
        """_detect_webhook_url() returns None → SystemExit."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "42",
        }

        with (
            patch(
                "scripts.setup_telegram.CacheManager",
                return_value=cache_instance,
            ),
            pytest.raises(SystemExit),
        ):
            register_webhook()

    @patch("scripts.setup_telegram._register_webhook")
    def test_skips_when_already_cached(
        self,
        mock_register: MagicMock,
    ) -> None:
        """Cache has webhook_url + webhook_secret, no override → early return."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "42",
            "webhook_url": "https://cached.run.app/webhook",
            "webhook_secret": "cached_secret",
        }

        with patch(
            "scripts.setup_telegram.CacheManager",
            return_value=cache_instance,
        ):
            register_webhook(override=False)

        mock_register.assert_not_called()

    @patch("scripts.setup_telegram.update_env_file")
    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value="https://svc.run.app/webhook",
    )
    @patch("scripts.setup_telegram.secrets.token_hex", return_value="new_secret")
    def test_override_re_registers(
        self,
        _mock_hex: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        mock_update_env: MagicMock,
    ) -> None:
        """Cache has webhook data but override=True → re-registers."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "42",
            "webhook_url": "https://old.run.app/webhook",
            "webhook_secret": "old_secret",
        }
        cache_instance.path = Path(".pac/telegram.json")

        with patch(
            "scripts.setup_telegram.CacheManager",
            return_value=cache_instance,
        ):
            register_webhook(override=True)

        mock_register.assert_called_once()

    @patch("scripts.setup_telegram.update_env_file")
    @patch("scripts.setup_telegram._register_webhook")
    @patch(
        "scripts.setup_telegram._detect_webhook_url",
        return_value="https://svc.run.app/webhook",
    )
    @patch("scripts.setup_telegram.secrets.token_hex", return_value="wh_secret")
    def test_prints_cloud_run_warning(
        self,
        _mock_hex: MagicMock,
        mock_detect: MagicMock,
        mock_register: MagicMock,
        mock_update_env: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """After registration, prints Cloud Run env var warning."""
        from scripts.setup_telegram import register_webhook

        cache_instance = MagicMock()
        cache_instance.load.return_value = {
            "bot_token": "123:ABC",
            "bot_username": "test_bot",
            "chat_id": "42",
        }
        cache_instance.path = Path(".pac/telegram.json")

        with patch(
            "scripts.setup_telegram.CacheManager",
            return_value=cache_instance,
        ):
            register_webhook(override=True)

        captured = capsys.readouterr()
        assert "Cloud Run env vars" in captured.out
        assert "TELEGRAM_WEBHOOK_SECRET" in captured.out
