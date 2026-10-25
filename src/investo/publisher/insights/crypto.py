"""FR-029: validated observations, explicit scopes and compatible daily sample changes."""
# ruff: noqa: E501 -- Keep HTML tag boundaries readable.

from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from investo._internal.disclaimer import DISCLAIMER_CRYPTO
from investo.models.insights import (
    InsightHistory,
    ValidatedInsightMetric,
    ValidatedInsightModule,
    canonical_bytes,
    digest,
)
from investo.models.insights_crypto import CRYPTO_BY_ID, CRYPTO_SLOTS, exact_difference, exact_scale

KST = ZoneInfo("Asia/Seoul")
GUIDES = {
    "btc_dominance": "CoinGecko 추적 자산 시가총액에서 BTC가 차지하는 비율입니다.",
    "market_cap_usd": "CoinGecko가 추적하는 자산의 USD 평가 시가총액 합계입니다.",
    "usd_stablecoin_supply": "peggedUSD 공급 단위의 합계입니다. 1단위=1USD의 액면 기준이며 실제 시장가격 평가액·순유입이 아닙니다.",
    "chain_tvl_sum": "제공된 체인별 TVL의 합계입니다. 가격·체인 범위·중복 자산의 영향을 받으며 순자금 유입·거래활동을 뜻하지 않습니다.",
    "btc_funding": "해당 계약·주기의 지시적 펀딩비입니다. 확정 정산값·24시간 평균·연율이 아닙니다.",
    "btc_oi_usd": "해당 거래소 BTC 계약의 USD 명목 미결제약정입니다. 코인 수량·계약 수·전체 시장 OI와 다릅니다.",
    "fear_greed_index": "Alternative.me의 BTC 중심 지수(0~100)입니다. 자체 위험 등급이나 매매 신호로 변환하지 않습니다.",
}
REASONS = {
    "rights_unverified": "공개 조건 확인 필요",
    "rights_revoked": "공개 조건 철회",
    "source_failed": "수집 실패",
    "source_zero": "수집 0건",
    "source_skipped": "수집 건너뜀",
    "time_unknown": "원천 시각 미확인",
    "stale": "관측 시점 경과",
    "definition_conflict": "정의·표본 충돌",
    "invalid_value": "값·단위 검증 제외",
    "missing_input": "확인된 자료 없음",
}
ATTEMPTS = {
    "ok": "수집됨",
    "zero": "수집 0건",
    "failed": "수집 실패",
    "skipped": "수집 건너뜀",
    "missing": "수집 미확인",
}
SOURCE_LABELS = {
    "coingecko-global-market": "CoinGecko",
    "defillama-market-structure": "DeFiLlama",
    "bybit-derivatives": "Bybit 경로",
    "okx-derivatives": "OKX 직접 경로",
    "alternative-fng": "Alternative.me",
}


def number(value: Decimal) -> str:
    result = format(value, ",f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def seven_day_change(
    row: ValidatedInsightMetric, module: ValidatedInsightModule, history: InsightHistory | None
) -> Decimal | None:
    if history is None or history.module != "crypto" or row.last_good or row.freshness != "fresh":
        return None
    day = module.collection_completed_at.astimezone(UTC).date()
    baseline = (day - timedelta(days=7)).isoformat()
    rows = {r.observation_key: r for r in history.rows if r.definition_key == row.comparison_key()}
    current, previous = rows.get(day.isoformat()), rows.get(baseline)
    if current is None or previous is None or current.revised_from or previous.revised_from:
        return None
    if current.value != row.value or canonical_bytes(current.time) != canonical_bytes(row.time):
        return None
    return exact_difference(row.value, previous.value)


