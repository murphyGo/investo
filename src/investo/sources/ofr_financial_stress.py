"""OFR's published aggregate FSI only; bounded single-download collection."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.macro_reference import NEW_YORK, MacroObservation, macro_number
from investo.sources._macro_reference import reference_cutoff, reference_item, reference_json
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

ENDPOINT = "https://www.financialresearch.gov/financial-stress-index/data/fsi.json"


@register
class OfrFinancialStressAdapter:
    name: ClassVar[str] = "ofr-financial-stress"
    category: ClassVar[Category] = "macro"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        as_of = reference_cutoff(window)
        response = await retry_get(
            client,
            ENDPOINT,
            source_name=self.name,
            config=RetryConfig(retries=1, total_budget_s=30, max_response_bytes=5 * 1024 * 1024),
        )
        payload = reference_json(response, self.name)
        try:
            rows = payload["OFRFSI"]["data"]
            if not isinstance(rows, list) or len(rows) > 10000:
                raise ValueError("invalid point count")
            latest_day = as_of.astimezone(NEW_YORK).date() - timedelta(days=1)
            values: dict[date, str] = {}
            for point in rows:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("invalid point")
                stamp, value = point
                if type(stamp) is not int or not 0 <= stamp <= 4102444800000:
                    raise ValueError("invalid timestamp")
                instant = datetime.fromtimestamp(stamp // 1000, UTC)
                if stamp % 1000 or instant.time() != time.min:
                    raise ValueError("expected date label at UTC midnight")
                if instant.date() > latest_day:
                    continue
                if type(value) not in (int, float):
                    raise ValueError("invalid index value")
                number = macro_number(str(value))
                day = instant.date()
                if day in values and values[day] != number:
                    raise ValueError("conflicting point")
                values[day] = number
            if not values:
                return []
            latest = max(values)
            if (latest_day - latest).days >= 10:
                return []
            observation = MacroObservation(
                self.name, latest, values[latest], datetime.now(UTC), as_of
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise SourceFetchError(self.name, "invalid OFR FSI schema", transient=False) from exc
        return [reference_item(observation)]
