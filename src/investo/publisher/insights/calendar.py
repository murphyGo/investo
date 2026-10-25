"""FR-028: deterministic schedule list; no countdown or inferred actual result."""
# ruff: noqa: E501 -- HTML literals retain readable tag boundaries.

from __future__ import annotations

from datetime import datetime
from html import escape

from investo._internal.disclaimer import DISCLAIMER
from investo.models.insights import (
    SourceInsightEvent,
    ValidatedInsightEvent,
    ValidatedInsightModule,
)
from investo.models.insights_events import KST, display_dates, in_range, range_anchor

SOURCE_NAMES = {
    "fomc-calendar": "연준 이사회",
    "us-economic-calendar": "BEA",
    "fred-economic-calendar": "FRED",
    "treasury-auctions": "미 재무부 Fiscal Data",
}
CATEGORIES = {
    "economic_release": "경제지표",
    "central_bank": "중앙은행",
    "treasury_auction": "국채 입찰",
}
GUIDES = {
    "economic_release": "경제 통계의 대상 기간과 원 발표를 확인하세요.",
    "central_bank": "회의·성명·의사록의 종류를 구별해 확인하세요.",
    "treasury_auction": "국채의 만기와 재발행 여부를 원천에서 확인하세요.",
}
ATTEMPTS = {
    "ok": "수집됨",
    "zero": "수집 0건",
    "failed": "수집 실패",
    "skipped": "수집 건너뜀",
    "missing": "수집 미확인",
}
RIGHTS = {
    "allowed": "공개 범위 확인",
    "blocked": "공개 조건 미충족",
    "mixed": "일부 정의만 공개 가능",
    "unverified": "공개 조건 미확인",
}
LIMITS = {
    "fomc-calendar": "선택된 연준 일정 유형과 기존 조회 범위만 포함합니다. feed가 하루만 명시하면 회의 기간을 늘리지 않습니다.",
    "us-economic-calendar": "기존 45일 조회에서 앞선 최대 12건을 사용합니다. 명시된 연도·시각이 검증된 행만 표시합니다.",
    "fred-economic-calendar": "기존 release ID별 최대 15개 날짜를 조회합니다. 일부 release 요청 실패는 전체 source 성공과 함께 발생할 수 있습니다.",
    "treasury-auctions": "기존 최대 500행과 선택된 국채 유형만 사용합니다. 원천 갱신 지연·필터·중복 제거에 따른 누락이 있을 수 있습니다.",
}


def _clock(row: SourceInsightEvent) -> str:
    start, end = display_dates(row)
    if row.time.precision == "exact" and row.time.exact_at:
        return f'<time datetime="{escape(row.time.exact_at.isoformat(), quote=True)}">{row.time.exact_at.astimezone(KST):%Y-%m-%d %H:%M}</time> KST · 한국 시각 확인'
    span = str(start) if start == end else f"{start} ~ {end}"
    return f"{escape(span)} · 미국 동부 현지 날짜 · 시간 미정"


def _event(row: ValidatedInsightEvent, now: datetime) -> str:
    category = row.details.category if row.details else "economic_release"
    seven = in_range(row, range_anchor(row, now), 7)
    status = "예정 · 결과 미확인"
    if row.time.exact_at and row.time.exact_at <= now:
        status = "예정 시각 경과 · 결과 미확인"
    elif row.time.precision == "date":
        start, _ = display_dates(row)
        if start and start <= range_anchor(row, now):
            status = "현지 당일 또는 기간 중 · 진행·결과 미확인"
    period = row.details.target_period if row.details else None
    context = f"대상 기간 {period}" if period else "대상 기간 원천 미제공"
    if row.details and row.details.instrument:
        context = f"{row.details.instrument} · 재발행 {dict(yes='예', no='아니오', unknown='미확인')[row.details.reopening]}"
    refs = [
        (
            row.source_name,
            row.source_href,
            row.collection_completed_at,
            row.last_good,
            row.latest_attempt,
        )
    ]
    refs.extend(
        (
            r.event.source_name,
            r.event.source_href,
            r.collection_completed_at,
            r.last_good,
            r.latest_attempt,
        )
        for r in row.references
    )
    sources = []
    for name, href, collected, last_good, attempt in refs:
        label = SOURCE_NAMES.get(name, "검증 출처")
        suffix = f"이전 수집 · {ATTEMPTS[attempt]}" if last_good else "수집 기준"
        sources.append(
            f'<a href="{escape(href, quote=True)}">{escape(label)}</a> · {suffix} {collected.astimezone(KST):%m-%d %H:%M} KST'
        )
    freshness = " · 수집 기준 36시간 경과" if row.freshness == "stale" else ""
    return (
        f'<li class="calendar-event" data-event="{escape(row.event_id, quote=True)}" data-category="{category}" data-within-seven="{str(seven).lower()}">'
        f'<p class="calendar-date">{_clock(row)}</p><h3>{escape(row.label)}</h3>'
        f"<p>{escape(context)} · {status}{freshness}</p>"
        f'<p class="calendar-guide">{GUIDES[category]}</p><p class="calendar-source">{"<br>".join(sources)}</p></li>'
    )


