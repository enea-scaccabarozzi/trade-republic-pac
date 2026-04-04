from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from pac.app import app
from pac.orchestrator import DispatchResult, SignalNotFoundError


@pytest.fixture()
def mock_orchestrator() -> MagicMock:
    """Create a mock orchestrator with sensible defaults."""
    orch = MagicMock()
    orch.settings = MagicMock()
    orch.settings.app.job_secret = "test-job-secret"

    orch.dispatch_signal = AsyncMock(
        return_value=DispatchResult(
            signal_name="deviation_check",
            signal_count=2,
            delivered=True,
        )
    )

    mock_channel = MagicMock()
    mock_channel.webhook_secret = "test-webhook-secret"
    mock_channel.process_update = AsyncMock()
    orch.get_channel = MagicMock(return_value=mock_channel)

    orch.start = AsyncMock()
    orch.stop = AsyncMock()

    return orch


@pytest.fixture()
def client(mock_orchestrator: MagicMock) -> TestClient:  # type: ignore[misc]
    """Test client with orchestrator injected — bypasses lifespan."""
    with (
        patch("pac.app.Orchestrator") as mock_orch_cls,
        patch("pac.app.load_config") as mock_load,
    ):
        mock_orch_cls.from_settings.return_value = mock_orchestrator
        mock_load.return_value = mock_orchestrator.settings

        with TestClient(app) as c:
            yield c


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
    mock_orchestrator: MagicMock,
) -> None:
    resp = client.post(
        "/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_orchestrator.get_channel.return_value.process_update.assert_called_once()


def test_run_signal_rejects_invalid_secret(client: TestClient) -> None:
    resp = client.post(
        "/jobs/signal/deviation_check",
        headers={"X-Job-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_run_signal_unknown_signal_returns_404(
    client: TestClient,
    mock_orchestrator: MagicMock,
) -> None:
    mock_orchestrator.dispatch_signal = AsyncMock(
        side_effect=SignalNotFoundError("nonexistent"),
    )
    resp = client.post(
        "/jobs/signal/nonexistent",
        headers={"X-Job-Secret": "test-job-secret"},
    )
    assert resp.status_code == 404


def test_run_signal_dispatches_and_returns_result(client: TestClient) -> None:
    resp = client.post(
        "/jobs/signal/deviation_check",
        headers={"X-Job-Secret": "test-job-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["signals"] == 2
    assert body["delivered"] is True


def test_run_signal_internal_error_returns_500(
    client: TestClient,
    mock_orchestrator: MagicMock,
) -> None:
    mock_orchestrator.dispatch_signal = AsyncMock(
        side_effect=RuntimeError("boom"),
    )
    resp = client.post(
        "/jobs/signal/deviation_check",
        headers={"X-Job-Secret": "test-job-secret"},
    )
    assert resp.status_code == 500


def test_old_routes_removed(client: TestClient) -> None:
    """Verify legacy routes return 404/405."""
    resp = client.post("/jobs/hourly-check")
    assert resp.status_code in (404, 405)
    resp = client.post("/jobs/monthly-pac")
    assert resp.status_code in (404, 405)
