"""Static flat-group observations, with DOM-only progressive filters."""

from collections import Counter
from decimal import Decimal, localcontext
from html import escape

from investo.models.market_groups import GroupKind
from investo.models.sector import SectorRegime
from investo.models.sector_public import PublicMarketGroupBundle, PublicMarketGroupRecord
from investo.sector_dashboard.public_format import format_public_metric

_REGIMES = {
    SectorRegime.RECOVERING: "회복",
    SectorRegime.LEADING: "주도",
    SectorRegime.LAGGING: "부진",
    SectorRegime.WEAKENING: "둔화",
    SectorRegime.INSUFFICIENT: "분류 불가",
}
_KINDS = {GroupKind.INDUSTRY: "업종", GroupKind.THEME: "테마", GroupKind.REPRESENTATIVE: "대표주"}


def _proxy(record: PublicMarketGroupRecord) -> str:
    return "대표 8종목" if record.kind is GroupKind.REPRESENTATIVE else record.members[0].value


def render_market_groups(bundle: PublicMarketGroupBundle) -> list[str]:
    records = sorted(bundle.records, key=lambda r: r.relative_rank.ordinal or 15)
    lines = [
        '<section id="sector-view-groups" class="sector-view" role="tabpanel" '
        'aria-labelledby="sector-tab-groups" markdown="1">',
        "",
        "## 분야별 비교",
        "",
        '<div class="sector-group-filters" role="group" aria-label="분야 표시 필터">',
    ]
    for category, label in (
        ("all", "전체"),
        ("technology", "기술"),
        ("consumer", "소비"),
        ("financial", "금융·부동산"),
        ("other", "기타"),
    ):
        lines.append(
            f'<button type="button" data-group-filter="{category}" '
            f'data-testid="sector-filter-{category}" '
            f'aria-pressed="{str(category == "all").lower()}">{label}</button>'
        )
    lines.extend(
        [
            "</div>",
            f'<p class="sector-filter-note">{bundle.available_group_count}/14 그룹 사용 가능 · '
            "순위와 도표 눈금은 전체 비교 대상 기준 · 필터는 표시만 바꿉니다.</p>",
            '<p class="sector-filter-announcement" aria-live="polite"></p>',
            "",
        ]
    )
    lines.extend(_cards(records))
    lines.extend(['<div class="sector-chart-grid">', ""])
    lines.extend(_bars(records))
    lines.extend(_regimes(bundle))
    lines.extend(
        [
            "</div>",
            "",
            "### 분야별 상세 지표",
            "",
            '<div class="sector-group-table" tabindex="0" role="region" '
            'aria-label="분야별 상세 지표" markdown="1">',
            "",
        ]
    )
    lines.extend(_table(records))
    lines.extend(["", "</div>", "", "</section>", ""])
    return lines


def _cards(records: list[PublicMarketGroupRecord]) -> list[str]:
    ranked = [r for r in records if r.relative_rank.ordinal is not None]
    counts: Counter[SectorRegime] = Counter(
        r.primary_regime.regime
        for r in records
        if r.primary_regime.regime is not SectorRegime.INSUFFICIENT
    )
    dominant = (
        max(_REGIMES, key=lambda regime: counts[regime]) if counts else SectorRegime.INSUFFICIENT
    )
    cards = (
        (
            "상대강도 상위",
            " · ".join(_proxy(r) for r in ranked[:2]) or "계산 대기",
            "5 · 21 · 63일 상대성과 기준",
        ),
        (
            "상대강도 하위",
            " · ".join(_proxy(r) for r in ranked[-2:]) or "계산 대기",
            "14개 관찰 그룹 중 비교",
        ),
        ("가장 많은 국면", _REGIMES[dominant], f"{counts[dominant]}개 그룹 · 종목 중복 가능"),
        (
            "비교 가능한 그룹",
            f"{sum(r.metrics.price_excess_21d.value is not None for r in records)} / 14",
            "8개 이상일 때 순위 표시",
        ),
    )
    lines = ['<div class="sector-overview">']
    for label, value, note in cards:
        lines.append(
            f'<div class="sector-stat"><span class="sector-stat-label">{escape(label)}</span>'
            f'<strong class="sector-stat-value">{escape(value)}</strong>'
            f'<span class="sector-stat-note">{escape(note)}</span></div>'
        )
    return [*lines, "</div>", ""]


