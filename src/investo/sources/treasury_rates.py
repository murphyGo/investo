"""U.S. Treasury daily yield-curve rates adapter."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import ClassVar
from urllib.parse import urlencode

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_DATA_PAGE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_M_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
_D_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"
_NY_CLOSE_UTC = time(21, 0, tzinfo=UTC)


@register
class TreasuryRatesAdapter:
    """Adapter for Treasury daily par yield curve XML."""

    name: ClassVar[str] = "treasury-rates"
    category: ClassVar[Category] = "macro"

    _ENDPOINT: ClassVar[str] = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    )

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        rows = await self._fetch_year(client, window.target_date.year)
        if not rows and window.target_date.month == 1:
            rows = await self._fetch_year(client, window.target_date.year - 1)
        selected = _select_latest_row(rows, target_date=window.target_date)
        if selected is None:
            return []
        try:
            return [_row_to_item(selected, source_name=self.name, target_date=window.target_date)]
        except (TypeError, ValueError, ValidationError):
            return []

    async def _fetch_year(self, client: httpx.AsyncClient, year: int) -> list[dict[str, str]]:
        query = urlencode({"data": "daily_treasury_yield_curve", "field_tdr_date_value": str(year)})
        url = f"{self._ENDPOINT}?{query}"
        response = await retry_get(client, url, source_name=self.name)
        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed XML: {exc}",
                transient=False,
                cause=exc,
            ) from exc
        rows: list[dict[str, str]] = []
        for entry in root.iter(f"{_ATOM_NS}entry"):
            properties = entry.find(f"{_ATOM_NS}content/{_M_NS}properties")
            if properties is None:
                continue
            row: dict[str, str] = {}
            for child in list(properties):
                key = child.tag.removeprefix(_D_NS)
                row[key] = (child.text or "").strip()
            if row:
                rows.append(row)
        return rows


def _select_latest_row(rows: list[dict[str, str]], *, target_date: date) -> dict[str, str] | None:
    dated_rows: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        try:
            row_date = _parse_date(row.get("NEW_DATE", ""))
        except ValueError:
            continue
        if row_date <= target_date:
            dated_rows.append((row_date, row))
    if not dated_rows:
        return None
    return max(dated_rows, key=lambda pair: pair[0])[1]


def _row_to_item(row: dict[str, str], *, source_name: str, target_date: date) -> NormalizedItem:
    row_date = _parse_date(row["NEW_DATE"])
    three_month = _parse_rate(row.get("BC_3MONTH"))
    two_year = _parse_rate(row.get("BC_2YEAR"))
    ten_year = _parse_rate(row.get("BC_10YEAR"))
    thirty_year = _parse_rate(row.get("BC_30YEAR"))
    spread_2y10y = ten_year - two_year
    spread_3m10y = ten_year - three_month
    published_at = datetime.combine(row_date, _NY_CLOSE_UTC)
    title = f"UST curve {row_date.isoformat()}: 10Y {ten_year:.2f}%, 2Y10Y {spread_2y10y:+.2f}pp"
    summary = (
        f"3M:{three_month:.2f}% 2Y:{two_year:.2f}% 10Y:{ten_year:.2f}% "
        f"30Y:{thirty_year:.2f}% 3M10Y:{spread_3m10y:+.2f}pp"
    )
    return NormalizedItem(
        source_name=source_name,
        category="macro",
        title=title,
        summary=summary,
        url=_DATA_PAGE_URL,
        published_at=published_at,
        raw_metadata={
            "date": row_date.isoformat(),
            "3m": format_float(three_month),
            "2y": format_float(two_year),
            "10y": format_float(ten_year),
            "30y": format_float(thirty_year),
            "spread_2y10y_pp": format_float(spread_2y10y),
            "spread_3m10y_pp": format_float(spread_3m10y),
            "source_date_lag_days": str((target_date - row_date).days),
        },
    )


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _parse_rate(value: str | None) -> float:
    text = (value or "").strip()
    if not text:
        raise ValueError("missing rate")
    return float(text)
