"""NY Fed GSCPI chart CSV, retaining observation month and release vintage."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.macro_reference import NEW_YORK, MacroObservation, macro_number
from investo.sources._macro_reference import reference_cutoff, reference_item
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

ENDPOINT = (
    "https://www.newyorkfed.org/medialibrary/research/interactives/data/"
    "gscpi/gscpi_interactive_data.csv"
)
_MONTHS = {
    name: i
    for i, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}


def _vintage(text: str) -> date:
    # The November 2026 CSV uses Excel's 1900-system serial month labels.
    if re.fullmatch(r"[0-9]{5}", text, re.ASCII):
        month = date(1899, 12, 30) + timedelta(days=int(text))
        if not 2000 <= month.year <= 2099 or month.day != 1:
            raise ValueError("invalid serial vintage")
        return month
    if not re.fullmatch(r"[A-Z][a-z]{2}-[0-9]{2}", text):
        raise ValueError("invalid vintage header")
    return date(2000 + int(text[4:]), _MONTHS[text[:3]], 1)


def _index_value(text: str) -> Decimal:
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,18})?", text, re.ASCII):
        raise ValueError("invalid index value")
    value = Decimal(text)
    if value.copy_abs() > 100:
        raise ValueError("index outside supported bounds")
    return value


def _observation_day(text: str) -> date:
    if not re.fullmatch(r"[0-9]{2}-[A-Z][a-z]{2}-[0-9]{4}", text):
        raise ValueError("invalid observation date")
    return date(int(text[7:]), _MONTHS[text[3:6]], int(text[:2]))


@register
class NyfedGscpiAdapter:
    name: ClassVar[str] = "nyfed-gscpi"
    category: ClassVar[Category] = "macro"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        as_of = reference_cutoff(window)
        response = await retry_get(
            client,
            ENDPOINT,
            source_name=self.name,
            config=RetryConfig(retries=1, total_budget_s=30, max_response_bytes=512 * 1024),
        )
        try:
            reader = csv.reader(io.StringIO(response.content.decode("utf-8-sig")), strict=True)
            header = next(reader)
            if not 2 <= len(header) <= 240 or header[0] != "Date":
                raise ValueError("invalid header")
            vintages = [_vintage(text) for text in header[1:]]
            if len(set(vintages)) != len(vintages):
                raise ValueError("duplicate vintage")
            vintage = max(vintages)
            # The current file cannot certify availability at an earlier cutoff.
            if vintage > as_of.astimezone(NEW_YORK).date():
                return []
            column = 1 + vintages.index(vintage)
            values: dict[date, Decimal] = {}
            for index, row in enumerate(reader):
                if index >= 600 or len(row) != len(header):
                    raise ValueError("CSV shape/row cap")
                if not any(cell.strip() for cell in row):
                    continue
                day = _observation_day(row[0])
                raw = row[column].strip()
                if raw in {"", "#N/A"}:
                    continue
                # Even invalid latest data must not silently fall back to older rows.
                value = _index_value(raw)
                if day in values and values[day] != value:
                    raise ValueError("conflicting observation")
                values[day] = value
            if not values:
                return []
            latest = max(values)
            if (as_of.astimezone(NEW_YORK).date() - latest).days > 75:
                return []
            # Compare duplicate source values before display precision is reduced.
            with localcontext() as context:
                context.prec = 32
                rounded = values[latest].quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
            displayed = format(rounded, "f").rstrip("0").rstrip(".") if rounded else "0"
            observation = MacroObservation(
                self.name,
                latest,
                macro_number(displayed),
                datetime.now(UTC),
                as_of,
                vintage.strftime("%Y-%m"),
            )
        except (ValueError, TypeError, KeyError, StopIteration, UnicodeError, csv.Error) as exc:
            raise SourceFetchError(self.name, "invalid GSCPI CSV schema", transient=False) from exc
        return [reference_item(observation)]
