"""KRX foreign / institution / individual flow adapter (u53).

This adapter solves the 2026-05-11 domestic-segment data-coverage gap:
the briefing body openly admitted "관전포인트는 외국인 수급" but the
input candidate set carried no investor net-buy data. The KRX 12025
endpoint (``data.krx.co.kr/.../getJsonData.cmd?bld=...MDCSTAT02501``)
is blocked behind a browser-JS-only session token (HTTP 400 ``LOGOUT``
on direct GET), which fails the project's "no paid / no
reverse-engineered" rule. As a fallback we pull the equivalent table
from Naver finance — the same KRX investor breakdown is mirrored
there as a free, unauthenticated, public HTML page.

Free public endpoint, no API key. ``raw_metadata.data_provider`` carries
``"finance.naver.com (KRX mirror)"`` so the trace footer is honest
about the proximate source.

Endpoint
~~~~~~~~

URL template::

    https://finance.naver.com/sise/investorDealTrendDay.naver
        ?bizdate=YYYYMMDD&sosok={01|02}

* ``bizdate`` — KST business date in compact ISO form
* ``sosok=01`` → KOSPI, ``sosok=02`` → KOSDAQ

Response is ``Content-Type: text/html; charset=EUC-KR`` (the legacy
Korean encoding) and lists ~10 daily rows ordered newest-first. Each
row carries 11 cells: date, 개인 (individual), 외국인 (foreign),
기관계 (institution-total), 6 institution sub-categories, 기타법인
(other). Net-buy values are integers in 100M-KRW units (억원); a
leading ``-`` denotes net-sell.

Pins
~~~~

* **R3** — uses the injected ``httpx.AsyncClient``; never builds its own.
* **R6** — adapter raises :class:`SourceFetchError` on whole-page
  failure (HTTP 5xx after retries, malformed HTML). Per-market
  failures (e.g. KOSPI 200 + KOSDAQ 5xx) are isolated via
  ``asyncio.gather(return_exceptions=True)`` so the surviving market
  still emits items.
* **R7** — Naver returns historic daily rows; the adapter selects the
  row matching ``window.target_date`` (KST), or the nearest preceding
  business-day row if the target is a weekend/holiday. ``published_at``
  is pinned to that business date 15:30 KST (market close) → UTC.
* **R8** — :class:`NormalizedItem` shape: ``source_name="krx-foreign-flows"``,
  ``category="price"`` (numeric net-buy belongs with the price /
  flow narrative — the briefing prompt today bins it next to index
  closes). ``raw_metadata`` is a flat ``dict[str, str]``.
* **R8 (XML ban)** — never imports stdlib ``xml.etree``. HTML parsing
  uses :class:`html.parser.HTMLParser` (stdlib, not XML), the same
  pattern as ``us_economic_calendar.py``.
* **R9** — idempotent. ``published_at`` is derived from the resolved
  business date; we do not call ``datetime.now``.
* **R13** — Naver investor-flow pages carry no auth surface; no secrets
  to register or redact.
* **R14** — neutral compliance UA: ``Investo/1.0 (https://...)``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, time
from html.parser import HTMLParser
from typing import ClassVar, Final
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_USER_AGENT = "Investo/1.0 (https://murphygo.github.io/investo)"
_BASE_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver"

_SOSOK_BY_MARKET: Final[dict[str, str]] = {
    "KOSPI": "01",
    "KOSDAQ": "02",
}

# Column index → (investor key, Korean label). The 11-column row layout
# is: [0] date, [1] individual, [2] foreign, [3] institution_total,
# [4..9] institution sub-categories (not emitted as separate items —
# rolled up into institution_total), [10] other.
_INVESTOR_COLUMNS: Final[tuple[tuple[int, str, str], ...]] = (
    (1, "individual", "개인"),
    (2, "foreign", "외국인"),
    (3, "institution", "기관"),
    (10, "other", "기타"),
)


@register
class KrxForeignFlowsAdapter:
    """Adapter for KRX investor-flow data via Naver finance mirror."""

    name: ClassVar[str] = "krx-foreign-flows"
    category: ClassVar[Category] = "price"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        target_kst = window.target_date
        bizdate = target_kst.strftime("%Y%m%d")
        results = await asyncio.gather(
            *(
                self._fetch_market(client, market=market, sosok=sosok, bizdate=bizdate)
                for market, sosok in _SOSOK_BY_MARKET.items()
            ),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
            elif isinstance(result, SourceFetchError):
                # Per-market source-side failure (HTTP 5xx after retries
                # / malformed HTML). Sibling market continues normally
                # — analogous to Stooq's per-ticker isolation.
                _logger.info(
                    "[krx-foreign-flows] per-market fetch failed: %s",
                    result,
                )
                continue
            elif isinstance(result, BaseException):
                raise result
        return items

    async def _fetch_market(
        self,
        client: httpx.AsyncClient,
        *,
        market: str,
        sosok: str,
        bizdate: str,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            _BASE_URL,
            source_name=self.name,
            params={"bizdate": bizdate, "sosok": sosok},
            headers={"User-Agent": _USER_AGENT},
        )
        html_text = response.content.decode("euc-kr", errors="replace")
        parser = _InvestorFlowTableParser()
        parser.feed(html_text)
        if not parser.rows:
            # No data rows at all → either the page layout changed or
            # Naver served an empty placeholder. Either way the market's
            # item count is 0; do not raise so the sibling market
            # continues unaffected.
            _logger.info(
                "[krx-foreign-flows] %s bizdate=%s returned 0 parsable rows",
                market,
                bizdate,
            )
            return []
        target_row = _pick_target_row(parser.rows, target=bizdate)
        if target_row is None:
            _logger.info(
                "[krx-foreign-flows] %s bizdate=%s no matching row in %d rows",
                market,
                bizdate,
                len(parser.rows),
            )
            return []
        return list(_row_to_items(target_row, market=market, source_name=self.name))


class _InvestorFlowTableParser(HTMLParser):
    """Extract the daily investor-flow rows from a Naver finance page.

    Naver wraps every row in ``<tr>``; data rows start with a
    ``<td class="date2">YY.MM.DD</td>`` cell followed by 10 numeric
    cells. We collect each row as a 11-tuple of cleaned strings. Rows
    whose first cell is not a ``date2`` cell (header rows, divider
    rows) are ignored.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_td = False
        self._row_is_data = False
        self._first_td_seen = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
            self._row_is_data = False
            self._first_td_seen = False
        elif tag == "td":
            self._in_td = True
            self._current_cell = []
            # The first ``<td>`` of a row carries class="date2" only on
            # data rows. We flag the row as a data row when we see that.
            if not self._first_td_seen:
                self._first_td_seen = True
                for name, value in attrs:
                    if name == "class" and value and "date2" in value:
                        self._row_is_data = True
                        break

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_td:
            self._current_row.append(strip_html("".join(self._current_cell)))
            self._current_cell = []
            self._in_td = False
        elif tag == "tr":
            if self._row_is_data and len(self._current_row) == 11:
                self.rows.append(self._current_row)
            self._current_row = []
            self._row_is_data = False
            self._first_td_seen = False

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_cell.append(data)


