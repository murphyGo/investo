# ruff: noqa: E501 -- HTML literals preserve tag boundaries.
"""u187 month presentation; source dates never acquire an invented KST time."""

from __future__ import annotations

from calendar import Calendar
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from html import escape

from investo.models.insights import ValidatedInsightEvent, ValidatedInsightModule
from investo.models.insights_events import KST, NY, display_dates, range_anchor


def short_clock(row: ValidatedInsightEvent) -> str:
    if row.time.precision == "exact" and row.time.exact_at:
        return row.time.exact_at.astimezone(KST).strftime("%H:%M KST")
    return "미 동부 · 시간 미정"


def calendar_bounds(now: datetime) -> tuple[date, date]:
    anchors = (now.astimezone(KST).date(), now.astimezone(NY).date())
    return min(anchors), max(anchors) + timedelta(days=29)


def on_day(row: ValidatedInsightEvent, day: date, now: datetime) -> bool:
    start, end = display_dates(row)
    anchor = range_anchor(row, now)
    return bool(
        start and end and start <= day <= end and anchor <= day < anchor + timedelta(days=30)
    )


def _day(
    day: date,
    month: date,
    module: ValidatedInsightModule,
    categories: Mapping[str, str],
    positions: Mapping[str, int],
) -> str:
    lower, upper = calendar_bounds(module.evaluated_at)
    if day.month != month.month or not lower <= day <= upper:
        return (
            '<td class="calendar-outside"><span class="calendar-day-number">'
            f'{day.day}</span><span class="calendar-outside-label">범위 밖</span></td>'
        )
    rows = [row for row in module.events if on_day(row, day, module.evaluated_at)]
    kst = sum(row.time.precision == "exact" for row in rows)
    label = (
        f"{day.isoformat()} · 표시 {len(rows)}건 · KST {kst}건 · 미 동부 날짜 {len(rows) - kst}건"
    )
    target = f"calendar-event-{positions[rows[0].event_id]}" if rows else "calendar-events"
    previews = []
    # The exact agenda always contains every event. Large calendars use counts
    # in the static grid; JS can enhance those from the same existing agenda.
    for row in rows[:2] if len(module.events) <= 64 else ():
        category = row.details.category if row.details else "economic_release"
        previews.append(
            f'<span class="calendar-preview" data-category="{category}">'
            f'<span class="calendar-preview-title">{escape(row.label)}</span>'
            f'<span class="calendar-preview-clock">{escape(short_clock(row))}</span>'
            f'<span class="calendar-preview-category">{categories[category]}</span></span>'
        )
    count = f"{len(rows)}건" if rows else "—"
    return (
        f'<td><a href="#{escape(target, quote=True)}" class="calendar-day" '
        f'data-calendar-day="{day.isoformat()}" aria-label="{escape(label, quote=True)}">'
        f'<span class="calendar-day-number">{day.day}</span>'
        f'<span class="calendar-day-count">{count}</span>'
        f'<span class="calendar-day-basis">KST {kst}<br>동부 {len(rows) - kst}</span>'
        f'<span class="calendar-day-previews">{"".join(previews)}</span>'
        f'<span class="calendar-day-more">{f"+{len(rows) - 2}건" if len(rows) > 2 and len(module.events) <= 64 else ""}</span>'
        "</a></td>"
    )


def render_calendar_grid(module: ValidatedInsightModule, categories: Mapping[str, str]) -> str:
    lower, upper = calendar_bounds(module.evaluated_at)
    month = lower.replace(day=1)
    months = []
    while month <= upper:
        months.append(month)
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    active = module.evaluated_at.astimezone(KST).strftime("%Y-%m")
    tables = []
    positions = {row.event_id: i for i, row in enumerate(module.events)}
    for month in months:
        label = f"{month.year}년 {month.month}월"
        rows = []
        for week in Calendar(firstweekday=6).monthdatescalendar(month.year, month.month):
            rows.append(
                "<tr>"
                + "".join(_day(day, month, module, categories, positions) for day in week)
                + "</tr>"
            )
        headings = "".join(f'<th scope="col">{day}</th>' for day in "일월화수목금토")
        tables.append(
            f'<div data-calendar-month="{month:%Y-%m}" data-month-label="{label}">'
            f'<table class="calendar-month-table"><caption>{label} · 제공된 일정</caption>'
            f"<thead><tr>{headings}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )
    return (
        '<section class="calendar-board" aria-label="월간 달력" '
        f'data-calendar-initial-month="{active}">'
        '<div class="calendar-month-toolbar" data-calendar-navigation hidden>'
        '<button type="button" data-calendar-previous aria-label="이전 달" data-testid="calendar-previous">←</button>'
        '<h2 data-calendar-month-title aria-live="polite"></h2>'
        '<button type="button" data-calendar-next aria-label="다음 달" data-testid="calendar-next">→</button></div>'
        '<p class="calendar-clock-key"><strong>KST</strong> 시각 확인 · '
        "<strong>미 동부</strong> 현지 날짜·시간 미정. 날짜를 선택하면 아래에서 자세히 볼 수 있습니다.</p>"
        '<div class="calendar-month-scroll" role="region" aria-label="월간 일정 날짜" tabindex="0">'
        + "".join(tables)
        + '</div><p class="calendar-window-note">표시 범위 '
        f"{lower.isoformat()} ~ {upper.isoformat()} · 각 시간 기준의 30일. 빈 날짜는 전체 시장 일정이 없다는 뜻이 아닙니다.</p></section>"
    )
