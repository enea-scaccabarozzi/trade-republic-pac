"""Tests for MarketEvent and EventCalendar."""

from __future__ import annotations

from datetime import date

import pytest

from pac.backtester.research.events import EventCalendar, MarketEvent


class TestMarketEvent:
    def test_market_event_creation(self) -> None:
        e = MarketEvent(
            date(2020, 1, 1),
            date(2020, 6, 30),
            "Test event",
            frozenset({"tag1", "tag2"}),
        )
        assert e.start == date(2020, 1, 1)
        assert e.end == date(2020, 6, 30)
        assert e.name == "Test event"
        assert e.tags == frozenset({"tag1", "tag2"})

    def test_market_event_invalid_dates(self) -> None:
        with pytest.raises(ValueError, match=r"start.*must not be after.*end"):
            MarketEvent(date(2020, 6, 30), date(2020, 1, 1))

    def test_market_event_duration_days(self) -> None:
        e = MarketEvent(date(2020, 1, 1), date(2020, 1, 11))
        assert e.duration_days == 10

    def test_market_event_default_tags(self) -> None:
        e = MarketEvent(date(2020, 1, 1), date(2020, 1, 2))
        assert e.tags == frozenset()

    def test_market_event_same_start_end(self) -> None:
        e = MarketEvent(date(2020, 1, 1), date(2020, 1, 1))
        assert e.duration_days == 0

    def test_market_event_is_frozen(self) -> None:
        e = MarketEvent(date(2020, 1, 1), date(2020, 1, 2))
        with pytest.raises(AttributeError):
            e.name = "other"  # type: ignore[misc]


class TestEventCalendar:
    def _make_events(self) -> tuple[MarketEvent, MarketEvent, MarketEvent]:
        return (
            MarketEvent(
                date(2020, 1, 1),
                date(2020, 3, 1),
                "A",
                frozenset({"crisis", "bear"}),
            ),
            MarketEvent(
                date(2020, 6, 1),
                date(2020, 9, 1),
                "B",
                frozenset({"bull"}),
            ),
            MarketEvent(
                date(2021, 1, 1),
                date(2021, 6, 1),
                "C",
                frozenset({"crisis"}),
            ),
        )

    def test_event_calendar_filter_by_tag(self) -> None:
        events = self._make_events()
        cal = EventCalendar(name="test", events=events)
        filtered = cal.filter_by_tag("crisis")
        assert len(filtered) == 2
        assert "crisis" in filtered.name

    def test_event_calendar_filter_empty(self) -> None:
        events = self._make_events()
        cal = EventCalendar(name="test", events=events)
        filtered = cal.filter_by_tag("nonexistent")
        assert len(filtered) == 0

    def test_event_calendar_merge(self) -> None:
        cal1 = EventCalendar(
            name="a",
            events=(MarketEvent(date(2021, 1, 1), date(2021, 6, 1), "Late"),),
        )
        cal2 = EventCalendar(
            name="b",
            events=(MarketEvent(date(2020, 1, 1), date(2020, 6, 1), "Early"),),
        )
        merged = cal1.merge(cal2)
        assert len(merged) == 2
        assert merged.name == "a+b"
        # Sorted by start date
        assert merged.events[0].name == "Early"
        assert merged.events[1].name == "Late"

    def test_event_calendar_merge_preserves_all(self) -> None:
        e = MarketEvent(date(2020, 1, 1), date(2020, 6, 1), "Overlap")
        cal1 = EventCalendar(name="a", events=(e,))
        cal2 = EventCalendar(name="b", events=(e,))
        merged = cal1.merge(cal2)
        assert len(merged) == 2

    def test_event_calendar_len(self) -> None:
        events = self._make_events()
        cal = EventCalendar(name="test", events=events)
        assert len(cal) == 3

    def test_event_calendar_is_frozen(self) -> None:
        cal = EventCalendar(name="test", events=())
        with pytest.raises(AttributeError):
            cal.name = "other"  # type: ignore[misc]
