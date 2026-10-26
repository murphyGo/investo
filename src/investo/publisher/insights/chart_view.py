# ruff: noqa: E501 -- HTML literals preserve tag boundaries.
"""u184 exact-value table and proportionate, labeled no-JS yield-curve fallback."""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from html import escape

from investo.models.insights import ValidatedInsightMetric
from investo.models.insights_macro import MACRO_BY_ID

MATURITIES = (
    ("ust_3m", Decimal("0.25")),
    ("ust_2y", Decimal(2)),
    ("ust_10y", Decimal(10)),
    ("ust_30y", Decimal(30)),
)


def yield_domain(values: list[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    """Readable linear axis bounds; does not modify any underlying observation."""
    with localcontext() as context:
        context.prec = 96
        low, high = min(values), max(values)
        pad = (
            (high - low) * Decimal("0.12")
            if low != high
            else max(abs(low) * Decimal("0.05"), Decimal("0.1"))
        )
        rough = (high - low + 2 * pad) / 4
        magnitude = Decimal(10) ** rough.adjusted()
        step = (
            next(n for n in map(Decimal, ("1", "2", "2.5", "5", "10")) if n * magnitude >= rough)
            * magnitude
        )
        lower = ((low - pad) / step).to_integral_value(rounding=ROUND_FLOOR) * step
        upper = ((high + pad) / step).to_integral_value(rounding=ROUND_CEILING) * step
        return lower, upper, step


def _label(value: Decimal) -> str:
    return format(value.normalize(), "f")


def render_yield_curve(rows: dict[str, ValidatedInsightMetric]) -> str:
    # Accepted source decimals are bounded to 64 characters; keep subtraction
    # and tick arithmetic precise even when observations differ far past float precision.
    with localcontext() as context:
        context.prec = 96
        return _render_yield_curve(rows)


def _render_yield_curve(rows: dict[str, ValidatedInsightMetric]) -> str:
    selected = [rows.get(mid) for mid, _ in MATURITIES]
    table = (
        "<table><caption>원천 기준일별 4개 만기 관측 · 금리 %</caption><thead><tr>"
        '<th scope="col">만기</th><th scope="col">금리 (%)</th><th scope="col">기준일</th></tr></thead><tbody>'
    )
    for (mid, years), row in zip(MATURITIES, selected, strict=True):
        attrs = f' data-curve-x="{years}" data-curve-y="{row.value}"' if row else ""
        value = f"{row.value:,f} %" if row else "—"
        table += (
            f'<tr{attrs}><th scope="row">{escape(MACRO_BY_ID[mid].label)}</th>'
            f"<td>{value}</td><td>{row.time.local_date if row else '미확인'}</td></tr>"
        )
    table += "</tbody></table>"
    complete = all(
        row is not None and not row.last_good and row.time.local_date for row in selected
    )
    dates = {row.time.local_date for row in selected if row is not None}
    if not complete or len(dates) != 1:
        return "<p>같은 날짜의 네 만기 자료가 모이면 비교 그림을 표시합니다.</p>" + table
    values = [row.value for row in selected if row is not None]
    low, high, step = yield_domain(values)
    points = [
        (64 + float(years / 30) * 526, 236 - float((value - low) / (high - low)) * 194)
        for (_, years), value in zip(MATURITIES, values, strict=True)
    ]
    line = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
    marks = []
    for index in range(min(12, int((high - low) / step) + 1)):
        tick = low + index * step
        y = 236 - float((tick - low) / (high - low)) * 194
        marks.append(
            f'<line x1="64" x2="590" y1="{y:.3f}" y2="{y:.3f}" class="insights-chart-grid"/>'
            f'<text x="55" y="{y + 5:.3f}" text-anchor="end">{_label(tick)}</text>'
        )
    for tick_years in (0, 10, 20, 30):
        x = 64 + tick_years / 30 * 526
        marks.append(f'<text x="{x:.3f}" y="260" text-anchor="middle">{tick_years}</text>')
    dots = "".join(
        f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4"><title>{years}년 · {value:f}%</title></circle>'
        for ((_, years), value, (x, y)) in zip(MATURITIES, values, points, strict=True)
    )
    notices = "".join(
        f'<p class="insights-attribution">{escape(notice)}</p>'
        for notice in sorted({row.attribution for row in selected if row is not None})
    )
    return (
        f'<figure class="insights-plot" data-curve-chart data-y-min="{low}" data-y-max="{high}">'
        f"<figcaption>미 국채 만기별 금리 · {next(iter(dates))} 기준</figcaption>{notices}"
        '<p class="insights-axis-note">가로축: 만기(년), 3개월=0.25년 · 실제 만기 간격. '
        f"세로축: 금리(%) · 선형 · {_label(low)}~{_label(high)}% 자동 범위, 0에 고정하지 않음.</p>"
        '<p class="insights-chart-note">원천의 네 관측점을 연결합니다. 사이 만기의 금리를 추정한 곡선은 아닙니다.</p>'
        "<div data-chart-mount></div>"
        '<svg class="insights-curve" data-chart-fallback viewBox="0 0 640 300" role="img" aria-labelledby="macro-curve-title macro-curve-desc">'
        '<title id="macro-curve-title">미 국채 만기와 금리</title>'
        '<desc id="macro-curve-desc">가로축은 0~30년 실제 만기 간격, 세로축은 퍼센트 금리의 선형 눈금입니다. 정확한 값과 날짜는 다음 표에 있습니다.</desc>'
        '<text x="64" y="24">금리 (%)</text>'
        + "".join(marks)
        + '<text x="327" y="289" text-anchor="middle">만기 (년)</text>'
        + f'<polyline points="{line}" fill="none" stroke="currentColor" stroke-width="2.5"/>{dots}</svg>'
        + '<p data-chart-status role="status"></p>'
        + table
        + "</figure>"
    )
