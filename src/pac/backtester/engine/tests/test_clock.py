from __future__ import annotations

from datetime import date
from decimal import Decimal

from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.engine.clock import SimulationClock


def _make_bars(
    dates: list[date], base_price: Decimal = Decimal("100")
) -> list[PriceBar]:
    """Create PriceBars for specific dates."""
    return [
        PriceBar(
            date=d,
            open=base_price,
            high=base_price + Decimal(5),
            low=base_price - Decimal(2),
            close=base_price + Decimal(i),
            volume=1_000_000,
        )
        for i, d in enumerate(dates)
    ]


def _make_series(dates: list[date]) -> PriceSeries:
    return PriceSeries(ticker="TEST", interval=Interval.DAILY, bars=_make_bars(dates))


class TestClockIteration:
    def test_clock_iterates_trading_days_only(self) -> None:
        # 3 specific trading days with a gap
        dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2, 16])
        assert list(clock) == dates

    def test_clock_len_matches_bars(self) -> None:
        dates = [date(2024, 1, d) for d in range(2, 12)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2, 16])
        assert len(clock) == 10

    def test_empty_series_no_pac_dates(self) -> None:
        clock = SimulationClock(
            PriceSeries(ticker="TEST", interval=Interval.DAILY, bars=[]),
            pac_execution_days=[2, 16],
        )
        assert len(clock) == 0
        assert list(clock) == []


class TestPacDateDetection:
    def test_pac_date_on_exact_day(self) -> None:
        # Jan 2 is a trading day
        dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.is_pac_date(date(2024, 1, 2)) is True

    def test_pac_date_rolls_forward_from_weekend(self) -> None:
        # Simulate: 2nd is missing (weekend), 3rd and 4th are trading days
        # The next trading day after the 2nd is the 3rd
        dates = [date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.is_pac_date(date(2024, 1, 3)) is True

    def test_pac_date_rolls_forward_from_holiday(self) -> None:
        # 2nd is a holiday (not in bars), 4th is next trading day
        dates = [date(2024, 1, 4), date(2024, 1, 5)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.is_pac_date(date(2024, 1, 4)) is True

    def test_multiple_pac_days_per_month(self) -> None:
        dates = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 15),
            date(2024, 1, 16),
            date(2024, 1, 17),
        ]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2, 16])
        assert clock.is_pac_date(date(2024, 1, 2)) is True
        assert clock.is_pac_date(date(2024, 1, 16)) is True

    def test_pac_day_beyond_month_length(self) -> None:
        # Feb 2024 has 29 days — pac_day=31 should be skipped
        dates = [
            date(2024, 2, d) for d in range(1, 29) if date(2024, 2, d).weekday() < 5
        ]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[31])
        for d in dates:
            assert clock.is_pac_date(d) is False

    def test_is_pac_date_non_pac_day_returns_false(self) -> None:
        dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.is_pac_date(date(2024, 1, 3)) is False
        assert clock.is_pac_date(date(2024, 1, 4)) is False


class TestWhichPacDay:
    def test_which_pac_day_returns_logical_day(self) -> None:
        # 2nd is missing, rolls forward to 3rd — which_pac_day returns 2
        dates = [date(2024, 1, 3), date(2024, 1, 4)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.which_pac_day(date(2024, 1, 3)) == 2

    def test_which_pac_day_returns_none_for_non_pac(self) -> None:
        dates = [date(2024, 1, 2), date(2024, 1, 3)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2])
        assert clock.which_pac_day(date(2024, 1, 3)) is None

    def test_multiple_pac_days_rolling_to_same_trading_day(self) -> None:
        # pac_days 2 and 3 both land on the same trading day (the 4th)
        # because 2nd and 3rd are missing
        dates = [date(2024, 1, 4), date(2024, 1, 5)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[2, 3])
        # The date is still a PAC date
        assert clock.is_pac_date(date(2024, 1, 4)) is True
        # which_pac_day returns whichever was set last (dict overwrite)
        result = clock.which_pac_day(date(2024, 1, 4))
        assert result in (2, 3)

    def test_clock_pac_date_in_month_with_no_remaining_trading_days(self) -> None:
        # Month where pac_day=28 but no trading day exists at or after 28
        dates = [date(2024, 1, d) for d in range(2, 26)]
        clock = SimulationClock(_make_series(dates), pac_execution_days=[28])
        for d in dates:
            assert clock.is_pac_date(d) is False
