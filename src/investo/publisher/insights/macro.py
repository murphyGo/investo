# ruff: noqa: E501 -- HTML literals retain readable tag boundaries.
"""FR-027 deterministic macro page; validated data only, complete without JS."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from investo._internal.disclaimer import DISCLAIMER
from investo.models.insights import (
    InsightHistory,
    InsightHistoryRow,
    ValidatedInsightMetric,
    ValidatedInsightModule,
    canonical_bytes,
    digest,
)
from investo.models.insights_calendar import previous_business_day
from investo.models.insights_macro import (
    MACRO_BY_ID,
    MACRO_RECIPES,
    SPREAD_RECIPES,
    difference_exact,
)
from investo.publisher.insights.chart_view import render_yield_curve

_GROUPS = (
    ("주요 관측", ("ust_2y", "ust_10y", "ust_10y_2y_bp", "usd_krw_h10")),
    ("국채 만기와 금리차", ("ust_3m", "ust_30y", "ust_10y_3m_bp")),
    ("단기 자금시장", ("sofr", "effr", "sofr_effr_bp")),
    ("물가와 고용", ("cpi_sa_index", "core_cpi_sa_index", "unemployment_rate")),
)
_UNITS = {"percent": "%", "basis_point": "bp", "krw_per_usd": "원/USD", "index": "지수"}
_STATES = {
    "fresh": "게시 시점 기준일 확인",
    "delayed": "원천 갱신 지연",
    "stale": "지난 확인 자료",
    "unknown": "최신 여부 미확인",
}


def number(value: Decimal) -> str:
    return f"{value:,f}"


def clock_label(row: ValidatedInsightMetric) -> str:
    if row.time.period:
        return row.time.period + " 대상 · 월간 · 계절조정"
    return str(row.time.local_date) + " 기준 · 원천 현지일"


def compatible_rows(
    row: ValidatedInsightMetric, history: InsightHistory | None
) -> tuple[InsightHistoryRow, ...]:
    if history is None or history.module != "macro":
        return ()
    key = row.comparison_key()
    if not any(d.key == key for d in history.definitions):
        return ()
    end = row.time.period or str(row.time.local_date)
    return tuple(
        sorted(
            (r for r in history.rows if r.definition_key == key and r.observation_key <= end),
            key=lambda r: r.observation_key,
        )
    )[-30:]


def five_day_change(row: ValidatedInsightMetric, history: InsightHistory | None) -> Decimal | None:
    if (
        row.last_good
        or row.freshness != "fresh"
        or row.cadence != "daily"
        or row.time.local_date is None
    ):
        return None
    target: date | None = row.time.local_date
    for _ in range(5):
        if target is None:
            return None
        target = previous_business_day(target, row.calendar_policy)
    if target is None:
        return None
    rows = compatible_rows(row, history)
    old = next((r for r in rows if r.observation_key == target.isoformat()), None)
    current = next((r for r in rows if r.observation_key == row.time.local_date.isoformat()), None)
    if (
        old is None
        or current is None
        or old.revised_from
        or current.revised_from
        or current.value != row.value
    ):
        return None
    return difference_exact(row.value, old.value, scale=100 if row.unit == "percent" else 1)


def _card(mid: str, row: ValidatedInsightMetric | None, history: InsightHistory | None) -> str:
    recipe = MACRO_BY_ID[mid]
    title = escape(recipe.label)
    source = escape(recipe.provider)
    if row is None:
        return (
            f'<article class="insights-card insights-card--missing" data-metric="{mid}">'
            f'<h3>{title}</h3><p class="insights-value">— <small>{_UNITS[recipe.unit]}</small></p>'
            '<p class="insights-status">자료 미확인</p>'
            + f'<p class="insights-date">관측일 확인 전</p><a href="{escape(recipe.href, quote=True)}">{source} 원천</a></article>'
        )
    change = five_day_change(row, history)
    if change is None:
        comparison = "5영업일 비교: 자료 부족 또는 비교 제외"
    else:
        unit = "bp" if row.unit == "percent" else _UNITS[row.unit]
        comparison = f"Investo 계산 · 5원천 영업일 변화 {change:+,f} {unit}"
    state = "이전 확인값 · " if row.last_good else ""
    state += _STATES[row.freshness]
    adjustment = "1982-84=100 · 상승률 아님" if row.unit == "index" else ""
    if mid in {spread[0] for spread in SPREAD_RECIPES}:
        adjustment = "Investo 계산값 · 원천기관이 발표한 금리차가 아닙니다."
    if mid == "usd_krw_h10":
        adjustment = "H.10 뉴욕 정오 매입률 · 일별 관측/주간 공표"
    if row.cadence == "monthly":
        comparison = "다음 공식 발표일 미확인 시 최신 여부를 판정하지 않습니다."
    return (
        f'<article class="insights-card" data-metric="{mid}" data-comparison-key="{row.comparison_key()}" data-observation="{row.time.period or row.time.local_date}" data-unit="{row.unit}"><h3>{title}</h3>'
        f'<p class="insights-value">{number(row.value)} <small>{_UNITS[row.unit]}</small></p>'
        f'<p class="insights-status">{state}</p><p class="insights-date">{escape(clock_label(row))}</p>'
        f'<p>{escape(adjustment)}</p><p class="insights-comparison">{comparison}</p>'
        f'<a href="{escape(row.source_href, quote=True)}">{source} 원천</a></article>'
    )


def _history(module: ValidatedInsightModule) -> str:
    return (
        "<p>선택하면 같은 정의의 최근 30개 관측을 불러옵니다.</p>"
        + '<div class="insights-history-loader" data-history-loader>'
        '<button type="button" hidden data-load-history>관측 이력 보기</button>'
        '<p role="status" aria-live="polite" data-history-status></p>'
        "<div data-history-content></div></div>"
        '<p><a href="../_data/macro/history.json">관측 이력 원본(JSON)</a></p>'
    )


def render_macro(
    module: ValidatedInsightModule,
    history: InsightHistory | None = None,
    *,
    briefing_date: date | None = None,
) -> str:
    if module.module != "macro":
        raise ValueError("macro renderer requires macro module")
    rows = {row.metric_id: row for row in module.metrics if row.metric_id in MACRO_BY_ID}
    evaluated = module.evaluated_at.astimezone(ZoneInfo("Asia/Seoul")).strftime(
        "%Y-%m-%d %H:%M KST"
    )
    body = [
        f"<!-- insights-snapshot:{module.snapshot_id} -->",
        f'<div class="insights-page" data-insights-module="macro" data-snapshot="{module.snapshot_id}" data-current-hash="{digest(canonical_bytes(module))}">',
        '<header class="insights-hero">'
        '<p class="insights-eyebrow">MACRO OBSERVATIONS</p><h1>매크로 환경판</h1>'
        "<p>금리 · 원달러 · 물가 · 고용의 배경을 원천 관측으로 확인하세요.</p>",
        f"<p>현재 값 {len(rows)}/13 · 게시 판단 {evaluated}</p>"
        "<p>각 카드의 관측일을 확인하세요. 이 화면의 시각은 모든 지표의 공표시각이 아닙니다.</p></header>",
    ]
    for title, ids in _GROUPS:
        group_class = "insights-primary" if title == "주요 관측" else ""
        body.append(f'<section class="{group_class}" aria-label="{title}"><h2>{title}</h2>')
        # Preserve source-required notices with each presentation of its data,
        # before numeric cards and before any optional history interaction.
        notices = sorted({rows[mid].attribution for mid in ids if mid in rows})
        for notice in notices:
            body.append(f'<p class="insights-attribution">{escape(notice)}</p>')
        body.append('<div class="insights-grid">')
        body.extend(_card(mid, rows.get(mid), history) for mid in ids)
        body.append("</div></section>")
        if title == "국채 만기와 금리차":
            body.append(
                '<section aria-label="만기 비교">' + render_yield_curve(rows) + "</section>"
            )
    body.append(
        '<section aria-label="관측 이력"><h2>관측 이력</h2>' + _history(module) + "</section>"
    )
    body.append(
        '<section class="insights-method"><h2>자료와 읽는 방법</h2>'
        "<p>1bp는 0.01%p입니다. 금리차는 같은 원천·같은 유효일의 금리로만 계산합니다. CPI는 계절조정 지수이며 물가 상승률이 아닙니다.</p>"
    )
    body.append('<p><a href="../_data/NOTICE.txt">원천 데이터 이용 조건</a></p>')
    if briefing_date is not None:
        route = briefing_date.strftime("../../archive/us-equity/%Y/%m/%Y-%m-%d/")
        body.append(f'<p><a href="{route}">보관 시황 · {briefing_date.isoformat()}</a></p>')
    body.append(
        "<p>"
        '<a href="../../archive/">시황 아카이브</a> · <a href="../">대시보드 모음</a> · <a href="../../sectors/">미국 분야별</a>'
        "</p></section></div>"
    )
    return "\n".join(body) + "\n\n" + DISCLAIMER + "\n"


def render_awaiting() -> str:
    """Committed shell has no fabricated data, operational clock or snapshot identity."""
    cards = "".join(_card(r.metric_id, None, None) for r in MACRO_RECIPES)
    return (
        '# 매크로 환경판\n\n<div class="insights-page"><header class="insights-hero">'
        '<p class="insights-eyebrow">MACRO OBSERVATIONS</p>'
        "<h2>금리부터 물가까지, 시장의 배경을 한곳에서</h2>"
        "<p>첫 자료를 준비 중입니다. 각 원천의 관측일과 단위가 확인된 값부터 표시합니다.</p></header>"
        '<div class="insights-grid">'
        + cards
        + '</div><p><a href="../">대시보드 모음</a> · <a href="../../sectors/">미국 분야별</a></p></div>\n\n'
        + DISCLAIMER
        + "\n"
    )