def _clock(row: ValidatedInsightMetric) -> str:
    clock = row.time
    if clock.basis == "collection_window":
        return (
            f"원천 갱신시각 미상 · 수집 구간 관찰 {clock.window_start.astimezone(KST):%Y-%m-%d %H:%M:%S} ~ {clock.window_end.astimezone(KST):%H:%M:%S} KST"
            if clock.window_start and clock.window_end
            else "원천 시각 미확인"
        )
    at = clock.source_updated_at or clock.exact_at
    label = (
        "지수 기준시각"
        if row.metric_id == "fear_greed_index"
        else "원천 갱신시각"
        if clock.source_updated_at
        else "제공자 응답 시각"
    )
    return f"{label} {at.astimezone(KST):%Y-%m-%d %H:%M:%S} KST" if at else "원천 시각 미확인"


def _card(mid: str, module: ValidatedInsightModule, history: InsightHistory | None) -> str:
    recipe = CRYPTO_BY_ID[mid]
    row = next((r for r in module.metrics if r.metric_id == mid), None)
    if row is None:
        slot_status = (
            next((s for s in module.crypto_coverage.slots if s.metric_id == mid), None)
            if module.crypto_coverage
            else None
        )
        reason = (
            " · ".join(REASONS[r] for r in slot_status.reasons if r in REASONS)
            if slot_status
            else "확인된 자료 없음"
        )
        return f'<article class="insights-card insights-card--missing" data-metric="{mid}"><h3>{recipe.label}</h3><p class="insights-value">—</p><p class="insights-status">{escape(reason)}</p><p>{GUIDES[mid]}</p><a href="{recipe.href}">원천 안내</a></article>'
    value = exact_scale(row.value, 100) if mid == "btc_funding" else row.value
    unit = (
        "%"
        if row.unit in {"fraction", "percent"}
        else "지수"
        if row.unit == "index"
        else "USD 명목"
        if row.unit == "usd_notional"
        else "USD 액면"
        if mid == "usd_stablecoin_supply"
        else "USD"
    )
    status = "이전 검증 관찰" if row.last_good else "게시 시점 기준 관찰"
    if row.freshness != "fresh":
        status += " · 관측 시점 경과" if row.freshness == "stale" else " · 최신 여부 미확인"
    scope = (
        "BTCUSDT · 선형 무기한"
        if row.provider == "Bybit"
        else "BTC-USD-SWAP · 역선형 무기한"
        if row.provider == "OKX"
        else "제공자 추적 범위"
    )
    cycle = ""
    if mid == "btc_funding" and row.time.applicable_start and row.time.applicable_end:
        cycle = f'<p class="crypto-cycle">지시적 관찰 · 적용 주기 {row.time.applicable_start.astimezone(KST):%Y-%m-%d %H:%M} ~ {row.time.applicable_end.astimezone(KST):%Y-%m-%d %H:%M} KST</p>'
    change = seven_day_change(row, module, history)
    comparison = "7일 표본 비교: 자료 부족 또는 비교 제외"
    if change is not None:
        change_unit = "%p" if row.unit in {"percent", "fraction"} else unit
        if row.unit == "fraction":
            change = exact_scale(change, 100)
        comparison = f"7일 관찰 표본 차이 {'+' if change > 0 else ''}{number(change)} {change_unit}"
    sampled = module.collection_completed_at.astimezone(UTC).date().isoformat()
    return f'<article class="insights-card" data-metric="{mid}" data-comparison-key="{row.comparison_key()}" data-unit="{row.unit}" data-observation="{sampled}"><h3>{recipe.label}</h3><p class="insights-value">{number(value)} <small>{unit}</small></p><p class="crypto-attribution">{escape(row.attribution)}</p><p class="insights-status">{status}</p><p>{escape(row.provider)} · {scope}</p><p class="insights-date">{_clock(row)}</p>{cycle}<p class="insights-comparison">{comparison}</p><p>{GUIDES[mid]}</p><a href="{escape(row.source_href, quote=True)}">{escape(row.provider)} 원천</a></article>'


