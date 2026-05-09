"""FOMC calendar adapter — forward-looking Federal Reserve schedule.

Consumes the Federal Reserve's public ``calendar.json`` (the same JSON
that drives the Federal Reserve website's events page) and emits one
:class:`NormalizedItem` per scheduled event whose date falls within the
adapter's forward lookahead window. Distinct from the existing
``fomc-rss`` adapter, which consumes the *backward-looking*
``press_all.xml`` press-release feed; the two coexist (one publishes
what *just happened*, the other publishes what is *about to happen*).

Design choices (u43, 2026-05-10):

* **Endpoint** — ``https://www.federalreserve.gov/json/calendar.json``
  is a public, unauthenticated JSON document containing a top-level
  ``events`` array. Each event has ``month`` (``"YYYY-MM"``), ``days``
  (string — usually ``"14"`` but sometimes ``"14, 15"`` for two-day
  meetings), ``time`` (local string like ``"2:00 p.m."`` — not
  reliably machine-parseable), ``title``, ``type`` (one of
  ``Speeches`` / ``FOMC`` / ``Beige`` / ``Stat`` / ``Testimony`` /
  ``Conferences`` / ``Board`` / ``Other``), and optional
  ``description``, ``location``, ``link``. The body has a UTF-8 BOM —
  the adapter handles it via ``utf-8-sig`` decoding.

* **Forward-only** — the calendar carries thousands of historical
  events. The adapter applies a strict forward window
  ``[target_date, target_date + N)`` so the briefing's "주요 일정"
  block stays focused on what is *about to happen*. ``N`` is read from
  ``INVESTO_FOMC_LOOKAHEAD_DAYS`` (default 30, clamped to
  ``[1, 180]``); blank / non-numeric / out-of-range falls back to the
  default with a one-line warning so an operator typo surfaces in the
  GHA log.

* **scheduled_at** — anchored to ``UTC midnight`` on the first day in
  ``days``. The local "2:00 p.m." text is not reliably machine-readable
  (single events use ``"7:00 p.m."``, multi-day meetings drop time
  entirely), so the adapter avoids inventing a precise wall-clock and
  keeps the date-level granularity that the u35 D-N selector already
  rounds to. The original ``time`` text is preserved verbatim in
  ``raw_metadata["local_time"]`` for the audit log. The ``time`` value
  on this feed represents Eastern Time, but since the adapter does not
  parse it into a datetime, no DST handling is needed — ``scheduled_at``
  uses UTC midnight, which is unambiguous.

* **published_at** — anchored to UTC midnight on the *target date*
  (the publish window's KST/UTC start). Mirrors the pattern from
  ``nasdaq-earnings-calendar`` so the briefing window filter keeps
  forward rows attached to the correct publish slice rather than
  letting them drift forward as their ``scheduled_at`` advances.

* **Tier S** — the Federal Reserve is the regulator-of-record for the
  events listed; the calendar is the source-of-truth for FOMC meeting
  dates and FOMC minutes release dates. Registered in
  :mod:`investo.sources.tiers` as tier ``S``.

* **Segment routing** — single-segment ``us-equity`` per
  :mod:`investo.briefing.segments` allow-list. Crypto readers consume
  Fed-policy lookahead via the cross-routing path the orchestrator
  already maintains for ``treasury-rates`` (shared sources). FOMC
  decisions are the canonical us-equity input; the crypto narrative
  only inherits them when an item triggers the strong-crypto-signal
  override (it does not, since titles are clinical: "FOMC Press
  Conference" / "Speech - Governor Barr" etc.). This is intentional:
  treating every Fed event as a crypto-equity dual is a noise floor
  that drowns the actual crypto-specific signal.

* **No secrets** — the endpoint is unauthenticated. R13 secret-hygiene
  contract is trivially satisfied (no env var to redact).

* **R14 UA** — Federal Reserve does not advertise a strict UA policy;
  the adapter sends ``Investo/1.0 (+https://murphygo.github.io/investo)``
  as a clear identity per the project's R14 fair-access convention.

Pins:

* AC-7.4 — ``scheduled_at`` is tz-aware UTC.
* AC-7.6 — JSON path; no XML, ``defusedxml`` not required.
* R7 (relaxed forward window per u35) — emits forward-scheduled rows
  outside the strict 24-hour publish window. Compatible with the
  ``_MAX_FUTURE_PUBLISHED_AT = 30 days`` aggregator guard via the
  ``published_at = target_date midnight`` anchor.
* R10 — the live ``calendar.json`` body is captured under
  ``tests/unit/sources/fixtures/api/fomc-calendar/upcoming.json`` and
  replayed via ``httpx.MockTransport`` in the test suite.
* R12 — ``INVESTO_FOMC_LOOKAHEAD_DAYS`` env-var override.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

# Operator opt-in: how many days of forward calendar to surface per run.
# Default 30 covers the next FOMC cycle (meetings ~6 weeks apart) plus
# the in-between speech / Beige Book / statistical-release cadence
# without flooding the briefing.
_ENV_LOOKAHEAD_DAYS: Final[str] = "INVESTO_FOMC_LOOKAHEAD_DAYS"
_DEFAULT_LOOKAHEAD_DAYS: Final[int] = 30
_LOOKAHEAD_MIN_DAYS: Final[int] = 1
_LOOKAHEAD_MAX_DAYS: Final[int] = 180

_USER_AGENT = "Investo/1.0 (+https://murphygo.github.io/investo)"

# Event types worth surfacing on the briefing. ``Other`` (Federal
# Reserve holidays) is included because a market-closed day adjacent to
# a publish date is reader-relevant. ``Conferences`` / ``Board`` are
# excluded by default — they tend to be non-decision-making logistics
# rows. The intent is editorial, not exhaustive: callers who want every
# event can subclass and override ``_KEEP_TYPES``.
_KEEP_TYPES: Final[frozenset[str]] = frozenset(
    {"FOMC", "Speeches", "Beige", "Stat", "Testimony", "Other"}
)


@register
class FomcCalendarAdapter:
    """Adapter for the Federal Reserve forward calendar JSON endpoint."""

    name: ClassVar[str] = "fomc-calendar"
    category: ClassVar[Category] = "calendar"

    _ENDPOINT: ClassVar[str] = "https://www.federalreserve.gov/json/calendar.json"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, */*",
            },
        )
        try:
            # Fed serves the body with a UTF-8 BOM. ``response.text``
            # decodes via charset detection; ``json.loads`` on the
            # decoded text strips the BOM correctly.
            text = response.content.decode("utf-8-sig")
            payload = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected object response, got {type(payload).__name__}",
                transient=False,
            )
        events = payload.get("events")
        if events is None:
            return []
        if not isinstance(events, list):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected events list, got {type(events).__name__}",
                transient=False,
            )

        lookahead_days = _resolve_lookahead_days()
        target_published_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)
        forward_window_end = window.target_date + timedelta(days=lookahead_days)

        items: list[NormalizedItem] = []
        for event in events:
            normalized = self._normalize_event(
                event,
                target_published_at=target_published_at,
                forward_start=window.target_date,
                forward_end=forward_window_end,
            )
            if normalized is not None:
                items.append(normalized)
        return items

    def _normalize_event(
        self,
        event: Any,
        *,
        target_published_at: datetime,
        forward_start: date,
        forward_end: date,
    ) -> NormalizedItem | None:
        if not isinstance(event, dict):
            return None
        type_raw = _clean_str(event.get("type"))
        if not type_raw or type_raw not in _KEEP_TYPES:
            return None
        title_raw = _clean_str(event.get("title"))
        if not title_raw:
            return None
        month = _clean_str(event.get("month"))
        days = _clean_str(event.get("days"))
        if not month or not days:
            return None

        scheduled_date = _parse_event_date(month, days)
        if scheduled_date is None:
            return None
        if not (forward_start <= scheduled_date < forward_end):
            return None

        scheduled_at = datetime.combine(scheduled_date, time.min, tzinfo=UTC)

        # Description + location join into one summary line.
        description = _clean_str(event.get("description"))
        location = _clean_str(event.get("location"))
        local_time = _clean_str(event.get("time"))
        summary_parts: list[str] = []
        if description:
            summary_parts.append(description)
        if location:
            summary_parts.append(location)
        if local_time:
            summary_parts.append(f"Time: {local_time}")
        summary = "; ".join(summary_parts) if summary_parts else None
        if summary is not None and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        # Title prepends the scheduled date (ISO) for greppability and
        # mirrors the nasdaq-earnings-calendar pattern.
        title = f"{scheduled_date.isoformat()} — {title_raw}"

        # URL: prefer the event's own ``link`` (relative path on
        # federalreserve.gov), fall back to the calendar landing page.
        # Reject schemes other than http/https implicitly via HttpUrl.
        link = _clean_str(event.get("link"))
        url: str
        if link and link.startswith("/"):
            url = f"https://www.federalreserve.gov{link}"
        elif link and (link.startswith("http://") or link.startswith("https://")):
            url = link
        else:
            url = "https://www.federalreserve.gov/newsevents/calendar.htm"

        raw_metadata: dict[str, str] = {
            "event_type": type_raw,
            "scheduled_date": scheduled_date.isoformat(),
        }
        if local_time:
            raw_metadata["local_time"] = local_time
        if location:
            raw_metadata["location"] = location

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=url,
                published_at=target_published_at,
                scheduled_at=scheduled_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _resolve_lookahead_days() -> int:
    """Read ``INVESTO_FOMC_LOOKAHEAD_DAYS`` and clamp to the supported range.

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


def _clean_str(value: Any) -> str | None:
    """Strip + HTML-strip a Federal Reserve calendar field, ``None`` on empty."""
    if not isinstance(value, str):
        return None
    cleaned = strip_html(value).strip()
    return cleaned or None


def _parse_event_date(month: str, days: str) -> date | None:
    """Parse the ``month`` (``"YYYY-MM"``) + ``days`` (``"14"`` or ``"14, 15"``) pair.

    Returns the first day of the event (multi-day meetings list both
    days; we anchor ``scheduled_at`` to the first). ``None`` when either
    field is malformed.
    """
    try:
        year_str, month_str = month.split("-", 1)
        year = int(year_str)
        month_num = int(month_str)
    except ValueError:
        return None
    first_day_text = days.split(",")[0].strip()
    try:
        day = int(first_day_text)
    except ValueError:
        return None
    try:
        return date(year, month_num, day)
    except ValueError:
        return None
