from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from tests.conftest import make_settings

from pac.config import Settings
from pac.models.portfolio import SavingsPlan
from pac.tr.client import TRClient, tr_session
from pac.tr.exceptions import TRClientError, TRConnectionError, TRSessionExpiredError


@pytest.fixture
def settings() -> Settings:
    return make_settings(
        broker={
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
            "cookies_path": "/tmp/test_cookies",
        },
    )


@pytest.fixture
def mock_api() -> AsyncMock:
    api = AsyncMock()
    api.resume_websession = AsyncMock(return_value=True)
    api.close = AsyncMock()
    api.unsubscribe = AsyncMock()
    return api


@pytest.fixture
def client(settings: Settings, mock_api: AsyncMock) -> TRClient:
    tr_client = TRClient(settings)
    tr_client._api = mock_api
    return tr_client


class TestConnect:
    async def test_connect_resumes_session(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        with patch("pytr.api.TradeRepublicApi", return_value=mock_api):
            tr_client = TRClient(settings)
            await tr_client.connect()
            mock_api.resume_websession.assert_awaited_once()

    async def test_connect_raises_on_expired_session(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        mock_api.resume_websession = AsyncMock(return_value=False)
        with patch("pytr.api.TradeRepublicApi", return_value=mock_api):
            tr_client = TRClient(settings)
            with pytest.raises(TRSessionExpiredError):
                await tr_client.connect()

    async def test_connect_raises_on_construction_failure(
        self, settings: Settings
    ) -> None:
        with patch("pytr.api.TradeRepublicApi", side_effect=RuntimeError("WAF failed")):
            tr_client = TRClient(settings)
            with pytest.raises(TRConnectionError, match="Failed to create"):
                await tr_client.connect()


class TestGetPortfolio:
    async def test_returns_snapshot_with_positions(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(return_value=1)
        mock_api.cash = AsyncMock(return_value=2)
        mock_api.instrument_details = AsyncMock(side_effect=[3, 4, 5])
        mock_api.ticker = AsyncMock(side_effect=[6, 7, 8])
        mock_api.recv = AsyncMock(
            side_effect=[
                (
                    1,
                    {},
                    {
                        "positions": [
                            {"instrumentId": "IE00BK5BQT80", "netSize": 10.0},
                            {"instrumentId": "IE00B4ND3602", "netSize": 5.0},
                            {"instrumentId": "IE00B3F81409", "netSize": 5.0},
                        ]
                    },
                ),
                (2, {}, [{"amount": 200.0, "currencyId": "EUR"}]),
                (3, {}, {"shortName": "FTSE All-World", "exchangeIds": ["LSX"]}),
                (4, {}, {"shortName": "Physical Gold", "exchangeIds": ["LSX"]}),
                (5, {}, {"shortName": "Gov Bond", "exchangeIds": ["LSX"]}),
                (6, {}, {"last": {"price": 100.0}}),
                (7, {}, {"last": {"price": 40.0}}),
                (8, {}, {"last": {"price": 20.0}}),
            ]
        )

        snapshot = await client.get_portfolio()

        assert len(snapshot.positions) == 3
        assert snapshot.cash == Decimal("200.0")
        assert snapshot.timestamp.tzinfo is not None

        stocks = next(p for p in snapshot.positions if p.isin == "IE00BK5BQT80")
        assert stocks.name == "FTSE All-World"
        assert stocks.quantity == Decimal("10.0")
        assert stocks.price == Decimal("100.0")
        assert stocks.market_value == Decimal("1000.0")
        assert stocks.asset_id == "stocks"

    async def test_maps_isin_to_asset_class(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(return_value=1)
        mock_api.cash = AsyncMock(return_value=2)
        mock_api.instrument_details = AsyncMock(side_effect=[3, 4, 5])
        mock_api.ticker = AsyncMock(side_effect=[6, 7, 8])
        mock_api.recv = AsyncMock(
            side_effect=[
                (
                    1,
                    {},
                    {
                        "positions": [
                            {"instrumentId": "IE00BK5BQT80", "netSize": 10.0},
                            {"instrumentId": "IE00B4ND3602", "netSize": 5.0},
                            {"instrumentId": "IE00B3F81409", "netSize": 5.0},
                        ]
                    },
                ),
                (2, {}, [{"amount": 0.0, "currencyId": "EUR"}]),
                (3, {}, {"shortName": "Stocks", "exchangeIds": ["LSX"]}),
                (4, {}, {"shortName": "Gold", "exchangeIds": ["LSX"]}),
                (5, {}, {"shortName": "Bonds", "exchangeIds": ["LSX"]}),
                (6, {}, {"last": {"price": 100.0}}),
                (7, {}, {"last": {"price": 40.0}}),
                (8, {}, {"last": {"price": 20.0}}),
            ]
        )

        snapshot = await client.get_portfolio()

        asset_ids = {p.isin: p.asset_id for p in snapshot.positions}
        assert asset_ids["IE00BK5BQT80"] == "stocks"
        assert asset_ids["IE00B4ND3602"] == "gold"
        assert asset_ids["IE00B3F81409"] == "bonds"

    async def test_skips_unknown_isin(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(return_value=1)
        mock_api.cash = AsyncMock(return_value=2)
        mock_api.instrument_details = AsyncMock(side_effect=[3])
        mock_api.ticker = AsyncMock(side_effect=[4])
        mock_api.recv = AsyncMock(
            side_effect=[
                (
                    1,
                    {},
                    {
                        "positions": [
                            {"instrumentId": "UNKNOWN_ISIN", "netSize": 1.0},
                        ]
                    },
                ),
                (2, {}, [{"amount": 100.0, "currencyId": "EUR"}]),
                (3, {}, {"shortName": "Unknown ETF", "exchangeIds": ["LSX"]}),
                (4, {}, {"last": {"price": 50.0}}),
            ]
        )

        snapshot = await client.get_portfolio()

        assert len(snapshot.positions) == 0
        assert snapshot.cash == Decimal("100.0")

    async def test_handles_empty_portfolio(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(return_value=1)
        mock_api.cash = AsyncMock(return_value=2)
        mock_api.recv = AsyncMock(
            side_effect=[
                (1, {}, {"positions": []}),
                (2, {}, [{"amount": 500.0, "currencyId": "EUR"}]),
            ]
        )

        snapshot = await client.get_portfolio()

        assert len(snapshot.positions) == 0
        assert snapshot.cash == Decimal("500.0")

    async def test_handles_ticker_timeout(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(return_value=1)
        mock_api.cash = AsyncMock(return_value=2)
        mock_api.instrument_details = AsyncMock(side_effect=[3])
        mock_api.ticker = AsyncMock(side_effect=[4])
        mock_api.recv = AsyncMock(
            side_effect=[
                (
                    1,
                    {},
                    {
                        "positions": [
                            {"instrumentId": "IE00BK5BQT80", "netSize": 10.0},
                        ]
                    },
                ),
                (2, {}, [{"amount": 200.0, "currencyId": "EUR"}]),
                (3, {}, {"shortName": "FTSE All-World", "exchangeIds": ["LSX"]}),
                TimeoutError(),
            ]
        )

        snapshot = await client.get_portfolio()

        assert len(snapshot.positions) == 0
        assert snapshot.cash == Decimal("200.0")


class TestGetCashBalance:
    async def test_returns_decimal(self, client: TRClient, mock_api: AsyncMock) -> None:
        mock_api.cash = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(
            return_value=(1, {}, [{"amount": 1234.56, "currencyId": "EUR"}])
        )

        balance = await client.get_cash_balance()

        assert balance == Decimal("1234.56")
        assert isinstance(balance, Decimal)

    async def test_handles_connection_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.cash = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(side_effect=TimeoutError())

        with pytest.raises(TRConnectionError):
            await client.get_cash_balance()


class TestGetSavingsPlans:
    async def test_returns_list(self, client: TRClient, mock_api: AsyncMock) -> None:
        mock_api.savings_plan_overview = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(
            return_value=(
                1,
                {},
                [
                    {
                        "instrumentId": "IE00BK5BQT80",
                        "name": "FTSE All-World",
                        "amount": 350.0,
                        "interval": "monthly",
                    },
                    {
                        "instrumentId": "IE00B4ND3602",
                        "name": "Physical Gold",
                        "amount": 75.0,
                        "interval": "monthly",
                    },
                ],
            )
        )

        plans = await client.get_savings_plans()

        assert len(plans) == 2
        assert isinstance(plans[0], SavingsPlan)
        assert plans[0].isin == "IE00BK5BQT80"
        assert plans[0].amount == Decimal("350.0")
        assert plans[0].interval == "monthly"
        assert plans[0].asset_id == "stocks"
        assert plans[1].asset_id == "gold"

    async def test_empty_plans(self, client: TRClient, mock_api: AsyncMock) -> None:
        mock_api.savings_plan_overview = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(return_value=(1, {}, []))

        plans = await client.get_savings_plans()

        assert plans == []

    async def test_skips_unparseable_plans(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.savings_plan_overview = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(
            return_value=(
                1,
                {},
                [
                    {"instrumentId": "IE00BK5BQT80", "amount": 100.0},
                    "not_a_dict",  # malformed entry
                ],
            )
        )

        plans = await client.get_savings_plans()

        assert len(plans) == 1
        assert plans[0].isin == "IE00BK5BQT80"


class TestClose:
    async def test_close_calls_api_close(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        await client.close()

        mock_api.close.assert_awaited_once()

    async def test_close_noop_when_no_api(self, settings: Settings) -> None:
        tr_client = TRClient(settings)
        # _api is None by default — close should not raise
        await tr_client.close()


class TestTrSession:
    async def test_yields_connected_client(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        with patch("pytr.api.TradeRepublicApi", return_value=mock_api):
            async with tr_session(settings) as client:
                assert isinstance(client, TRClient)
                mock_api.resume_websession.assert_awaited_once()

    async def test_closes_connection_on_normal_exit(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        with patch("pytr.api.TradeRepublicApi", return_value=mock_api):
            async with tr_session(settings):
                pass

        mock_api.close.assert_awaited_once()

    async def test_closes_connection_on_exception(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        with (
            patch("pytr.api.TradeRepublicApi", return_value=mock_api),
            pytest.raises(RuntimeError, match="boom"),
        ):
            async with tr_session(settings):
                raise RuntimeError("boom")

        mock_api.close.assert_awaited_once()

    async def test_propagates_connect_error(
        self, settings: Settings, mock_api: AsyncMock
    ) -> None:
        mock_api.resume_websession = AsyncMock(return_value=False)
        with (
            patch("pytr.api.TradeRepublicApi", return_value=mock_api),
            pytest.raises(TRSessionExpiredError),
        ):
            async with tr_session(settings):
                pass  # pragma: no cover


class TestSubscribeOneErrorWrapping:
    async def test_trade_republic_error_wrapped_as_client_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        # Create an exception whose class name contains "TradeRepublicError"
        class TradeRepublicError(Exception):
            pass

        mock_api.cash = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(side_effect=TradeRepublicError("invalid request"))

        with pytest.raises(TRClientError, match="TR API error"):
            await client.get_cash_balance()

    async def test_connection_closed_wrapped_as_connection_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        class ConnectionClosed(Exception):
            pass

        mock_api.cash = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(side_effect=ConnectionClosed("gone"))

        with pytest.raises(TRConnectionError, match="TR connection closed"):
            await client.get_cash_balance()

    async def test_unexpected_error_wrapped_as_client_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.cash = AsyncMock(return_value=1)
        mock_api.recv = AsyncMock(side_effect=ValueError("something odd"))

        with pytest.raises(TRClientError, match="Unexpected error"):
            await client.get_cash_balance()


class TestGetPortfolioErrorWrapping:
    async def test_trade_republic_error_wrapped_as_client_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        class TradeRepublicError(Exception):
            pass

        mock_api.compact_portfolio = AsyncMock(
            side_effect=TradeRepublicError("API fail")
        )

        with pytest.raises(TRClientError, match="TR API error"):
            await client.get_portfolio()

    async def test_timeout_wrapped_as_connection_error(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(side_effect=TimeoutError())

        with pytest.raises(TRConnectionError, match="TR request timed out"):
            await client.get_portfolio()

    async def test_existing_client_error_not_double_wrapped(
        self, client: TRClient, mock_api: AsyncMock
    ) -> None:
        mock_api.compact_portfolio = AsyncMock(
            side_effect=TRClientError("original error")
        )

        with pytest.raises(TRClientError, match="original error"):
            await client.get_portfolio()