def render_crypto(module: ValidatedInsightModule, history: InsightHistory | None = None) -> str:
    if module.module != "crypto":
        raise ValueError("crypto renderer requires crypto module")
    panels = (
        ("시장 규모", CRYPTO_SLOTS[:2]),
        ("공급·TVL 참고", CRYPTO_SLOTS[2:4]),
        ("BTC 거래소 파생상품", CRYPTO_SLOTS[4:6]),
        ("보조 심리", CRYPTO_SLOTS[6:]),
    )
    sections = "".join(
        f'<section><h2>{title}</h2><div class="insights-grid">{"".join(_card(mid, module, history) for mid in mids)}</div></section>'
        for title, mids in panels
    )
    sources = ""
    if module.crypto_coverage:
        sources = "".join(
            f"<li>{SOURCE_LABELS.get(s.source_name, '검증 출처')} · {ATTEMPTS[s.latest_attempt]} · {dict(allowed='공개 범위 확인', blocked='공개 조건 미충족', mixed='일부 정의 공개', unverified='공개 조건 미확인')[s.rights]}</li>"
            for s in module.crypto_coverage.sources
        )
    return f'''<!-- insights-snapshot:{module.snapshot_id} -->
<div class="insights-page insights-crypto" data-insights-module="crypto" data-snapshot="{module.snapshot_id}" data-current-hash="{digest(canonical_bytes(module))}">
<header class="insights-hero"><p class="insights-eyebrow">CRYPTO OBSERVATIONS</p><h1>크립토 시장 내부</h1><p>시장 규모 · 공급·TVL · BTC 파생상품을 관측 범위와 함께 확인하세요.</p><p>게시 판단 {module.evaluated_at.astimezone(KST):%Y-%m-%d %H:%M} KST · 현재 관찰 {sum(r.metric_id in CRYPTO_SLOTS for r in module.metrics)}/7</p><p>카드마다 제공자·계약·관측 시각이 다릅니다. 게시 당시 기준이며 실시간·일봉 종가·하루 평균을 뜻하지 않습니다.</p></header>
{sections}
<section><h2>관찰 이력</h2><p>UTC 수집 날짜별 마지막 원격 확인 표본입니다. 같은 제공자·계약·정의·펀딩 주기의 D와 D-7 표본이 있을 때만 차이를 표시합니다. 당일 표본 교체와 같은 시점의 수정은 구별합니다.</p><button type="button" class="insights-history-button" data-load-history hidden data-testid="crypto-load-history">최근 30개 표본 보기</button><p role="status" aria-live="polite" data-history-status>이력은 선택한 뒤 확인합니다.</p><div data-history-content></div><a href="../_data/crypto/history.json">검증된 관찰 이력 JSON</a></section>
<section class="insights-method"><h2>출처·해석 범위</h2><ul>{sources}</ul><p>수집 상태는 경로의 결과입니다. 카드의 실제 제공자를 확인하세요. Bybit 경로에서 OKX 대체 응답이 제공될 수 있으며 두 거래소 값을 합산하지 않습니다.</p><p>펀딩은 원천이 확인한 적용 주기의 지시적 관찰이며 시간 경과로 확정 정산값이 되지 않습니다. 미결제약정은 특정 거래소·계약의 USD 명목값입니다. TVL·공급 변화를 순유입으로 해석하지 않습니다.</p><p>공개 조건·자료·시점이 미확인인 카드는 값을 표시하지 않습니다. 정상적인 다른 지표는 계속 표시합니다.</p><a href="../">대시보드 모음</a> · <a href="../macro/">매크로 환경</a> · <a href="../calendar/">주요 일정</a></section>
</div>

{DISCLAIMER_CRYPTO}
'''


def render_awaiting_crypto() -> str:
    cards = "".join(
        f'<article class="insights-card insights-card--missing"><h2>{CRYPTO_BY_ID[mid].label}</h2><p>확인된 공개 관찰 자료를 기다립니다.</p><p>{GUIDES[mid]}</p></article>'
        for mid in CRYPTO_SLOTS
    )
    return f'<div class="insights-page insights-crypto"><header class="insights-hero"><p class="insights-eyebrow">CRYPTO OBSERVATIONS</p><h1>크립토 시장 내부</h1><p>공개 조건·단위·관측 시각을 확인한 자료를 기다립니다.</p></header><div class="insights-grid">{cards}</div><a href="../">대시보드 모음</a></div>\n\n{DISCLAIMER_CRYPTO}\n'
