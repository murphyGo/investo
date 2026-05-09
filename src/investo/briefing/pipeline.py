"""Two-stage briefing pipeline — classify + synthesize + assemble Briefing.

References:
    Functional Design L1 (`u2-briefing/functional-design/business-logic-model.md`)
        — end-to-end 11-step flow
    Functional Design L2 — Stage 1 classification algorithm
    Functional Design L3 — Stage 2 synthesis algorithm
    Functional Design R1 (`business-rules.md`) — two-stage LLM pipeline
    Functional Design R3 — retry policy + total budget
    Functional Design R5 — disclaimer auto-insert
    Functional Design R6 — PII / secret leak guard
    Functional Design R7 — NormalizedItem JSON serialization
    Functional Design R10 — LLM-decided section assignment (category as hint)
    Functional Design R12 — atomic generate_briefing (no partial commits)
    Functional Design E2 (`domain-entities.md`) — ClassificationResult
    Functional Design E3 — SectionPlan
    NFR Requirements AC-1.1 / 1.2 / 1.5 — RetryBudget shared across stages
    NFR Requirements AC-3.1 / 3.5 — failure contract (Briefing-or-BGE,
        no Optional / no partial)
    NFR Requirements AC-6.2 — serialize round-trip PBT
    NFR Requirements AC-6.3 — parse_six_sections round-trip PBT
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from investo.briefing import numeric_self_check, trace_footer
from investo.briefing.action_tag import apply_action_tag
from investo.briefing.claude_code import (
    DEFAULT_TIMEOUT_S,
    DEFAULT_TOTAL_BUDGET_S,
    ClaudeRunner,
    RetryBudget,
    call_claude_code,
)
from investo.briefing.context import RecentBriefingEntry, RecentBriefingsContext
from investo.briefing.disclaimer import DISCLAIMER, append_disclaimer
from investo.briefing.errors import BriefingGenerationError, SubprocessOutcome
from investo.briefing.glossary import audit_glossary_compliance, render_glossary_callout
from investo.briefing.leak_guard import scan as leak_guard_scan
from investo.briefing.market_anchor import MarketAnchor, render_market_anchor_line
from investo.briefing.prompts import (
    DEFAULT_SEGMENT_CONTEXT,
    SEGMENT_CONTEXT_TEMPLATE,
    SEGMENT_DATA_LIMITED_NOTE,
    SEGMENT_DATA_READY_NOTE,
    STAGE1_SYSTEM,
    STAGE1_USER_TEMPLATE,
    STAGE2_SECTION_HEADERS,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
    format_lookahead_section,
    format_recent_context_section,
)
from investo.briefing.segments import (
    SEGMENT_LABELS,
    MarketSegment,
    SegmentCoverage,
    build_segment_coverage,
    segment_source_outcomes,
)
from investo.briefing.watchlist import (
    WatchlistConfig,
    WatchlistImpact,
    load_watchlist,
    match_watchlist_items,
    render_watchlist_impact,
    render_watchlist_prompt_context,
)
from investo.models import Briefing, NormalizedItem, SourceOutcome

_logger = logging.getLogger("investo.briefing.pipeline")

# Retry constants per FD R3.
MAX_ATTEMPTS: Final[int] = 3

# Backoff seconds before each attempt (attempt index 0 = no sleep).
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (0.0, 2.0, 8.0)

# Sanity floor for Stage 2 stdout length. Anything shorter is treated
# as a malformed response. Stage 1 has no equivalent floor — a valid
# empty result (``{"assignments": {}, "unassigned": []}``) is short.
_STAGE2_SANITY_FLOOR: Final[int] = 200

# Upper bound for Stage 1 stdout before JSON parsing. Classification
# should be tiny; over-cap output is malformed LLM output and should
# enter the normal classification retry path instead of stressing the
# JSON parser.
_STAGE1_STDOUT_MAX_BYTES: Final[int] = 64 * 1024

# Closed set of section IDs that Stage 1 may assign to (FD R10).
_VALID_SECTION_IDS: Final[frozenset[int]] = frozenset({2, 3, 4, 5})
_MAX_LLM_ITEMS: Final[int] = 96
_MAX_LLM_ITEMS_PER_SOURCE: Final[int] = 24
# u35 event-lookahead sub-cap: at most 12 forward-scheduled items per
# segment land in the LLM input (or downstream "주요 일정" block) so a
# busy earnings calendar cannot starve the backward-evidence budget.
# Lives inside the existing 96-total / 24-per-source cap — selection
# walks lookahead items first, then backward, but each path counts
# against the same per-source slot.
_MAX_LLM_LOOKAHEAD_ITEMS: Final[int] = 12
_SEGMENT_NAV_LABELS: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "국내 증시",
    "us-equity": "미국 증시",
    "crypto": "크립토",
}
# Segment → market clock used to express the day window. Mirrors the
# adapter routing in ``investo.sources.aggregator._window_for_adapter``
# so the reader-facing watermark matches the data collection window.
# Re-binding the ZoneInfo at import time avoids hot-path lookups.
_SEGMENT_MARKET_TZ: Final[dict[MarketSegment, ZoneInfo]] = {
    "domestic-equity": ZoneInfo("Asia/Seoul"),
    "us-equity": ZoneInfo("America/New_York"),
    "crypto": ZoneInfo("UTC"),
}
_SEGMENT_MARKET_TZ_LABEL: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "KST",
    "us-equity": "NY",
    "crypto": "UTC",
}
_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_LEADING_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:>\s*)?(?:#{1,6}\s*)?(?:(?:[-*+])|\d+[.)]|[①-⑳])\s*"
)
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")
# Reject patterns the summary sentence picker uses to skip a candidate
# (matches mirror summary_quality gate-side rejects so the producer
# never emits what the gate would block).
_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
_EN_CONJUNCTION_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:vs|and|or|but|that|where|which|because|with|of|to|for|on|in|by)\.\s*$",
    re.IGNORECASE,
)
_KO_PARTICLE_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:과|와|및|또는|에서|의|을|를|이|가|은|는)\.\s*$"
)
# Sentence terminator markers, longest-first so ``니다.`` matches before
# the shorter ``다.`` substring inside it.
_SENTENCE_TERMINATORS: Final[tuple[str, ...]] = (
    "니다.",
    "다.",
    "요.",
    "?",
    "!",
)


# ---------------------------------------------------------------------------
# Domain types (E2, E3)
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """Stage 1 LLM output (FD E2).

    ``assignments`` maps synthetic item id → section id ∈ {2, 3, 4, 5}.
    ``unassigned`` lists item ids the LLM judged not section-worthy
    (Stage 2 uses these for context for sections ① and ⑥ only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignments: dict[int, int] = Field(default_factory=dict)
    unassigned: list[int] = Field(default_factory=list)

    @field_validator("assignments")
    @classmethod
    def _validate_section_ids(cls, value: dict[int, int]) -> dict[int, int]:
        valid_str = "{" + ", ".join(str(s) for s in sorted(_VALID_SECTION_IDS)) + "}"
        for k, v in value.items():
            if v not in _VALID_SECTION_IDS:
                raise ValueError(f"assignments value {v!r} for item id {k} not in {valid_str}")
        return value


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """Intermediate fed to Stage 2's prompt builder (FD E3)."""

    target_date: date
    items_by_section: dict[int, tuple[NormalizedItem, ...]]
    unassigned: tuple[NormalizedItem, ...]


@dataclass(frozen=True, slots=True)
class SummaryHeader:
    """Validated first-viewport summary lines for segmented briefings."""

    conclusion: str
    driver: str
    caution: str


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    """Per-run LLM timeout/retry policy for briefing generation."""

    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = MAX_ATTEMPTS
    total_budget_s: float = DEFAULT_TOTAL_BUDGET_S


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def serialize_items_for_prompt(items: Sequence[NormalizedItem]) -> str:
    """Emit the prompt-side JSON array for Stage 1 (FD R7).

    One JSON object per item. Synthetic ``id`` is assigned at this step
    via ``enumerate(items, start=1)`` and is NOT propagated into
    ``Briefing`` output. ``raw_metadata`` is excluded (provenance noise
    for the LLM). ``summary`` and ``url`` collapse ``None`` → ``""``
    for prompt stability. ``ts`` is RFC 3339 UTC.
    """
    payload = [
        {
            "id": idx,
            "category": item.category,
            "source": item.source_name,
            "title": item.title,
            "summary": item.summary if item.summary is not None else "",
            "url": str(item.url) if item.url is not None else "",
            "ts": item.published_at.astimezone(UTC).isoformat(),
        }
        for idx, item in enumerate(items, start=1)
    ]
    return json.dumps(payload, ensure_ascii=False)


def _select_llm_candidate_items(items: Sequence[NormalizedItem]) -> tuple[NormalizedItem, ...]:
    """Bound the item set sent to Claude while preserving source diversity.

    Public feeds can occasionally return hundreds of low-signal rows
    from one adapter, especially earnings calendars. The briefing only
    needs representative evidence; uncapped inputs can exhaust the LLM
    timeout/budget before any user-facing market note is produced.

    u35 event-lookahead extension: forward-scheduled items
    (``scheduled_at is not None``) are subject to an additional sub-cap
    (:data:`_MAX_LLM_LOOKAHEAD_ITEMS`) that prevents a busy lookahead
    bucket from starving backward evidence. The sub-cap lives inside
    the same 96-total / 24-per-source cap so the overall LLM input
    budget is preserved (NFR-002 token cost guard).
    """
    selected: list[NormalizedItem] = []
    per_source_counts: dict[str, int] = {}
    lookahead_count = 0

    for item in items:
        is_lookahead = item.scheduled_at is not None
        if is_lookahead and lookahead_count >= _MAX_LLM_LOOKAHEAD_ITEMS:
            continue
        source_count = per_source_counts.get(item.source_name, 0)
        if source_count >= _MAX_LLM_ITEMS_PER_SOURCE:
            continue
        selected.append(item)
        per_source_counts[item.source_name] = source_count + 1
        if is_lookahead:
            lookahead_count += 1
        if len(selected) >= _MAX_LLM_ITEMS:
            break

    return tuple(selected)


def _extract_braced_object(text: str, start: int) -> str | None:
    """Return the balanced ``{...}`` slice starting at ``start``."""
    depth = 0
    in_string = False
    quote = ""
    escaped = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _load_classification_payload(stdout: str) -> object:
    """Load the first JSON value from Claude's Stage 1 stdout.

    The prompt asks for JSON only, but production LLMs sometimes wrap
    the object in prose or a Markdown code fence. Recover a single JSON
    value when it is still unambiguous. Claude may also emit a Python-
    dict-like object with integer keys (``{1: 5}``) even after being
    asked for JSON; accept that literal shape and let pydantic validate
    it. Malformed output still raises ``JSONDecodeError`` and remains
    retryable.
    """
    stripped = stdout.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as original:
        decoder = json.JSONDecoder()
        for start, char in enumerate(stripped):
            if char != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(stripped[start:])
            except json.JSONDecodeError:
                braced = _extract_braced_object(stripped, start)
                if braced is None:
                    continue
                try:
                    return ast.literal_eval(braced)
                except (SyntaxError, ValueError):
                    continue
            return payload
        raise original


def _maybe_flip_inverted_assignments(data: object) -> object | None:
    """Detect and flip an inverted Stage 1 ``assignments`` payload.

    Production LLMs occasionally emit the schema upside-down — using
    ``section_id`` as the key and a list of ``item_ids`` as the value
    (e.g., ``{"3": [9, 10, 11], "5": [2, 7]}``) instead of the spec'd
    ``{<item_id>: <section_id>}`` shape. The drift burns through the
    retry budget on the same misread, so this helper offers a single
    auto-recovery: when ``assignments`` matches the inverted shape, flip
    it to the canonical orientation and let pydantic re-validate.

    Returns the flipped payload (a fresh dict) when the inversion is
    unambiguous, or ``None`` when any of the safety conditions fail —
    in which case the caller re-raises the original ``ValidationError``
    rather than papering over a different malformation:

    1. ``data["assignments"]`` is a dict (else nothing to flip).
    2. Every key parses to an int in ``{2, 3, 4, 5}`` (the closed Stage 1
       section-id set; key=1 is treated as a regular item-id payload
       and rejected so the original error surfaces).
    3. Every value is a list whose elements all parse to int.
    4. No item-id appears under more than one section (a true ambiguity
       that we refuse to silently resolve).
    """
    if not isinstance(data, dict):
        return None
    assignments = data.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        return None

    flipped: dict[str, int] = {}
    for raw_key, raw_value in assignments.items():
        try:
            section_id = int(raw_key)
        except (TypeError, ValueError):
            return None
        if section_id not in _VALID_SECTION_IDS:
            return None
        if not isinstance(raw_value, list) or not raw_value:
            return None
        for raw_item in raw_value:
            try:
                item_id = int(raw_item)
            except (TypeError, ValueError):
                return None
            key = str(item_id)
            if key in flipped:
                # Same item assigned to multiple sections — refuse to pick.
                return None
            flipped[key] = section_id

    rebuilt = dict(data)
    rebuilt["assignments"] = flipped
    return rebuilt


def _parse_classification(stdout: str, item_count: int) -> ClassificationResult:
    """Parse Stage 1 stdout as JSON → ``ClassificationResult``.

    Performs both structural validation (via pydantic) and id-set
    validation (every key + every unassigned element must be a valid
    item id in ``1..item_count``).

    Raises ``ValueError`` (or wrapped ``ValidationError`` /
    ``json.JSONDecodeError``) on any structural or semantic mismatch;
    the caller catches and routes to retry.

    Inverted-schema auto-recovery: production LLMs sometimes emit the
    schema upside-down (``{"<section_id>": [<item_ids>, ...]}``). When
    pydantic rejects the original payload, :func:`_maybe_flip_inverted_assignments`
    is given exactly one chance to flip the orientation; the flipped
    payload is then re-validated. The original ``ValidationError`` is
    re-raised when the flip is not unambiguously safe (overlap between
    sections, non-integer values, keys outside ``{2, 3, 4, 5}``).
    """
    stdout_size = len(stdout.encode("utf-8"))
    if stdout_size > _STAGE1_STDOUT_MAX_BYTES:
        raise ValueError(f"Stage 1 stdout exceeds {_STAGE1_STDOUT_MAX_BYTES} bytes: {stdout_size}")

    data = _load_classification_payload(stdout)
    try:
        result = ClassificationResult.model_validate(data)
    except ValidationError as original_validation_error:
        flipped = _maybe_flip_inverted_assignments(data)
        if flipped is None:
            raise
        try:
            result = ClassificationResult.model_validate(flipped)
        except ValidationError:
            # Flip looked plausible structurally but still failed validation
            # (e.g., a section-id leaked into the value list). Surface the
            # original error so callers see the real schema mismatch.
            raise original_validation_error from None
        _logger.info(
            "classification: recovered from inverted schema (auto-flip)",
            extra={"item_count": item_count},
        )
    valid_ids = set(range(1, item_count + 1))
    seen_ids = set(result.assignments.keys()) | set(result.unassigned)
    invalid = seen_ids - valid_ids
    if invalid:
        raise ValueError(
            f"Stage 1 referenced item id(s) outside 1..{item_count}: {sorted(invalid)}"
        )
    return result


def build_section_plan(
    items: Sequence[NormalizedItem],
    classification: ClassificationResult,
    target_date: date,
) -> SectionPlan:
    """Group items by section per Stage 1's classification (FD E3, L1.5).

    Items within each section preserve ``published_at`` descending order
    (newest first) — most recent context lands at the top of each Stage
    2 section. Items in ``unassigned`` are forwarded as-is for Stage 2
    to use as context for sections ① and ⑥.
    """
    items_by_id = {idx + 1: item for idx, item in enumerate(items)}

    buckets: dict[int, list[NormalizedItem]] = {2: [], 3: [], 4: [], 5: []}
    for item_id, section_id in classification.assignments.items():
        if item_id in items_by_id and section_id in buckets:
            buckets[section_id].append(items_by_id[item_id])

    for section_id in buckets:
        buckets[section_id].sort(key=lambda it: it.published_at, reverse=True)

    unassigned_items = tuple(items_by_id[i] for i in classification.unassigned if i in items_by_id)

    return SectionPlan(
        target_date=target_date,
        items_by_section={k: tuple(v) for k, v in buckets.items()},
        unassigned=unassigned_items,
    )


def parse_six_sections(markdown: str) -> tuple[str, str, str, str, str, str]:
    """Split ``markdown`` on the six fixed Stage 2 headers (FD L3 / R1).

    Returns the six bodies in section order. Raises ``ValueError`` if:

    * any of the six headers is missing,
    * any of the six headers appears more than once
      (inline duplicates would silently fuse adjacent bodies),
    * the headers appear out of order,
    * any body (text between consecutive headers, after strip) is empty.

    The input is NFC-normalized before search. Korean numerals (① … ⑥)
    are sensitive to Unicode normalization form (NFC vs NFD); LLMs
    occasionally emit NFD even when the prompt and constants are NFC.
    A single normalization mismatch would otherwise burn all 3 retry
    attempts before failing.

    Used by both ``_synthesize`` (validation gate before returning) and
    ``generate_briefing`` (final extraction into ``Briefing`` fields).
    Pure: no side effects, no I/O.
    """
    markdown = unicodedata.normalize("NFC", markdown)

    positions: list[int] = []
    for header in STAGE2_SECTION_HEADERS:
        count = markdown.count(header)
        if count == 0:
            raise ValueError(f"missing section header: {header!r}")
        if count > 1:
            raise ValueError(
                f"section header {header!r} appears {count} times; "
                f"each header must be unique to avoid silent body fusion"
            )
        positions.append(markdown.find(header))

    for i in range(len(positions) - 1):
        if positions[i] >= positions[i + 1]:
            raise ValueError(
                f"section headers out of order: {STAGE2_SECTION_HEADERS[i]!r} at {positions[i]} "
                f"is not before {STAGE2_SECTION_HEADERS[i + 1]!r} at {positions[i + 1]}"
            )

    bodies: list[str] = []
    for i, header in enumerate(STAGE2_SECTION_HEADERS):
        start = positions[i] + len(header)
        end = positions[i + 1] if i + 1 < len(positions) else len(markdown)
        body = markdown[start:end].strip()
        if not body:
            raise ValueError(f"section body for {header!r} is blank")
        bodies.append(body)

    return (bodies[0], bodies[1], bodies[2], bodies[3], bodies[4], bodies[5])


def _render_grouped_sections(
    items_by_section: dict[int, tuple[NormalizedItem, ...]],
) -> str:
    """Render the per-section items as bullet text for Stage 2 prompt.

    Sections without items emit ``(no items)`` so the LLM sees an
    explicit "empty" signal rather than a missing entry — Stage 2's
    system prompt instructs it to write ``특이사항 없음`` for empty
    sections.
    """
    parts: list[str] = []
    for section_id in (2, 3, 4, 5):
        items = items_by_section.get(section_id, ())
        parts.append(f"Section {section_id}:")
        if not items:
            parts.append("  (no items)")
        else:
            for item in items:
                summary = (item.summary or "").strip()
                url = f" ({item.url})" if item.url is not None else ""
                if summary:
                    parts.append(f"  - [{item.source_name}] {item.title}{url} — {summary}")
                else:
                    parts.append(f"  - [{item.source_name}] {item.title}{url}")
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_unassigned(unassigned: tuple[NormalizedItem, ...]) -> str:
    """Render the unassigned items as bullet text. Empty → ``(none)``."""
    if not unassigned:
        return "(none)"
    lines: list[str] = []
    for item in unassigned:
        url = f" ({item.url})" if item.url is not None else ""
        lines.append(f"  - [{item.source_name}] {item.title}{url}")
    return "\n".join(lines)


def _render_recent_context_block(
    segment: MarketSegment | None,
    recent_context: RecentBriefingsContext | None,
) -> str:
    """Render the u34 "최근 N일 컨텍스트" block for Stage 2.

    Returns the empty string for the unsegmented legacy path or when
    ``recent_context`` is ``None`` — the Stage 2 user template absorbs
    an empty placeholder cleanly because the surrounding template
    already provides whitespace structure.

    When ``recent_context.is_empty()`` (or the per-segment list is
    empty) the rendered block carries the "no recent context" note so
    the LLM still sees an explicit acknowledgement that the context is
    intentionally absent (vs. silently missing).

    Each entry collapses to a single line: the loader has already
    truncated the conclusion / drivers fields to the per-day budget;
    this renderer only stitches labels.
    """
    if segment is None or recent_context is None:
        return ""
    entries = recent_context.for_segment(segment)
    if not entries:
        return format_recent_context_section("")
    lines = [_render_recent_entry(entry) for entry in entries]
    return format_recent_context_section("\n".join(lines))


def _render_recent_entry(entry: RecentBriefingEntry) -> str:
    """Render one :class:`RecentBriefingEntry` as a single bullet line.

    Format::

        - YYYY-MM-DD: 결론="..." | 핵심 동인="..."

    The fields are already truncated + redacted by the loader (per the
    u34 trust contract); this function adds no additional sanitization.
    Empty fields collapse to ``(없음)`` so the LLM can see the gap
    rather than guess.
    """
    conclusion = entry.conclusion or "(없음)"
    drivers = entry.key_drivers or "(없음)"
    return f'- {entry.publish_date.isoformat()}: 결론="{conclusion}" | 핵심 동인="{drivers}"'


def _render_lookahead_context_block(items: Sequence[NormalizedItem]) -> str:
    """Render the u35 "주요 일정" block from forward-scheduled items.

    Walks ``items`` (already capped by :func:`_select_llm_candidate_items`)
    pulling out rows whose ``scheduled_at`` is set and emitting one
    bullet line per row. Empty input falls through to the
    "no lookahead" note so the LLM sees an explicit acknowledgement
    rather than silently dropping the rule.

    Each row is intentionally compact (date + source + title) — the
    block must stay under the ~300-char-per-segment budget the plan
    locks. The selection cap (:data:`_MAX_LLM_LOOKAHEAD_ITEMS` = 12)
    plus an inline character ceiling per line keeps the total bounded
    even when an upstream adapter floods.
    """
    lookahead = tuple(item for item in items if item.scheduled_at is not None)
    if not lookahead:
        return format_lookahead_section("")

    lines: list[str] = []
    for item in lookahead:
        scheduled_at = item.scheduled_at
        # Defensive — ``scheduled_at is not None`` was already checked
        # in the comprehension; this assert is for the type checker.
        assert scheduled_at is not None
        scheduled_date = scheduled_at.astimezone(UTC).date().isoformat()
        # Trim extra-long titles so a single row cannot blow the budget.
        title = item.title if len(item.title) <= 80 else item.title[:79] + "…"
        lines.append(f"- {scheduled_date}: [{item.source_name}] {title}")
    return format_lookahead_section("\n".join(lines))


def _render_segment_context(segment: MarketSegment | None, *, data_limited: bool) -> str:
    """Render prompt-side segment scope instructions for u7.

    ``segment=None`` keeps the original u2 unsegmented behavior. When a
    segment is supplied, both Stage 1 and Stage 2 see the same scope so
    classification and synthesis cannot silently drift apart.
    """
    if segment is None:
        return DEFAULT_SEGMENT_CONTEXT

    data_limited_note = SEGMENT_DATA_LIMITED_NOTE if data_limited else SEGMENT_DATA_READY_NOTE
    return SEGMENT_CONTEXT_TEMPLATE.format(
        segment_label=SEGMENT_LABELS[segment],
        segment_slug=segment,
        data_limited_note=data_limited_note,
    )


def _build_data_limited_body(target_date: date, segment: MarketSegment) -> str:
    """Return a concise six-section body for a segment with zero routed items."""
    label = SEGMENT_LABELS[segment]
    h1, h2, h3, h4, h5, h6 = STAGE2_SECTION_HEADERS
    return (
        f"{h1}\n{target_date.isoformat()} {label} 세그먼트는 정식 시황을 만들 만큼 "
        "검증된 입력 데이터가 수집되지 않았습니다. 오늘 문서는 시장 방향을 단정하지 않고, "
        "수집 공백과 확인할 항목만 짧게 남깁니다.\n\n"
        f"{h2}\n확인된 핵심 이슈 없음 — 해당 세그먼트의 뉴스/공시 입력이 충분하지 않아 "
        "주요 이벤트를 선별하지 않았습니다.\n\n"
        f"{h3}\n가격·수급 데이터 미확인 — 섹터, 자금 흐름, 상대강도 판단은 다음 정상 "
        "수집 이후로 보류합니다.\n\n"
        f"{h4}\n일정·거시 이벤트 미확인 — 세그먼트에 직접 연결되는 지표와 이벤트 근거가 "
        "부족합니다.\n\n"
        f"{h5}\n개별 종목·자산 선별 보류 — 충분한 가격/뉴스 근거 없이 티커를 나열하지 "
        "않습니다.\n\n"
        f"{h6}\n"
        "1. 데이터 수집 로그에서 실패한 소스와 성공했지만 0건을 반환한 소스를 구분합니다.\n"
        "2. 해당 시장의 대표 가격 지표와 주요 뉴스 소스가 회복됐는지 확인합니다.\n"
        "3. 다음 발행 전까지는 공신력 있는 원천 데이터로 가격과 이벤트를 별도 확인합니다.\n"
    )


def _segment_nav(target_date: date, segment: MarketSegment) -> str:
    filename = f"{target_date.isoformat()}.md"
    links: list[str] = []
    for target_segment, label in _SEGMENT_NAV_LABELS.items():
        href = (
            filename
            if target_segment == segment
            else f"../../../{target_segment}/{target_date.year}/{target_date.month:02d}/{filename}"
        )
        links.append(f"[{label}]({href})")
    return " | ".join(links)


def _clean_summary_line(line: str) -> str:
    """Strip markdown punctuation off a single line and return its prose.

    Returns ``""`` if the line is empty after stripping, or if all that
    remains is a list marker / punctuation with no meaningful text.
    """
    cleaned = line.strip()
    if not cleaned:
        return ""
    cleaned = _LEADING_MARKDOWN_RE.sub("", cleaned).strip()
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    if not _MEANINGFUL_TEXT_RE.search(cleaned):
        return ""
    if _MARKER_ONLY_RE.fullmatch(cleaned):
        return ""
    return cleaned


def _is_unsafe_summary_candidate(candidate: str) -> bool:
    """Reject candidate strings that would later trip the publish gate.

    Mirrors the rejects in ``summary_quality.validate_first_viewport_summary``
    so the producer never emits a string the gate would block. Keeping
    the two lists aligned is the contract; a regression here surfaces
    as a publish-time ``SummaryQualityError``.
    """
    if not candidate:
        return True
    if _MARKER_ONLY_RE.fullmatch(candidate):
        return True
    if not _MEANINGFUL_TEXT_RE.search(candidate):
        return True
    if candidate.count("**") % 2 != 0:
        return True
    if candidate.count("[") != candidate.count("]"):
        return True
    if candidate.count("(") != candidate.count(")"):
        return True
    if _EN_CONJUNCTION_TAIL_RE.search(candidate):
        return True
    return bool(_KO_PARTICLE_TAIL_RE.search(candidate))


def _split_into_sentences(normalized: str) -> list[str]:
    """Split a single normalized prose line into sentence-shaped chunks.

    Splits on the closed set of Korean sentence terminators
    (``다.``, ``니다.``, ``요.``, ``?``, ``!``) so each candidate ends
    on a complete clause. The terminator stays attached to its
    preceding chunk so the caller can decide whether to keep it. If no
    terminator is found the whole string is returned as a single chunk.
    """
    chunks: list[str] = []
    remaining = normalized
    while remaining:
        best_idx = -1
        best_marker = ""
        for marker in _SENTENCE_TERMINATORS:
            idx = remaining.find(marker)
            if idx < 0:
                continue
            if best_idx < 0 or idx < best_idx:
                best_idx = idx
                best_marker = marker
        if best_idx < 0:
            chunks.append(remaining.strip())
            break
        chunk = remaining[: best_idx + len(best_marker)].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_idx + len(best_marker) :].lstrip()
    return [c for c in chunks if c]


