from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from pac.models.portfolio import AssetClass, PortfolioSnapshot, Position
from pac.models.signals import Signal, SignalSeverity

_NOW = datetime(2026, 4, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars for Settings to load."""
    monkeypatch.setenv("PAC_TR_PHONE_NUMBER", "+491234567890")
    monkeypatch.setenv("PAC_TR_PIN", "1234")
    monkeypatch.setenv("PAC_TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("PAC_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("PAC_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("PAC_JOB_SECRET", "test-job-secret")
    monkeypatch.setenv("PAC_WEBHOOK_URL", "")


@pytest.fixture
def sample_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Vanguard FTSE All-World",
                quantity=Decimal("10"),
                price=Decimal("100.00"),
                market_value=Decimal("1000.00"),
                asset_class=AssetClass.STOCKS,
            ),
            Position(
                isin="IE00B4ND3602",
                name="iShares Physical Gold",
                quantity=Decimal("5"),
                price=Decimal("40.00"),
                market_value=Decimal("200.00"),
                asset_class=AssetClass.GOLD,
            ),
            Position(
                isin="IE00B3F81409",
                name="Vanguard Gov Bond",
                quantity=Decimal("5"),
                price=Decimal("20.00"),
                market_value=Decimal("100.00"),
                asset_class=AssetClass.BONDS,
            ),
        ],
        cash=Decimal("200.00"),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )


@pytest.fixture
def mock_ptb_app() -> MagicMock:
    """Mock PTB Application that skips real Telegram connections."""
    ptb = MagicMock()
    ptb.initialize = AsyncMock()
    ptb.start = AsyncMock()
    ptb.stop = AsyncMock()
    ptb.shutdown = AsyncMock()
    ptb.process_update = AsyncMock()
    ptb.bot = MagicMock()
    ptb.bot.set_webhook = AsyncMock()
    ptb.bot.delete_webhook = AsyncMock()
    ptb.bot.send_message = AsyncMock()
    return ptb


@pytest.fixture
def client(
    mock_ptb_app: MagicMock,
    sample_snapshot: PortfolioSnapshot,
) -> TestClient:
    """TestClient with mocked PTB app and TR session."""
    with (
        patch("pac.app.create_bot", return_value=mock_ptb_app),
        patch("pac.app.tr_session") as mock_tr_ctx,
    ):
        mock_tr = AsyncMock()
        mock_tr.get_portfolio = AsyncMock(return_value=sample_snapshot)
        mock_tr_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_tr)
        mock_tr_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from pac.app import app

        with TestClient(app) as tc:
            yield tc


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_rejects_invalid_secret(client: TestClient) -> None:
    resp = client.post(
        "/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_webhook_accepts_valid_update(
    client: TestClient,
    mock_ptb_app: MagicMock,
) -> None:
    resp = client.post(
        "/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_ptb_app.process_update.assert_called_once()


def test_hourly_check_rejects_invalid_secret(client: TestClient) -> None:
    resp = client.post(
        "/jobs/hourly-check",
        headers={"X-Job-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_hourly_check_no_signals(client: TestClient) -> None:
    with patch("pac.app.SignalRegistry.evaluate_all", return_value=[]):
        resp = client.post(
            "/jobs/hourly-check",
            headers={"X-Job-Secret": "test-job-secret"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["signals"] == 0


def test_hourly_check_with_signals(
    client: TestClient,
    mock_ptb_app: MagicMock,
) -> None:
    signals = [
        Signal(
            name="threshold_deviation",
            severity=SignalSeverity.WARNING,
            message="STOCKS deviation +3.5%",
            triggered_at=_NOW,
        ),
    ]
    with patch(
        "pac.app.SignalRegistry.evaluate_all",
        return_value=signals,
    ):
        resp = client.post(
            "/jobs/hourly-check",
            headers={"X-Job-Secret": "test-job-secret"},
        )
    assert resp.status_code == 200
    assert resp.json()["signals"] == 1


def test_monthly_pac_rejects_invalid_secret(client: TestClient) -> None:
    resp = client.post(
        "/jobs/monthly-pac",
        headers={"X-Job-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_monthly_pac_sends_notification(
    client: TestClient,
    mock_ptb_app: MagicMock,
) -> None:
    with patch("pac.app.send_pac_notification", new_callable=AsyncMock) as mock_send:
        resp = client.post(
            "/jobs/monthly-pac",
            headers={"X-Job-Secret": "test-job-secret"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_send.assert_called_once()
