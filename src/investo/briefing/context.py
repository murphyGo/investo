"""Recent-briefings context loader (u34).

Lifts each daily briefing from a single-shot report into a "today inside
the weekly arc" narrative by feeding Stage 2 the conclusions and key
drivers of the most recent ``N`` publish days (default 5 = 1 trading
week) per segment, so the LLM can naturally surface continuity,
divergence, and "no material change" signals — without inventing facts
beyond the input data and without disturbing existing budgets, gates,
or UI surfaces (CLAUDE.md u34 plan).

Module boundary
---------------
This module is a pure read-side helper. It imports only:

* :mod:`investo.briefing.segments` — for the ``MarketSegment`` literal,
* :mod:`investo._internal.redaction` — defensive STRICT-policy scrub
  of the extracted fields (the archive bytes have already been gated
  through ``verify_disclaimer`` + ``leak_guard.scan`` at publish time,
  so this is belt-and-suspenders).

It does NOT import any other unit package (publisher / notifier /
orchestrator) — the orchestrator wires the loader into Stage 2 (per
CLAUDE.md project-rule #2 "module boundary"). It does NOT touch the
network or any LLM machinery (no Anthropic SDK regression).

Trust contract
--------------
1. Loader reads only files under ``archive/{segment}/YYYY/MM/YYYY-MM-DD.md``
   that already passed publish-side gates (``verify_disclaimer``,
   ``briefing.leak_guard.scan``, ``summary_quality``). No raw source
   bytes, no fixtures, no secret-bearing surfaces (R8 / R13 preserved).
2. Defensive STRICT-policy redaction is applied to every extracted
   field before it is handed to the LLM prompt. Even if a future
   archive bypassed the publish gates, a credential-shaped substring
   would be scrubbed before it reaches the prompt.
3. The loader degrades gracefully — missing archive directories,
   missing per-segment files, or unparseable markdown produce an
   empty entry list (the loader never raises during a normal pipeline
   run).

Token / character budget
------------------------
Each entry's ``conclusion`` and ``key_drivers`` strings are truncated
at :data:`_FIELD_CHAR_BUDGET` (50 chars) so a 5-day x 3-segment context
block stays well under the per-segment ~500-char-per-day budget the
plan locks. This budget is **separate** from the u13 LLM input cap
(96 total / 24 per source) — the recent context lives in the system
prompt, not the candidate-item list, and cannot starve fresh evidence.

The character budget is enforced **inside** the loader so callers
cannot accidentally bypass it; the prompt builder simply renders what
the loader returns.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.briefing.segments import MarketSegment
from investo.briefing.summary_quality import (
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    WATERMARK_PREFIX,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------

DEFAULT_RECENT_DAYS: Final[int] = 5
"""Default trailing-publish-day window — one trading week (Mon-Fri)."""

MAX_RECENT_DAYS: Final[int] = 10
"""Upper bound for the env-var override; clamps runaway prompt size."""

ENV_RECENT_DAYS: Final[str] = "INVESTO_RECENT_CONTEXT_DAYS"
"""Env var that adjusts the trailing-day window (clamped to ``[0, 10]``)."""

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Anchor prefixes are imported from
# ``investo.briefing.summary_quality`` (DEBT-060 chokepoint, 2026-05-08)
# so a future shape change to any blockquote marker lands in exactly
# one place. The local module-level aliases preserve the original
# private-symbol shape used by tests and internal helpers.
_CONCLUSION_PREFIX: Final[str] = CONCLUSION_PREFIX
_DRIVER_PREFIX: Final[str] = DRIVER_PREFIX
_WATERMARK_PREFIX: Final[str] = WATERMARK_PREFIX

# Per-field character cap fed to the LLM. 50 chars per Korean line is
# enough to carry the conclusion's verb / direction without bleeding
# into bullet structure or hyperlinks. The plan's ~500-char-per-segment-
# per-day envelope absorbs prefix labels + watermark on top of this.
_FIELD_CHAR_BUDGET: Final[int] = 50

# Maximum lookback in calendar days when scanning for ``N`` publish
# days. Bounded above to keep the loader fast even when long stretches
# are missing (e.g., a fresh repo with one archived day). 21 calendar
# days easily covers a 10-day publish window plus weekends + holidays.
_MAX_LOOKBACK_DAYS: Final[int] = 21


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class RecentBriefingEntry(BaseModel):
    """One archived day's first-viewport summary for a single segment.

    All string fields are pre-truncated at :data:`_FIELD_CHAR_BUDGET`
    and pre-redacted under ``RedactionPolicy.STRICT`` by the loader.
    Empty fields collapse to ``""`` (e.g., when a legacy archive
    omitted the watermark line).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    publish_date: date
    segment: MarketSegment
    conclusion: str
    key_drivers: str
    watermark: str


