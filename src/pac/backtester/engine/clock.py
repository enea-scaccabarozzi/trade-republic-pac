from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from pac.backtester.data.models import PriceSeries


class SimulationClock:
    """Iterates through trading days from a PriceSeries.

    Only yields dates where we have actual price data (the PriceSeries
    bars). This naturally skips weekends and holidays — if the exchange
    was closed, there's no bar, the clock skips that day.

    PAC date detection: a date is a PAC execution date if its day-of-month
    matches one of the configured pac_execution_days OR if the actual
    PAC day fell on a non-trading day and this is the next available
    trading day.
    """

    def __init__(
        self,
        series: PriceSeries,
        pac_execution_days: list[int],
    ) -> None:
        self._trading_days: list[date] = [bar.date for bar in series.bars]
        self._pac_execution_days = set(pac_execution_days)
        self._pac_date_to_logical: dict[date, int] = self._compute_pac_dates()
        self._pac_dates: set[date] = set(self._pac_date_to_logical)

    def _compute_pac_dates(self) -> dict[date, int]:
        """Pre-compute PAC execution dates → logical PAC day mapping.

        For each month in the range, for each configured PAC day:
        - If that day is a trading day, use it.
        - Otherwise, use the next trading day in that month.
        - If no trading day remains in the month, skip (rare edge case).

        Returns a dict mapping each resolved trading date to the
        configured PAC day it represents (e.g. Monday the 4th → 2).
        """
        if not self._trading_days:
            return {}

        trading_set = set(self._trading_days)
        pac_dates: dict[date, int] = {}

        # Collect all (year, month) pairs in the range
        months: set[tuple[int, int]] = set()
        for d in self._trading_days:
            months.add((d.year, d.month))

        for year, month in months:
            for pac_day in self._pac_execution_days:
                try:
                    target = date(year, month, pac_day)
                except ValueError:
                    # pac_day > days in month (e.g. 31 in Feb)
                    continue

                if target in trading_set:
                    pac_dates[target] = pac_day
                else:
                    # Find next trading day in same month
                    for td in self._trading_days:
                        if td.year == year and td.month == month and td >= target:
                            pac_dates[td] = pac_day
                            break

        return pac_dates

    def is_pac_date(self, d: date) -> bool:
        """Check if a date is a PAC execution date."""
        return d in self._pac_dates

    def which_pac_day(self, d: date) -> int | None:
        """Return the configured PAC day that date `d` represents.

        When a PAC day (e.g. the 2nd) falls on a non-trading day and
        rolls forward (e.g. to the 4th), this returns the *logical*
        PAC day (2), not the calendar day (4).

        Returns None if `d` is not a PAC date.
        """
        return self._pac_date_to_logical.get(d)

    def __iter__(self) -> Iterator[date]:
        return iter(self._trading_days)

    def __len__(self) -> int:
        return len(self._trading_days)
