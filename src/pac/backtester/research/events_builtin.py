"""Built-in event calendars shipped with the research framework."""

from __future__ import annotations

from datetime import date

from pac.backtester.research.events import EventCalendar, MarketEvent

__all__ = ["BUILTIN_CALENDARS"]

BUILTIN_CALENDARS: dict[str, EventCalendar] = {
    "crises": EventCalendar(
        name="crises",
        description="Major market crises with >20% equity drawdown",
        events=(
            MarketEvent(
                date(2000, 3, 10),
                date(2002, 10, 9),
                "Dot-com crash",
                frozenset({"crisis", "bear"}),
            ),
            MarketEvent(
                date(2007, 10, 9),
                date(2009, 3, 9),
                "Global Financial Crisis",
                frozenset({"crisis", "bear", "systemic"}),
            ),
            MarketEvent(
                date(2011, 7, 1),
                date(2012, 6, 30),
                "Eurozone debt crisis",
                frozenset({"crisis", "sovereign"}),
            ),
            MarketEvent(
                date(2020, 2, 19),
                date(2020, 3, 23),
                "COVID crash",
                frozenset({"crisis", "bear", "pandemic"}),
            ),
            MarketEvent(
                date(2022, 1, 3),
                date(2022, 10, 12),
                "2022 bear market",
                frozenset({"crisis", "bear", "rates"}),
            ),
        ),
    ),
    "bull_runs": EventCalendar(
        name="bull_runs",
        description="Extended bull market periods with >50% equity appreciation",
        events=(
            MarketEvent(
                date(2003, 3, 11),
                date(2007, 10, 9),
                "Post dot-com recovery",
                frozenset({"bull", "recovery"}),
            ),
            MarketEvent(
                date(2009, 3, 9),
                date(2020, 2, 19),
                "Post-GFC expansion",
                frozenset({"bull", "expansion"}),
            ),
            MarketEvent(
                date(2020, 3, 23),
                date(2021, 12, 31),
                "Post-COVID rally",
                frozenset({"bull", "recovery", "stimulus"}),
            ),
            MarketEvent(
                date(2022, 10, 12),
                date(2025, 12, 31),
                "2023+ recovery",
                frozenset({"bull", "ai"}),
            ),
        ),
    ),
    "corrections": EventCalendar(
        name="corrections",
        description="Shallow drawdowns (-10% to -20%)",
        events=(
            MarketEvent(
                date(2010, 4, 23),
                date(2010, 7, 2),
                "Flash crash correction",
                frozenset({"correction"}),
            ),
            MarketEvent(
                date(2015, 8, 17),
                date(2016, 2, 11),
                "China/oil correction",
                frozenset({"correction"}),
            ),
            MarketEvent(
                date(2018, 9, 20),
                date(2018, 12, 24),
                "Q4 2018 selloff",
                frozenset({"correction", "rates"}),
            ),
        ),
    ),
    "rate_regimes": EventCalendar(
        name="rate_regimes",
        description="Monetary policy regime changes",
        events=(
            MarketEvent(
                date(2008, 12, 16),
                date(2015, 12, 16),
                "ZIRP era",
                frozenset({"rates", "zirp", "dovish"}),
            ),
            MarketEvent(
                date(2020, 3, 15),
                date(2022, 3, 16),
                "COVID ZIRP",
                frozenset({"rates", "zirp", "qe"}),
            ),
            MarketEvent(
                date(2022, 3, 16),
                date(2024, 9, 18),
                "Hiking cycle",
                frozenset({"rates", "hawkish", "tightening"}),
            ),
        ),
    ),
}
