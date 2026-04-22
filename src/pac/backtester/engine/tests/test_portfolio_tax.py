from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from pac.backtester.data.models import PriceBar
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.engine.tax import (
    AssetTaxMeta,
    ItalianTaxRegime,
    NoTaxRegime,
)


def _make_portfolio(
    *,
    tax_regime: ItalianTaxRegime | NoTaxRegime | None = None,
    rng: random.Random | None = None,
    cash: Decimal = Decimal("10000"),
) -> SimulatedPortfolio:
    assets = {
        "stocks": SimulatedPosition(
            asset_id="stocks", isin="IE00BK5BQT80", name="Stocks ETF"
        ),
    }
    return SimulatedPortfolio(
        assets=assets,
        cash=cash,
        pac_volumes={"stocks": Decimal("250")},
        settlement_fee=Decimal("1"),
        spread_bps=Decimal("10"),
        pac_execution_days=[2, 16],
        tax_regime=tax_regime or NoTaxRegime(),
        asset_tax_meta={"stocks": AssetTaxMeta()},
        rng=rng or random.Random(42),
    )


def _bar(price: Decimal) -> PriceBar:
    return PriceBar(
        date=date(2024, 1, 15),
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price,
        volume=1000,
    )


class TestPortfolioTaxOnSell:
    def test_sell_with_italian_regime_deducts_tax(self) -> None:
        regime = ItalianTaxRegime()
        portfolio = _make_portfolio(tax_regime=regime, cash=Decimal("0"))
        pos = portfolio._assets["stocks"]
        pos.quantity = Decimal("10")
        pos.avg_cost = Decimal("100")

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("200"))}
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="sell", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(orders, date(2024, 1, 15), prices)
        assert len(trades) == 1
        trade = trades[0]
        assert trade.tax > Decimal("0")
        assert trade.direction == "sell"

    def test_sell_with_no_tax_regime_zero_tax(self) -> None:
        portfolio = _make_portfolio(tax_regime=NoTaxRegime(), cash=Decimal("0"))
        pos = portfolio._assets["stocks"]
        pos.quantity = Decimal("10")
        pos.avg_cost = Decimal("100")

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("200"))}
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="sell", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(orders, date(2024, 1, 15), prices)
        assert trades[0].tax == Decimal("0")

    def test_buy_never_triggers_tax(self) -> None:
        regime = ItalianTaxRegime()
        portfolio = _make_portfolio(tax_regime=regime)

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("100"))}
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="buy", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(orders, date(2024, 1, 15), prices)
        assert trades[0].tax == Decimal("0")


class TestPacIntradayPrice:
    def test_pac_uses_random_price_in_range(self) -> None:
        rng = random.Random(42)
        portfolio = _make_portfolio(rng=rng)
        bar = PriceBar(
            date=date(2024, 1, 2),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=1000,
        )
        prices = {"stocks": bar}
        trades = portfolio.execute_pac(date(2024, 1, 2), prices, Decimal("500"), 2)
        assert len(trades) == 1
        trade = trades[0]
        assert Decimal("90") <= trade.price <= Decimal("110")
        assert trade.price != bar.close

    def test_pac_price_deterministic_with_seed(self) -> None:
        prices = {
            "stocks": PriceBar(
                date=date(2024, 1, 2),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=1000,
            )
        }
        p1 = _make_portfolio(rng=random.Random(99))
        t1 = p1.execute_pac(date(2024, 1, 2), prices, Decimal("500"), 2)
        p2 = _make_portfolio(rng=random.Random(99))
        t2 = p2.execute_pac(date(2024, 1, 2), prices, Decimal("500"), 2)
        assert t1[0].price == t2[0].price
