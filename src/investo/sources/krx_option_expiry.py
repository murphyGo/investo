"""Rule-derived KRX KOSPI 200 monthly and Monday/Thursday weekly calendar."""

from __future__ import annotations

from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.option_expiry import PRODUCT_URL, option_expiries
from investo.models.option_expiry import monthly_expiry as _monthly_expiry  # noqa: F401
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError


@register
class KrxOptionExpiryAdapter:
    name: ClassVar[str] = "krx-option-expiry"
    category: ClassVar[Category] = "calendar"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        try:
            expiries = option_expiries(window.target_date)
        except ValueError as exc:
            raise SourceFetchError(self.name, str(exc), transient=False) from exc
        return [
            NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=f"KOSPI 200 {expiry.label} 옵션 최종거래일 — {expiry.day} (규칙 기반 계산)",
                summary=(
                    f"{expiry.day} 15:20 KST. KRX 월물 둘째 목요일, 월요일 위클리 휴장은 "
                    "다음 거래일, 목요일 위클리·월물 휴장은 직전 거래일로 Investo 계산. "
                    "둘째 목요일 위클리 제외. 최종결제일·현재 상장 여부를 뜻하지 않음. "
                    "2026년 달력만 지원하며 수능일 11월 19일은 거래시간 미검증으로 제외. "
                    "임시휴장·특례는 거래소 공지 확인."
                ),
                url=PRODUCT_URL,
                published_at=window.start_utc,
                scheduled_at=expiry.scheduled_at,
                raw_metadata=expiry.metadata(),
            )
            for expiry in expiries
        ]