class RecentBriefingsContext(BaseModel):
    """Per-segment list of trailing recent-briefing entries.

    ``entries_by_segment`` is keyed by :data:`MarketSegment` and ordered
    newest-first within each list. Segments missing from the mapping
    represent "no archived briefings found" rather than a load failure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_date: date
    days: int
    entries_by_segment: dict[MarketSegment, tuple[RecentBriefingEntry, ...]]

    def for_segment(self, segment: MarketSegment) -> tuple[RecentBriefingEntry, ...]:
        """Return the entries for ``segment``; empty tuple when absent."""
        return self.entries_by_segment.get(segment, ())

    def is_empty(self) -> bool:
        """Return ``True`` when no segment has any entry.

        Callers (``generate_briefing`` / ``_stage_generate_segments``)
        use this to short-circuit the prompt-rendering branch when the
        archive is empty (first publish, fresh repo).
        """
        return all(not entries for entries in self.entries_by_segment.values())


# ---------------------------------------------------------------------------
# Loader entry point
# ---------------------------------------------------------------------------


def load_recent_briefings(
    archive_root: Path,
    target_date: date,
    *,
    days: int = DEFAULT_RECENT_DAYS,
    segments: Sequence[MarketSegment] = ("domestic-equity", "us-equity", "crypto"),
) -> RecentBriefingsContext:
    """Load the trailing ``days`` weekday archive entries per segment.

    Walks back from ``target_date - 1`` skipping weekends (Sat/Sun) and
    days with no archived markdown for **any** of the requested
    segments. The walk stops once each segment has ``days`` entries OR
    after :data:`_MAX_LOOKBACK_DAYS` calendar days, whichever comes
    first.

    A segment-day with no archived file is silently skipped — the
    loader does NOT pad the entry list with placeholder rows. Callers
    use ``is_empty()`` and per-segment list length to detect "first
    publish" / "gap day" scenarios.

    Parameters
    ----------
    archive_root:
        Repo-root-relative ``archive`` directory (matches
        :data:`investo.publisher.paths.ARCHIVE_ROOT` in production).
        Tests pass a tmp directory.
    target_date:
        The publish date being generated. The loader looks at
        ``target_date - 1`` and earlier.
    days:
        Trailing-publish-day window. ``0`` is a valid value and yields
        an empty context object (clean A/B disable). Values ``> days``
        are clamped to :data:`MAX_RECENT_DAYS` by the orchestrator's
        env-var parser (:func:`resolve_recent_days`); this loader
        accepts whatever the caller passes to keep the contract minimal.
    segments:
        Segments to scan. Defaults to all three published segments.

    Returns
    -------
    RecentBriefingsContext
        Frozen, with one tuple of entries per segment in the same
        order requested. Newest entry first within each tuple.
    """
    if days <= 0 or not segments:
        return RecentBriefingsContext(
            target_date=target_date,
            days=max(days, 0),
            entries_by_segment={segment: () for segment in segments},
        )

    per_segment: dict[MarketSegment, list[RecentBriefingEntry]] = {
        segment: [] for segment in segments
    }
    cursor = target_date - timedelta(days=1)
    lookback_used = 0
    while lookback_used < _MAX_LOOKBACK_DAYS and any(
        len(per_segment[segment]) < days for segment in segments
    ):
        if _is_weekday(cursor):
            for segment in segments:
                if len(per_segment[segment]) >= days:
                    continue
                entry = _try_load_entry(archive_root, segment, cursor)
                if entry is not None:
                    per_segment[segment].append(entry)
        cursor -= timedelta(days=1)
        lookback_used += 1

    return RecentBriefingsContext(
        target_date=target_date,
        days=days,
        entries_by_segment={segment: tuple(per_segment[segment]) for segment in segments},
    )


def resolve_recent_days(env: dict[str, str] | None = None) -> int:
    """Read ``INVESTO_RECENT_CONTEXT_DAYS`` and clamp to ``[0, MAX]``.

    Returns :data:`DEFAULT_RECENT_DAYS` when the env var is unset,
    empty, non-numeric, or outside the valid range. Invalid values
    (non-numeric, negative, above :data:`MAX_RECENT_DAYS`) emit a
    ``WARNING`` log line so operator typos surface in the GHA log
    instead of degrading silently. Unset / blank values are the normal
    "use the default" path and stay quiet.

    ``env`` is a test seam; production callers pass ``None`` to read
    from :data:`os.environ`.
    """
    import os  # local import keeps the test seam side-effect-free

    source: dict[str, str] | object = env if env is not None else os.environ
    raw = (
        source.get(ENV_RECENT_DAYS, "")
        if isinstance(source, dict)
        else os.environ.get(ENV_RECENT_DAYS, "")
    )
    raw = raw.strip()
    if not raw:
        return DEFAULT_RECENT_DAYS
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "%s=%r invalid (non-numeric); using default=%d",
            ENV_RECENT_DAYS,
            raw,
            DEFAULT_RECENT_DAYS,
        )
        return DEFAULT_RECENT_DAYS
    if value < 0 or value > MAX_RECENT_DAYS:
        _logger.warning(
            "%s=%r invalid (out of range [0, %d]); using default=%d",
            ENV_RECENT_DAYS,
            raw,
            MAX_RECENT_DAYS,
            DEFAULT_RECENT_DAYS,
        )
        return DEFAULT_RECENT_DAYS
    return value


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_weekday(day: date) -> bool:
    """Return ``True`` for Mon-Fri (``date.weekday()`` 0-4)."""
    return day.weekday() < 5


def _archive_markdown_path(archive_root: Path, segment: MarketSegment, day: date) -> Path:
    """Compose the archived markdown path for ``(segment, day)``.

    Mirrors :func:`investo.publisher.paths.archive_path` but kept as a
    local helper to avoid an import cycle with the publisher unit
    (project-rule #2 keeps unit packages decoupled).
    """
    return archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"


def _try_load_entry(
    archive_root: Path,
    segment: MarketSegment,
    day: date,
) -> RecentBriefingEntry | None:
    """Load and parse one archive markdown file. Returns ``None`` on miss.

    Errors are swallowed — a malformed or missing file is treated as
    "no entry for this day" rather than a hard failure. The pipeline
    must remain robust against partial archive history (the very first
    publish cannot have any context to load).
    """
    path = _archive_markdown_path(archive_root, segment, day)
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    conclusion = _extract_field(content, _CONCLUSION_PREFIX)
    drivers = _extract_field(content, _DRIVER_PREFIX)
    watermark = _extract_field(content, _WATERMARK_PREFIX)

    # Skip entries that have no usable signal — both the conclusion and
    # key drivers are empty. A watermark-only entry adds no narrative
    # value to the LLM (and would inflate the budget for nothing).
    if not conclusion and not drivers:
        return None

    return RecentBriefingEntry(
        publish_date=day,
        segment=segment,
        conclusion=conclusion,
        key_drivers=drivers,
        watermark=watermark,
    )


def _extract_field(markdown: str, prefix: str) -> str:
    """Return the first ``prefix``-anchored line's value, scrubbed + truncated.

    Iterates lines, finds the first that starts with ``prefix``, strips
    the prefix, applies STRICT-policy redaction (defensive — the
    archive bytes already passed leak-guard at publish time), and
    truncates to :data:`_FIELD_CHAR_BUDGET`. Returns ``""`` when no
    line matches or the matched value is empty after redaction.
    """
    for raw_line in markdown.splitlines():
        if not raw_line.startswith(prefix):
            continue
        value = raw_line.removeprefix(prefix).strip()
        if not value:
            return ""
        scrubbed = redact_text(value, policy=RedactionPolicy.STRICT).strip()
        if not scrubbed:
            return ""
        return _truncate(scrubbed, _FIELD_CHAR_BUDGET)
    return ""


def _truncate(text: str, limit: int) -> str:
    """Return ``text`` capped at ``limit`` characters with an ellipsis suffix.

    Idempotent for short inputs. The single-character ``…`` suffix is
    intentional — it stays under the limit even when ``len(text) ==
    limit + 1`` and renders cleanly in Korean / English mixed prose.
    """
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + "…"


__all__ = [
    "DEFAULT_RECENT_DAYS",
    "ENV_RECENT_DAYS",
    "MAX_RECENT_DAYS",
    "RecentBriefingEntry",
    "RecentBriefingsContext",
    "load_recent_briefings",
    "resolve_recent_days",
]