def render_calendar(module: ValidatedInsightModule) -> str:
    if module.module != "calendar":
        raise ValueError("calendar renderer requires calendar module")
    coverage = module.calendar_coverage
    events = "".join(_event(row, module.evaluated_at) for row in module.events)
    sources = []
    if coverage:
        for source in coverage.sources:
            query = source.query
            queried = (
                f" 확인된 조회 범위 {query.start_date} ~ {query.end_date}(원천 현지 날짜)."
                if query
                else " 이번 조회 범위 미확인."
            )
            cap = " 상한 도달 가능성이 있습니다." if query and query.cap_reached else ""
            sources.append(
                f"<li><strong>{SOURCE_NAMES.get(source.source_name, '검증 출처')}</strong> · {ATTEMPTS[source.latest_attempt]} · {RIGHTS[source.rights]}<p>{LIMITS.get(source.source_name, '')}{queried}{cap}</p></li>"
            )
    # Attribution is repeated once per distinct source/notice, not on every event.
    notices = {(e.source_name, e.attribution) for e in module.events}
    notices.update(
        (r.event.source_name, r.attribution) for e in module.events for r in e.references
    )
    attribution = "".join(
        f"<p>{escape(SOURCE_NAMES.get(name, '검증 출처'))}: {escape(text)}</p>"
        for name, text in sorted(notices)
    )
    limitations = ""
    if coverage:
        limitations = f"선택 상한으로 제외 {coverage.excluded_count}건 · 충돌로 제외 {coverage.conflict_count}건 · 검증 제외 {coverage.invalid_count}건. "
    return f"""<!-- insights-snapshot:{module.snapshot_id} -->
<div class="insights-page insights-calendar" data-calendar>
<header class="insights-hero"><p class="insights-eyebrow">UPCOMING EVENTS</p><h1>주요 일정</h1><p>경제지표 · 중앙은행 · 국채 입찰의 공식 예정 일정을 확인하세요.</p><p>게시 판단 {module.evaluated_at.astimezone(KST):%Y-%m-%d %H:%M} KST · 30일 범위 표시 {len(module.events)}건</p><p>확인된 시각은 한국 시각으로, 날짜만 있는 일정은 미국 동부 현지 날짜로 표시합니다. 각 기준의 오늘부터 7일·30일 범위이며 달력의 날짜가 서로 다를 수 있습니다.</p><a href="#calendar-events" data-testid="calendar-thirty-anchor">30일 목록으로 이동</a></header>
<section aria-label="일정 선택"><div class="calendar-filters" data-calendar-filters hidden>
<fieldset><legend>기간</legend><button type="button" data-days="7" aria-pressed="true" data-testid="calendar-range-seven">7일</button><button type="button" data-days="30" aria-pressed="false" data-testid="calendar-range-thirty">30일</button></fieldset>
<fieldset><legend>분류</legend><button type="button" data-category-filter="all" aria-pressed="true">전체</button>{"".join(f'<button type="button" data-category-filter="{key}" aria-pressed="false">{label}</button>' for key, label in CATEGORIES.items())}</fieldset></div>
<noscript><p>JavaScript 없이 30일 목록 전체를 표시합니다. 날짜와 원천 링크를 바로 확인할 수 있습니다.</p></noscript>
<p role="status" aria-live="polite" data-calendar-status>30일 범위 표시 {len(module.events)}건</p><p data-calendar-empty {"hidden" if module.events else ""}>선택 범위에 표시할 일정이 없습니다. 아래 수집·공개 범위를 함께 확인하세요.</p>
<ol id="calendar-events" class="calendar-events">{events}</ol></section>
<section class="insights-method"><h2>수집·공개 범위</h2><p>{limitations}이 목록은 전체 시장 일정이 아닙니다. 수집 0건·실패·미확인은 일정이 없다는 뜻이 아닙니다.</p><ul class="calendar-coverage">{"".join(sources)}</ul>{attribution}</section>
<section class="insights-method"><h2>읽는 방법</h2><p>예정 날짜의 경과나 목록에서의 누락은 발표 완료·취소의 확인이 아닙니다. 실제 결과·시장 예상·예상 대비 차이는 제공하지 않습니다. 수집 시각과 원천 일정 갱신 시각은 다르며 원천 갱신 시각이 제공되지 않으면 만들어 넣지 않습니다.</p><p>이 화면의 판단은 게시 당시 기준입니다. 시간이 지난 후에는 원천에서 변경 여부를 확인하세요.</p><a href="../_data/calendar/current.json">검증된 일정 JSON</a> · <a href="../">대시보드 모음</a> · <a href="../macro/">매크로 환경</a></section>
</div>

{DISCLAIMER}
"""


def render_awaiting_calendar() -> str:
    return f"""<div class="insights-page insights-calendar"><header class="insights-hero"><p class="insights-eyebrow">UPCOMING EVENTS</p><h1>주요 일정</h1><p>공개 조건과 일정 검증을 마친 자료를 기다리고 있습니다.</p></header><p>확인된 시각은 한국 시각으로, 날짜만 있는 일정은 원천 현지 날짜와 시간 미정으로 표시합니다. 자료 대기는 일정이 없다는 뜻이 아닙니다.</p><p>예정 날짜의 경과만으로 발표 완료·취소를 판단하지 않습니다.</p><a href="../">대시보드 모음</a> · <a href="../macro/">매크로 환경</a></div>

{DISCLAIMER}
"""
