"""FRED API adapter — macro indicator releases.

Implements the algorithm from FD L6.4 (extension 2026-05-01). Fetches
the most recent observation per configured FRED series id and emits
one :class:`NormalizedItem` per series with `category="macro"`.

Design choices (audit log 2026-05-01):

* **API key required** (Q5) — read from ``FRED_API_KEY`` env at fetch
  time. Missing key → :class:`SourceFetchError(transient=False)` per
  FD R13. The aggregator catches per FD R6 and other adapters
  continue unaffected.
* **Widened R7 window** (FD L6.4 / R11 relaxation) — FRED series
  release on irregular cadences (CPI monthly; UNRATE monthly; DFF
  daily). Strict R7 would silently drop most-recent monthly releases.
  Adapter accepts observations within ``[target_date - 65 days,
  target_date + 1 day]`` and emits at most ONE item per series. The
  65-day window covers the worst case: a monthly indicator whose
  latest observation is ``"."`` (revision in progress), forcing
  fall-through to the prior month's release ≈ 60 days before
  target.
* **Per-series isolation** — each series's HTTP request is independent
  inside the per-series ``asyncio.gather``. A 401 (bad key) will surface
  once per series since they all share the same key, but each is
  classified independently — siblings still complete. A 4xx on a
  single series id (typo / delisted) only fails that series.
* **Secret hygiene** (R13) — ``FRED_API_KEY`` value MUST NOT appear in
  log lines, error messages, ``raw_metadata`` payloads, or test
  fixtures. Tests pin this with a sentinel value.

Pins (extension 2026-05-01):

* AC-3.6 / R13 — missing/empty `FRED_API_KEY` → graceful degradation
* AC-5.5 / R12 — `INVESTO_FRED_SERIES` env-var override
* L6.4 — `published_at` = NY midnight ET on observation date → UTC
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, parse_symbol_list
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_LOOKBACK_DAYS = 65
_ENV_SERIES = "INVESTO_FRED_SERIES"
_ENV_KEY = "FRED_API_KEY"
_PLACEHOLDER = "."


@register
class FredMacroAdapter:
    """Adapter for the FRED REST API ``/fred/series/observations`` endpoint."""

    name: ClassVar[str] = "fred-macro"
    category: ClassVar[Category] = "macro"

    _DEFAULT_SERIES: ClassVar[tuple[str, ...]] = (
        "CPIAUCSL",
        "UNRATE",
        "DFF",
        "DGS10",
        "DEXKOUS",
        "PPIFID",
    )

    _ENDPOINT: ClassVar[str] = "https://api.stlouisfed.org/fred/series/observations"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        # R13: read secret at fetch time (not import) so the test suite
        # never requires a live key. Missing → graceful degradation
        # via aggregator R6. Crucially, the error message names the
        # ENV VAR, never any partial/full key value.
        api_key = os.environ.get(_ENV_KEY, "")
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=(f"{_ENV_KEY} not set; {self.name} adapter will not run"),
                transient=False,
                cause=None,
            )

        series_list = parse_symbol_list(_ENV_SERIES, self._DEFAULT_SERIES)
        # Per-series source-side failure (bad series id, "." only
        # observations, release > 65d old) is isolated and dropped;
        # sibling series continue.
        return await gather_with_error_isolation(
            (self._fetch_one(client, series_id, api_key, window) for series_id in series_list),
            source_name=self.name,
        )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        series_id: str,
        api_key: str,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "2",
            },
        )
        # Series id named in the message; api_key is NOT.
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed JSON for {series_id}",
            append_exc=False,
        )

        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"non-object FRED response for {series_id}",
                transient=False,
            )
        observations = payload.get("observations")
        if not isinstance(observations, list) or not observations:
            raise SourceFetchError(
                source_name=self.name,
                message=f"empty observations for {series_id}",
                transient=False,
            )

        # Walk most-recent first; skip "." placeholders.
        latest_idx = self._find_latest_valid(observations)
        if latest_idx is None:
            raise SourceFetchError(
                source_name=self.name,
                message=f"all observations placeholder ('.') for {series_id}",
                transient=False,
            )
        latest = observations[latest_idx]

        try:
            latest_value = float(latest["value"])
            latest_date_str = str(latest["date"])
            published_at = self._resolve_release_timestamp(latest_date_str)
        except (KeyError, ValueError, TypeError):
            return None

        # Widened window check — emit only if observation is within
        # _LOOKBACK_DAYS (65) of the target trading date.
        if not self._within_widened_window(published_at, window):
            return None

        prior_idx = self._find_latest_valid(observations, start_idx=latest_idx + 1)
        prior_value: float | None = None
        prior_date_str: str | None = None
        if prior_idx is not None:
            try:
                prior_value = float(observations[prior_idx]["value"])
                prior_date_str = str(observations[prior_idx]["date"])
            except (KeyError, ValueError, TypeError):
                prior_value = None
                prior_date_str = None

        delta_text = f"{latest_value - prior_value:+.4f}" if prior_value is not None else "n/a"
        title = f"{series_id} {latest_value} ({delta_text} from prior)"
        if prior_value is not None:
            summary = (
                f"{series_id}: latest={latest_value} "
                f"({latest_date_str}); prior={prior_value} ({prior_date_str})"
            )
        else:
            summary = (
                f"{series_id}: latest={latest_value} "
                f"({latest_date_str}); no prior observation in window"
            )
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "series_id": series_id,
            "value": format_float(latest_value),
            "release_date": latest_date_str,
        }
        if prior_value is not None and prior_date_str is not None:
            raw_metadata["previous_value"] = format_float(prior_value)
            raw_metadata["previous_release_date"] = prior_date_str

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://fred.stlouisfed.org/series/{series_id}",
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None

    @staticmethod
    def _find_latest_valid(observations: list[Any], *, start_idx: int = 0) -> int | None:
        """Return the index of the first non-placeholder observation at or after ``start_idx``.

        Observations are already sorted desc by date (per the API params).
        """

        for idx in range(start_idx, len(observations)):
            obs = observations[idx]
            if not isinstance(obs, dict):
                continue
            value = obs.get("value")
            if isinstance(value, str) and value != _PLACEHOLDER:
                return idx
        return None

    @staticmethod
    def _resolve_release_timestamp(date_str: str) -> datetime:
        """Parse FRED ``YYYY-MM-DD`` to NY midnight ET → UTC tz-aware.

        FRED uses NY local dates for releases. Midnight ET on the
        release date is the conventional anchor; converting via
        ``zoneinfo`` handles DST automatically.
        """

        d = date.fromisoformat(date_str)
        ny_midnight = datetime.combine(d, datetime.min.time(), tzinfo=_NY)
        return ny_midnight.astimezone(UTC)

    @staticmethod
    def _within_widened_window(published_at: datetime, window: FetchWindow) -> bool:
        lookback = window.start_utc - timedelta(days=_LOOKBACK_DAYS)
        return lookback <= published_at <= window.end_utc
