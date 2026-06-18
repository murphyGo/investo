"""FRED economic calendar adapter — forward-looking release schedule.

Consumes the FRED ``/fred/release/dates`` endpoint per market-relevant
release id and emits one :class:`NormalizedItem` per scheduled release
whose ``date`` falls within the adapter's forward lookahead window.
Distinct from the existing ``fred-macro`` adapter, which consumes the
*backward-looking* ``series/observations`` shape (latest data point per
series); this adapter answers "when does CPI / NFP / GDP next print?"
rather than "what was the last CPI value?".

Design choices (u43 follow-up, 2026-05-10):

* **Endpoint** — ``https://api.stlouisfed.org/fred/release/dates`` with
  ``release_id`` per request. The sibling ``/fred/releases/dates``
  endpoint (no leading singular ``release``) only returns *historical*
  release dates filtered by the realtime metadata window — it does not
  expose the forward schedule. The ``release/dates`` endpoint with
  ``include_release_dates_with_no_data=true&sort_order=desc`` returns
  the announcement schedule including forward dates that have no
  observation yet (FRED publishes the calendar slot before the data
  lands).

* **Release set** — limited to a curated, market-moving subset rather
  than every FRED release (FRED tracks ~3000 release ids, most of them
  state-level / niche aggregates that would flood the briefing). The
  default set covers the prints persona #4 ("미국 적극") explicitly
  asked for: CPI, PPI, Employment Situation (NFP / Unemployment Rate),
  GDP, Personal Income & Outlays (PCE), Industrial Production,
  Advance Monthly Retail Sales, JOLTS, New Residential Construction
  (Housing Starts), Existing Home Sales. ``release_id=101`` (FOMC
  Press Release) is intentionally **excluded** because the
  ``fomc-calendar`` adapter (sibling u43 deliverable) already surfaces
  every Federal Reserve event from the federalreserve.gov
  ``calendar.json`` source-of-record. Operators can override via
  ``INVESTO_FRED_CALENDAR_RELEASES`` (R12).

* **Forward-only** — the FRED schedule extends back decades. The
  adapter applies a strict forward window
  ``[target_date, target_date + N)`` so the briefing's "주요 일정"
  block stays focused on what is *about to happen*. ``N`` is read from
  ``INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS`` (default 30, clamped to
  ``[1, 180]``); blank / non-numeric / out-of-range falls back to the
  default with a one-line warning so an operator typo surfaces in the
  GHA log.

* **scheduled_at** — anchored to ``UTC midnight`` on the release date.
  FRED publishes most US macro releases at 08:30 ET (BLS / BEA
  convention) but the API ``date`` field is the local date string only,
  not a wall-clock; converting the published-time literal "08:30 ET"
  per release would require a per-release offset table that drifts
  silently if BLS shifts. UTC midnight is unambiguous, deterministic,
  and matches the ``fomc-calendar`` / ``nasdaq-earnings-calendar``
  date-level granularity the u35 D-N selector already rounds to.

* **published_at** — anchored to UTC midnight on the *target date*
  (the publish window's KST/UTC start). Mirrors the pattern from
  ``nasdaq-earnings-calendar`` + ``fomc-calendar`` so the briefing
  window filter keeps forward rows attached to the correct publish
  slice rather than letting them drift forward as their
  ``scheduled_at`` advances.

* **Tier A** — FRED is a first-party publishing endpoint operated by
  the Federal Reserve Bank of St. Louis aggregating regulator-of-record
  releases (BLS / BEA / Fed). Not the original source of the underlying
  prints (BLS publishes the CPI release; FRED republishes the
  schedule), so tier ``A`` rather than ``S``. Registered in
  :mod:`investo.sources.tiers`.

* **Segment routing** — single-segment ``us-equity`` per
  :mod:`investo.briefing.segments` allow-list. US macro releases drive
  the us-equity narrative; crypto inherits the macro context via the
  shared ``treasury-rates`` source the orchestrator already fans out.
  Per-release calendar fan-out across segments is intentionally
  avoided — readers should see "CPI prints Tuesday" once in the
  us-equity block, not duplicated in crypto.

* **Per-release isolation** — each release id's HTTP request runs
  independently inside ``asyncio.gather(return_exceptions=True)``. A
  4xx for a single release id (typo / delisted) only fails that
  release; siblings still complete. Mirrors the ``fred-macro``
  pattern.

* **Secret hygiene (R13)** — ``FRED_API_KEY`` value MUST NOT appear in
  log lines, error messages, ``raw_metadata`` payloads, or test
  fixtures. The error message names the env-var, never any partial /
  full key value. Tests pin this with a sentinel value. Missing key
  raises ``SourceFetchError(transient=False)`` so the aggregator's
  R6 isolation surfaces the misconfiguration once rather than
  silently emitting empty results.

Pins:

* AC-7.4 — ``scheduled_at`` is tz-aware UTC.
* AC-7.6 — JSON path; no XML, ``defusedxml`` not required.
* R7 (relaxed forward window per u35) — emits forward-scheduled rows
  outside the strict 24-hour publish window. Compatible with the
  ``_MAX_FUTURE_PUBLISHED_AT = 30 days`` aggregator guard via the
  ``published_at = target_date midnight`` anchor.
* R10 — live ``release/dates`` bodies captured under
  ``tests/unit/sources/fixtures/api/fred-economic-calendar/`` and
  replayed via ``httpx.MockTransport`` in the test suite.
* R12 — ``INVESTO_FRED_CALENDAR_RELEASES`` +
  ``INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS`` env-var overrides.
* R13 — ``FRED_API_KEY`` secret read at fetch time; missing →
  ``SourceFetchError(transient=False)``; key value never in logs,
  errors, or ``raw_metadata``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, parse_symbol_list
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_ENV_KEY: Final[str] = "FRED_API_KEY"
_ENV_RELEASES: Final[str] = "INVESTO_FRED_CALENDAR_RELEASES"
_ENV_LOOKAHEAD_DAYS: Final[str] = "INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS"
_DEFAULT_LOOKAHEAD_DAYS: Final[int] = 30
_LOOKAHEAD_MIN_DAYS: Final[int] = 1
_LOOKAHEAD_MAX_DAYS: Final[int] = 180

# Curated market-moving FRED release ids. release_id=101 (FOMC Press
# Release) is intentionally excluded — fomc-calendar already surfaces
# every Federal Reserve event from the source-of-record calendar.json.
# Names below are FRED's own ``release_name`` values (cached here for
# stable rendering when the per-release lookup fails).
_DEFAULT_RELEASES: Final[tuple[str, ...]] = (
    "10",  # Consumer Price Index
    "46",  # Producer Price Index
    "50",  # Employment Situation (NFP / Unemployment)
    "53",  # Gross Domestic Product
    "54",  # Personal Income and Outlays (PCE)
    "13",  # G.17 Industrial Production and Capacity Utilization
    "9",  # Advance Monthly Sales for Retail and Food Services
    "192",  # Job Openings and Labor Turnover Survey (JOLTS)
    "27",  # New Residential Construction (Housing Starts)
    "291",  # Existing Home Sales
)

# Stable display names keyed by release_id. Used for title rendering
# and ``raw_metadata["release_name"]``. Operators adding a new
# release_id via the env-var override get a generic "FRED Release {id}"
# title until they add an entry here — intentional: the editorial name
# table stays a deliberate change rather than autogenerated.
_RELEASE_NAMES: Final[dict[str, str]] = {
    "10": "Consumer Price Index",
    "46": "Producer Price Index",
    "50": "Employment Situation",
    "53": "Gross Domestic Product",
    "54": "Personal Income and Outlays",
    "13": "Industrial Production",
    "9": "Advance Monthly Retail Sales",
    "192": "Job Openings and Labor Turnover Survey",
    "27": "New Residential Construction",
    "291": "Existing Home Sales",
}
_CANONICAL_EVENT_CODES: Final[dict[str, tuple[str, str]]] = {
    "10": ("CPI", "previous_month"),
    "46": ("PPI", "previous_month"),
    "50": ("NFP", "previous_month"),
    "53": ("GDP", "previous_quarter"),
    "54": ("PCE", "previous_month"),
}


@register
class FredEconomicCalendarAdapter:
    """Adapter for the FRED REST API ``/fred/release/dates`` endpoint."""

    name: ClassVar[str] = "fred-economic-calendar"
    category: ClassVar[Category] = "calendar"

    _ENDPOINT: ClassVar[str] = "https://api.stlouisfed.org/fred/release/dates"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        # R13: read secret at fetch time (not import) so the test suite
        # never requires a live key. Missing → SourceFetchError so the
        # aggregator's R6 isolation surfaces the misconfiguration once
        # rather than silently emitting empty results.
        api_key = os.environ.get(_ENV_KEY, "")
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=(f"{_ENV_KEY} not set; {self.name} adapter will not run"),
                transient=False,
                cause=None,
            )

        release_ids = parse_symbol_list(_ENV_RELEASES, _DEFAULT_RELEASES)
        lookahead_days = _resolve_lookahead_days()
        target_published_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)
        forward_window_end = window.target_date + timedelta(days=lookahead_days)

        results = await asyncio.gather(
            *(
                self._fetch_one(
                    client,
                    release_id=release_id,
                    api_key=api_key,
                    target_published_at=target_published_at,
                    forward_start=window.target_date,
                    forward_end=forward_window_end,
                )
                for release_id in release_ids
            ),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
            elif isinstance(result, SourceFetchError):
                # Per-release isolation — bad release_id, transient
                # 4xx, etc. Drop and continue; siblings still surface.
                continue
            elif isinstance(result, BaseException):
                raise result
        return items

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        *,
        release_id: str,
        api_key: str,
        target_published_at: datetime,
        forward_start: date,
        forward_end: date,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "release_id": release_id,
                "api_key": api_key,
                "file_type": "json",
                "include_release_dates_with_no_data": "true",
                "sort_order": "desc",
                "limit": "15",
            },
        )
        # release_id is named in the message; api_key is NOT.
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed JSON for release_id={release_id}",
            append_exc=False,
        )

        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=(
                    f"non-object FRED response for release_id={release_id}: "
                    f"{type(payload).__name__}"
                ),
                transient=False,
            )
        release_dates = payload.get("release_dates")
        if release_dates is None:
            return []
        if not isinstance(release_dates, list):
            raise SourceFetchError(
                source_name=self.name,
                message=(
                    f"expected release_dates list for release_id={release_id}, "
                    f"got {type(release_dates).__name__}"
                ),
                transient=False,
            )

        release_name = _RELEASE_NAMES.get(release_id, f"FRED Release {release_id}")
        items: list[NormalizedItem] = []
        for entry in release_dates:
            normalized = self._normalize_entry(
                entry,
                release_id=release_id,
                release_name=release_name,
                target_published_at=target_published_at,
                forward_start=forward_start,
                forward_end=forward_end,
            )
            if normalized is not None:
                items.append(normalized)
        return items

    def _normalize_entry(
        self,
        entry: Any,
        *,
        release_id: str,
        release_name: str,
        target_published_at: datetime,
        forward_start: date,
        forward_end: date,
    ) -> NormalizedItem | None:
        if not isinstance(entry, dict):
            return None
        date_raw = entry.get("date")
        if not isinstance(date_raw, str) or not date_raw:
            return None
        try:
            scheduled_date = date.fromisoformat(date_raw)
        except ValueError:
            return None
        if not (forward_start <= scheduled_date < forward_end):
            return None

        scheduled_at = datetime.combine(scheduled_date, time.min, tzinfo=UTC)
        # Title prepends ISO date for greppability — mirrors the
        # fomc-calendar / nasdaq-earnings-calendar pattern.
        title = f"{scheduled_date.isoformat()} — {release_name}"
        summary = (
            f"FRED release_id={release_id} ({release_name}) "
            f"scheduled for {scheduled_date.isoformat()}"
        )
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "release_id": release_id,
            "release_name": release_name,
            "scheduled_date": scheduled_date.isoformat(),
        }
        event_code = _CANONICAL_EVENT_CODES.get(release_id)
        if event_code is not None:
            code, cadence = event_code
            period = _canonical_period_for_schedule(scheduled_date, cadence)
            raw_metadata["macro_event_key"] = f"us:{code}:period={period}"
            raw_metadata["macro_event_status"] = "scheduled"
            raw_metadata["macro_event_label"] = release_name

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://fred.stlouisfed.org/release?rid={release_id}",
                published_at=target_published_at,
                scheduled_at=scheduled_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _resolve_lookahead_days() -> int:
    """Read ``INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS`` and clamp to the supported range.

    Default ``_DEFAULT_LOOKAHEAD_DAYS`` (30) when unset / blank /
    non-numeric / out of range. Out-of-range / non-numeric values log
    one warning so an operator typo surfaces in the GHA log.
    """
    raw = os.environ.get(_ENV_LOOKAHEAD_DAYS, "").strip()
    if not raw:
        return _DEFAULT_LOOKAHEAD_DAYS
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "%s=%r invalid (non-numeric); using default=%d",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _DEFAULT_LOOKAHEAD_DAYS,
        )
        return _DEFAULT_LOOKAHEAD_DAYS
    if value < _LOOKAHEAD_MIN_DAYS:
        _logger.warning(
            "%s=%r below min=%d; using default=%d",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _LOOKAHEAD_MIN_DAYS,
            _DEFAULT_LOOKAHEAD_DAYS,
        )
        return _DEFAULT_LOOKAHEAD_DAYS
    if value > _LOOKAHEAD_MAX_DAYS:
        _logger.warning(
            "%s=%r above max=%d; clamping",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _LOOKAHEAD_MAX_DAYS,
        )
        return _LOOKAHEAD_MAX_DAYS
    return value


def _canonical_period_for_schedule(scheduled_date: date, cadence: str) -> str:
    if cadence == "previous_quarter":
        return _previous_quarter_period(scheduled_date)
    shifted = _shift_months(scheduled_date, -1)
    return f"{shifted.year:04d}-{shifted.month:02d}"


def _previous_quarter_period(value: date) -> str:
    release_quarter = ((value.month - 1) // 3) + 1
    if release_quarter == 1:
        return f"{value.year - 1:04d}Q4"
    return f"{value.year:04d}Q{release_quarter - 1}"


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1)
