"""Core event models — MarketEvent and EventCalendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

__all__ = ["EventCalendar", "MarketEvent"]


@dataclass(frozen=True)
class MarketEvent:
    """A named, tagged period in market history."""

    start: date
    end: date
    name: str | None = None
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.start > self.end:
            msg = f"start ({self.start}) must not be after end ({self.end})"
            raise ValueError(msg)

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days


@dataclass(frozen=True)
class EventCalendar:
    """A named collection of market events."""

    name: str
    events: tuple[MarketEvent, ...]
    description: str | None = None

    def filter_by_tag(self, tag: str) -> EventCalendar:
        """Return a new calendar with only events matching the tag."""
        filtered = tuple(e for e in self.events if tag in e.tags)
        return EventCalendar(
            name=f"{self.name}[{tag}]",
            events=filtered,
            description=self.description,
        )

    def merge(self, other: EventCalendar) -> EventCalendar:
        """Combine two calendars. Events are concatenated and sorted by start date.

        Does not deduplicate — overlapping events from different calendars
        are kept as separate entries (they may have different names/tags).
        """
        combined = sorted(self.events + other.events, key=lambda e: e.start)
        return EventCalendar(
            name=f"{self.name}+{other.name}",
            events=tuple(combined),
            description=None,
        )

    def __len__(self) -> int:
        return len(self.events)
