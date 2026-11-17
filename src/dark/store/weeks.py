"""ISO weeks, in a given time zone."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import NamedTuple

UTC = timezone.utc


class IsoWeek(NamedTuple):
    year: int
    week: int

    @classmethod
    def of(cls, moment: datetime, tz: tzinfo = UTC) -> IsoWeek:
        year, week, _ = moment.astimezone(tz).isocalendar()
        return cls(year, week)

    def monday(self) -> date:
        return date.fromisocalendar(self.year, self.week, 1)

    def start(self, tz: tzinfo = UTC) -> datetime:
        """Monday 00:00 in `tz`."""
        return datetime.combine(self.monday(), datetime.min.time(), tzinfo=tz)

    def end(self, tz: tzinfo = UTC) -> datetime:
        return self.next().start(tz)

    def previous(self) -> IsoWeek:
        return IsoWeek.of(self.start() - timedelta(days=7))

    def next(self) -> IsoWeek:
        return IsoWeek.of(self.start() + timedelta(days=7))

    def __str__(self) -> str:
        return f"{self.year}-W{self.week:02d}"
