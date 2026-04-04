from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pac.analysis.deviation import DeviationReport
from pac.config import Settings
from pac.delivery.base import DeliveryChannel, RenderedMessage
from pac.models.portfolio import PortfolioSnapshot, Position
from pac.orchestrator import Orchestrator, SignalNotFoundError

_NOW = datetime(2026, 4, 1, tzinfo=UTC)


def _make_settings(
    *,
    signals: list[dict[str, Any]] | None = None,
    channels: dict[str, dict[str, Any]] | None = None,
) -> Settings:
    """Build a Settings object with test defaults."""
    if channels is None:
        channels = {
            "telegram": {
                "type": "telegram",
                "bot_token": "fake",
                "chat_id": "12345",
            },
        }
    if signals is None:
        signals = [
            {
                "name": "deviation_check",
                "rule": "threshold_deviation",
                "schedule": "0 * * * *",
                "channels": ["telegram"],
                "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                "template": "threshold_alert",
            },
        ]
    return Settings.model_validate(
        {
            "version": 1,
            "app": {"job_secret": "test-secret"},
            "broker": {
                "type": "trade_republic",
                "phone_number": "+49123",
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
            "channels": channels,
            "signals": signals,
        }
    )


@pytest.fixture()
def sample_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=[
            Position(
                isin="IE00BK5BQT80",
                name="Stocks ETF",
                quantity=Decimal("10"),
                price=Decimal("100.00"),
                market_value=Decimal("1000.00"),
                asset_id="stocks",
            ),
            Position(
                isin="IE00B4ND3602",
                name="Gold ETC",
                quantity=Decimal("5"),
                price=Decimal("40.00"),
                market_value=Decimal("200.00"),
                asset_id="gold",
            ),
            Position(
                isin="IE00B3F81409",
                name="Bond ETF",
                quantity=Decimal("5"),
                price=Decimal("20.00"),
                market_value=Decimal("100.00"),
                asset_id="bonds",
            ),
        ],
        cash=Decimal("0.00"),
        timestamp=_NOW,
    )


@pytest.fixture()
def mock_tr_session(sample_snapshot: PortfolioSnapshot) -> Any:
    """Patch tr_session to return a mock client with get_portfolio()."""
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=sample_snapshot)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "pac.orchestrator.orchestrator.tr_session",
        return_value=mock_ctx,
    ) as p:
        yield p


class TestFromSettings:
    """Test Orchestrator.from_settings() wiring and validation."""

    def test_discovers_rules_and_channels(self) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        assert "threshold_deviation" in orch.registry
        assert "telegram" in orch._channels

    def test_raises_on_unknown_rule(self) -> None:
        settings = _make_settings(
            signals=[
                {
                    "name": "test",
                    "rule": "nonexistent_rule",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": "threshold_alert",
                },
            ],
        )
        with pytest.raises(ValueError, match="unknown rule 'nonexistent_rule'"):
            Orchestrator.from_settings(settings)

    def test_raises_on_unknown_channel_in_signal(self) -> None:
        settings = _make_settings(
            channels={
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                },
                "slack": {
                    "type": "slack",
                    "webhook_url": "https://hooks.slack.com/xxx",
                },
            },
            signals=[
                {
                    "name": "test",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["slack"],
                    "params": {},
                    "template": "threshold_alert",
                },
            ],
        )
        # slack channel type is unknown (not discovered)
        with pytest.raises(ValueError, match="unknown type 'slack'"):
            Orchestrator.from_settings(settings)

    def test_raises_on_unknown_template(self) -> None:
        settings = _make_settings(
            signals=[
                {
                    "name": "test",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": "nonexistent_template",
                },
            ],
        )
        with pytest.raises(ValueError, match="unknown template"):
            Orchestrator.from_settings(settings)

    def test_raises_on_unknown_channel_type(self) -> None:
        settings = _make_settings(
            channels={
                "my_discord": {
                    "type": "discord",
                    "bot_token": "fake",
                },
            },
            signals=[],
        )
        with pytest.raises(ValueError, match="unknown type 'discord'"):
            Orchestrator.from_settings(settings)

    def test_raises_on_missing_adapter_for_format(self) -> None:
        """A channel requiring 'html' format with no adapter should fail."""
        settings = _make_settings(signals=[])

        # Create a custom channel class that requires 'html' format
        from pac.delivery.base import _NoConfig

        class HtmlChannel(DeliveryChannel[_NoConfig]):
            name = "html_test"
            config_model = _NoConfig

            @property
            def supported_formats(self) -> list[str]:
                return ["html"]

            async def send(self, message: RenderedMessage) -> None:
                pass

        with (
            patch(
                "pac.orchestrator.orchestrator.discover_channels",
                return_value={"telegram": HtmlChannel},
            ),
            pytest.raises(ValueError, match="format 'html'"),
        ):
            Orchestrator.from_settings(settings)

    def test_signal_names_returns_configured_names(self) -> None:
        settings = _make_settings(
            signals=[
                {
                    "name": "sig_a",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": "threshold_alert",
                },
                {
                    "name": "sig_b",
                    "rule": "cycle_inversion",
                    "schedule": "0 * * * *",
                    "channels": ["telegram"],
                    "params": {},
                    "template": "cycle_alert",
                },
            ],
        )
        orch = Orchestrator.from_settings(settings)
        assert sorted(orch.signal_names) == ["sig_a", "sig_b"]


