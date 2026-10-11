"""Deterministic source-backed story linking and transitions, without I/O."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from investo._internal.event_context import (
    event_context_refs,
    resolve_context_ref,
    validate_context_event,
)
from investo._internal.event_identity import source_receipt
from investo._internal.event_v3_contract import fact_source_map
from investo.models.event_context import ContextEventDraft, EventContextDocument
from investo.models.event_evidence import event_digest
from investo.models.event_identity import CanonicalEventBinding
from investo.models.event_story import (
    NextCheck,
    ObservationQuestion,
    ResolutionTarget,
    StoryLinkResult,
    StoryObservation,
    StoryRecord,
    StoryState,
    StoryStateProposal,
    StoryTransitionProposal,
    StoryTransitionResult,
    StoryTransitionSignal,
    StoryTransitionTime,
    StoryTransitionTimeDraft,
    VerifiedStoryDelta,
    story_record_hash,
)
from investo.models.segments import MarketSegment

_SIGNAL_STATES: dict[StoryTransitionSignal, StoryState] = {
    "announcement": "announced",
    "pending_confirmation": "pending",
    "outcome_confirmed": "confirmed",
    "implementation_verified": "implemented",
    "resolution_verified": "resolved",
    "cancellation_verified": "cancelled",
    "evidence_conflict": "unknown",
    "no_new_evidence": "unknown",
}
_ORDER = {
    "unknown": 0,
    "announced": 1,
    "pending": 2,
    "confirmed": 3,
    "implemented": 4,
    "resolved": 5,
    "cancelled": 5,
}
_CANCELLATION = frozenset({"cancelled", "canceled", "withdrawn", "취소", "철회", "결렬"})
_RESOLUTION = frozenset({"resolved", "completed", "완료", "해소", "종료"})
_PENDING = frozenset({"pending", "awaiting confirmation", "미결", "확인 대기"})


def link_story(
    observation: StoryObservation, baseline: Sequence[StoryRecord], *, segment: MarketSegment
) -> StoryLinkResult:
    matches = [
        r
        for r in baseline
        if r.segment == segment and r.story_id == observation.story_hint.story_key_hash
    ]
    if len(matches) > 1:
        return StoryLinkResult(
            story_id=observation.story_hint.story_key_hash, disposition="conflict"
        )
    prior = matches[0] if matches else None
    if prior is not None and (
        prior.kind != observation.event_kind
        or prior.subject_ids != tuple(sorted(observation.story_hint.entity_ids))
        or (
            observation.event_id not in prior.event_ids
            and observation.story_hint.confidence != "explicit"
        )
    ):
        return StoryLinkResult(
            story_id=observation.story_hint.story_key_hash,
            prior_record=prior,
            disposition="conflict",
        )
    return StoryLinkResult(
        story_id=observation.story_hint.story_key_hash,
        prior_record=prior,
        disposition="matched" if prior else "new",
    )


def _resolution_matches(prior: StoryRecord, binding: CanonicalEventBinding) -> bool:
    question = prior.open_question
    if question is None:
        return False
    target = question.resolution_target
    if target.kind == "same_occurrence":
        if target.occurrence_id != binding.identity.event_id:
            return False
    elif (
        binding.story_hint.confidence != "explicit"
        or target.thread_key_hash != binding.story_hint.story_key_hash
    ):
        return False
    actual = [
        f
        for f in binding.facts
        if f.canonical.status == target.expected_status
        and f.canonical.subject_id in target.subject_ids
        and (target.period is None or f.canonical.period == target.period)
    ]
    return bool(actual) and set(target.required_metric_keys) <= {
        f.canonical.metric_key_hash for f in actual
    }


def observe_story(
    binding: CanonicalEventBinding,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    *,
    observed_at: datetime,
    prior: StoryRecord | None = None,
) -> StoryObservation:
    validate_context_event(source, documents, observed_at=observed_at)
    actual = [f for f in binding.facts if f.canonical.status == "actual"]
    values = {
        f.canonical.value.casefold() for f in actual if f.canonical.predicate == "status_change"
    }
    stage = binding.identity.occurrence_stage
    signal: StoryTransitionSignal = "no_new_evidence"
    if binding.delta.unresolved_conflict_ids or binding.match_outcome == "conflict":
        signal = "evidence_conflict"
    elif not binding.delta.added_fact_ids and not binding.delta.correction_pairs:
        signal = "no_new_evidence"
    elif values & _CANCELLATION:
        signal = "cancellation_verified"
    elif (prior is not None and _resolution_matches(prior, binding)) or (values & _RESOLUTION):
        signal = "resolution_verified"
    elif values & _PENDING:
        signal = "pending_confirmation"
    elif (
        stage == "implementation"
        and actual
        and binding.identity.event_kind
        in {
            "monetary_policy",
            "regulation",
            "geopolitical",
            "corporate_action",
            "product_service",
            "market_structure",
        }
    ):
        signal = "implementation_verified"
    elif (stage in {"decision", "result"} and actual) or (
        source.event_kind == "public_statement"
        and any(f.canonical.status == "quoted_opinion" for f in binding.facts)
        and any(
            resolve_context_ref(ref, documents).casefold() in {"said", "stated", "발언", "말했다"}
            for ref in source.action_refs
        )
    ):
        signal = "outcome_confirmed"
    elif source.timing in {"announced", "scheduled"} and any(
        resolve_context_ref(ref, documents).casefold()
        in {"announced", "announces", "발표", "발표했다", "공표"}
        for ref in source.action_refs
    ):
        signal = "announcement"
    # A future time alone is never a pending/confirmed signal.
    refs = tuple(
        dict.fromkeys(
            (
                *event_context_refs(source, optional=False),
                *source.follow_up_refs,
                *binding.identity.stage_refs,
                *binding.story_hint.explicit_thread_refs,
            )
        )
    )
    owner = documents[source.item_ids[0] - 1]
    point = (
        owner.time.occurred_at
        if owner.time.occurred_at.precision != "unknown"
        else owner.time.announced_at
    )
    transition_time = StoryTransitionTimeDraft(
        value=point.value, precision=point.precision, evidence_refs=point.source_refs
    )
    refs = tuple(dict.fromkeys((*refs, *point.source_refs)))
    question = None
    next_check = None
    questions = [resolve_context_ref(r, documents) for r in source.follow_up_refs]
    question_text = next(
        (text for text in questions if text.endswith("?") and 8 <= len(text) <= 180), None
    )
    if question_text is not None:
        periods = {f.canonical.period for f in binding.facts if f.canonical.period is not None}
        metrics = tuple(
            sorted(
                {
                    f.canonical.metric_key_hash
                    for f in binding.facts
                    if f.canonical.metric_key_hash is not None
                }
            )
        )
        linked = binding.story_hint.confidence == "explicit" and len(periods) == 1 and bool(metrics)
        receipts = tuple(source_receipt(r, documents) for r in source.follow_up_refs)
        target = ResolutionTarget(
            kind="linked_release_result" if linked else "same_occurrence",
            occurrence_id=None if linked else binding.identity.event_id,
            thread_key_hash=binding.story_hint.story_key_hash if linked else None,
            subject_ids=binding.identity.actor_ids,
            period=next(iter(periods)) if len(periods) == 1 else None,
            required_metric_keys=metrics,
            expected_status="actual",
            source_refs=receipts,
        )
        question = ObservationQuestion(
            question_id=event_digest(
                "story-question-v3", binding.story_hint.story_key_hash, question_text
            ),
            kind="release_result"
            if source.event_kind in {"earnings_result", "macro_release"}
            else "source_confirmation",
            text=question_text,
            subject_ids=binding.identity.actor_ids,
            resolution_target=target,
            source_refs=receipts,
        )
        next_check = NextCheck(
            kind="observation_question",
            text=question.text,
            question_id=question.question_id,
            source_refs=receipts,
        )
    for fact in binding.facts:
        if fact.canonical.status != "scheduled":
            continue
        literal = fact.original_value.strip()
        try:
            scheduled = (
                datetime.fromisoformat(literal.replace("Z", "+00:00"))
                if "T" in literal
                else date.fromisoformat(literal)
            )
            receipts = tuple(source_receipt(r, documents) for r in fact.source_refs)
            time_refs = fact_source_map(binding, source, documents)[fact.fact_id].value_refs
            point_refs = tuple(source_receipt(r, documents) for r in time_refs)
            scheduled_time = StoryTransitionTime(
                value=scheduled,
                precision="exact" if isinstance(scheduled, datetime) else "date",
                evidence_refs=point_refs,
            )
        except ValueError:
            continue
        next_check = NextCheck(
            kind="scheduled_fact",
            text=literal,
            fact_id=fact.fact_id,
            scheduled_time=scheduled_time,
            source_refs=receipts,
        )
        break
    return StoryObservation(
        story_hint=binding.story_hint,
        event_id=binding.identity.event_id,
        event_kind=binding.identity.event_kind,
        fact_delta=binding.delta,
        transition_proposal=StoryTransitionProposal(
            signal=signal,
            proposed_state=_SIGNAL_STATES[signal],
            evidence_refs=refs,
            occurrence_ids=(binding.identity.event_id,),
            resolution_fact_ids=tuple(f.fact_id for f in actual)
            if signal in {"resolution_verified", "cancellation_verified"}
            else (),
            transition_time=transition_time,
        ),
        question_proposal=question,
        next_check_proposal=next_check,
        context_refs=refs,
        observation_clock=observed_at,
    )


def advance_story(
    prior: StoryRecord | None,
    observation: StoryObservation,
    binding: CanonicalEventBinding,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    *,
    segment: MarketSegment,
) -> StoryTransitionResult:
    signal = observation.transition_proposal.signal

    def result(disposition: str, reason: str) -> StoryTransitionResult:
        return StoryTransitionResult.model_validate(
            {"record": prior, "disposition": disposition, "reason_code": reason}
        )

    if prior is not None and prior.disposition == "closed":
        return result("unchanged", "story.closed_immutable")
    if signal == "no_new_evidence":
        return result("unchanged", "story.no_new_evidence")
    if signal == "evidence_conflict" or binding.identity.object_ids != (
        prior.object_ids if prior is not None else binding.identity.object_ids
    ):
        return result("conflict", "story.state_conflict")
    state = _SIGNAL_STATES[signal]
    if prior is not None and _ORDER[state] < _ORDER[prior.latest_state]:
        return result("conflict", "story.state_conflict")
    explicit_completion = any(
        f.canonical.status == "actual"
        and f.canonical.predicate == "status_change"
        and f.canonical.value.casefold() in _RESOLUTION
        for f in binding.facts
    )
    if (
        state == "resolved"
        and not explicit_completion
        and (prior is None or not _resolution_matches(prior, binding))
    ):
        return result("limited", "story.resolution_unbound")
    if state == "unknown":
        return result("limited", "story.transition_unbound")
    facts = [f for f in binding.facts if f.fact_id in observation.fact_delta.added_fact_ids]
    if not facts:
        return result("unchanged", "story.no_new_evidence")
    fact = facts[0]
    fs = fact_source_map(binding, source, documents)[fact.fact_id]
    label = (
        " ".join(resolve_context_ref(r, documents) for r in fs.metric_refs)
        or " ".join(resolve_context_ref(r, documents) for r in fs.predicate_refs)
        or ("상태" if fact.canonical.predicate == "status_change" else "변화")
    )
    entity = next(
        e.entity.display_label
        for e in binding.entities
        if e.entity.entity_id == fact.canonical.subject_id
    )
    text = " · ".join(
        v
        for v in (
            entity,
            label,
            fact.original_value,
            fact.canonical.unit,
            fact.canonical.period,
            {
                "actual": "실제",
                "forecast": "예상",
                "scheduled": "예정",
                "quoted_opinion": "인용 발언",
            }[fact.canonical.status],
        )
        if v
    )
    if len(text) > 240:
        return result("limited", "story.record_budget_exhausted")
    receipts = tuple(source_receipt(r, documents) for r in observation.context_refs)
    fact_receipts = tuple(source_receipt(r, documents) for r in fact.source_refs)
    point = observation.transition_proposal.transition_time
    public_time = StoryTransitionTime(
        value=point.value,
        precision=point.precision,
        evidence_refs=tuple(source_receipt(r, documents) for r in point.evidence_refs),
    )
    event_ids = tuple(sorted({*(prior.event_ids if prior else ()), observation.event_id}))
    combined_refs = tuple(dict.fromkeys((*(prior.source_refs if prior else ()), *receipts)))
    if len(event_ids) > 128 or len(combined_refs) > 64:
        return result("limited", "story.record_budget_exhausted")
    delta = VerifiedStoryDelta(
        fact_ids=(fact.fact_id,),
        delta_hash=event_digest(
            "verified-story-delta-v3",
            fact.fact_id,
            text,
            tuple(r.model_dump(mode="json") for r in fact_receipts),
        ),
        reader_text=text,
        source_refs=fact_receipts,
    )
    record = StoryRecord(
        story_id=observation.story_hint.story_key_hash,
        segment=segment,
        event_ids=event_ids,
        latest_state=state,
        verified_delta=delta,
        open_question=None
        if state in {"resolved", "cancelled"}
        else observation.question_proposal or (prior.open_question if prior else None),
        next_check=None
        if state in {"resolved", "cancelled"}
        else observation.next_check_proposal or (prior.next_check if prior else None),
        resolution_evidence=receipts if state in {"resolved", "cancelled"} else (),
        updated_at=observation.observation_clock,
        last_evidence_at=observation.observation_clock,
        closed_at=observation.observation_clock if state in {"resolved", "cancelled"} else None,
        kind=binding.identity.event_kind,
        subject_ids=binding.identity.actor_ids,
        object_ids=binding.identity.object_ids,
        disposition="closed" if state in {"resolved", "cancelled"} else "active",
        source_refs=combined_refs,
        state_time=public_time,
    )
    proposal = StoryStateProposal(
        story_id=record.story_id,
        segment=segment,
        prior_record_hash=story_record_hash(prior) if prior else None,
        next_record=record,
        next_record_hash=story_record_hash(record),
        event_ids=(observation.event_id,),
        fact_ids=tuple(f.fact_id for f in binding.facts),
        evidence_refs=observation.context_refs,
        observed_clock=observation.observation_clock,
    )
    return StoryTransitionResult(
        record=record, disposition="applied", reason_code="story.applied", proposed_delta=proposal
    )


def propose_story(
    binding: CanonicalEventBinding,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    baseline: Sequence[StoryRecord],
    *,
    segment: MarketSegment,
    observed_at: datetime,
) -> StoryTransitionResult:
    preliminary = observe_story(binding, source, documents, observed_at=observed_at)
    link = link_story(preliminary, baseline, segment=segment)
    if link.disposition == "conflict":
        return StoryTransitionResult(
            record=link.prior_record, disposition="conflict", reason_code="story.state_conflict"
        )
    observation = observe_story(
        binding, source, documents, observed_at=observed_at, prior=link.prior_record
    )
    return advance_story(
        link.prior_record, observation, binding, source, documents, segment=segment
    )
