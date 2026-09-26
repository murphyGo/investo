"""Deterministic, derived-only public projections for the u145 sector radar."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Final

from pydantic import ValidationError

from investo._internal.redaction import SECRET_ENV_VARS, scan_for_leak
from investo.models.sector import (
    MetricMissingReason,
    MetricValue,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)
from investo.models.sector_public import (
    FreshnessState,
    PublicSectorDashboardSnapshot,
    PublicSectorRecord,
    RenderedPublicSectorProjection,
    SectorAvailability,
)

MAX_PUBLIC_PROJECTION_BYTES: Final[int] = 512 * 1024
_SNAPSHOT_MARKER_PREFIX: Final[str] = "<!-- snapshot_id: "
_SECTOR_LABELS: Final[Mapping[SectorTicker, str]] = {
    SectorTicker.XLC: "커뮤니케이션 서비스",
    SectorTicker.XLY: "경기소비재",
    SectorTicker.XLP: "필수소비재",
    SectorTicker.XLE: "에너지",
    SectorTicker.XLF: "금융",
    SectorTicker.XLV: "헬스케어",
    SectorTicker.XLI: "산업재",
    SectorTicker.XLB: "소재",
    SectorTicker.XLRE: "부동산",
    SectorTicker.XLK: "정보기술",
    SectorTicker.XLU: "유틸리티",
}
_FRESHNESS_LABELS: Final[Mapping[FreshnessState, str]] = {
    FreshnessState.FRESH: "최신",
    FreshnessState.STALE: "지연",
    FreshnessState.UNKNOWN: "확인 불가",
}
_COVERAGE_LABELS: Final[Mapping[SectorCoverageStatus, str]] = {
    SectorCoverageStatus.NORMAL: "정상",
    SectorCoverageStatus.PARTIAL: "일부 커버리지",
    SectorCoverageStatus.WARMING_UP: "지표 준비 중",
    SectorCoverageStatus.INSUFFICIENT: "데이터 부족",
}
_REGIME_LABELS: Final[Mapping[SectorRegime, str]] = {
    SectorRegime.LEADING: "주도",
    SectorRegime.WEAKENING: "둔화",
    SectorRegime.RECOVERING: "회복",
    SectorRegime.LAGGING: "부진",
    SectorRegime.INSUFFICIENT: "분류 불가",
}
_RAW_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "account",
        "api_key",
        "bars",
        "close",
        "headers",
        "high",
        "low",
        "open",
        "points",
        "raw_rows",
        "request_url",
        "response_body",
        "signed_url",
        "token",
        "volume",
    }
)
_FORBIDDEN_PUBLIC_FRAGMENTS: Final[tuple[str, ...]] = (
    "미국 시장 전체",
    "미국 증시 전체 섹터",
    "미국 시장 자금 전체",
    "전체 거래량",
    "자금 유입",
    "자금 유출",
    "거래강도",
    "수급",
    "매수",
    "매도",
    "비중확대",
    "비중축소",
    "목표가",
    "overweight",
    "underweight",
    "target price",
    "actual flow",
    "dollar volume",
    "archive/",
    "site_docs/",
    "/private/",
    "download-token",
    "api.hfdatalibrary.com/v1/download",
)
_REQUIRED_FIRST_VIEWPORT_LABELS: Final[tuple[str, ...]] = (
    "제한 공개 베타",
    "IEX venue sample 기준",
    "10/11 섹터 사용 가능 · XLRE unavailable",
    "미국 전체시장 거래량 또는 자금 흐름이 아님",
)


class PublicProjectionError(ValueError):
    """Closed projection failure that never includes rejected content."""

    def __init__(self) -> None:
        super().__init__("public_projection.invalid")


def render_public_sector_projection(
    snapshot: PublicSectorDashboardSnapshot,
) -> RenderedPublicSectorProjection:
    """Render canonical JSON and Markdown from one immutable snapshot."""

    snapshot_id = _snapshot_id(snapshot)
    snapshot_bytes = _canonical_snapshot_bytes(snapshot)
    markdown_bytes = _render_markdown(snapshot).encode("utf-8")
    projection = RenderedPublicSectorProjection(
        snapshot_bytes=snapshot_bytes,
        markdown_bytes=markdown_bytes,
        snapshot_id=snapshot_id,
    )
    verify_public_sector_projection(snapshot_bytes, markdown_bytes)
    return projection


def verify_public_sector_projection(
    snapshot_bytes: bytes,
    markdown_bytes: bytes,
) -> PublicSectorDashboardSnapshot:
    """Return the parsed snapshot only when both bytes are the canonical safe pair."""

    if any(
        not payload
        or len(payload) > MAX_PUBLIC_PROJECTION_BYTES
        or b"\r" in payload
        or b"\x00" in payload
        or not payload.endswith(b"\n")
        for payload in (snapshot_bytes, markdown_bytes)
    ):
        raise PublicProjectionError
    try:
        raw = json.loads(snapshot_bytes)
        snapshot = PublicSectorDashboardSnapshot.model_validate(raw)
        markdown = markdown_bytes.decode("utf-8")
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        TypeError,
        ValueError,
    ):
        raise PublicProjectionError from None
    if not isinstance(raw, dict):
        raise PublicProjectionError
    snapshot_id = _snapshot_id(snapshot)
    if snapshot_id != _computed_snapshot_id(snapshot):
        raise PublicProjectionError
    if snapshot_bytes != _canonical_snapshot_bytes(snapshot):
        raise PublicProjectionError
    _reject_raw_snapshot_keys(raw)
    _verify_rank_contract(snapshot)
    _verify_public_text(snapshot, markdown)
    if markdown_bytes != _render_markdown(snapshot).encode("utf-8"):
        raise PublicProjectionError
    return snapshot


def _render_markdown(snapshot: PublicSectorDashboardSnapshot) -> str:
    coverage = snapshot.coverage
    as_of = snapshot.as_of_date.isoformat() if snapshot.as_of_date is not None else "기준일 없음"
    comparable = max(
        (record.relative_rank.comparable_sector_count for record in snapshot.records),
        default=0,
    )
    lines = [
        "# 미국 섹터 코어 레이더",
        "",
        "> **제한 공개 베타**",
        "> **IEX venue sample 기준**",
        "> **10/11 섹터 사용 가능 · XLRE unavailable**",
        "> 미국 전체시장 거래량 또는 자금 흐름이 아님",
        "",
        "## 기준 및 커버리지",
        "",
        f"- 기준일: {as_of} (미국 정규장 마감 기준)",
        f"- 신선도: {_FRESHNESS_LABELS[snapshot.freshness]}",
        f"- 커버리지: {_COVERAGE_LABELS[coverage.status]} · "
        f"{coverage.available_sector_count}/11 가용 · {comparable}/11 비교 가능",
        "- 벤치마크: SPY (IEX venue sample)",
        "- 출처: HF Data Library",
        f"- 정책: {snapshot.primary_policy.policy_id}",
        "- 대상: S&P 500 11개 섹터 ETF 프록시",
        "",
    ]
    if coverage.status in (SectorCoverageStatus.PARTIAL, SectorCoverageStatus.NORMAL):
        lines.extend(_render_summary(snapshot.records))
    lines.extend(_render_table(snapshot.records))
    if coverage.status in (SectorCoverageStatus.PARTIAL, SectorCoverageStatus.NORMAL):
        lines.extend(_render_quadrant(snapshot.records))
    lines.extend(_render_missing_coverage())
    lines.extend(_render_method(snapshot))
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_summary(records: Sequence[PublicSectorRecord]) -> list[str]:
    ranked = sorted(
        (record for record in records if record.relative_rank.ordinal is not None),
        key=lambda record: record.relative_rank.ordinal or 0,
    )
    if len(ranked) < 8:
        raise PublicProjectionError
    denominator = ranked[0].relative_rank.comparable_sector_count
    top = ", ".join(record.ticker.value for record in ranked[:2])
    bottom = ", ".join(record.ticker.value for record in ranked[-2:])
    counts = Counter(record.primary_regime.regime for record in ranked)
    return [
        "## 레이더 요약",
        "",
        f"- 상위 2개 ({denominator}개 비교): {top}",
        f"- 하위 2개 ({denominator}개 비교): {bottom}",
        "- 국면 분포: "
        + " · ".join(
            f"{_REGIME_LABELS[regime]} {counts[regime]}"
            for regime in (
                SectorRegime.LEADING,
                SectorRegime.WEAKENING,
                SectorRegime.RECOVERING,
                SectorRegime.LAGGING,
            )
        ),
        "- 이 IEX 샘플의 상대강도는 관찰값이며 투자 권유나 전체 종목 섹터 폭을 뜻하지 않습니다.",
        "",
    ]


def _render_table(records: Sequence[PublicSectorRecord]) -> list[str]:
    lines = [
        "## 섹터 레이더",
        "",
        "| 순위 | 섹터/티커 | 가용성 | 국면 | IEX 가격수익률 1D | "
        "SPY 대비 5D | SPY 대비 21D | 5D 상대 가속 | "
        "IEX 실현변동성 20D | IEX 최대 낙폭 20D |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in records:
        metrics = record.metrics
        lines.append(
            "| "
            + " | ".join(
                (
                    _format_rank(record),
                    f"{_SECTOR_LABELS[record.ticker]} ({record.ticker.value})",
                    _availability_label(record),
                    _REGIME_LABELS[record.primary_regime.regime],
                    _format_metric(metrics.iex_price_return_1d, "%"),
                    _format_metric(metrics.iex_price_excess_5d, "pp"),
                    _format_metric(metrics.iex_price_excess_21d, "pp"),
                    _format_metric(metrics.iex_price_relative_acceleration_5d, "pp"),
                    _format_metric(metrics.iex_price_realized_volatility_20d, "%"),
                    _format_metric(metrics.iex_price_max_drawdown_20d, "%"),
                )
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_quadrant(records: Sequence[PublicSectorRecord]) -> list[str]:
    lines = ["## 텍스트 국면", "", "기본 중립 구간: 10 bps", ""]
    for regime in (
        SectorRegime.LEADING,
        SectorRegime.WEAKENING,
        SectorRegime.RECOVERING,
        SectorRegime.LAGGING,
    ):
        tickers = [
            record.ticker.value for record in records if record.primary_regime.regime is regime
        ]
        lines.append(f"- {_REGIME_LABELS[regime]}: {', '.join(tickers) if tickers else '없음'}")
    unavailable = [
        record.ticker.value
        for record in records
        if record.primary_regime.regime is SectorRegime.INSUFFICIENT
    ]
    lines.extend([f"- 분류 불가: {', '.join(unavailable) if unavailable else '없음'}", ""])
    return lines


def _render_missing_coverage() -> list[str]:
    return [
        "## 미제공 커버리지",
        "",
        "- HF v1 카탈로그는 XLRE를 제공하지 않습니다.",
        "- 대체 ETF나 추정 시리즈를 사용하지 않습니다.",
        "- 순위는 현재 비교 가능한 섹터 샘플만 대상으로 합니다.",
        "- 커버리지 확장은 별도로 검증된 출처 버전이 필요합니다.",
        "",
    ]


def _render_method(snapshot: PublicSectorDashboardSnapshot) -> list[str]:
    lines = [
        "## 방법과 출처",
        "",
        "- 수익률은 IEX 일별 종가의 단순 수익률입니다.",
        "- 초과 수익률은 같은 날짜 구간의 섹터 수익률에서 SPY 수익률을 뺀 값입니다.",
        "- 5D 상대 가속은 현재 5일과 직전의 겹치지 않는 5일 초과 수익률 차이입니다.",
        "- 실현변동성은 20개 일별 단순 수익률을 연율화한 값이고, 최대 낙폭은 "
        "20세션 구간의 고점 대비 종가 변화입니다.",
        "- IEX volume은 점수, 순위, 국면 및 요약에서 제외됩니다.",
        f"- 방법론: {snapshot.primary_policy.policy_id} · 소스 스키마 v{snapshot.schema_version}",
        "",
        "### 출처 및 라이선스",
        "",
    ]
    for attribution in snapshot.provenance.attributions:
        lines.append(f"- [{attribution.display_text}]({attribution.url})")
    lines.extend(
        [
            "",
            "이 자료는 정보 제공용이며 투자 권유, 예측 또는 개인화된 조언이 아닙니다.",
            f"<!-- snapshot_id: {_snapshot_id(snapshot)} -->",
            "",
        ]
    )
    return lines


def _format_rank(record: PublicSectorRecord) -> str:
    rank = record.relative_rank
    if rank.ordinal is None or rank.comparable_sector_count <= 0:
        return "—"
    return f"{rank.ordinal}/{rank.comparable_sector_count}"


def _format_metric(metric: MetricValue, unit: str) -> str:
    if metric.value is None:
        return "—"
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        displayed = (metric.value * Decimal(100)).quantize(Decimal("0.01"))
    if displayed == 0:
        displayed = Decimal("0.00")
    sign = "+" if displayed > 0 else ""
    return f"{sign}{displayed:.2f} {unit}"


def _availability_label(record: PublicSectorRecord) -> str:
    if record.availability is SectorAvailability.TEMPORARILY_UNAVAILABLE:
        return "일시 수집 불가"
    if record.availability is SectorAvailability.PROVIDER_UNAVAILABLE:
        return "provider 미지원"
    if record.availability is SectorAvailability.INSUFFICIENT_HISTORY:
        return "이력 부족"
    reasons = {
        value.missing_reason
        for name, value in record.metrics
        if name != "ticker" and value.missing_reason is not None
    }
    if MetricMissingReason.WARMING_UP in reasons:
        return "사용 가능 · 장기 지표 준비 중"
    if reasons:
        return "사용 가능 · 일부 지표 부족"
    return "사용 가능"


def _snapshot_id(snapshot: PublicSectorDashboardSnapshot) -> str:
    if snapshot.snapshot_id is None:
        raise PublicProjectionError
    return snapshot.snapshot_id


def _computed_snapshot_id(snapshot: PublicSectorDashboardSnapshot) -> str:
    payload = snapshot.model_dump(mode="json", exclude={"snapshot_id"})
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _canonical_snapshot_bytes(snapshot: PublicSectorDashboardSnapshot) -> bytes:
    payload = snapshot.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _reject_raw_snapshot_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in _RAW_SNAPSHOT_KEYS:
                raise PublicProjectionError
            _reject_raw_snapshot_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_snapshot_keys(child)


def _verify_rank_contract(snapshot: PublicSectorDashboardSnapshot) -> None:
    if snapshot.coverage.status not in (
        SectorCoverageStatus.PARTIAL,
        SectorCoverageStatus.NORMAL,
    ):
        return
    ranked = [
        record.relative_rank
        for record in snapshot.records
        if record.relative_rank.score is not None
    ]
    expected_count = snapshot.coverage.available_sector_count
    if (
        len(ranked) != expected_count
        or {rank.ordinal for rank in ranked} != set(range(1, expected_count + 1))
        or {rank.comparable_sector_count for rank in ranked} != {expected_count}
    ):
        raise PublicProjectionError


def _verify_public_text(snapshot: PublicSectorDashboardSnapshot, markdown: str) -> None:
    snapshot_id = _snapshot_id(snapshot)
    if markdown.count(f"{_SNAPSHOT_MARKER_PREFIX}{snapshot_id} -->") != 1:
        raise PublicProjectionError
    metric_position = markdown.find("## 섹터 레이더")
    if metric_position < 0 or any(
        (position := markdown.find(label)) < 0 or position > metric_position
        for label in _REQUIRED_FIRST_VIEWPORT_LABELS
    ):
        raise PublicProjectionError
    for attribution in snapshot.provenance.attributions:
        if f"[{attribution.display_text}]({attribution.url})" not in markdown:
            raise PublicProjectionError
    lowered = markdown.casefold()
    if any(fragment.casefold() in lowered for fragment in _FORBIDDEN_PUBLIC_FRAGMENTS):
        raise PublicProjectionError
    combined = (_canonical_snapshot_bytes(snapshot).decode("utf-8") + markdown).replace(
        snapshot_id, "[SNAPSHOT_ID]"
    )
    if any(name.casefold() in combined.casefold() for name in SECRET_ENV_VARS):
        raise PublicProjectionError
    if scan_for_leak(combined) is not None:
        raise PublicProjectionError


__all__ = [
    "MAX_PUBLIC_PROJECTION_BYTES",
    "PublicProjectionError",
    "render_public_sector_projection",
    "verify_public_sector_projection",
]
