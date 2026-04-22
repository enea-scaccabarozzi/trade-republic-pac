"""Tests for built-in event calendars."""

from __future__ import annotations

from pac.backtester.research.events_builtin import BUILTIN_CALENDARS


class TestBuiltinCalendars:
    def test_builtin_calendars_exist(self) -> None:
        expected = {"crises", "bull_runs", "corrections", "rate_regimes"}
        assert set(BUILTIN_CALENDARS.keys()) == expected

    def test_builtin_calendars_non_empty(self) -> None:
        for name, cal in BUILTIN_CALENDARS.items():
            assert len(cal) > 0, f"Calendar '{name}' is empty"

    def test_builtin_events_valid_dates(self) -> None:
        for name, cal in BUILTIN_CALENDARS.items():
            for event in cal.events:
                assert event.start < event.end, (
                    f"Calendar '{name}', event '{event.name}': "
                    f"start ({event.start}) >= end ({event.end})"
                )

    def test_builtin_events_have_names(self) -> None:
        for name, cal in BUILTIN_CALENDARS.items():
            for event in cal.events:
                assert event.name is not None, (
                    f"Calendar '{name}' has event without name"
                )

    def test_builtin_events_have_tags(self) -> None:
        for name, cal in BUILTIN_CALENDARS.items():
            for event in cal.events:
                assert len(event.tags) > 0, (
                    f"Calendar '{name}', event '{event.name}' has no tags"
                )

    def test_builtin_crises_count(self) -> None:
        assert len(BUILTIN_CALENDARS["crises"]) == 5