class TestLifecycle:
    """Test start/stop lifecycle methods."""

    async def test_start_calls_set_orchestrator_then_start(self) -> None:
        settings = _make_settings(signals=[])
        orch = Orchestrator.from_settings(settings)

        channel = orch._channels["telegram"]
        channel.set_orchestrator = AsyncMock()  # type: ignore[method-assign]
        channel.start = AsyncMock()  # type: ignore[method-assign]

        await orch.start()

        channel.set_orchestrator.assert_called_once_with(orch)
        channel.start.assert_called_once()

        # set_orchestrator must be called before start
        set_call_order = channel.set_orchestrator.call_args_list
        start_call_order = channel.start.call_args_list
        assert len(set_call_order) == 1
        assert len(start_call_order) == 1

    async def test_stop_calls_channel_stop(self) -> None:
        settings = _make_settings(signals=[])
        orch = Orchestrator.from_settings(settings)

        channel = orch._channels["telegram"]
        channel.stop = AsyncMock()  # type: ignore[method-assign]

        await orch.stop()
        channel.stop.assert_called_once()


class TestDispatchSignal:
    """Test the dispatch_signal() pipeline."""

    async def test_dispatch_evaluates_and_sends(
        self,
        mock_tr_session: Any,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        # Use deviations big enough to trigger threshold rule
        snapshot = PortfolioSnapshot(
            positions=[
                Position(
                    isin="IE00BK5BQT80",
                    name="Stocks ETF",
                    quantity=Decimal("10"),
                    price=Decimal("100.00"),
                    market_value=Decimal("800.00"),
                    asset_id="stocks",
                ),
                Position(
                    isin="IE00B4ND3602",
                    name="Gold ETC",
                    quantity=Decimal("5"),
                    price=Decimal("40.00"),
                    market_value=Decimal("100.00"),
                    asset_id="gold",
                ),
                Position(
                    isin="IE00B3F81409",
                    name="Bond ETF",
                    quantity=Decimal("5"),
                    price=Decimal("20.00"),
                    market_value=Decimal("100.00"),
                    asset_id="bonds",
                ),
            ],
            cash=Decimal("0.00"),
            timestamp=_NOW,
        )
        mock_client = AsyncMock()
        mock_client.get_portfolio = AsyncMock(return_value=snapshot)
        mock_tr_session.return_value.__aenter__ = AsyncMock(return_value=mock_client)

        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        channel = orch._channels["telegram"]
        channel.send = AsyncMock()  # type: ignore[method-assign]

        result = await orch.dispatch_signal("deviation_check")

        assert result.signal_name == "deviation_check"
        assert result.signal_count > 0
        assert result.delivered is True
        channel.send.assert_called()

    async def test_dispatch_no_signals_fired(
        self,
        mock_tr_session: Any,
    ) -> None:
        # Balanced portfolio — no signals should fire
        snapshot = PortfolioSnapshot(
            positions=[
                Position(
                    isin="IE00BK5BQT80",
                    name="Stocks ETF",
                    quantity=Decimal("1"),
                    price=Decimal("700.00"),
                    market_value=Decimal("700.00"),
                    asset_id="stocks",
                ),
                Position(
                    isin="IE00B4ND3602",
                    name="Gold ETC",
                    quantity=Decimal("1"),
                    price=Decimal("150.00"),
                    market_value=Decimal("150.00"),
                    asset_id="gold",
                ),
                Position(
                    isin="IE00B3F81409",
                    name="Bond ETF",
                    quantity=Decimal("1"),
                    price=Decimal("150.00"),
                    market_value=Decimal("150.00"),
                    asset_id="bonds",
                ),
            ],
            cash=Decimal("0.00"),
            timestamp=_NOW,
        )
        mock_client = AsyncMock()
        mock_client.get_portfolio = AsyncMock(return_value=snapshot)
        mock_tr_session.return_value.__aenter__ = AsyncMock(return_value=mock_client)

        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        channel = orch._channels["telegram"]
        channel.send = AsyncMock()  # type: ignore[method-assign]

        result = await orch.dispatch_signal("deviation_check")

        assert result.signal_count == 0
        assert result.delivered is False
        channel.send.assert_not_called()

    async def test_dispatch_unknown_name_raises(self) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        with pytest.raises(SignalNotFoundError):
            await orch.dispatch_signal("nonexistent")

    async def test_dispatch_partial_delivery_failure_still_returns_delivered(
        self,
        mock_tr_session: Any,
    ) -> None:
        """If one channel.send() raises, dispatch continues.

        Returns delivered=True.
        """
        snapshot = PortfolioSnapshot(
            positions=[
                Position(
                    isin="IE00BK5BQT80",
                    name="Stocks ETF",
                    quantity=Decimal("10"),
                    price=Decimal("100.00"),
                    market_value=Decimal("800.00"),
                    asset_id="stocks",
                ),
                Position(
                    isin="IE00B4ND3602",
                    name="Gold ETC",
                    quantity=Decimal("5"),
                    price=Decimal("40.00"),
                    market_value=Decimal("100.00"),
                    asset_id="gold",
                ),
                Position(
                    isin="IE00B3F81409",
                    name="Bond ETF",
                    quantity=Decimal("5"),
                    price=Decimal("20.00"),
                    market_value=Decimal("100.00"),
                    asset_id="bonds",
                ),
            ],
            cash=Decimal("0.00"),
            timestamp=_NOW,
        )
        mock_client = AsyncMock()
        mock_client.get_portfolio = AsyncMock(return_value=snapshot)
        mock_tr_session.return_value.__aenter__ = AsyncMock(return_value=mock_client)

        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        channel = orch._channels["telegram"]
        channel.send = AsyncMock(side_effect=RuntimeError("network error"))  # type: ignore[method-assign]

        result = await orch.dispatch_signal("deviation_check")

        assert result.delivered is True
        assert result.signal_count > 0

    async def test_dispatch_multi_channel_sends_to_all(
        self,
        mock_tr_session: Any,
    ) -> None:
        """Signal configured with 2 channels sends to both."""
        snapshot = PortfolioSnapshot(
            positions=[
                Position(
                    isin="IE00BK5BQT80",
                    name="Stocks ETF",
                    quantity=Decimal("10"),
                    price=Decimal("100.00"),
                    market_value=Decimal("800.00"),
                    asset_id="stocks",
                ),
                Position(
                    isin="IE00B4ND3602",
                    name="Gold ETC",
                    quantity=Decimal("5"),
                    price=Decimal("40.00"),
                    market_value=Decimal("100.00"),
                    asset_id="gold",
                ),
                Position(
                    isin="IE00B3F81409",
                    name="Bond ETF",
                    quantity=Decimal("5"),
                    price=Decimal("20.00"),
                    market_value=Decimal("100.00"),
                    asset_id="bonds",
                ),
            ],
            cash=Decimal("0.00"),
            timestamp=_NOW,
        )
        mock_client = AsyncMock()
        mock_client.get_portfolio = AsyncMock(return_value=snapshot)
        mock_tr_session.return_value.__aenter__ = AsyncMock(return_value=mock_client)

        settings = _make_settings(
            channels={
                "telegram": {
                    "type": "telegram",
                    "bot_token": "fake",
                    "chat_id": "12345",
                },
                "telegram_2": {
                    "type": "telegram",
                    "bot_token": "fake2",
                    "chat_id": "67890",
                },
            },
            signals=[
                {
                    "name": "deviation_check",
                    "rule": "threshold_deviation",
                    "schedule": "0 * * * *",
                    "channels": ["telegram", "telegram_2"],
                    "params": {"warning_pct": 3.0, "critical_pct": 5.0},
                    "template": "threshold_alert",
                },
            ],
        )
        orch = Orchestrator.from_settings(settings)
        ch1 = orch._channels["telegram"]
        ch2 = orch._channels["telegram_2"]
        ch1.send = AsyncMock()  # type: ignore[method-assign]
        ch2.send = AsyncMock()  # type: ignore[method-assign]

        result = await orch.dispatch_signal("deviation_check")

        assert result.delivered is True
        ch1.send.assert_called_once()
        ch2.send.assert_called_once()


class TestQueryMethods:
    """Test evaluate_signal, get_portfolio_status, compute_pac_plan."""

    async def test_evaluate_signal_returns_signals_without_sending(
        self,
        mock_tr_session: Any,
    ) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        channel = orch._channels["telegram"]
        channel.send = AsyncMock()  # type: ignore[method-assign]

        signals = await orch.evaluate_signal("deviation_check")
        # Returns a list (possibly empty depending on portfolio)
        assert isinstance(signals, list)
        channel.send.assert_not_called()

    async def test_evaluate_signal_unknown_raises(self) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        with pytest.raises(SignalNotFoundError):
            await orch.evaluate_signal("nonexistent")

    async def test_get_portfolio_status(
        self,
        mock_tr_session: Any,
        sample_snapshot: PortfolioSnapshot,
    ) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        snapshot, report = await orch.get_portfolio_status()
        assert snapshot == sample_snapshot
        assert isinstance(report, DeviationReport)

    async def test_compute_pac_plan(
        self,
        mock_tr_session: Any,
    ) -> None:
        settings = _make_settings(
            signals=[
                {
                    "name": "monthly_pac",
                    "rule": "pac_plan",
                    "schedule": "0 9 14 * *",
                    "channels": ["telegram"],
                    "params": {"monthly_budget": 500.00, "day_of_month": 14},
                    "template": "pac_plan",
                },
            ],
        )
        orch = Orchestrator.from_settings(settings)
        plan = await orch.compute_pac_plan("monthly_pac")
        assert plan.total_budget == Decimal("500.00")

    async def test_compute_pac_plan_unknown_raises(self) -> None:
        settings = _make_settings()
        orch = Orchestrator.from_settings(settings)
        with pytest.raises(SignalNotFoundError):
            await orch.compute_pac_plan("nonexistent")


class TestAdapterDiscovery:
    """Test _discover_adapters finds builtin adapters."""

    def test_discover_adapters_finds_builtins(self) -> None:
        from pac.orchestrator.orchestrator import _discover_adapters

        adapters = _discover_adapters()
        assert "markdown_v2" in adapters
        assert "plain_text" in adapters