def _summary_sentence(text: str, *, fallback: str) -> str:
    """Extract the first publish-safe sentence from a section body.

    Iterates sentence-shaped chunks (terminator-anchored) and returns
    the first one that passes :func:`_is_unsafe_summary_candidate`.
    Falls back to ``fallback`` when no chunk survives — this keeps the
    first-viewport summary well-formed even when the LLM's section
    body opens with a marker fragment, an unfinished bold pair, or a
    conjunction tail (the three persona-cited 2026-05-06 failures).
    """
    cleaned_lines = [
        cleaned for line in text.splitlines() if (cleaned := _clean_summary_line(line))
    ]
    normalized = " ".join(cleaned_lines)
    if not normalized:
        return fallback

    sentences = _split_into_sentences(normalized)

    # Per-sentence scan first: pick the first complete, safe sentence.
    for candidate in sentences:
        if not _is_unsafe_summary_candidate(candidate):
            return candidate[:280].strip()

    # No complete sentence survived. Try each cleaned line as a
    # standalone candidate (truncated to 140 chars) — line-shaped
    # phrases without a terminator can still be valid summaries.
    for line in cleaned_lines:
        candidate = line[:140].strip()
        if not _is_unsafe_summary_candidate(candidate):
            return candidate

    # Last resort: the truncated normalized blob. If even that is
    # unsafe, hand back the explicit data-limited fallback string.
    candidate = normalized[:140].strip()
    if not _is_unsafe_summary_candidate(candidate):
        return candidate
    return fallback


