from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.orchestrator import Orchestrator, SignalNotFoundError

_NOW = datetime(2026, 4, 1, tzinfo=UTC)


# ── Scenarios ───────────────────────────────────────────────────────────


@scenario(
    "../features/signal_dispatch.feature",
    "Dispatch a configured signal that fires",
)
def test_dispatch_fires() -> None:
    pass


@scenario(
    "../features/signal_dispatch.feature",
    "Dispatch a configured signal that does not fire",
)
def test_dispatch_no_fire() -> None:
    pass


@scenario(
    "../features/signal_dispatch.feature",
    "Dispatch an unknown signal",
)
def test_dispatch_unknown() -> None:
    pass


@scenario(
    "../features/signal_dispatch.feature",
    "Evaluate signal returns results without sending",
)
def test_evaluate_without_send() -> None:
    pass


@scenario(
    "../features/signal_dispatch.feature",
    "Dispatch continues when one channel fails",
)
def test_dispatch_continues_on_channel_failure() -> None:
    pass


@scenario(
    "../features/signal_dispatch.feature",
    "Dispatch with no configured channels skips delivery",
)
def test_dispatch_no_channels() -> None:
    pass


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def dispatch_context() -> dict[str, Any]:
    return {}


# ── Steps ───────────────────────────────────────────────────────────────


@given("a portfolio with deviations above threshold", target_fixture="snapshot")
def snapshot_with_deviations() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal("10"),
                price=Decimal("80"),
                market_value=Decimal("800"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold ETC",
                quantity=Decimal("5"),
                price=Decimal("20"),
                market_value=Decimal("100"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal("5"),
                price=Decimal("20"),
                market_value=Decimal("100"),
                asset_id="bonds",
            ),
        ],
        cash=Decimal("0"),
        timestamp=_NOW,
    )


@given("a balanced portfolio within thresholds", target_fixture="snapshot")
def balanced_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal("1"),
                price=Decimal("700"),
                market_value=Decimal("700"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold ETC",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal("1"),
                price=Decimal("150"),
                market_value=Decimal("150"),
                asset_id="bonds",
            ),
        ],
        cash=Decimal("0"),
        timestamp=_NOW,
    )


@given(
    parsers.parse('a signal "{sig_name}" configured with rule "{rule_name}"'),
    target_fixture="orchestrator",
)
def orchestrator_with_signal(
    sig_name: str,
    rule_name: str,
    snapshot: PortfolioSnapshot,
) -> Orchestrator:
    settings = Settings.model_validate(
        {
            "version": 1,
            "app": {"job_secret": "test"},
            "broker": {
                "type": "trade_republic",
                "phone_number": "+49",
                "pin": "1234",
            },
            "assets": [
                {
                    "id": "stocks",
                    "name": "Stocks ETF",
                    "isin": "IE00BK5BQT80",
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "target_pct": 15,
                },
            ],
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [
                {
                    "name": sig_name,
                    "rule": rule_name,
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                    "template": "threshold_alert",
                }
            ],
        }
    )
    orch = Orchestrator.from_settings(settings)
    # Mock the channel to track sends
    orch._channels["telegram"].send = AsyncMock()  # type: ignore[method-assign]
    return orch


@when("the signal is dispatched", target_fixture="dispatch_result")
def dispatch_signal(
    orchestrator: Orchestrator,
    snapshot: PortfolioSnapshot,
    dispatch_context: dict[str, Any],
) -> Any:
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=snapshot)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("pac.orchestrator.orchestrator.tr_session", return_value=mock_ctx):
        result = asyncio.run(orchestrator.dispatch_signal("deviation_check"))
        dispatch_context["result"] = result
        return result


@when(
    parsers.parse('the signal "{sig_name}" is dispatched'),
    target_fixture="dispatch_error",
)
def dispatch_unknown_signal(sig_name: str) -> Exception | None:
    settings = Settings.model_validate(
        {
            "version": 1,
            "app": {"job_secret": "test"},
            "broker": {
                "type": "trade_republic",
                "phone_number": "+49",
                "pin": "1234",
            },
            "assets": [
                {
                    "id": "stocks",
                    "name": "Stocks ETF",
                    "isin": "IE00BK5BQT80",
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "target_pct": 15,
                },
            ],
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [],
        }
    )
    orch = Orchestrator.from_settings(settings)
    try:
        asyncio.run(orch.dispatch_signal(sig_name))
    except SignalNotFoundError as e:
        return e
    return None


