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
    DEFAULT_SEGMENT_CONTEXT,
    SEGMENT_CONTEXT_TEMPLATE,
    SEGMENT_DATA_LIMITED_NOTE,
    SEGMENT_DATA_READY_NOTE,
    STAGE1_SYSTEM,
    STAGE1_USER_TEMPLATE,
    STAGE2_SECTION_HEADERS,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
)
from investo.briefing.segments import SEGMENT_LABELS, MarketSegment
from investo.models import Briefing, NormalizedItem

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
_SEGMENT_NAV_LABELS: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "국내 증시",
    "us-equity": "미국 증시",
    "crypto": "크립토",
}


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


def _parse_classification(stdout: str, item_count: int) -> ClassificationResult:
    """Parse Stage 1 stdout as JSON → ``ClassificationResult``.

    Performs both structural validation (via pydantic) and id-set
    validation (every key + every unassigned element must be a valid
    item id in ``1..item_count``).

    Raises ``ValueError`` (or wrapped ``ValidationError`` /
    ``json.JSONDecodeError``) on any structural or semantic mismatch;
    the caller catches and routes to retry.
    """
    stdout_size = len(stdout.encode("utf-8"))
    if stdout_size > _STAGE1_STDOUT_MAX_BYTES:
        raise ValueError(f"Stage 1 stdout exceeds {_STAGE1_STDOUT_MAX_BYTES} bytes: {stdout_size}")

    data = _load_classification_payload(stdout)
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


def _first_sentence(text: str, *, fallback: str) -> str:
    normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return fallback
    for marker in (". ", "다. ", "요. "):
        idx = normalized.find(marker)
        if idx >= 0:
            return normalized[: idx + len(marker.strip())].strip()
    return normalized[:140].strip()


def _enhance_reader_experience(
    body_markdown: str,
    *,
    target_date: date,
    segment: MarketSegment | None,
    sections: tuple[str, str, str, str, str, str],
) -> str:
    """Prepend the reader-facing title, segment nav, and 3-line brief."""
    if segment is None:
        return body_markdown

    label = SEGMENT_LABELS[segment]
    conclusion = _first_sentence(sections[0], fallback="확인된 요약이 부족합니다.")
    driver = _first_sentence(sections[1], fallback="핵심 동인은 추가 확인이 필요합니다.")
    caution = _first_sentence(sections[5], fallback="관전 포인트는 데이터 회복 후 보강합니다.")
    header = (
        f"# {target_date.isoformat()} {label} 시황\n\n"
        f"**세그먼트**: {_segment_nav(target_date, segment)}\n\n"
        f"> **오늘의 결론**: {conclusion}\n"
        f"> **핵심 동인**: {driver}\n"
        f"> **주의할 점**: {caution}\n\n"
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
                last_stdout=last_outcome.stdout if last_outcome is not None else None,
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
        last_stdout=last_outcome.stdout if last_outcome is not None else None,
        cause=last_cause,
    )


async def _synthesize(
    plan: SectionPlan,
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
    segment_context: str,
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
        segment_context=segment_context,
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
                last_stdout=last_outcome.stdout if last_outcome is not None else None,
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

    if segment is not None and data_limited and not items:
        body_markdown = _build_data_limited_body(target_date, segment)
        sections = parse_six_sections(body_markdown)
        enhanced_markdown = _enhance_reader_experience(
            body_markdown,
            target_date=target_date,
            segment=segment,
            sections=sections,
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

    segment_context = _render_segment_context(segment, data_limited=data_limited)
    classification = await _classify(
        items,
        runner=runner,
        budget=budget,
        segment_context=segment_context,
    )
    plan = build_section_plan(items, classification, target_date)
    body_markdown = await _synthesize(
        plan,
        runner=runner,
        budget=budget,
        segment_context=segment_context,
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
