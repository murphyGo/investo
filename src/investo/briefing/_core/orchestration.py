"""Stage 1 / Stage 2 LLM orchestration — retry + budget loops.

References:
    Functional Design R3 — retry policy + total budget
    Functional Design R7 — NormalizedItem JSON serialization
    NFR Requirements AC-1.1 / 1.2 / 1.5 — RetryBudget shared across stages

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). The Claude-Code-CLI-only rule and the
timeout/retry budget are preserved exactly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date
from typing import Final

from pydantic import ValidationError

from investo.briefing._assembly.markdown_render import (
    _render_grouped_sections,
    _render_required_macro_actuals,
    _render_unassigned,
    _stage2_retry_feedback,
)
from investo.briefing._assembly.prompt_fields import (
    _render_stage1_prompt_summary,
    _render_stage1_prompt_title,
    _render_stage1_prompt_url,
)
from investo.briefing._assembly.text_normalize import parse_six_sections
from investo.briefing._core.classification import ClassificationResult, _parse_classification
from investo.briefing._core.section_planning import SectionPlan, _required_macro_item_ids
from investo.briefing.claude_code import (
    DEFAULT_TIMEOUT_S,
    DEFAULT_TOTAL_BUDGET_S,
    ClaudeRunner,
    RetryBudget,
    call_claude_code,
)
from investo.briefing.errors import BriefingGenerationError, SubprocessOutcome
from investo.briefing.prompts import (
    STAGE1_SYSTEM,
    STAGE1_USER_TEMPLATE,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
)
from investo.briefing.segments import MarketSegment
from investo.models import NormalizedItem
from investo.models.macro import (
    macro_event_date,
    macro_priority,
    macro_priority_rank,
    macro_prompt_payload,
)

_logger = logging.getLogger("investo.briefing.pipeline")

# Retry constants per FD R3.
MAX_ATTEMPTS: Final[int] = 3

# Backoff seconds before each attempt (attempt index 0 = no sleep).
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (0.0, 2.0, 8.0)

# Sanity floor for Stage 2 stdout length. Anything shorter is treated
# as a malformed response. Stage 1 has no equivalent floor — a valid
# empty result (``{"assignments": {}, "unassigned": []}``) is short.
_STAGE2_SANITY_FLOOR: Final[int] = 200

_MAX_LLM_ITEMS: Final[int] = 96
_MAX_LLM_ITEMS_PER_SOURCE: Final[int] = 24
_MAX_LLM_MACRO_PRIORITY_ITEMS: Final[int] = 12
# u35 event-lookahead sub-cap: at most 12 forward-scheduled items per
# segment land in the LLM input (or downstream "주요 일정" block) so a
# busy earnings calendar cannot starve the backward-evidence budget.
# Lives inside the existing 96-total / 24-per-source cap — selection
# walks lookahead items first, then backward, but each path counts
# against the same per-source slot.
_MAX_LLM_LOOKAHEAD_ITEMS: Final[int] = 12


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    """Per-run LLM timeout/retry policy for briefing generation."""

    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = MAX_ATTEMPTS
    total_budget_s: float = DEFAULT_TOTAL_BUDGET_S


def serialize_items_for_prompt(items: Sequence[NormalizedItem]) -> str:
    """Emit the prompt-side JSON array for Stage 1 (FD R7).

    One JSON object per item. Synthetic ``id`` is assigned at this step
    via ``enumerate(items, start=1)`` and is NOT propagated into
    ``Briefing`` output. ``raw_metadata`` is excluded (provenance noise
    for the LLM). ``summary`` and ``url`` collapse ``None`` → ``""``
    for prompt stability. ``ts`` is RFC 3339 UTC.
    """
    payload: list[dict[str, object]] = []
    for idx, item in enumerate(items, start=1):
        entry: dict[str, object] = {
            "id": idx,
            "category": item.category,
            "source": item.source_name,
            "title": _render_stage1_prompt_title(item.title),
            "summary": _render_stage1_prompt_summary(item.summary),
            "url": _render_stage1_prompt_url(item.url),
            "ts": item.published_at.astimezone(UTC).isoformat(),
        }
        macro_payload = macro_prompt_payload(item)
        if macro_payload is not None:
            entry["macro"] = macro_payload
        payload.append(entry)
    return json.dumps(payload, ensure_ascii=False)


def _select_llm_candidate_items(
    items: Sequence[NormalizedItem], *, target_date: date | None = None
) -> tuple[NormalizedItem, ...]:
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
    selected_indexes: set[int] = set()

    def add_item(index: int, item: NormalizedItem) -> None:
        nonlocal lookahead_count
        if len(selected) >= _MAX_LLM_ITEMS:
            return
        if index in selected_indexes:
            return
        is_lookahead = item.scheduled_at is not None
        if is_lookahead and lookahead_count >= _MAX_LLM_LOOKAHEAD_ITEMS:
            return
        source_count = per_source_counts.get(item.source_name, 0)
        if source_count >= _MAX_LLM_ITEMS_PER_SOURCE:
            return
        selected.append(item)
        selected_indexes.add(index)
        per_source_counts[item.source_name] = source_count + 1
        if is_lookahead:
            lookahead_count += 1

    # u59 — official macro events such as CPI/PPI/NFP/FOMC are
    # high-recall signals. Preserve a bounded number before generic
    # lookahead/news rows spend the candidate budget.
    macro_candidates = [
        (index, item) for index, item in enumerate(items) if macro_priority(item) in {"P0", "P1"}
    ]
    if target_date is not None:
        macro_candidates.sort(
            key=lambda candidate: (
                macro_priority_rank(macro_priority(candidate[1])),
                abs((macro_event_date(candidate[1]) - target_date).days),
                candidate[1].source_name,
                candidate[0],
            )
        )
    for index, item in macro_candidates[:_MAX_LLM_MACRO_PRIORITY_ITEMS]:
        add_item(index, item)
        if len(selected) >= _MAX_LLM_ITEMS:
            break

    # u58 — official crypto-regulation items are high-recall signals.
    # They often lack price/BTC/ETH tokens, so preserve a bounded number
    # before the generic source-diversity pass can spend the budget on
    # high-volume news or earnings feeds.
    for index, item in enumerate(items):
        if _is_official_crypto_policy_item(item):
            add_item(index, item)
        if len(selected) >= _MAX_LLM_ITEMS:
            break

    for index, item in enumerate(items):
        add_item(index, item)
        if len(selected) >= _MAX_LLM_ITEMS:
            break

    return tuple(selected)


def _is_official_crypto_policy_item(item: NormalizedItem) -> bool:
    return (
        item.raw_metadata.get("policy_priority") == "crypto_regulation"
        and item.raw_metadata.get("official_source") == "true"
    )


def _validate_required_macro_mentions(
    markdown: str, required_macro_items: tuple[NormalizedItem, ...]
) -> None:
    """Ensure required macro actuals survived Stage 2 generation."""

    if not required_macro_items:
        return

    for item in required_macro_items:
        payload = macro_prompt_payload(item) or {}
        candidates = [
            item.title,
            payload.get("label", ""),
            str(item.url) if item.url is not None else "",
        ]
        if not any(candidate and candidate in markdown for candidate in candidates):
            event_key = payload.get("event_key", item.title)
            raise ValueError(f"Stage 2 omitted required macro actual: {event_key}")


async def _classify(
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None,
    budget: RetryBudget,
    policy: GenerationPolicy,
    segment_context: str,
    segment: MarketSegment | None = None,
) -> ClassificationResult:
    """Run Stage 1 with the FD R3 retry loop.

    Raises ``BriefingGenerationError(stage="classification")`` after
    exhausting attempts, or ``BriefingGenerationError(stage="budget")``
    if the cumulative budget is hit before a retry can dispatch.
    """
    serialized = serialize_items_for_prompt(items)
    required_item_ids = _required_macro_item_ids(items)
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
        _logger.info(
            "llm attempt segment=%s stage=classification attempt=%d timeout_s=%.1f "
            "elapsed_s=%.3f prompt_bytes=%d stdout_len=%d stderr_len=%d returncode=%d",
            segment,
            attempt + 1,
            policy.timeout_s,
            outcome.elapsed_s,
            len(full_prompt.encode("utf-8")),
            len(outcome.stdout),
            len(outcome.stderr),
            outcome.returncode,
            extra={
                "segment": segment,
                "llm_stage": "classification",
                "attempt": attempt + 1,
                "timeout_s": policy.timeout_s,
                "elapsed_s": outcome.elapsed_s,
                "prompt_bytes": len(full_prompt.encode("utf-8")),
                "stdout_len": len(outcome.stdout),
                "stderr_len": len(outcome.stderr),
                "returncode": outcome.returncode,
            },
        )
        budget.record(outcome.elapsed_s)
        last_outcome = outcome

        if outcome.returncode != 0 or not outcome.stdout.strip():
            last_cause = ValueError(
                f"Stage 1 subprocess returned rc={outcome.returncode}, "
                f"stdout_len={len(outcome.stdout)}"
            )
            continue

        try:
            return _parse_classification(
                outcome.stdout,
                item_count=len(items),
                required_item_ids=required_item_ids,
            )
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
    carryover_context_block: str = "",
    bundle_context_block: str = "",
    segment: MarketSegment | None = None,
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

    ``carryover_context_block`` is the optional u52 "## Watchlist
    Carryover (입력)" block — pre-rendered by
    :func:`_render_carryover_context_block`. Empty string means the
    segment has no carryover from prior briefings (matching CARRY-4:
    omit the table rather than fabricate rows).
    """
    grouped = _render_grouped_sections(plan.items_by_section, segment=segment)
    required_macro_actuals = _render_required_macro_actuals(plan.required_macro_items)
    unassigned = _render_unassigned(plan.unassigned, segment=segment)
    user_prompt = STAGE2_USER_TEMPLATE.format(
        segment_context=segment_context,
        grouped_sections=grouped,
        required_macro_actuals=required_macro_actuals,
        unassigned=unassigned,
        target_date=plan.target_date.isoformat(),
        recent_context=recent_context_block,
        lookahead_context=lookahead_context_block,
        carryover_context=carryover_context_block,
        bundle_context=bundle_context_block,
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

        attempt_prompt = f"{full_prompt}{_stage2_retry_feedback(last_cause)}"
        outcome = await call_claude_code(attempt_prompt, timeout_s=policy.timeout_s, runner=runner)
        _logger.info(
            "llm attempt segment=%s stage=synthesis attempt=%d timeout_s=%.1f "
            "elapsed_s=%.3f prompt_bytes=%d stdout_len=%d stderr_len=%d returncode=%d",
            segment,
            attempt + 1,
            policy.timeout_s,
            outcome.elapsed_s,
            len(attempt_prompt.encode("utf-8")),
            len(outcome.stdout),
            len(outcome.stderr),
            outcome.returncode,
            extra={
                "segment": segment,
                "llm_stage": "synthesis",
                "attempt": attempt + 1,
                "timeout_s": policy.timeout_s,
                "elapsed_s": outcome.elapsed_s,
                "prompt_bytes": len(attempt_prompt.encode("utf-8")),
                "stdout_len": len(outcome.stdout),
                "stderr_len": len(outcome.stderr),
                "returncode": outcome.returncode,
            },
        )
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
            _validate_required_macro_mentions(outcome.stdout, plan.required_macro_items)
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


__all__ = [
    "MAX_ATTEMPTS",
    "GenerationPolicy",
    "_classify",
    "_is_official_crypto_policy_item",
    "_select_llm_candidate_items",
    "_synthesize",
    "_validate_required_macro_mentions",
    "serialize_items_for_prompt",
]
