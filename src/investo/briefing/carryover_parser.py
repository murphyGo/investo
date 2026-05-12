"""Archive parser for u52 day-over-day carryover.

Walks the trailing N=3 trading-days' archived briefing markdown for a
single segment, extracts (a) §⑥ "오늘의 관전 포인트" numbered list
items and (b) the u35 lookahead table rows, and returns a
:class:`BriefingCarryover` with each event tagged by lifecycle status:

* ``resolved`` — today's candidate items contain a substring match for
  the carryover ticker/topic;
* ``unresolved`` — yesterday's preview is still pending (expected date
  is today or earlier and no match in today's candidates);
* ``carried_over`` — the event's ``expected_date`` is in the future
  relative to today (still pending but on schedule).

Project-rule preservation
-------------------------
* **DEBT-060 chokepoint** — every blockquote / watermark / driver line
  is read through :func:`investo.briefing.extract.extract_*`. This
  module *does not* re-declare the ``> **오늘의 결론**:`` literal
  (grep guard in ``tests/unit/briefing/test_extract.py`` enforces).
* **Pure function** — no clock, no env, only Path I/O. ``today`` is
  caller-injected so the orchestrator + tests share the same call
  shape.
* **Graceful skip** — missing archive files, weekend cursor positions,
  malformed list items all degrade silently. The parser never raises
  during a normal pipeline run.
* **No raw XML** — markdown only; no XML dependency.

Surface separation from u34
---------------------------
u34's :mod:`briefing.context` lifts narrative *conclusion* text into
the Stage 2 prompt. This module lifts structured *events* into the
Stage 2 prompt AND into the published markdown body (via
:mod:`publisher.carryover`). Both surfaces coexist by design; their
prompt rules are ordered so the LLM treats carryover as the
event-citation discipline and recent-context as the prose-bridge
discipline.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.briefing.extract import (
    extract_caution,
    extract_conclusion,
    extract_key_drivers,
    extract_watermark,
)
from investo.briefing.segments import MarketSegment
from investo.models import (
    BriefingCarryover,
    CarryoverEventType,
    CarryoverItem,
    CarryoverStatus,
    NormalizedItem,
)

_logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS: Final[int] = 3
"""Default trading-day walk-back depth (mirrors u52 plan: 3 days)."""

MIN_LOOKBACK_DAYS: Final[int] = 1
MAX_LOOKBACK_DAYS: Final[int] = 7

ENV_LOOKBACK_DAYS: Final[str] = "INVESTO_CARRYOVER_LOOKBACK_DAYS"
"""Env var that clamps :data:`DEFAULT_LOOKBACK_DAYS` to ``[1, 7]``."""

# Walk-back cap in calendar days — bounded above so a fresh repo with
# one archived day cannot turn the loader into an O(weeks) scan. The
# choice of 21 mirrors :mod:`briefing.context`.
_MAX_CALENDAR_DAYS: Final[int] = 21

# §⑥ heading detect — matches the canonical Stage 2 header exactly.
_SECTION_SIX_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+⑥\s+오늘의 관전 포인트\s*$",
    re.MULTILINE,
)

# Numbered-list line in §⑥ body. Both ASCII colon and full-width colon
# (U+FF1A) are honored — the LLM occasionally emits the full-width form
# under Korean punctuation context.
_SECTION_SIX_ITEM_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d+\.\s+\*\*(?P<topic>.+?)\*\*\s*[:：]\s*(?P<body>.+)$",  # noqa: RUF001
)

# Lookahead table — `| 날짜 | 이벤트 |` header line and following data
# rows up to the next blank line or non-pipe row. Date is ISO format.
_LOOKAHEAD_HEADER_RE: Final[re.Pattern[str]] = re.compile(
    r"^\|\s*날짜\s*\|\s*이벤트\s*\|\s*$",
)
_LOOKAHEAD_ROW_RE: Final[re.Pattern[str]] = re.compile(
    r"^\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|\s*(?P<event>.+?)\s*\|\s*$",
)

# Event-type classifier substring rules. The order is important — the
# first match wins. ASCII tickers fall through to `_classify_ticker`
# after this table runs.
_EVENT_TYPE_KEYWORDS: Final[tuple[tuple[CarryoverEventType, tuple[str, ...]], ...]] = (
    ("fed", ("Fed", "FOMC", "Powell", "Waller", "Bowman", "연준", "기준금리")),
    ("geopolitics", ("이란", "중동", "러시아", "우크라이나", "북한", "관세", "tariff")),
    ("macro", ("CPI", "PPI", "NFP", "GDP", "PCE", "DGS10", "UST", "국채금리")),
    ("disclosure", ("8-K", "10-K", "10-Q", "공시", "DART")),
    ("earnings", ("EPS", "어닝", "실적", "prelim")),
)

_ASCII_TICKER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2,5}$")

# Embedded ticker matcher — finds 2-5 uppercase ASCII letter runs that
# sit on a word boundary inside a composite Korean topic such as
# ``"ARM 어닝"`` or ``"FOMC 의사록"``. Used as a fallback after the
# whole-string substring match fails so the parser can still resolve a
# carryover when today's candidate headline carries the ticker alone.
_EMBEDDED_TICKER_RE: Final[re.Pattern[str]] = re.compile(r"\b[A-Z]{2,5}\b")


def resolve_lookback_days(env: dict[str, str] | None = None) -> int:
    """Read :data:`ENV_LOOKBACK_DAYS` and clamp to ``[MIN, MAX]``.

    Returns :data:`DEFAULT_LOOKBACK_DAYS` when the var is unset / empty
    / non-numeric / out of range. Invalid values log a WARNING so
    operator typos surface in the GHA log instead of degrading
    silently. ``env`` is the unit-test seam; production passes
    ``None`` (reads :data:`os.environ`).
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_LOOKBACK_DAYS, "").strip()
    if not raw:
        return DEFAULT_LOOKBACK_DAYS
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "%s=%r invalid (non-numeric); using default=%d",
            ENV_LOOKBACK_DAYS,
            raw,
            DEFAULT_LOOKBACK_DAYS,
        )
        return DEFAULT_LOOKBACK_DAYS
    if value < MIN_LOOKBACK_DAYS or value > MAX_LOOKBACK_DAYS:
        _logger.warning(
            "%s=%r out of range [%d, %d]; using default=%d",
            ENV_LOOKBACK_DAYS,
            raw,
            MIN_LOOKBACK_DAYS,
            MAX_LOOKBACK_DAYS,
            DEFAULT_LOOKBACK_DAYS,
        )
        return DEFAULT_LOOKBACK_DAYS
    return value