def _build_summary_header(
    sections: tuple[str, str, str, str, str, str],
    *,
    data_limited: bool = False,
) -> SummaryHeader:
    """Build the three first-viewport summary lines.

    u30 Step 3 — the conclusion line is post-processed to carry exactly
    one closed-set action tag (``[관망]`` / ``[변동성↑]`` / ``[강세]`` /
    ``[약세]`` / ``[혼조]`` / ``[데이터부족]``). When ``data_limited`` is
    true the tag is forced to ``[데이터부족]`` regardless of what (if
    anything) the LLM emitted; otherwise an off-set or missing tag is
    rewritten to the deterministic default ``[관망]``. See
    :mod:`investo.briefing.action_tag`.
    """
    raw_conclusion = _summary_sentence(sections[0], fallback="확인된 요약이 부족합니다.")
    return SummaryHeader(
        conclusion=apply_action_tag(
            raw_conclusion,
            data_limited=data_limited,
            section_text=sections[0],
        ),
        driver=_summary_sentence(sections[1], fallback="핵심 동인은 추가 확인이 필요합니다."),
        caution=_summary_sentence(sections[5], fallback="관전 포인트는 데이터 회복 후 보강합니다."),
    )


def _render_coverage_badge(coverage: SegmentCoverage) -> str:
    """Render the reader-facing coverage badge.

    The badge is one or three blockquote lines:

    * line 1 — status, item / source counts, missing categories
    * line 2 (only when reason codes are present) — Korean labels for
      every reason code in deterministic order
    * line 3 (only when source outcomes are present) — sanitized
      per-source breakdown (failed first, then zero) so readers can
      see *which* source caused the partial / insufficient verdict.
      Failure reasons go through
      :func:`investo.models.sanitize_source_error_message` upstream and
      are guaranteed not to leak secret-shaped tokens.
    """
    lines = [
        f"> **데이터 상태**: {coverage.status_label} — "
        f"수집 {coverage.item_count}건 / 소스 {coverage.source_count}개 / "
        f"누락: {coverage.missing_category_label}",
    ]
    tier_label = coverage.tier_mix_label
    if tier_label:
        lines.append(f"> **소스 등급 분포**: {tier_label}")
    if coverage.reason_codes:
        lines.append(f"> **상세 사유**: {', '.join(coverage.reason_labels)}")
    source_line = _render_source_outcome_line(coverage)
    if source_line:
        lines.append(f"> **소스별 상태**: {source_line}")
    return "\n".join(lines) + "\n"


