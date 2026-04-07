from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.config import BacktestConfig
from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.engine.actions import Action
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.strategies.base import BacktestStrategy
from pac.config import Settings
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.registry import SignalRegistry


def make_settings(**overrides: Any) -> Settings:
    """Build a Settings instance with test defaults."""
    base: dict[str, Any] = {
        "version": 1,
        "broker": {
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
        },
        "assets": [
            {
                "id": "stocks",
                "name": "Stocks ETF",
                "isin": "IE00BK5BQT80",
                "ticker": "EUNL.DE",
                "target_pct": 70,
            },
            {
                "id": "gold",
                "name": "Gold ETC",
                "isin": "IE00B4ND3602",
                "ticker": "4GLD.DE",
                "target_pct": 15,
            },
            {
                "id": "bonds",
                "name": "Bond ETF",
                "isin": "IE00B3F81409",
                "ticker": "EUN4.DE",
                "target_pct": 15,
            },
        ],
        "app": {"job_secret": "test-job-secret"},
        "channels": {},
        "signals": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)


def make_price_bars(
    start_date: date,
    n_days: int,
    base_price: Decimal = Decimal("100"),
    *,
    skip_weekends: bool = True,
) -> list[PriceBar]:
    """Generate n_days of PriceBars, optionally skipping weekends."""
    bars: list[PriceBar] = []
    current = start_date
    while len(bars) < n_days:
        if skip_weekends and current.weekday() >= 5:
            current += timedelta(days=1)
            continue
        price = base_price + Decimal(len(bars))
        bars.append(
            PriceBar(
                date=current,
                open=price - Decimal(1),
                high=price + Decimal(5),
                low=price - Decimal(2),
                close=price,
                volume=1_000_000,
            ),
        )
        current += timedelta(days=1)
    return bars


def make_price_series(
    ticker: str,
    bars: list[PriceBar],
) -> PriceSeries:
    """Build a PriceSeries from bars."""
    return PriceSeries(ticker=ticker, interval=Interval.DAILY, bars=bars)


def make_three_asset_price_data(
    start_date: date,
    n_days: int,
) -> dict[str, PriceSeries]:
    """Create price data for all 3 assets (stocks, gold, bonds)."""
    bars = make_price_bars(start_date, n_days)
    return {
        "EUNL.DE": make_price_series("EUNL.DE", bars),
        "4GLD.DE": make_price_series("4GLD.DE", bars),
        "EUN4.DE": make_price_series("EUN4.DE", bars),
    }


@pytest.fixture
def three_asset_settings() -> Settings:
    return make_settings()


@pytest.fixture
def sample_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        strategy="noop",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        pac_execution_days=[2, 16],
        monte_carlo_iterations=1,
        slippage_days=(0, 0),
    )


def make_portfolio(
    *,
    cash: Decimal = Decimal("10000"),
    pac_volumes: dict[str, Decimal] | None = None,
    settlement_fee: Decimal = Decimal("1.00"),
    spread_bps: Decimal = Decimal("10"),
    pac_execution_days: list[int] | None = None,
) -> SimulatedPortfolio:
    """Build a SimulatedPortfolio with 3 assets."""
    assets = {
        "stocks": SimulatedPosition(
            asset_id="stocks",
            isin="IE00BK5BQT80",
            name="Stocks ETF",
        ),
        "gold": SimulatedPosition(
            asset_id="gold",
            isin="IE00B4ND3602",
            name="Gold ETC",
        ),
        "bonds": SimulatedPosition(
            asset_id="bonds",
            isin="IE00B3F81409",
            name="Bond ETF",
        ),
    }
    return SimulatedPortfolio(
        assets=assets,
        cash=cash,
        pac_volumes=pac_volumes
        or {
            "stocks": Decimal("350"),
            "gold": Decimal("75"),
            "bonds": Decimal("75"),
        },
        settlement_fee=settlement_fee,
        spread_bps=spread_bps,
        pac_execution_days=pac_execution_days or [2, 16],
    )


@pytest.fixture
def sample_portfolio() -> SimulatedPortfolio:
    return make_portfolio()


class _NoopParams(BaseModel):
    """Empty params for NoopStrategy."""


class NoopStrategy(BacktestStrategy[_NoopParams]):
    """Strategy that returns no actions — only PAC executions occur."""

    name = "noop"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


class _StubParams(BaseModel):
    """Empty params for StubStrategy."""


class StubStrategy(BacktestStrategy[_StubParams]):
    """Strategy that returns fixed actions whenever signals are received."""

    name = "stub"

    def __init__(self, params: _StubParams, actions: list[Action]) -> None:
        super().__init__(params)
        self._actions = actions
        self.calls: list[tuple[list[Signal], date]] = []

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        self.calls.append((signals, current_date))
        return list(self._actions)


@pytest.fixture
def noop_strategy() -> NoopStrategy:
    return NoopStrategy(_NoopParams())


@pytest.fixture
def sample_signal_registry() -> SignalRegistry:
    return SignalRegistry()
