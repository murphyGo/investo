"""Qualified KOSPI 200 regular-session last-trading dates, not settlement dates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from investo.models.market_calendar import KRX_HOLIDAYS_2026

PRODUCT_URL = "https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp"
RULE_VERSION = "kospi200-monthly-weekly-2026-10-30"
CALENDAR_VERSION = "krx-2026-reviewed-2026-10-30"
CALENDAR_END = date(2026, 12, 31)
# MOE boardSeq=100526 confirms the CSAT date; KRX session-time notice is
# not yet qualified. Do not invent the usual 15:20 close on that day.
UNQUALIFIED_SESSION_DAYS = frozenset({date(2026, 11, 19)})
EXPIRY_LABELS = {
    "monthly": "월물",
    "monday_weekly": "월요일 위클리",
    "thursday_weekly": "목요일 위클리",
}
_KST = ZoneInfo("Asia/Seoul")


def adjusted_day(day: date, holidays: frozenset[date], *, forward: bool = False) -> date:
    for _ in range(14):
        if day.weekday() < 5 and day not in holidays:
            return day
        day += timedelta(days=1 if forward else -1)
    raise ValueError("holiday calendar contains no nearby trading day")


def monthly_expiry(year: int, month: int, holidays: frozenset[date]) -> date:
    first = date(year, month, 1)
    return adjusted_day(first + timedelta(days=(3 - first.weekday()) % 7 + 7), holidays)


@dataclass(frozen=True, slots=True)
class OptionExpiry:
    kind: str
    nominal_day: date

    def __post_init__(self) -> None:
        if self.kind not in EXPIRY_LABELS or type(self.nominal_day) is not date:
            raise ValueError("invalid option expiry")
        if self.nominal_day.year != 2026:
            raise ValueError("option calendar requires annual qualification")
        weekday = 0 if self.kind == "monday_weekly" else 3
        second = 8 <= self.nominal_day.day <= 14
        if self.nominal_day.weekday() != weekday:
            raise ValueError("invalid nominal weekday")
        if self.kind == "monthly" and not second:
            raise ValueError("monthly expiry requires second Thursday")
        if self.kind == "thursday_weekly" and second:
            raise ValueError("monthly/weekly overlap")
        if self.day in UNQUALIFIED_SESSION_DAYS:
            raise ValueError("special session time requires qualification")
        if self.day.year != 2026:
            raise ValueError("adjustment crosses qualified calendar")

    @property
    def day(self) -> date:
        return adjusted_day(
            self.nominal_day, KRX_HOLIDAYS_2026, forward=self.kind == "monday_weekly"
        )

    @property
    def scheduled_at(self) -> datetime:
        return datetime.combine(self.day, time(15, 20), _KST).astimezone(UTC)

    @property
    def label(self) -> str:
        return EXPIRY_LABELS[self.kind]

    def metadata(self) -> dict[str, str]:
        return {
            "event_type": "monthly_option_last_trading_day"
            if self.kind == "monthly"
            else "weekly_option_last_trading_day",
            "expiry_kind": self.kind,
            "nominal_date": self.nominal_day.isoformat(),
            "scheduled_date": self.day.isoformat(),
            "local_time": "15:20 KST",
            "rule_version": RULE_VERSION,
            "calendar_version": CALENDAR_VERSION,
            "calendar_valid_through": CALENDAR_END.isoformat(),
        }

    @classmethod
    def from_metadata(cls, meta: Mapping[str, object]) -> OptionExpiry:
        kind, nominal = meta.get("expiry_kind"), meta.get("nominal_date")
        if not isinstance(kind, str) or not isinstance(nominal, str) or len(nominal) != 10:
            raise ValueError("invalid expiry metadata")
        result = cls(kind, date.fromisoformat(nominal))
        if any(meta.get(key) != value for key, value in result.metadata().items()):
            raise ValueError("expiry metadata differs from qualified calculation")
        return result


def option_expiries(start: date) -> tuple[OptionExpiry, ...]:
    if start.year != 2026:
        raise ValueError("option calendar requires annual qualification")
    end = min(start + timedelta(days=30), CALENDAR_END + timedelta(days=1))
    # Include nominal days outside the display window whose holiday adjustment
    # lands inside it. Never walk through an unqualified year.
    nominal = max(start - timedelta(days=13), date(2026, 1, 1))
    stop = min(end + timedelta(days=13), CALENDAR_END + timedelta(days=1))
    results = []
    while nominal < stop:
        if nominal.weekday() in (0, 3):
            kind = (
                "monday_weekly"
                if nominal.weekday() == 0
                else ("monthly" if 8 <= nominal.day <= 14 else "thursday_weekly")
            )
            adjusted = adjusted_day(nominal, KRX_HOLIDAYS_2026, forward=kind == "monday_weekly")
            if adjusted.year != 2026 or adjusted in UNQUALIFIED_SESSION_DAYS:
                nominal += timedelta(days=1)
                continue
            expiry = OptionExpiry(kind, nominal)
            if start <= expiry.day < end:
                results.append(expiry)
        nominal += timedelta(days=1)
    if not results and end.year != start.year:
        raise ValueError("option calendar requires annual qualification")
    return tuple(sorted(results, key=lambda expiry: (expiry.day, expiry.kind)))
