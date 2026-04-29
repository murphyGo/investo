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

import asyncio
import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from investo.briefing.claude_code import (
    DEFAULT_TIMEOUT_S,
    ClaudeRunner,
    RetryBudget,
    call_claude_code,
)
from investo.briefing.disclaimer import DISCLAIMER, append_disclaimer
from investo.briefing.errors import BriefingGenerationError, SubprocessOutcome
from investo.briefing.leak_guard import scan as leak_guard_scan
from investo.briefing.prompts import (
    STAGE1_SYSTEM,
    STAGE1_USER_TEMPLATE,
    STAGE2_SECTION_HEADERS,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
)
from investo.models import Briefing, NormalizedItem

# Retry constants per FD R3.
MAX_ATTEMPTS: Final[int] = 3

# Backoff seconds before each attempt (attempt index 0 = no sleep).
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (0.0, 2.0, 8.0)

# Sanity floor for Stage 2 stdout length. Anything shorter is treated
# as a malformed response. Stage 1 has no equivalent floor — a valid
# empty result (``{"assignments": {}, "unassigned": []}``) is short.
_STAGE2_SANITY_FLOOR: Final[int] = 200

# Closed set of section IDs that Stage 1 may assign to (FD R10).
_VALID_SECTION_IDS: Final[frozenset[int]] = frozenset({2, 3, 4, 5})


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


def _parse_classification(stdout: str, item_count: int) -> ClassificationResult:
    """Parse Stage 1 stdout as JSON → ``ClassificationResult``.

    Performs both structural validation (via pydantic) and id-set
    validation (every key + every unassigned element must be a valid
    item id in ``1..item_count``).

    Raises ``ValueError`` (or wrapped ``ValidationError`` /
    ``json.JSONDecodeError``) on any structural or semantic mismatch;
    the caller catches and routes to retry.
    """
    data = json.loads(stdout)
    result = ClassificationResult.model_validate(data)
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
                if summary:
                    parts.append(f"  - [{item.source_name}] {item.title} — {summary}")
                else:
                    parts.append(f"  - [{item.source_name}] {item.title}")
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_unassigned(unassigned: tuple[NormalizedItem, ...]) -> str:
    """Render the unassigned items as bullet text. Empty → ``(none)``."""
    if not unassigned:
        return "(none)"
    return "\n".join(f"  - [{item.source_name}] {item.title}" for item in unassigned)


# ---------------------------------------------------------------------------
# Async stage helpers
# ---------------------------------------------------------------------------


async def _classify(
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
) -> ClassificationResult:
    """Run Stage 1 with the FD R3 retry loop.

    Raises ``BriefingGenerationError(stage="classification")`` after
    exhausting attempts, or ``BriefingGenerationError(stage="budget")``
    if the cumulative budget is hit before a retry can dispatch.
    """
    serialized = serialize_items_for_prompt(items)
    user_prompt = STAGE1_USER_TEMPLATE.format(items_json=serialized)
    full_prompt = f"{STAGE1_SYSTEM}\n\n{user_prompt}"

    last_outcome: SubprocessOutcome | None = None
    last_cause: BaseException | None = None

    for attempt in range(MAX_ATTEMPTS):
        # FD R3: pre-dispatch budget gate. If the next attempt would
        # push cumulative elapsed at or past ``total_budget_s``, raise
        # immediately rather than dispatching a call we cannot afford.
        # ``DEFAULT_TIMEOUT_S`` is the worst-case duration of a single
        # call (the per-call timeout); using it as the estimate is the
        # conservative choice — a fast call may still be allowed when
        # remaining budget < timeout, but we cannot prove that ahead
        # of time.
        if budget.would_exceed(DEFAULT_TIMEOUT_S):
            raise BriefingGenerationError(
                stage="budget",
                attempt_count=attempt,
                last_stderr=last_outcome.stderr if last_outcome is not None else None,
                cause=last_cause,
            )
        if attempt > 0:
            await asyncio.sleep(_BACKOFF_SCHEDULE[attempt])

        outcome = await call_claude_code(full_prompt, runner=runner)
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
        attempt_count=MAX_ATTEMPTS,
        last_stderr=last_outcome.stderr if last_outcome is not None else None,
        cause=last_cause,
    )


async def _synthesize(
    plan: SectionPlan,
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
) -> str:
    """Run Stage 2 with the FD R3 retry loop. Returns body markdown.

    The returned markdown is verified to contain all six section
    headers in order and non-blank bodies (via ``parse_six_sections``).
    Raises ``BriefingGenerationError(stage="synthesis")`` after
    exhausting attempts, or ``BriefingGenerationError(stage="budget")``
    if the cumulative budget hits.
    """
    grouped = _render_grouped_sections(plan.items_by_section)
    unassigned = _render_unassigned(plan.unassigned)
    user_prompt = STAGE2_USER_TEMPLATE.format(
        grouped_sections=grouped,
        unassigned=unassigned,
        target_date=plan.target_date.isoformat(),
    )
    full_prompt = f"{STAGE2_SYSTEM}\n\n{user_prompt}"

    last_outcome: SubprocessOutcome | None = None
    last_cause: BaseException | None = None

    for attempt in range(MAX_ATTEMPTS):
        # FD R3: pre-dispatch budget gate. See ``_classify`` for the
        # rationale — same shape, shared budget across both stages
        # (AC-1.5).
        if budget.would_exceed(DEFAULT_TIMEOUT_S):
            raise BriefingGenerationError(
                stage="budget",
                attempt_count=attempt,
                last_stderr=last_outcome.stderr if last_outcome is not None else None,
                cause=last_cause,
            )
        if attempt > 0:
            await asyncio.sleep(_BACKOFF_SCHEDULE[attempt])

        outcome = await call_claude_code(full_prompt, runner=runner)
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
        attempt_count=MAX_ATTEMPTS,
        last_stderr=last_outcome.stderr if last_outcome is not None else None,
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
    if budget is None:
        budget = RetryBudget()

    classification = await _classify(items, runner=runner, budget=budget)
    plan = build_section_plan(items, classification, target_date)
    body_markdown = await _synthesize(plan, runner=runner, budget=budget)

    # Body markdown is verified to have all 6 sections (by _synthesize's
    # internal parse_six_sections check). Re-parse here to extract the
    # section bodies for the Briefing fields.
    sections = parse_six_sections(body_markdown)

    full_markdown = append_disclaimer(body_markdown)

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
