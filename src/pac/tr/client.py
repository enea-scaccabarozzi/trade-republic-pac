from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

from pac.models.portfolio import (
    PortfolioSnapshot,
    Position,
    SavingsPlan,
)
from pac.tr.exceptions import (
    TRClientError,
    TRConnectionError,
    TRSessionExpiredError,
)

if TYPE_CHECKING:
    from pac.config import Settings

logger = structlog.get_logger()


class TRClient:
    """Read-only async client for Trade Republic via pytr."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api: Any = None
        self._isin_to_asset_id: dict[str, str] = settings.isin_to_asset_id

    async def connect(self) -> None:
        """Connect to Trade Republic and resume session from cookies.

        Raises:
            TRSessionExpiredError: If session cookies are expired or missing.
            TRConnectionError: If the connection fails.
        """
        from pytr.api import TradeRepublicApi

        try:
            self._api = TradeRepublicApi(
                phone_no=self._settings.broker.phone_number,
                pin=self._settings.broker.pin,
                save_cookies=True,
                cookies_file=self._settings.broker.cookies_path,
            )
        except Exception as exc:
            raise TRConnectionError(f"Failed to create TR API client: {exc}") from exc

        resumed = await self._api.resume_websession()
        if not resumed:
            raise TRSessionExpiredError(
                "TR session expired — re-authentication required"
            )
        logger.info("tr_session_resumed")

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._api is not None:
            await self._api.close()

    async def _subscribe_one(
        self, subscription_fut: Any, *, timeout: float = 10.0
    ) -> Any:
        """Subscribe, receive one response, and unsubscribe.

        Args:
            subscription_fut: Awaitable returning a subscription ID.
            timeout: Seconds to wait for a response.

        Returns:
            The response payload.

        Raises:
            TRClientError: On API error.
            TRConnectionError: On timeout or connection failure.
        """
        try:
            sub_id = await subscription_fut
            while True:
                recv_sub_id, _sub_dict, payload = await asyncio.wait_for(
                    self._api.recv(), timeout=timeout
                )
                if recv_sub_id == sub_id:
                    await self._api.unsubscribe(sub_id)
                    return payload
                # SAFETY: responses for other sub IDs are discarded;
                # assumes no concurrent subscriptions
        except (TRClientError, TRConnectionError):
            raise
        except TimeoutError as exc:
            raise TRConnectionError("TR request timed out") from exc
        except Exception as exc:
            if "TradeRepublicError" in type(exc).__name__:
                raise TRClientError(f"TR API error: {exc}") from exc
            if "ConnectionClosed" in type(exc).__name__:
                raise TRConnectionError(f"TR connection closed: {exc}") from exc
            raise TRClientError(f"Unexpected error: {exc}") from exc

    async def get_portfolio(self) -> PortfolioSnapshot:
        """Fetch current portfolio snapshot with positions and cash.

        Returns:
            PortfolioSnapshot with typed positions and computed allocations.
        """
        try:
            return await self._fetch_portfolio()
        except (TRClientError, TRConnectionError):
            raise
        except TimeoutError as exc:
            raise TRConnectionError("TR request timed out") from exc
        except Exception as exc:
            if "TradeRepublicError" in type(exc).__name__:
                raise TRClientError(f"TR API error: {exc}") from exc
            raise TRClientError(f"Unexpected error: {exc}") from exc

    async def _fetch_portfolio(self) -> PortfolioSnapshot:
        """Internal portfolio fetch with parallel subscriptions."""
        # Step 1: Fetch positions and cash in parallel
        sub_portfolio = await self._api.compact_portfolio()
        sub_cash = await self._api.cash()

        raw_positions: list[dict[str, Any]] = []
        cash_response: list[dict[str, Any]] = []
        pending = {sub_portfolio, sub_cash}

        while pending:
            sub_id, _sub_dict, payload = await asyncio.wait_for(
                self._api.recv(), timeout=10.0
            )
            if sub_id == sub_portfolio:
                raw_positions = payload.get("positions", [])
                pending.discard(sub_id)
                await self._api.unsubscribe(sub_id)
            elif sub_id == sub_cash:
                cash_response = payload
                pending.discard(sub_id)
                await self._api.unsubscribe(sub_id)

        # pytr returns cash as a list of currency entries (one per currency);
        # index [0] is the primary EUR balance.
        cash = Decimal(str(cash_response[0]["amount"]))

        if not raw_positions:
            return PortfolioSnapshot(
                positions=[], cash=cash, timestamp=datetime.now(UTC)
            )

        # Step 2: Resolve instrument details
        detail_subs: dict[int, str] = {}
        for pos in raw_positions:
            isin = pos["instrumentId"]
            sid = await self._api.instrument_details(isin)
            detail_subs[sid] = isin

        instrument_info: dict[str, dict[str, Any]] = {}
        pending_details = set(detail_subs.keys())

        while pending_details:
            sub_id, _sub_dict, payload = await asyncio.wait_for(
                self._api.recv(), timeout=10.0
            )
            if sub_id in pending_details:
                isin = detail_subs[sub_id]
                instrument_info[isin] = payload
                pending_details.discard(sub_id)
                await self._api.unsubscribe(sub_id)

        # Step 3: Fetch ticker prices
        ticker_subs: dict[int, str] = {}
        for pos in raw_positions:
            isin = pos["instrumentId"]
            details = instrument_info.get(isin, {})
            exchange_ids = details.get("exchangeIds", ["LSX"])
            exchange = exchange_ids[0] if exchange_ids else "LSX"
            sid = await self._api.ticker(isin, exchange)
            ticker_subs[sid] = isin

        prices: dict[str, Decimal] = {}
        pending_tickers = set(ticker_subs.keys())

        while pending_tickers:
            try:
                sub_id, _sub_dict, payload = await asyncio.wait_for(
                    self._api.recv(), timeout=10.0
                )
            except TimeoutError:
                logger.warning(
                    "ticker_timeout",
                    missing_isins=[ticker_subs[s] for s in pending_tickers],
                )
                break
            if sub_id in pending_tickers:
                # NOTE: No bond price /100 adjustment — all tracked ISINs
                # are ETFs, not direct bonds. If direct bonds are added,
                # revisit pytr/portfolio.py:167.
                ticker_isin = ticker_subs[sub_id]
                prices[ticker_isin] = Decimal(str(payload["last"]["price"]))
                pending_tickers.discard(sub_id)
                await self._api.unsubscribe(sub_id)

        # Step 4: Build typed positions
        positions: list[Position] = []
        for pos in raw_positions:
            isin = pos["instrumentId"]
            if isin not in self._isin_to_asset_id:
                logger.warning("unknown_isin_skipped", isin=isin)
                continue
            if isin not in prices:
                logger.warning("position_missing_price", isin=isin)
                continue
            details = instrument_info.get(isin, {})
            name = details.get("shortName", isin)
            quantity = Decimal(str(pos["netSize"]))
            price = prices[isin]
            positions.append(
                Position(
                    isin=isin,
                    name=name,
                    quantity=quantity,
                    price=price,
                    market_value=quantity * price,
                    asset_id=self._isin_to_asset_id[isin],
                )
            )

        return PortfolioSnapshot(
            positions=positions, cash=cash, timestamp=datetime.now(UTC)
        )

    async def get_cash_balance(self) -> Decimal:
        """Fetch available cash balance.

        Returns:
            Cash balance as Decimal.
        """
        response = await self._subscribe_one(self._api.cash())
        return Decimal(str(response[0]["amount"]))

    async def get_savings_plans(self) -> list[SavingsPlan]:
        """Fetch configured savings plans.

        Returns:
            List of SavingsPlan models. Items that fail to parse are
            skipped with a warning.
        """
        response = await self._subscribe_one(self._api.savings_plan_overview())
        plans: list[SavingsPlan] = []
        for raw_plan in response:
            try:
                isin = raw_plan.get("instrumentId", "")
                plans.append(
                    SavingsPlan(
                        isin=isin,
                        name=raw_plan.get("name", isin),
                        amount=Decimal(str(raw_plan.get("amount", 0))),
                        interval=raw_plan.get("interval", "unknown"),
                        asset_id=self._isin_to_asset_id.get(isin),
                    )
                )
            except Exception:
                logger.warning("savings_plan_parse_error", raw_plan=raw_plan)
        return plans


@asynccontextmanager
async def tr_session(settings: Settings) -> AsyncIterator[TRClient]:
    """Connect a TRClient for the duration of a request, then close it."""
    client = TRClient(settings)
    await client.connect()
    try:
        yield client
    finally:
        await client.close()