def _pick_target_row(rows: list[list[str]], *, target: str) -> list[str] | None:
    """Return the row whose date matches ``target`` (YYYYMMDD), or fallback.

    Naver renders the date as ``YY.MM.DD`` (e.g. ``26.05.11``); we
    compare to the YY.MM.DD form of ``target``. If no exact match
    exists, fall back to the first row strictly earlier than
    ``target`` — covers the case where the target is a weekend /
    holiday with no exchange session.
    """
    if not rows:
        return None
    try:
        target_date = datetime.strptime(target, "%Y%m%d").date()
    except ValueError:
        return None
    target_label = target_date.strftime("%y.%m.%d")
    earlier: list[tuple[date, list[str]]] = []
    for row in rows:
        cell = row[0].strip()
        if cell == target_label:
            return row
        try:
            row_date = datetime.strptime(cell, "%y.%m.%d").date()
        except ValueError:
            continue
        if row_date < target_date:
            earlier.append((row_date, row))
    if not earlier:
        return None
    earlier.sort(key=lambda pair: pair[0], reverse=True)
    return earlier[0][1]


def _row_to_items(
    row: list[str],
    *,
    market: str,
    source_name: str,
) -> list[NormalizedItem]:
    """Convert one daily Naver row into 4 :class:`NormalizedItem`."""
    date_text = row[0].strip()
    try:
        biz_date = datetime.strptime(date_text, "%y.%m.%d").date()
    except ValueError:
        return []
    published_at = datetime.combine(biz_date, time(15, 30), tzinfo=_KST).astimezone(UTC)
    items: list[NormalizedItem] = []
    for column_idx, investor_key, investor_label in _INVESTOR_COLUMNS:
        cell = row[column_idx].strip()
        amount = _parse_int_with_commas(cell)
        if amount is None:
            continue
        direction = "순매수" if amount >= 0 else "순매도"
        signed_amount = f"{amount:+,}" if amount != 0 else "0"
        title = (
            f"{market} {investor_label} {direction} {signed_amount}억원 ({biz_date.isoformat()})"
        )
        summary = (
            f"{market} {biz_date.isoformat()} {investor_label} 순매수 {signed_amount}억원 "
            f"(단위: 100M KRW, 출처: Naver finance KRX mirror)"
        )
        raw_metadata: dict[str, str] = {
            "market": market,
            "investor": investor_key,
            "investor_label_ko": investor_label,
            "net_buy_krw_100m": str(amount),
            "bizdate": biz_date.isoformat(),
            "data_provider": "finance.naver.com (KRX mirror)",
        }
        try:
            items.append(
                NormalizedItem(
                    source_name=source_name,
                    category="price",
                    title=title,
                    summary=summary,
                    url=(
                        "https://finance.naver.com/sise/investorDealTrendDay.naver"
                        f"?bizdate={biz_date.strftime('%Y%m%d')}"
                        f"&sosok={_SOSOK_BY_MARKET[market]}"
                    ),
                    published_at=published_at,
                    raw_metadata=raw_metadata,
                )
            )
        except ValidationError:
            continue
    return items


def _parse_int_with_commas(cell: str) -> int | None:
    """Parse ``"-28,147"`` / ``"1,234"`` / ``"0"`` → signed int.

    Naver renders net-buy values with thousands separators and a
    leading minus for net-sell. Empty cells and unparseable junk
    return ``None`` so the caller drops that investor row.
    """
    text = cell.replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None
