"""KRX KOSPI 200 monthly option last-trading calendar (rule-derived)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar
from zoneinfo import ZoneInfo

import httpx

from investo.models import Category, NormalizedItem
from investo.models.market_calendar import KRX_HOLIDAYS_2026
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_PRODUCT_URL = "https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp"
_RULE_VERSION = "kospi200-monthly-2026-10-28"
_CALENDAR_VERSION = "krx-2026-reviewed-2026-10-29"
_KST = ZoneInfo("Asia/Seoul")


def _monthly_expiry(year: int, month: int, holidays: frozenset[date]) -> date:
    first = date(year, month, 1)
    day = first + timedelta(days=(3 - first.weekday()) % 7 + 7)
    for _ in range(14):
        if day.weekday() < 5 and day not in holidays:
            return day
        day -= timedelta(days=1)
    raise ValueError("holiday calendar contains no nearby trading day")


@register
class KrxOptionExpiryAdapter:
    name: ClassVar[str] = "krx-option-expiry"
    category: ClassVar[Category] = "calendar"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        start = window.target_date
        end = start + timedelta(days=30)
        if start.year != 2026:
            raise SourceFetchError(
                self.name, "monthly expiry calendar requires annual qualification", transient=False
            )
        items = []
        last_month = end.month if end.year == 2026 else 12
        for month in range(start.month, last_month + 1):
            day = _monthly_expiry(2026, month, KRX_HOLIDAYS_2026)
            if not start <= day < end:
                continue
            scheduled = datetime.combine(day, time(15, 20), _KST).astimezone(UTC)
            items.append(
                NormalizedItem(
                    source_name=self.name,
                    category=self.category,
                    title=f"KOSPI 200 월물 옵션 최종거래일 — {day} (규칙 기반 계산)",
                    summary=(
                        f"{day} 15:20 KST. KRX 둘째 목요일·휴장 시 직전 거래일 규칙으로 "
                        "Investo 계산. 최종결제일/위클리 제외. 임시휴장·특례는 거래소 공지 확인."
                    ),
                    url=_PRODUCT_URL,
                    published_at=window.start_utc,
                    scheduled_at=scheduled,
                    raw_metadata={
                        "event_type": "monthly_option_last_trading_day",
                        "scheduled_date": day.isoformat(),
                        "local_time": "15:20 KST",
                        "calculation": "second-thursday-previous-trading-day",
                        "rule_version": _RULE_VERSION,
                        "calendar_version": _CALENDAR_VERSION,
                        "calendar_valid_through": "2026-12-31",
                    },
                )
            )
        if not items and end.year != 2026:
            raise SourceFetchError(
                self.name, "monthly expiry calendar requires annual qualification", transient=False
            )
        return items