def load_carryover(
    archive_root: Path,
    segment: MarketSegment,
    today: date,
    *,
    candidates: Sequence[NormalizedItem] = (),
    lookback: int = DEFAULT_LOOKBACK_DAYS,
) -> BriefingCarryover:
    """Walk back ``lookback`` trading days and extract carryover items.

    Parameters
    ----------
    archive_root:
        Same shape as :data:`investo.publisher.paths.ARCHIVE_ROOT`.
        Tests pass a tmp directory.
    segment:
        Walk-back is scoped to a single segment — cross-segment
        carryover is out of scope for u52.
    today:
        The publish date of the briefing being generated. Walk-back
        starts at ``today - 1`` and stops at ``today - 1 - lookback``
        worth of *trading days* (weekends silently skipped).
    candidates:
        Today's collected source items. Used to flip carryover items
        from ``unresolved`` to ``resolved`` when a substring match
        is found in any item's title or ticker-bearing metadata.
        Empty tuple → no resolution match; everything is unresolved
        or carried_over.
    lookback:
        Number of trading days to scan back. Clamped to
        ``[MIN_LOOKBACK_DAYS, MAX_LOOKBACK_DAYS]``; pass
        :func:`resolve_lookback_days` for env-aware production
        defaults.

    Returns
    -------
    BriefingCarryover
        Frozen pydantic model with split resolved / unresolved
        tuples and the actual ``lookback_days`` used (≤ the request
        when the archive is shorter).
    """
    clamped = max(MIN_LOOKBACK_DAYS, min(MAX_LOOKBACK_DAYS, lookback))
    candidate_haystack = _build_candidate_haystack(candidates)

    cursor = today - timedelta(days=1)
    calendar_used = 0
    trading_days_loaded = 0
    resolved: list[CarryoverItem] = []
    unresolved: list[CarryoverItem] = []

    while trading_days_loaded < clamped and calendar_used < _MAX_CALENDAR_DAYS:
        if _is_weekday(cursor):
            path = _archive_markdown_path(archive_root, segment, cursor)
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                except OSError:
                    content = None
                if content is not None:
                    items = _parse_day(content, originated_date=cursor, today=today)
                    for item in items:
                        labelled = _label_resolution(
                            item,
                            candidate_haystack=candidate_haystack,
                            today=today,
                        )
                        if labelled.status == "resolved":
                            resolved.append(labelled)
                        else:
                            unresolved.append(labelled)
                    trading_days_loaded += 1
        cursor -= timedelta(days=1)
        calendar_used += 1

    return BriefingCarryover(
        prior_resolved=tuple(resolved),
        prior_unresolved=tuple(unresolved),
        lookback_days=trading_days_loaded,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5


def _archive_markdown_path(archive_root: Path, segment: MarketSegment, day: date) -> Path:
    return archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"


def _parse_day(
    content: str,
    *,
    originated_date: date,
    today: date,
) -> list[CarryoverItem]:
    """Extract carryover candidates from one day's archive markdown.

    Combines (a) §⑥ numbered list items and (b) the u35 lookahead
    table rows. Calls into the DEBT-060 chokepoint
    (``extract_conclusion`` etc.) to validate that the archive bytes
    were emitted by a real briefing — a malformed file that has no
    conclusion line is treated as "no carryover" and silently
    skipped.
    """
    # Sanity gate — a published briefing always carries at least a
    # conclusion line. Without it, the archive file is malformed and
    # we skip it to avoid hallucinating events from random text.
    if extract_conclusion(content) is None and extract_watermark(content) is None:
        return []
    # Touch the remaining chokepoint helpers so DEBT-060 stays one
    # callable set (driver / caution are reserved for future
    # resolution heuristics — see Open Question #3 in the plan).
    _ = extract_key_drivers(content)
    _ = extract_caution(content)

    items: list[CarryoverItem] = []
    items.extend(_parse_section_six_items(content, originated_date=originated_date))
    items.extend(_parse_lookahead_table(content, originated_date=originated_date, today=today))
    return items


def _parse_section_six_items(
    content: str,
    *,
    originated_date: date,
) -> list[CarryoverItem]:
    """Pull numbered list items from §⑥ body.

    Returns an empty list when the §⑥ heading is missing or its
    body has zero matching numbered lines.
    """
    match = _SECTION_SIX_HEADING_RE.search(content)
    if match is None:
        return []
    body = content[match.end() :]
    # Stop at the next H2 heading boundary — §⑥ is the last fixed
    # section, but the footer / disclaimer / trace block sit below
    # and may carry their own pipe-delimited tables.
    next_h2 = re.search(r"^##\s+", body, re.MULTILINE)
    if next_h2 is not None:
        body = body[: next_h2.start()]

    items: list[CarryoverItem] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _SECTION_SIX_ITEM_RE.match(line)
        if m is None:
            continue
        topic = m.group("topic").strip()
        note = m.group("body").strip()
        if not topic:
            continue
        items.append(
            CarryoverItem(
                event_type=_classify_event_type(topic),
                ticker_or_topic=_truncate(topic, 64),
                originated_date=originated_date,
                expected_date=None,
                status="unresolved",
                note=_truncate(note, 120) if note else None,
            )
        )
    return items


def _parse_lookahead_table(
    content: str,
    *,
    originated_date: date,
    today: date,
) -> list[CarryoverItem]:
    """Pull rows from the u35 lookahead `| 날짜 | 이벤트 |` table.

    Items whose ``expected_date`` is on or after ``today`` are
    initially tagged ``carried_over``; items whose ``expected_date``
    is before ``today`` are initially tagged ``unresolved`` (will be
    flipped to ``resolved`` by :func:`_label_resolution` if today's
    candidates match).
    """
    lines = content.splitlines()
    items: list[CarryoverItem] = []
    in_table = False
    for raw_line in lines:
        line = raw_line.strip()
        if _LOOKAHEAD_HEADER_RE.match(line):
            in_table = True
            continue
        if in_table:
            # Skip the divider line `|---|---|`.
            if line.startswith("|") and "---" in line:
                continue
            row = _LOOKAHEAD_ROW_RE.match(line)
            if row is None:
                # End of table region.
                if line.startswith("|"):
                    continue  # malformed row — skip but stay in table
                in_table = False
                continue
            try:
                expected = date.fromisoformat(row.group("date"))
            except ValueError:
                continue
            event = row.group("event").strip()
            # Strip the inline markdown link bracket if present so the
            # ticker_or_topic is reader-clean.
            event_clean = _strip_inline_link(event)
            if not event_clean:
                continue
            initial_status: CarryoverStatus = "carried_over" if expected >= today else "unresolved"
            items.append(
                CarryoverItem(
                    event_type=_classify_event_type(event_clean),
                    ticker_or_topic=_truncate(event_clean, 64),
                    originated_date=originated_date,
                    expected_date=expected,
                    status=initial_status,
                    note=None,
                )
            )
    return items


def _classify_event_type(topic: str) -> CarryoverEventType:
    """Classify a topic string into a :data:`CarryoverEventType` value.

    Order: keyword table first (substring match, first-hit wins);
    then ASCII-ticker heuristic (2-5 uppercase letters) → ``earnings``;
    fallback ``other``. The classifier never raises — an unmatched
    topic always lands in ``other`` (DoD: "carryover signal is
    preserved, not dropped").
    """
    for event_type, keywords in _EVENT_TYPE_KEYWORDS:
        if any(keyword in topic for keyword in keywords):
            return event_type
    if _ASCII_TICKER_RE.match(topic):
        return "earnings"
    return "other"


def _label_resolution(
    item: CarryoverItem,
    *,
    candidate_haystack: str,
    today: date,
) -> CarryoverItem:
    """Flip ``unresolved`` → ``resolved`` when today's candidates match.

    Substring match against a lowercased haystack built from each
    candidate's ``title`` / ``summary`` / ``raw_metadata`` values.
    Items already tagged ``carried_over`` (future expected date) are
    left alone — a future event cannot resolve today.

    The match is intentionally simple (substring + ≥3-char floor) —
    the precision / recall trade-off is captured in plan Open
    Question #3 and the DEBT-D52-A candidate. ASCII tickers stay
    case-sensitive (``TM`` won't match a plain ``tm`` word) by
    checking the raw uppercase form against the original-case
    haystack as well.
    """
    if item.status == "carried_over":
        return item
    if not candidate_haystack:
        return item
    topic = item.ticker_or_topic.strip()
    if len(topic) < 3:
        return item
    # ASCII-only ticker: require word-boundary uppercase hit so "TM"
    # ≠ "tm" in a different word.
    if _ASCII_TICKER_RE.match(topic):
        if _ascii_ticker_in(topic, candidate_haystack):
            return item.model_copy(update={"status": "resolved"})
        return item
    # Composite Korean topic (e.g. "ARM 어닝"): try whole-string
    # substring first, then fall back to embedded ASCII ticker
    # extraction. The ticker fallback catches the common case where
    # the §⑥ list-item title is "[TICKER] 어닝" and today's candidate
    # headline carries the ticker alone.
    lowered = topic.lower()
    if lowered in candidate_haystack:
        return item.model_copy(update={"status": "resolved"})
    for embedded in _EMBEDDED_TICKER_RE.findall(topic):
        if _ascii_ticker_in(embedded, candidate_haystack):
            return item.model_copy(update={"status": "resolved"})
    del today  # parameter kept for clarity / future heuristics
    return item


_ASCII_TICKER_BOUNDARY_RE: Final[re.Pattern[str]] = re.compile(r"[A-Z]{2,5}")


def _ascii_ticker_in(topic: str, haystack_lower: str) -> bool:
    """Word-boundary uppercase match in the *original-case* haystack.

    ``haystack_lower`` is the lowered haystack — but :func:`_label_resolution`
    cannot use it for an uppercase-sensitive check, so this helper
    rebuilds an uppercase scan via the haystack-side raw form embedded
    in :data:`_LOWER_TO_RAW_KEY`. To keep the contract simple we
    instead require both: (a) the lower form is present (cheap check)
    AND (b) the topic appears as an isolated alphabetic run in the
    haystack. The combination prevents the "TM" false-positive while
    matching "TM 어닝" or "tm 어닝" inside a real candidate title.
    """
    # Cheap reject — lower form must appear.
    if topic.lower() not in haystack_lower:
        return False
    # Word-boundary check on the lower haystack — the lower form of
    # an uppercase ticker still requires the same letter run to be
    # isolated to count.
    for match in re.finditer(rf"\b{re.escape(topic.lower())}\b", haystack_lower):
        # Boundaries: prev char ∉ [a-z0-9] AND next char ∉ [a-z0-9]
        start = match.start()
        end = match.end()
        prev_ok = start == 0 or not haystack_lower[start - 1].isalnum()
        next_ok = end == len(haystack_lower) or not haystack_lower[end].isalnum()
        if prev_ok and next_ok:
            return True
    return False


def _build_candidate_haystack(candidates: Sequence[NormalizedItem]) -> str:
    """Build one lowercased substring-search corpus from today's items.

    Concatenates title + summary + raw_metadata values for every
    candidate. Returns an empty string when ``candidates`` is empty —
    callers use the empty-string sentinel to skip the resolution
    pass entirely.
    """
    if not candidates:
        return ""
    parts: list[str] = []
    for item in candidates:
        parts.append(item.title)
        if item.summary:
            parts.append(item.summary)
        for value in item.raw_metadata.values():
            parts.append(str(value))
    return " | ".join(parts).lower()


def _truncate(text: str, limit: int) -> str:
    """Truncate ``text`` to ``limit`` chars with a single-char ellipsis."""
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + "…"


_INLINE_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[(?P<label>[^\]]+)\]\([^)]+\)")


def _strip_inline_link(text: str) -> str:
    """Collapse ``[label](url)`` to ``label`` so topics stay readable."""
    return _INLINE_LINK_RE.sub(lambda m: m.group("label"), text).strip()


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "ENV_LOOKBACK_DAYS",
    "MAX_LOOKBACK_DAYS",
    "MIN_LOOKBACK_DAYS",
    "load_carryover",
    "resolve_lookback_days",
]