def _bars(records: list[PublicMarketGroupRecord]) -> list[str]:
    ordered = sorted(
        records,
        key=lambda r: (
            r.metrics.price_excess_21d.value is None,
            -(r.metrics.price_excess_21d.value or Decimal(0)),
        ),
    )
    scale = max(
        (abs(r.metrics.price_excess_21d.value or Decimal(0)) for r in records), default=Decimal(0)
    )
    lines = [
        '<section class="sector-panel" aria-labelledby="sector-group-performance-title">',
        '<div class="sector-panel-heading"><h3 id="sector-group-performance-title">'
        '21일 상대성과</h3><span class="sector-tag">SPY 대비 · pp</span></div>',
        '<p class="sector-panel-description">ETF·대표주 가격지수의 같은 기간 상대성과</p>',
        '<ol class="sector-bars">',
    ]
    for record in ordered:
        value = record.metrics.price_excess_21d.value
        with localcontext() as context:
            context.prec = 34
            width = abs(value) / scale * Decimal(48) if value is not None and scale else Decimal(0)
            left = Decimal(50) - width if value is not None and value < 0 else Decimal(50)
        fill = (
            ""
            if value is None
            else '<span class="sector-bar-fill '
            f'sector-bar-fill--{"negative" if value < 0 else "positive"}" '
            f'style="left:{left:.4f}%;width:{width:.4f}%;"></span>'
        )
        number = (
            format_public_metric(record.metrics.price_excess_21d, "pp")
            if value is not None
            else "사용 불가"
        )
        lines.append(
            '<li class="sector-bar-row sector-group-row" '
            f'data-group-category="{record.category.value}" '
            f'data-testid="sector-bar-{record.group_id.value}">'
            f'<span class="sector-bar-label"><strong>{escape(record.name)}</strong>'
            f"<small>{escape(_proxy(record))} · {_KINDS[record.kind]}</small></span>"
            f'<span class="sector-bar-track" aria-hidden="true">{fill}</span>'
            f'<span class="sector-bar-value">{escape(number)}</span></li>'
        )
    return [
        *lines,
        '</ol><p class="sector-chart-caption">왼쪽: SPY 하회 · 오른쪽: SPY 상회</p>',
        "</section>",
        "",
    ]


def _regimes(bundle: PublicMarketGroupBundle) -> list[str]:
    lines = [
        '<section class="sector-panel" aria-labelledby="sector-group-regime-title">',
        '<div class="sector-panel-heading"><h3 id="sector-group-regime-title">그룹 국면 분포</h3>'
        '<span class="sector-tag">21일 상대강도 · 5일 가속</span></div>',
        '<p class="sector-panel-description">그룹 수 기준 · 시장 비중을 뜻하지 않습니다.</p>',
        '<div class="sector-regime-grid">',
    ]
    for regime, label in _REGIMES.items():
        if regime is SectorRegime.INSUFFICIENT:
            continue
        members = [r for r in bundle.records if r.primary_regime.regime is regime]
        lines.append(
            f'<div class="sector-regime sector-regime--{regime.value}"><h4>{label}'
            f"<span data-group-regime-count>{len(members)}</span></h4>"
            '<div class="sector-regime-members">'
        )
        for record in members:
            lines.append(
                '<span class="sector-regime-ticker sector-group-chip" '
                f'data-group-category="{record.category.value}" '
                f'title="{escape(record.name)}">{escape(_proxy(record))}</span>'
            )
        lines.append(
            '<span class="sector-regime-empty" '
            f"data-group-regime-empty{' hidden' if members else ''}>"
            "해당 그룹 없음</span></div></div>"
        )
    missing = [
        r.name for r in bundle.records if r.primary_regime.regime is SectorRegime.INSUFFICIENT
    ]
    lines.extend(
        [
            "</div>",
            '<p class="sector-chart-caption">기본 중립 구간: 10 bps · '
            "이전 관찰 상태를 반영합니다.</p>",
            '<p class="sector-chart-caption">분류 불가: '
            f"{escape(' · '.join(missing)) if missing else '없음'}</p>",
            "</section>",
            "",
        ]
    )
    return lines


def _table(records: list[PublicMarketGroupRecord]) -> list[str]:
    lines = [
        '<table class="sector-group-detail-table"><thead><tr><th>순위</th>'
        "<th>관찰 그룹</th><th>측정 대상</th><th>국면</th><th>가격수익률 1D</th>"
        "<th>SPY 대비 5D</th><th>SPY 대비 21D</th><th>SPY 대비 63D</th>"
        "<th>실현변동성 20D</th><th>최대 낙폭 20D</th></tr></thead><tbody>"
    ]
    for record in records:
        rank = record.relative_rank
        metrics = record.metrics
        ordinal = (
            f"{rank.ordinal}/{rank.comparable_group_count}" if rank.ordinal is not None else "—"
        )
        values = (
            format_public_metric(metrics.price_return_1d, "%"),
            format_public_metric(metrics.price_excess_5d, "pp"),
            format_public_metric(metrics.price_excess_21d, "pp"),
            format_public_metric(metrics.price_excess_63d, "pp"),
            format_public_metric(metrics.price_realized_volatility_20d, "%"),
            format_public_metric(metrics.price_max_drawdown_20d, "%"),
        )
        cells = "".join(f"<td>{escape(value)}</td>" for value in values)
        status = (
            ""
            if rank.ordinal is not None
            else " · 사용 불가"
            if metrics.price_excess_21d.value is None
            else " · 순위 대기"
        )
        lines.append(
            f'<tr class="sector-group-row" data-group-category="{record.category.value}" '
            f'data-testid="sector-row-{record.group_id.value}"><td>{ordinal}</td>'
            f'<td><strong>{escape(record.name)}</strong><span class="sector-group-kind">'
            f"{_KINDS[record.kind]}{status}</span></td>"
            f'<td title="{escape(record.scope)}">{escape(_proxy(record))}</td>'
            f"<td>{_REGIMES[record.primary_regime.regime]}</td>{cells}</tr>"
        )
    return [*lines, "</tbody></table>"]
