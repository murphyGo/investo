"""Alternative.me Crypto Fear & Greed adapter (FD L6.13, u66).

Fetches the latest Crypto Fear & Greed Index value from the no-key
Alternative.me endpoint and emits a single :class:`NormalizedItem` with
``category="macro"`` tagged ``indicator=fear_greed``. This is a crypto-
native sentiment anchor consumed by the u74 crypto indicator contract.

Design choices (u66 plan 2026-05-24):

* **No key, no secret** — Alternative.me ``/fng/`` is fully public; R13
  has no surface here.
* **Snapshot semantics** — the index is a once-daily value; the Unix
  ``timestamp`` field is used for ``published_at`` (R9 idempotent, never
  ``datetime.now()``). The crypto segment runs on a UTC 24h frame, so the
  daily 00:00Z stamp lands inside the window.
* **Single item** — ``limit=1`` returns the most recent reading only.

u74 interface contract (load-bearing — do not rename keys):
``indicator=fear_greed``, ``value`` (int 0-100 as str),
``classification`` (e.g. ``"Fear"``), ``timestamp``,
``time_until_update`` (empty str when absent), ``window=utc_24h``.

Pins:

* R8 — flat string ``raw_metadata``; ``published_at`` tz-aware UTC.
* R6 — only ``SourceFetchError`` for source-side schema failures.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError


@register
class AlternativeFearGreedAdapter:
    """Adapter for the Alternative.me Crypto Fear & Greed endpoint."""

    name: ClassVar[str] = "alternative-fng"
    category: ClassVar[Category] = "macro"

    _ENDPOINT: ClassVar[str] = "https://api.alternative.me/fng/"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={"limit": "1"},
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            raise SourceFetchError(
                source_name=self.name,
                message="missing or empty data array",
                transient=False,
            )
        entry = data[0]
        if not isinstance(entry, dict):
            raise SourceFetchError(
                source_name=self.name,
                message="data[0] is not an object",
                transient=False,
            )

        value_raw = entry.get("value")
        classification = entry.get("value_classification")
        timestamp_raw = entry.get("timestamp")
        if (
            not isinstance(value_raw, str)
            or not isinstance(classification, str)
            or not isinstance(timestamp_raw, str)
        ):
            raise SourceFetchError(
                source_name=self.name,
                message="value / value_classification / timestamp not present as strings",
                transient=False,
            )
        try:
            value = int(value_raw)
            published_at = datetime.fromtimestamp(int(timestamp_raw), tz=UTC)
        except (ValueError, OverflowError, OSError) as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"unparseable value or timestamp: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        time_until_update = entry.get("time_until_update")
        raw_metadata: dict[str, str] = {
            "indicator": "fear_greed",
            "value": str(value),
            "classification": classification,
            "timestamp": timestamp_raw,
            "time_until_update": (time_until_update if isinstance(time_until_update, str) else ""),
            "window": "utc_24h",
        }

        try:
            return [
                NormalizedItem(
                    source_name=self.name,
                    category=self.category,
                    title=f"Crypto Fear & Greed {value} ({classification})",
                    summary=f"Fear & Greed index {value}/100 — {classification} (UTC 24h)",
                    url="https://alternative.me/crypto/fear-and-greed-index/",
                    published_at=published_at,
                    raw_metadata=raw_metadata,
                )
            ]
        except ValidationError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"normalization failed: {exc}",
                transient=False,
                cause=exc,
            ) from exc
