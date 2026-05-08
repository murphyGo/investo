"""Official U.S. economic release calendar adapter."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from html.parser import HTMLParser
from typing import ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
_LOOKAHEAD_DAYS = 45
_MAX_ITEMS = 12
_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


@register
class UsEconomicCalendarAdapter:
    """Adapter for the official BEA release schedule page."""

    name: ClassVar[str] = "us-economic-calendar"
    category: ClassVar[Category] = "calendar"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(client, _SCHEDULE_URL, source_name=self.name)
        parser = _ScheduleTableParser()
        parser.feed(response.text)
        if "<table" in response.text.lower() and not parser.rows:
            raise SourceFetchError(
                source_name=self.name,
                message="unexpected BEA schedule table shape",
                transient=False,
            )
        start_date = window.target_date
        end_date = start_date + timedelta(days=_LOOKAHEAD_DAYS)
        items: list[NormalizedItem] = []
        seen: set[tuple[datetime, str, str]] = set()
        for row in parser.rows:
            event = _row_to_event(row, start_date=start_date)
            if event is None:
                continue
            scheduled_at, release_type, title = event
            scheduled_date = scheduled_at.astimezone(_NY).date()
            if not (start_date <= scheduled_date <= end_date):
                continue
            key = (scheduled_at, release_type, title)
            if key in seen:
                continue
            seen.add(key)
            try:
                items.append(
                    NormalizedItem(
                        source_name=self.name,
                        category="calendar",
                        title=f"BEA {title}",
                        summary=f"{release_type} release scheduled by BEA",
                        url=_SCHEDULE_URL,
                        published_at=window.end_utc,
                        scheduled_at=scheduled_at,
                        raw_metadata={
                            "agency": "BEA",
                            "release_type": release_type,
                            "scheduled_date": scheduled_date.isoformat(),
                        },
                    )
                )
            except ValidationError:
                continue
        return sorted(
            items,
            key=lambda item: item.scheduled_at or datetime.max.replace(tzinfo=UTC),
        )[:_MAX_ITEMS]


class _ScheduleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_td = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._current_row = []
        elif tag.lower() == "td":
            self._in_td = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "td" and self._in_td:
            self._current_row.append(strip_html("".join(self._current_cell)))
            self._current_cell = []
            self._in_td = False
        elif tag.lower() == "tr" and len(self._current_row) >= 3:
            self.rows.append(self._current_row)
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_cell.append(data)


def _row_to_event(
    row: list[str],
    *,
    start_date: date,
) -> tuple[datetime, str, str] | None:
    date_text, release_type, title = row[0], row[1], row[2]
    parts = date_text.split()
    if len(parts) < 4:
        return None
    month = _MONTHS.get(parts[0])
    if month is None:
        return None
    try:
        day = int(parts[1])
        hour, minute = _parse_time(parts[2], parts[3])
        scheduled_date = date(start_date.year, month, day)
        if scheduled_date < start_date:
            next_year_date = date(start_date.year + 1, month, day)
            if next_year_date <= start_date + timedelta(days=_LOOKAHEAD_DAYS):
                scheduled_date = next_year_date
        scheduled = datetime.combine(scheduled_date, time(hour, minute), tzinfo=_NY)
    except ValueError:
        return None
    clean_title = strip_html(title)
    clean_type = strip_html(release_type) or "News"
    if not clean_title:
        return None
    return scheduled.astimezone(UTC), clean_type, clean_title


def _parse_time(clock: str, meridiem: str) -> tuple[int, int]:
    hour_text, minute_text = clock.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    marker = meridiem.upper()
    if marker == "PM" and hour != 12:
        hour += 12
    if marker == "AM" and hour == 12:
        hour = 0
    return hour, minute
