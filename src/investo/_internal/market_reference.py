"""Source-backed supplemental reference data for native event editions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from investo._internal.crypto_indicators import validated_exchange_flows
from investo._internal.network_activity import validated_network_activity
from investo.models import NormalizedItem
from investo.models.event_document import MarketReferencePanel
from investo.models.market_anchor import MarketAnchor
from investo.models.option_expiry import PRODUCT_URL, OptionExpiry
from investo.models.segments import MarketSegment

_KST = ZoneInfo("Asia/Seoul")
_KRX_URL = PRODUCT_URL


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
            try:
                expiry = OptionExpiry.from_metadata(item.raw_metadata)
            except (ValueError, TypeError, OverflowError):
                continue
            if (
                scheduled == expiry.scheduled_at
                and target_date <= expiry.day < target_date + timedelta(days=30)
            ):
                expiries.add(expiry)
    # Preserve the nearest monthly event even when weekly dates occur earlier.
    selected_expiries = sorted(expiries, key=lambda e: (e.kind != "monthly", e.day, e.kind))[:2]
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
        daily_network_activity=tuple(
            activity
            for activity in validated_network_activity(items)
            if segment == "crypto"
            and timedelta(0) <= observed_at - activity.as_of <= timedelta(days=1)
        ),
        daily_exchange_flows=flows,
        calculated_option_expiries=tuple(sorted(selected_expiries, key=lambda e: (e.day, e.kind))),
    )


def render_option_expiry_reference(expiries: Sequence[OptionExpiry]) -> str:
    if not expiries:
        return ""
    lines = ["### 국내 옵션 일정", ""]
    for expiry in expiries:
        local = expiry.scheduled_at.astimezone(_KST)
        lines.append(
            f"- {local:%Y-%m-%d %H:%M} KST · KOSPI 200 {expiry.label} 옵션 최종거래일 "
            "(규칙 기반 계산)"
        )
    lines.extend(
        [
            "",
            f"출처: [KRX 상품명세]({_KRX_URL}). Investo가 월물 둘째 목요일, "
            "월요일 위클리 휴장은 다음 거래일, 목요일 위클리·월물 휴장은 직전 거래일로 계산. "
            "둘째 목요일 위클리 제외. 월물 우선·가까운 일정 최대 2개 표시. "
            "2026년 달력만 지원(11월 19일 수능일은 거래시간 미검증으로 제외). "
            "최종결제일·현재 상장 여부를 뜻하지 않음. "
            "임시휴장·특례는 거래소 공지 확인.",
            "",
        ]
    )
    return "\n".join(lines)
