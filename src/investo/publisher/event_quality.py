"""Read-only event coverage from stage receipts and sealed public bytes.

This is a measurement/gate collaborator of u144, never another finalizer. It
does not reconstruct deleted prose or infer news the sources did not collect.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from hashlib import sha256
from typing import TYPE_CHECKING, cast, get_args

from investo._internal.briefing_extract import SUMMARY_PREFIXES
from investo._internal.event_rendering import first_event_sentence
from investo.models.event_narratives import EventGenerationPayload
from investo.models.event_quality import (
    EventCoverage,
    EventCoverageState,
    EventIssueCode,
    EventReason,
    EventStage,
    EventStageReceipt,
    EventTraceEntry,
)
from investo.models.public_notification import PublicNotificationSummary
from investo.publisher.event_blocks import (
    TerminalEvent,
    event_hard_issue_codes,
    event_plain_text,
    reconcile_event_summaries,
    terminal_events,
)

if TYPE_CHECKING:
    from investo.publisher.public_document import FinalizedPublicDocument

_ISSUE_CODES = frozenset(get_args(EventIssueCode))
_UNSUPPORTED_CODES = frozenset(
    {"event.fact_unsupported", "event.entity_unsupported", "event.evidence_invalid"}
)
_TLDR = re.compile(
    r"(?ms)^ {0,3}##[ \t]+한눈에 보기(?:[ \t]+#+)?[ \t]*\n(.*?)(?=^ {0,3}#{1,2}[ \t]+|\Z)"
)
_EVENT_BLOCK = re.compile(
    r"<!-- investo:block event:([0-9a-f]{24}) -->\n.*?<!-- /investo:block event:\1 -->",
    re.DOTALL,
)
_WATCHPOINT_ID = re.compile(r"<!-- investo:event-watchpoint ([0-9a-f]{24}) -->")


def _visible_summary_markdown(markdown: str) -> str:
    """Project summary containers without letting hidden copies own a match."""
    without_comments = re.sub(r"<!--.*?(?:-->|\Z)", "", markdown, flags=re.DOTALL)
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    for line in without_comments.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match is not None:
            marker, suffix = match.groups()
            if fence is None:
                if marker[0] != "`" or "`" not in suffix:
                    fence = marker[0], len(marker)
                    continue
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not suffix.strip():
                fence = None
                continue
        if fence is None:
            visible.append(line)
    return "\n".join(visible)


def _summary_surfaces(markdown: str) -> tuple[str, ...]:
    values = tuple(
        event_plain_text(line.removeprefix(prefix).strip())
        for line in markdown.splitlines()
        for prefix in SUMMARY_PREFIXES
        if line.startswith(prefix)
    )
    bullets: list[str] = []
    for match in _TLDR.finditer(markdown):
        for line in match.group(1).lstrip("\n").splitlines():
            if not line.strip() or not line.startswith("- "):
                break
            bullets.append(event_plain_text(line))
    return (*values, *bullets)


def terminal_event_issue_codes(
    markdown: str,
    *,
    payload: EventGenerationPayload,
    notification_summary: PublicNotificationSummary,
    surviving_event_ids: Sequence[str],
) -> tuple[EventIssueCode, ...]:
    """Check terminal identity and dependent summaries without changing bytes.

    Incomplete blocks are counted as removals, not invented trust failures.
    A declared survivor or summary cannot claim such a block survived. Existing
    canonical minimal documents may retain their generic empty summary.
    """
    codes = set(event_hard_issue_codes(markdown, payload))
    if codes:
        return tuple(cast(EventIssueCode, code) for code in sorted(codes))
    terminal = terminal_events(markdown, payload)
    actual_ids = tuple(event.event_id for event in terminal)
    if tuple(surviving_event_ids) != actual_ids:
        codes.add("event.terminal_mismatch")
    expected_summaries = {event.event_id: event.notification_summary() for event in terminal}
    summary_ids = tuple(event.event_id for event in notification_summary.events)
    if (
        len(summary_ids) > 3
        or summary_ids != tuple(event_id for event_id in actual_ids if event_id in summary_ids)
        or any(
            expected_summaries.get(event.event_id) != event for event in notification_summary.events
        )
    ):
        codes.add("event.summary_reexposure")
    visible_markdown = _visible_summary_markdown(markdown)
    surfaces = _summary_surfaces(visible_markdown)
    tldr_count = len(_TLDR.findall(visible_markdown))
    prefix_counts = tuple(
        sum(line.startswith(prefix) for line in visible_markdown.splitlines())
        for prefix in SUMMARY_PREFIXES
    )
    if tldr_count > 1 or any(count > 1 for count in prefix_counts):
        codes.add("event.summary_reexposure")
    if terminal:
        expected_markdown = reconcile_event_summaries(visible_markdown, payload, terminal)
        if (
            tldr_count != 1
            or any(count != 1 for count in prefix_counts)
            or notification_summary.conclusion != terminal[0].first_sentence
            or surfaces != _summary_surfaces(expected_markdown)
        ):
            codes.add("event.summary_reexposure")
    # An all-removed/minimal document can retain its deterministic generic
    # summary, but no removed event sentence/identity may reappear there.
    removed = set(event.event_id for event in payload.plan.selected) - set(actual_ids)
    public_summaries = (*surfaces, notification_summary.conclusion)
    for narrative in payload.narratives:
        if narrative.event_id not in removed:
            continue
        first_sentence = first_event_sentence(narrative)
        if any(
            first_sentence in value or narrative.event_id in value for value in public_summaries
        ):
            codes.add("event.summary_reexposure")
    if not set(_WATCHPOINT_ID.findall(markdown)) <= set(actual_ids):
        codes.add("event.summary_reexposure")
    return tuple(cast(EventIssueCode, code) for code in sorted(codes))


def _stage_count(receipts: dict[EventStage, EventStageReceipt], stage: EventStage) -> int | None:
    receipt = receipts.get(stage)
    return receipt.count if receipt is not None and receipt.status == "completed" else None


def _unsupported_event_ids(
    markdown: str, payload: EventGenerationPayload
) -> tuple[str, ...] | None:
    """Count distinct implicated events, not repeated codes on the same event."""
    unsupported: set[str] = set()
    narratives = {narrative.event_id: narrative for narrative in payload.narratives}
    bodies: dict[str, list[str]] = {}
    for match in _EVENT_BLOCK.finditer(markdown):
        bodies.setdefault(match.group(1), []).append(match.group(0))
    selected_ids = {event.event_id for event in payload.plan.selected}
    unsupported.update(set(bodies) - selected_ids)
    for candidate in payload.plan.selected:
        narrative = narratives.get(candidate.event_id)
        if narrative is None:
            continue
        one = payload.model_copy(
            update={
                "plan": payload.plan.model_copy(update={"selected": (candidate,)}),
                "narratives": (narrative,),
            }
        )
        body = "\n\n".join(bodies.get(candidate.event_id, ()))
        candidate_codes = event_hard_issue_codes("## ② 전일 핵심 이슈\n\n" + body, one)
        if _UNSUPPORTED_CODES.intersection(candidate_codes):
            unsupported.add(candidate.event_id)
    return tuple(sorted(unsupported)) if len(unsupported) <= 5 else None


def _terminal_receipts(
    receipts: tuple[EventStageReceipt, ...],
    *,
    payload: EventGenerationPayload | None,
    document: FinalizedPublicDocument | None,
    terminal: tuple[TerminalEvent, ...] | None,
    unsupported_ids: tuple[str, ...] | None,
    hard_blocked: bool,
) -> tuple[EventStageReceipt, ...]:
    """Replace terminal-stage claims with observations of this exact document."""
    previous = {receipt.stage: receipt for receipt in receipts}
    selected_ids = tuple(event.event_id for event in payload.plan.selected) if payload else ()
    if terminal is not None and document is not None:
        coverage_by_id = {event.event_id: event.coverage for event in terminal}
        finalized = EventStageReceipt(
            stage="finalized",
            status="completed",
            count=len(terminal),
            trace=tuple(
                EventTraceEntry(
                    hash_id=event_id,
                    stage="finalized",
                    reason=(
                        "finalization_removed"
                        if event_id not in coverage_by_id
                        else "detail_limited"
                        if coverage_by_id[event_id] == "detail_limited"
                        else None
                    ),
                )
                for event_id in selected_ids
            ),
        )
        summary = EventStageReceipt(
            stage="summary",
            status="completed",
            count=len(document.notification_summary.events),
            trace=tuple(
                EventTraceEntry(hash_id=event.event_id, stage="summary")
                for event in document.notification_summary.events
            ),
        )
    else:
        unavailable_reason: EventReason = (
            "hard_trust_blocked" if hard_blocked else "finalization_unavailable"
        )
        failed = hard_blocked or document is not None
        previous_finalized = previous.get("finalized")
        previous_summary = previous.get("summary")
        finalized = EventStageReceipt(
            stage="finalized",
            status=(
                "failed"
                if failed
                or (previous_finalized is not None and previous_finalized.status == "failed")
                else "not_run"
            ),
            trace=tuple(
                EventTraceEntry(hash_id=event_id, stage="finalized", reason=unavailable_reason)
                for event_id in selected_ids
            ),
        )
        summary = EventStageReceipt(
            stage="summary",
            status=(
                "failed"
                if failed or (previous_summary is not None and previous_summary.status == "failed")
                else "not_run"
            ),
        )
    if unsupported_ids is not None:
        checked_ids = tuple(dict.fromkeys((*selected_ids, *unsupported_ids)))
        structure = EventStageReceipt(
            stage="structure_checked",
            status="completed",
            count=len(unsupported_ids),
            trace=tuple(
                EventTraceEntry(
                    hash_id=event_id,
                    stage="structure_checked",
                    reason="hard_trust_blocked" if event_id in unsupported_ids else None,
                )
                for event_id in checked_ids
            ),
        )
    else:
        previous_structure = previous.get("structure_checked")
        if (
            document is None
            and previous_structure is not None
            and (previous_structure.count is None or previous_structure.count <= 5)
        ):
            structure = previous_structure
        else:
            structure = EventStageReceipt(
                stage="structure_checked", status="failed" if document is not None else "not_run"
            )
    return (
        *(
            receipt
            for receipt in receipts
            if receipt.stage not in {"finalized", "summary", "structure_checked"}
        ),
        finalized,
        summary,
        structure,
    )


def evaluate_event_quality(
    document: FinalizedPublicDocument | None,
    *,
    payload: EventGenerationPayload | None,
    receipts: Sequence[EventStageReceipt],
    hard_issue_codes: Sequence[str] = (),
) -> EventCoverage:
    """Derive E8 metrics; unknown stages stay null and completed zero stays zero.

    ``collected`` counts input event candidates before downstream caps. Later
    candidate-stage zeros must never overwrite failed collection. No notifier
    status is consumed; confirmed publication aggregation belongs to E11.
    """
    receipt_values = tuple(receipts)
    by_stage = {receipt.stage: receipt for receipt in receipt_values}
    if len(by_stage) != len(receipt_values):
        raise ValueError("event.stage_receipt_invalid")
    reasons: set[EventReason] = {
        entry.reason
        for receipt in receipt_values
        for entry in receipt.trace
        if entry.reason is not None
    }
    codes = {cast(EventIssueCode, code) for code in hard_issue_codes if code in _ISSUE_CODES}
    effective_hard = bool(hard_issue_codes) or "hard_trust_blocked" in reasons
    selected = _stage_count(by_stage, "selected")
    prompted = _stage_count(by_stage, "prompted")
    classified_count = _stage_count(by_stage, "classified")
    generated = _stage_count(by_stage, "generated")
    for stage, count in (("selected", selected), ("prompted", prompted)):
        if count is not None and count > 5:
            codes.add("event.stage_receipt_invalid")
            if stage == "selected":
                selected = None
            else:
                prompted = None
    if selected is not None and (
        (payload is not None and selected != len(payload.plan.selected))
        or (prompted is not None and prompted != selected)
        or (classified_count is not None and classified_count < selected)
    ):
        codes.add("event.stage_receipt_invalid")
        selected = prompted = None
    if generated is not None and payload is not None and generated != len(payload.narratives):
        codes.add("event.stage_receipt_invalid")
    classified = by_stage.get("classified")
    if classified is not None and classified.status != "completed" and selected is not None:
        codes.add("event.stage_receipt_invalid")
        selected = prompted = None

    terminal_count = qualified = limited = summary_count = None
    terminal: tuple[TerminalEvent, ...] | None = None
    unsupported_ids: tuple[str, ...] | None = None
    unsupported = _stage_count(by_stage, "structure_checked")
    if unsupported is not None and unsupported > 5:
        codes.add("event.stage_receipt_invalid")
        unsupported = None
    effective_hard = effective_hard or bool(unsupported)
    source_limited = (
        bool(payload is not None and payload.collection_limited)
        or any(
            receipt.status == "failed" and receipt.stage in {"collected", "routed", "candidate"}
            for receipt in receipt_values
        )
        or bool(reasons & {"source_unavailable", "source_limited"})
    )
    if source_limited:
        reasons.update(("source_limited", "source_unavailable"))

    if document is not None and payload is not None:
        markdown = document.briefing.rendered_markdown
        codes.update(
            terminal_event_issue_codes(
                markdown,
                payload=payload,
                notification_summary=document.notification_summary,
                surviving_event_ids=document.surviving_event_ids,
            )
        )
        if document.markdown_sha256 != sha256(markdown.encode("utf-8")).hexdigest():
            codes.add("event.seal_mismatch")
        if (
            tuple(receipt.event_id for receipt in document.event_identity_receipts)
            != document.surviving_event_ids
            or document.notification_summary.segment != document.segment
            or document.notification_summary.target_date != document.target_date
        ):
            codes.add("event.terminal_mismatch")
        unsupported_ids = _unsupported_event_ids(markdown, payload)
        unsupported = len(unsupported_ids) if unsupported_ids is not None else None
        if not codes and not effective_hard:
            terminal = terminal_events(markdown, payload)
            terminal_count = len(terminal)
            qualified = sum(event.coverage == "supported" for event in terminal)
            limited = terminal_count - qualified
            summary_count = len(document.notification_summary.events)

    if selected is None:
        reasons.add("classification_unavailable")
    if terminal_count is None:
        reasons.add("finalization_unavailable")
    if selected is not None and terminal_count is not None and terminal_count < selected:
        reasons.add("finalization_removed")
    if limited:
        reasons.add("detail_limited")
    if qualified == 0:
        reasons.add("no_qualifying_event")
    if codes or effective_hard:
        reasons.add("hard_trust_blocked")
    priority: tuple[EventCoverageState, ...] = (
        "hard_trust_blocked",
        "classification_unavailable",
        "finalization_unavailable",
        "source_limited",
        "detail_limited",
        "no_qualifying_event",
        "qualified",
    )
    state = next((value for value in priority if value in reasons), "qualified")
    return EventCoverage(
        collected_candidate_count=_stage_count(by_stage, "collected"),
        selected_count=selected,
        prompted_count=prompted,
        terminal_event_count=terminal_count,
        qualified_event_count=qualified,
        details_limited_count=limited,
        summary_event_count=summary_count,
        unsupported_count=unsupported,
        state=state,
        reasons=tuple(sorted(reasons)),
        issue_codes=tuple(sorted(codes)),
        receipts=_terminal_receipts(
            receipt_values,
            payload=payload,
            document=document,
            terminal=terminal,
            unsupported_ids=unsupported_ids,
            hard_blocked=bool(codes or effective_hard),
        ),
    )


__all__ = ["evaluate_event_quality", "terminal_event_issue_codes"]
