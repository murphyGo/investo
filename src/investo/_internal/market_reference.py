"""Source-backed supplemental reference data for native event editions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from investo._internal.crypto_indicators import validated_exchange_flows
from investo.models import NormalizedItem
from investo.models.event_document import MarketReferencePanel
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import MarketSegment

_KST = ZoneInfo("Asia/Seoul")
_KRX_URL = "https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp"


def source_market_reference(
    items: Sequence[NormalizedItem],
    *,
    anchors: tuple[MarketAnchor, ...],
    segment: MarketSegment,
    target_date: date,
    observed_at: datetime,
) -> MarketReferencePanel:
    """Rebuild supplements from collected inputs, never from generated prose."""
    expiries = set()
    if segment == "domestic-equity":
        for item in items:
            scheduled = item.scheduled_at
            if item.source_name != "krx-option-expiry" or scheduled is None:
                continue
            local = scheduled.astimezone(_KST)
            if (
                item.raw_metadata.get("event_type") == "monthly_option_last_trading_day"
                and item.raw_metadata.get("calendar_valid_through") == "2026-12-31"
                and item.raw_metadata.get("scheduled_date") == local.date().isoformat()
                and local.year == 2026
                and local.time() == time(15, 20)
                and target_date <= local.date() < target_date + timedelta(days=30)
            ):
                expiries.add(scheduled.astimezone(UTC))
    flows = (
        tuple(
            flow
            for flow in validated_exchange_flows(items)
            if flow.as_of <= observed_at
            and timedelta(0) <= observed_at - flow.as_of <= timedelta(days=1)
        )
        if segment == "crypto"
        else ()
    )
    return MarketReferencePanel(
        anchors=anchors,
        daily_exchange_flows=flows,
        calculated_option_expiries=tuple(sorted(expiries))[:2],
    )


def render_option_expiry_reference(expiries: Sequence[datetime]) -> str:
    if not expiries:
        return ""
    lines = ["### 국내 월물 옵션 일정", ""]
    for instant in expiries:
        local = instant.astimezone(_KST)
        lines.append(
            f"- {local:%Y-%m-%d %H:%M} KST · KOSPI 200 월물 옵션 최종거래일 (규칙 기반 계산)"
        )
    lines.extend(
        [
            "",
            f"출처: [KRX 상품명세]({_KRX_URL}). Investo가 둘째 목요일·휴장 시 "
            "직전 거래일 규칙으로 계산. 2026년 달력만 지원. 최종결제일·위클리 제외. "
            "임시휴장·특례는 거래소 공지 확인.",
            "",
        ]
    )
    return "\n".join(lines)