def _render_source_outcome_line(coverage: SegmentCoverage) -> str:
    """Compose the per-source sanitized status line.

    The composition is deterministic: failed sources first (with their
    sanitized reason), then zero-item sources, then a concise count of
    healthy sources. We omit individual healthy source names to keep
    the line short — the reader-relevant signal is *what went wrong*,
    not the full healthy adapter list.
    """
    failed = coverage.failed_source_outcomes
    zero = coverage.zero_source_outcomes
    ok = coverage.ok_source_outcomes
    if not failed and not zero and not ok:
        return ""
    parts: list[str] = []
    for outcome in failed:
        reason = outcome.failure_reason or "사유 미확인"
        parts.append(f"{outcome.source_name} 실패 ({reason})")
    for outcome in zero:
        parts.append(f"{outcome.source_name} 0건")
    if ok:
        parts.append(f"정상 {len(ok)}개")
    return ", ".join(parts)


def _render_watchlist_callout(impact: WatchlistImpact) -> str:
    """Render the site-channel watchlist callout (u28).

    Always emits a callout for the public site, including the ``unconfigured``
    onboarding nudge and the ``coverage_hold`` branch. The Telegram surface
    is rendered separately via :func:`render_watchlist_impact` with
    ``channel='telegram'`` and is allowed to skip these branches.
    """
    return f"> **내 관심 자산 영향**: {render_watchlist_impact(impact, channel='site')}\n"


