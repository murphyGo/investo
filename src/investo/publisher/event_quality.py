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
from investo.models.event_context import ContextClassificationResult, EventSupportVector
from investo.models.event_document import EditorialPlan
from investo.models.event_narratives import EventGenerationPayload
from investo.models.event_quality import (
    EventCoverage,
    EventCoverageState,
    EventIssueCode,
    EventQualityV3Measurement,
    EventReason,
    EventSemanticAnnotation,
    EventSemanticReview,
    EventStage,
    EventStageReceipt,
    EventTraceEntry,
    SemanticRate,
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
        if not isinstance(document.notification_summary, PublicNotificationSummary):
            raise ValueError("v2 coverage requires a legacy terminal notification")
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


def support_vector_reader_limits(vector: EventSupportVector) -> tuple[str, ...]:
    """Render separate truthful limits; never expose private generation buffers."""
    limits: list[str] = []
    if vector.facts == "missing":
        limits.append("핵심 사실 근거 부족")
    elif vector.facts == "limited":
        limits.append("일부 사실의 세부 정보 미확인")
    if vector.time in {"publication_only", "unknown"}:
        limits.append("사건 발생·발표 시각 미확인")
    if vector.novelty == "unknown":
        limits.append("이전 발행과 비교할 이력 미확인")
    if vector.locator == "missing":
        limits.append("공개 원문 위치 미확인")
    if vector.meaning == "unavailable":
        limits.append("시장 의미 확인 자료 부족")
    if vector.reaction == "unavailable":
        limits.append("비교 가능한 시장 반응 미확인")
    return tuple(limits)


def measure_event_quality_v3(
    document: FinalizedPublicDocument | None,
    *,
    annotation: EventSemanticAnnotation,
    candidate_event_ids: tuple[str, ...] | None,
    selected_event_ids: tuple[str, ...] | None,
    issue_codes: tuple[str, ...] = (),
    remote_confirmed_sha: str | None = None,
    human_review: EventSemanticReview | None = None,
) -> EventQualityV3Measurement:
    """Separate observed terminal counts from external and human baselines."""
    view = document.edition_view if document is not None else None
    if document is not None and (
        view is None
        or document.segment != annotation.segment
        or document.target_date != annotation.target_date
    ):
        raise ValueError("semantic.document_identity_invalid")
    terminal = {event.event_id for event in view.edition.events} if view else None
    facts = (
        {fact.fact_id for event in view.edition.events for fact in event.facts}
        | {fact.fact_id for panel in view.edition.reference_panels for fact in panel.facts}
        if view
        else None
    )

    def rate(denominator: set[str] | None, observed: set[str] | None) -> SemanticRate:
        if denominator is None or observed is None:
            return SemanticRate()
        return SemanticRate(numerator=len(denominator & observed), denominator=len(denominator))

    candidates = set(candidate_event_ids) if candidate_event_ids is not None else None
    selected = set(selected_event_ids) if selected_event_ids is not None else None
    if candidates is not None and selected is not None and not selected <= candidates:
        raise ValueError("semantic.selection_identity_invalid")
    if terminal is not None and selected is not None and not terminal <= selected:
        raise ValueError("semantic.selection_identity_invalid")
    must = set(annotation.must_include)
    selection = rate(must if candidates is not None else None, selected)
    preservation = rate(set(annotation.required_fact_ids), facts)
    unsupported = (
        len(terminal - set(annotation.expected_event_ids)) if terminal is not None else None
    )
    causal = sum(
        code in {"event.meaning_unbound", "event.reaction_unbound"} for code in issue_codes
    )
    human = SemanticRate()
    review_refs: tuple[str, ...] = ()
    if human_review is not None:
        if (
            human_review.case_id != annotation.case_id
            or human_review.annotation_sha256 != annotation.annotation_sha256
            or (view is not None and human_review.markdown_sha256 != view.edition.markdown_sha256)
            or (
                human_review.scores is not None
                and {s.event_id for s in human_review.scores} != set(annotation.expected_event_ids)
            )
        ):
            raise ValueError("semantic.review_identity_invalid")
        if human_review.scores is not None:
            if view is not None:
                supports = {e.event_id: e.support for e in view.edition.events}
                for score in human_review.scores:
                    support = supports.get(score.event_id)
                    if support is None or (
                        (score.what == 1 and support.facts != "complete")
                        or (
                            score.when == 1
                            and support.time in {"publication_only", "unknown"}
                            and "사건 시점: 확인 불가" not in view.rendered_markdown
                        )
                        or (score.why == 1 and support.meaning == "unavailable")
                        or (
                            score.react == 1
                            and support.reaction == "unavailable"
                            and "시장 반응은 확인하지 못했습니다." not in view.rendered_markdown
                        )
                        or (score.source == 1 and support.locator != "complete")
                    ):
                        raise ValueError("semantic.support_score_invalid")
            human = SemanticRate(
                numerator=sum(s.total == 5 for s in human_review.scores),
                denominator=len(human_review.scores),
            )
        review_refs = (human_review.annotation_sha256,)
    passed = (
        view is not None
        and (
            not annotation.expected_support
            or annotation.expected_support == tuple(e.support for e in view.edition.events)
        )
        and not issue_codes
        and unsupported == 0
        and selection.numerator is not None
        and preservation.numerator is not None
        and selected is not None
        and selection.numerator == selection.denominator
        and preservation.numerator == preservation.denominator
    )
    return EventQualityV3Measurement(
        segment=annotation.segment,
        basis="remote_confirmed" if remote_confirmed_sha else "terminal",
        publication_sha=remote_confirmed_sha,
        must_include_selection=selection,
        selected_survival=rate(selected, terminal),
        required_fact_preservation=preservation,
        external_event_capture=rate(
            set(annotation.external_baseline_event_ids)
            if annotation.external_baseline_event_ids is not None
            else None,
            terminal,
        ),
        human_five_of_five=human,
        unsupported_event_count=unsupported,
        unsupported_causality_count=causal if terminal is not None else None,
        support_vectors=tuple(event.support for event in view.edition.events) if view else None,
        automated_result="pass" if passed else "fail" if issue_codes or view else "unobserved",
        review_references=review_refs,
    )


def evaluate_native_event_coverage(
    document: FinalizedPublicDocument | None,
    *,
    classification: ContextClassificationResult,
    plan: EditorialPlan,
    hard_issue_codes: Sequence[str] = (),
) -> EventCoverage:
    """Current v3 counts read typed terminal facts, not legacy callout text."""
    from investo.models.event_document import PublicEditionView

    selected = sum(p.placement == "article" for p in plan.events)
    if hard_issue_codes:
        return EventCoverage(
            collected_candidate_count=len(classification.events),
            selected_count=selected,
            prompted_count=selected,
            state="hard_trust_blocked",
            reasons=("hard_trust_blocked",),
            issue_codes=("event.fact_unsupported",),
        )
    view = document.payload if document else None
    if not isinstance(view, PublicEditionView):
        return EventCoverage(
            collected_candidate_count=len(classification.events),
            selected_count=selected,
            prompted_count=selected,
            state="finalization_unavailable",
            reasons=("finalization_unavailable",),
        )
    edition = view.edition
    qualified = sum(
        e.support.facts == "complete"
        and e.support.time in {"exact", "date"}
        and e.support.locator == "complete"
        and e.support.meaning != "unavailable"
        for e in edition.events
    )
    limited = len(edition.events) - qualified
    state = (
        "source_limited"
        if edition.availability.status == "source_limited"
        else "detail_limited"
        if limited
        else "no_qualifying_event"
        if not edition.events
        else "qualified"
    )
    return EventCoverage(
        collected_candidate_count=len(classification.events),
        selected_count=selected,
        prompted_count=selected,
        terminal_event_count=len(edition.events),
        qualified_event_count=qualified,
        details_limited_count=limited,
        summary_event_count=min(len(edition.events), 3),
        unsupported_count=0,
        state=state,
        reasons=(state,),
    )