@when("the signal is evaluated without dispatch", target_fixture="eval_result")
def evaluate_signal(
    orchestrator: Orchestrator,
    snapshot: PortfolioSnapshot,
) -> list[Any]:
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=snapshot)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("pac.orchestrator.orchestrator.tr_session", return_value=mock_ctx):
        return asyncio.run(orchestrator.evaluate_signal("deviation_check"))


@then("the rule is evaluated with configured params")
def rule_evaluated(dispatch_context: dict[str, Any]) -> None:
    result = dispatch_context["result"]
    assert result.signal_count > 0


@then("the message is sent to all configured channels")
def message_sent(orchestrator: Orchestrator) -> None:
    channel = orchestrator._channels["telegram"]
    channel.send.assert_called()  # type: ignore[attr-defined]


@then("no messages are sent")
def no_messages_sent(orchestrator: Orchestrator) -> None:
    channel = orchestrator._channels["telegram"]
    channel.send.assert_not_called()  # type: ignore[attr-defined]


@then("the result shows zero signals")
def zero_signals(dispatch_context: dict[str, Any]) -> None:
    result = dispatch_context["result"]
    assert result.signal_count == 0
    assert result.delivered is False


@then("a signal-not-found error is raised")
def signal_not_found_error(dispatch_error: Exception | None) -> None:
    assert isinstance(dispatch_error, SignalNotFoundError)


@then("signals are returned")
def signals_returned(eval_result: list[Any]) -> None:
    assert isinstance(eval_result, list)


@then("no messages are sent through channels")
def no_messages_through_channels(orchestrator: Orchestrator) -> None:
    channel = orchestrator._channels["telegram"]
    channel.send.assert_not_called()  # type: ignore[attr-defined]


@given("one channel is configured to fail on send")
def configure_failing_channel(orchestrator: Orchestrator) -> None:
    channel = orchestrator._channels["telegram"]
    channel.send = AsyncMock(side_effect=RuntimeError("send failed"))  # type: ignore[method-assign]


@then("the result shows signals were delivered")
def result_delivered(dispatch_context: dict[str, Any]) -> None:
    result = dispatch_context["result"]
    assert result.signal_count > 0
    assert result.delivered is True


@then("the failing channel attempted to send")
def failing_channel_attempted(orchestrator: Orchestrator) -> None:
    channel = orchestrator._channels["telegram"]
    channel.send.assert_called()  # type: ignore[attr-defined]


@given(
    parsers.parse('a signal "{sig_name}" configured with no channels'),
    target_fixture="orchestrator",
)
def orchestrator_with_no_channels(
    sig_name: str,
    snapshot: PortfolioSnapshot,
) -> Orchestrator:
    settings = Settings.model_validate(
        {
            "version": 1,
            "app": {"job_secret": "test"},
            "broker": {
                "type": "trade_republic",
                "phone_number": "+49",
                "pin": "1234",
            },
            "assets": [
                {
                    "id": "stocks",
                    "name": "Stocks ETF",
                    "isin": "IE00BK5BQT80",
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold ETC",
                    "isin": "IE00B4ND3602",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bond ETF",
                    "isin": "IE00B3F81409",
                    "target_pct": 15,
                },
            ],
            "channels": {
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                }
            },
            "signals": [
                {
                    "name": sig_name,
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": [],
                    "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                    "template": "threshold_alert",
                }
            ],
        }
    )
    return Orchestrator.from_settings(settings)


@when(
    parsers.parse('the signal "{sig_name}" is dispatched through the orchestrator'),
    target_fixture="dispatch_result",
)
def dispatch_named_signal(
    sig_name: str,
    orchestrator: Orchestrator,
    snapshot: PortfolioSnapshot,
    dispatch_context: dict[str, Any],
) -> Any:
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=snapshot)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("pac.orchestrator.orchestrator.tr_session", return_value=mock_ctx):
        result = asyncio.run(orchestrator.dispatch_signal(sig_name))
        dispatch_context["result"] = result
        return result


@then("the result shows signals were fired but delivered is true")
def signals_fired_delivered(dispatch_context: dict[str, Any]) -> None:
    result = dispatch_context["result"]
    assert result.signal_count > 0
    assert result.delivered is True