def _render_timestamp_watermark(target_date: date, segment: MarketSegment) -> str:
    """Render the per-segment data-window watermark line.

    Format::

        **기준 시각**: 2026-05-06 KST · [2026-05-05T15:00Z, 2026-05-06T15:00Z)

    The local-clock label (KST / NY / UTC) is the segment's market
    clock — domestic-equity uses KST, us-equity uses America/New_York,
    crypto uses UTC. The bracketed window is the half-open UTC range
    used by the adapters that fed this segment, so the line reads
    "this is what trading day this is, and what slice of UTC it
    covered". Pure: no I/O, no clock reads — the value is a function
    of ``(target_date, segment)`` only.
    """
    market_tz = _SEGMENT_MARKET_TZ[segment]
    tz_label = _SEGMENT_MARKET_TZ_LABEL[segment]
    start_local = datetime.combine(target_date, time.min, tzinfo=market_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    end_str = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    return f"**기준 시각**: {target_date.isoformat()} {tz_label} · [{start_str}, {end_str})"


def _enhance_reader_experience(
    body_markdown: str,
    *,
    target_date: date,
    segment: MarketSegment | None,
    sections: tuple[str, str, str, str, str, str],
    coverage: SegmentCoverage | None = None,
    watchlist_impact: WatchlistImpact | None = None,
    data_limited: bool = False,
    candidates: Sequence[NormalizedItem] | None = None,
    market_anchors: Sequence[MarketAnchor] = (),
) -> str:
    """Prepend the reader-facing title, segment nav, and 3-line brief."""
    if segment is None:
        return body_markdown

    label = SEGMENT_LABELS[segment]
    effective_data_limited = data_limited or (coverage is not None and coverage.status != "normal")
    summary_header = _build_summary_header(sections, data_limited=effective_data_limited)
    watermark = _render_timestamp_watermark(target_date, segment)
    # u49 — deterministic market anchor line (ATH / 52w / MTD / YTD).
    # Empty when no anchors landed (history fetch failed or empty
    # input); the helper returns "" so the f-string collapses cleanly.
    anchor_line = render_market_anchor_line(market_anchors)
    # u32 Step 2 — Stage 3 numeric self-check. Compare flaggable numeric
    # tokens in the body against the Stage 1 candidate haystack and
    # render a single-line warning callout when mismatches are found.
    numeric_warning_line = ""
    if candidates is not None:
        unverified = numeric_self_check.find_unverified(body_markdown, candidates)
        numeric_warning_line = numeric_self_check.render_warning_line(unverified)
    glossary_line = render_glossary_callout(
        audit_glossary_compliance(body_markdown, segment=segment)
    )
    header = (
        f"# {target_date.isoformat()} {label} 시황\n\n"
        f"{watermark}\n\n"
        f"{anchor_line}"
        f"**세그먼트**: {_segment_nav(target_date, segment)}\n\n"
        f"{_render_coverage_badge(coverage) if coverage is not None else ''}"
        f"{_render_watchlist_callout(watchlist_impact) if watchlist_impact is not None else ''}"
        f"{numeric_warning_line}"
        f"{glossary_line}"
        f"> **오늘의 결론**: {summary_header.conclusion}\n"
        f"> **핵심 동인**: {summary_header.driver}\n"
        f"> **주의할 점**: {summary_header.caution}\n\n"
    )
    return f"{header}{body_markdown}"


# ---------------------------------------------------------------------------
# Async stage helpers
# ---------------------------------------------------------------------------


async def _classify(
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
    policy: GenerationPolicy,
    segment_context: str,
) -> ClassificationResult:
    """Run Stage 1 with the FD R3 retry loop.

    Raises ``BriefingGenerationError(stage="classification")`` after
    exhausting attempts, or ``BriefingGenerationError(stage="budget")``
    if the cumulative budget is hit before a retry can dispatch.
    """
    serialized = serialize_items_for_prompt(items)
    user_prompt = STAGE1_USER_TEMPLATE.format(
        segment_context=segment_context,
        items_json=serialized,
    )
    full_prompt = f"{STAGE1_SYSTEM}\n\n{user_prompt}"

    last_outcome: SubprocessOutcome | None = None
    last_cause: BaseException | None = None

    for attempt in range(policy.max_attempts):
        # FD R3: pre-dispatch budget gate. If the next attempt would
        # push cumulative elapsed at or past ``total_budget_s``, raise
        # immediately rather than dispatching a call we cannot afford.
        # ``DEFAULT_TIMEOUT_S`` is the worst-case duration of a single
        # call (the per-call timeout); using it as the estimate is the
        # conservative choice — a fast call may still be allowed when
        # remaining budget < timeout, but we cannot prove that ahead
        # of time.
        if budget.would_exceed(policy.timeout_s):
            raise BriefingGenerationError(
                stage="budget",
                attempt_count=attempt,
                last_stderr=last_outcome.stderr if last_outcome is not None else None,
                last_stdout=last_outcome.stdout if last_outcome is not None else None,
                cause=last_cause,
            )
        if attempt > 0:
            await asyncio.sleep(_BACKOFF_SCHEDULE[attempt])

        outcome = await call_claude_code(full_prompt, timeout_s=policy.timeout_s, runner=runner)
        budget.record(outcome.elapsed_s)
        last_outcome = outcome

        if outcome.returncode != 0 or not outcome.stdout.strip():
            last_cause = ValueError(
                f"Stage 1 subprocess returned rc={outcome.returncode}, "
                f"stdout_len={len(outcome.stdout)}"
            )
            continue

        try:
            return _parse_classification(outcome.stdout, item_count=len(items))
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_cause = exc
            continue

    raise BriefingGenerationError(
        stage="classification",
        attempt_count=policy.max_attempts,
        last_stderr=last_outcome.stderr if last_outcome is not None else None,
        last_stdout=last_outcome.stdout if last_outcome is not None else None,
        cause=last_cause,
    )


async def _synthesize(
    plan: SectionPlan,
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
    policy: GenerationPolicy,
    segment_context: str,
    recent_context_block: str = "",
    lookahead_context_block: str = "",
) -> str:
    """Run Stage 2 with the FD R3 retry loop. Returns body markdown.

    The returned markdown is verified to contain all six section
    headers in order and non-blank bodies (via ``parse_six_sections``).
    Raises ``BriefingGenerationError(stage="synthesis")`` after
    exhausting attempts, or ``BriefingGenerationError(stage="budget")``
    if the cumulative budget hits.

    ``recent_context_block`` is the optional u34 "최근 N일 컨텍스트"
    block — pre-rendered by :func:`_render_recent_context_block` so
    this function stays a thin retry wrapper. Empty string means the
    Stage 2 prompt omits the block entirely (first publish path).

    ``lookahead_context_block`` is the optional u35 "주요 일정" block —
    pre-rendered by :func:`_render_lookahead_context_block`. Empty
    string means no opt-in adapter contributed forward items, in which
    case the Stage 2 prompt omits the block (the system rule still
    forbids invented forward forecasts).
    """
    grouped = _render_grouped_sections(plan.items_by_section)
    unassigned = _render_unassigned(plan.unassigned)
    user_prompt = STAGE2_USER_TEMPLATE.format(
        segment_context=segment_context,
        grouped_sections=grouped,
        unassigned=unassigned,
        target_date=plan.target_date.isoformat(),
        recent_context=recent_context_block,
        lookahead_context=lookahead_context_block,
    )
    full_prompt = f"{STAGE2_SYSTEM}\n\n{user_prompt}"

    last_outcome: SubprocessOutcome | None = None
    last_cause: BaseException | None = None

    for attempt in range(policy.max_attempts):
        # FD R3: pre-dispatch budget gate. See ``_classify`` for the
        # rationale — same shape, shared budget across both stages
        # (AC-1.5).
        if budget.would_exceed(policy.timeout_s):
            raise BriefingGenerationError(
                stage="budget",
                attempt_count=attempt,
                last_stderr=last_outcome.stderr if last_outcome is not None else None,
                last_stdout=last_outcome.stdout if last_outcome is not None else None,
                cause=last_cause,
            )
        if attempt > 0:
            await asyncio.sleep(_BACKOFF_SCHEDULE[attempt])

        outcome = await call_claude_code(full_prompt, timeout_s=policy.timeout_s, runner=runner)
        budget.record(outcome.elapsed_s)
        last_outcome = outcome

        if outcome.returncode != 0 or len(outcome.stdout) < _STAGE2_SANITY_FLOOR:
            last_cause = ValueError(
                f"Stage 2 subprocess returned rc={outcome.returncode}, "
                f"stdout_len={len(outcome.stdout)}"
            )
            continue

        try:
            parse_six_sections(outcome.stdout)
        except ValueError as exc:
            last_cause = exc
            continue

        return outcome.stdout

    raise BriefingGenerationError(
        stage="synthesis",
        attempt_count=policy.max_attempts,
        last_stderr=last_outcome.stderr if last_outcome is not None else None,
        last_stdout=last_outcome.stdout if last_outcome is not None else None,
        cause=last_cause,
    )


# ---------------------------------------------------------------------------
# Public entry point — atomic L1
# ---------------------------------------------------------------------------


async def generate_briefing(
    target_date: date,
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None = None,
    budget: RetryBudget | None = None,
    segment: MarketSegment | None = None,
    data_limited: bool = False,
    watchlist_config: WatchlistConfig | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    recent_context: RecentBriefingsContext | None = None,
    market_anchors: Sequence[MarketAnchor] = (),
    generation_policy: GenerationPolicy | None = None,
) -> Briefing:
    """Atomic two-stage briefing generation (FD L1 + R12).

    Returns a fully-validated ``Briefing`` on success. Raises
    ``BriefingGenerationError`` on LLM-traceable failure (stage = one
    of ``classification`` / ``synthesis`` / ``post_validation`` /
    ``budget``). Programmer errors (``KeyError``, ``ValidationError``
    constructing ``Briefing``, ...) propagate as-is per the failure
    contract — they are NOT wrapped.

    ``runner`` is the ``ClaudeRunner`` test seam (``None`` →
    ``call_claude_code`` uses its default real-subprocess runner).
    ``budget`` is the shared retry budget; constructed fresh if not
    provided.
    """
    policy = generation_policy if generation_policy is not None else GenerationPolicy()
    if budget is None:
        budget = RetryBudget(total_budget_s=policy.total_budget_s)

    if segment is not None:
        # source_outcomes coming from the orchestrator span every
        # registered adapter; the reader-facing coverage card only
        # cares about adapters mapped to *this* segment.
        relevant_outcomes = segment_source_outcomes(segment, source_outcomes)
        coverage = build_segment_coverage(segment, items, source_outcomes=relevant_outcomes)
    else:
        coverage = None
    watchlist = load_watchlist() if watchlist_config is None else watchlist_config
    watchlist_impact = match_watchlist_items(
        items,
        watchlist,
        coverage_status=coverage.status if coverage is not None else None,
    )
    effective_data_limited = data_limited or (coverage is not None and coverage.status != "normal")

    if segment is not None and effective_data_limited and not items:
        body_markdown = _build_data_limited_body(target_date, segment)
        sections = parse_six_sections(body_markdown)
        enhanced_markdown = _enhance_reader_experience(
            body_markdown,
            target_date=target_date,
            segment=segment,
            sections=sections,
            coverage=coverage,
            watchlist_impact=watchlist_impact,
            data_limited=True,
            candidates=items,
            market_anchors=market_anchors,
        )
        full_markdown = append_disclaimer(enhanced_markdown)
        hit = leak_guard_scan(full_markdown)
        if hit is not None:
            raise BriefingGenerationError(
                stage="post_validation",
                attempt_count=1,
                last_stderr=None,
                cause=ValueError(f"leak guard matched pattern: {hit.pattern_name}"),
            )
        return Briefing(
            target_date=target_date,
            market_summary=sections[0],
            key_issues=sections[1],
            sector_flow=sections[2],
            indicators_events=sections[3],
            notable_tickers=sections[4],
            today_watch=sections[5],
            disclaimer=DISCLAIMER,
            rendered_markdown=full_markdown,
        )

    segment_context = _render_segment_context(segment, data_limited=effective_data_limited)
    watchlist_context = render_watchlist_prompt_context(watchlist_impact)
    if watchlist_context:
        segment_context = f"{segment_context}\n\n{watchlist_context}"
    recent_context_block = _render_recent_context_block(segment, recent_context)
    llm_items = _select_llm_candidate_items(items)
    lookahead_context_block = _render_lookahead_context_block(llm_items)
    classification = await _classify(
        llm_items,
        runner=runner,
        budget=budget,
        policy=policy,
        segment_context=segment_context,
    )
    plan = build_section_plan(llm_items, classification, target_date)
    body_markdown = await _synthesize(
        plan,
        runner=runner,
        budget=budget,
        policy=policy,
        segment_context=segment_context,
        recent_context_block=recent_context_block,
        lookahead_context_block=lookahead_context_block,
    )

    # Body markdown is verified to have all 6 sections (by _synthesize's
    # internal parse_six_sections check). Re-parse here to extract the
    # section bodies for the Briefing fields.
    sections = parse_six_sections(body_markdown)

    enhanced_markdown = _enhance_reader_experience(
        body_markdown,
        target_date=target_date,
        segment=segment,
        sections=sections,
        coverage=coverage,
        watchlist_impact=watchlist_impact,
        data_limited=effective_data_limited,
        candidates=llm_items,
        market_anchors=market_anchors,
    )
    # u32 Step 3 — append the traceability + signature footer just
    # before the disclaimer. The footer is `<details>`-collapsed so it
    # does not crowd the first viewport but stays one click away for
    # readers who want to verify the signature chain.
    enhanced_markdown += "\n" + trace_footer.render_traceability_footer(
        llm_items,
        classification.model_dump(),
        body_markdown,
    )
    full_markdown = append_disclaimer(enhanced_markdown)

    hit = leak_guard_scan(full_markdown)
    if hit is not None:
        raise BriefingGenerationError(
            stage="post_validation",
            attempt_count=1,
            last_stderr=None,
            cause=ValueError(f"leak guard matched pattern: {hit.pattern_name}"),
        )

    return Briefing(
        target_date=target_date,
        market_summary=sections[0],
        key_issues=sections[1],
        sector_flow=sections[2],
        indicators_events=sections[3],
        notable_tickers=sections[4],
        today_watch=sections[5],
        disclaimer=DISCLAIMER,
        rendered_markdown=full_markdown,
    )


__all__ = [
    "MAX_ATTEMPTS",
    "ClassificationResult",
    "SectionPlan",
    "build_section_plan",
    "generate_briefing",
    "parse_six_sections",
    "serialize_items_for_prompt",
]
