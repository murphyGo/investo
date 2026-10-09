"""Standalone story contracts bind exact typed records without a reducer import."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from investo.briefing.event_identity import source_receipt
from investo.models.event_story import (
    NextCheck,
    ResolutionTarget,
    StoryPublicationDelta,
    StoryRecord,
    StoryStateProposal,
    StoryTransitionTime,
    story_record_hash,
)
from tests._helpers.event_context_v3 import NOW, document, ref


def record():
    doc = document()
    source = source_receipt(ref(doc, "Acme"), (doc,))
    return StoryRecord(
        story_id="a" * 64,
        segment="us-equity",
        event_ids=("b" * 24,),
        latest_state="announced",
        updated_at=NOW,
        last_evidence_at=NOW,
        source_refs=(source,),
        kind="earnings_result",
    )


def test_typed_record_roundtrip_and_hash_binding() -> None:
    original = record()
    assert StoryRecord.model_validate_json(original.model_dump_json()) == original
    proposal = StoryStateProposal(
        story_id=original.story_id,
        segment=original.segment,
        next_record=original,
        next_record_hash=story_record_hash(original),
        event_ids=original.event_ids,
        fact_ids=(),
        evidence_refs=(original.source_refs[0].context_ref,),
        observed_clock=NOW,
    )
    delta = StoryPublicationDelta(
        story_id=original.story_id,
        segment=original.segment,
        next_state=original.latest_state,
        event_ids=original.event_ids,
        fact_ids=(),
        next_record=proposal.next_record,
        next_record_hash=proposal.next_record_hash,
        source_receipts=original.source_refs,
        observed_clock=NOW,
        disposition="active",
    )
    assert (
        StoryPublicationDelta.model_validate_json(delta.model_dump_json()).next_record == original
    )
    with pytest.raises(ValidationError, match="record_hash_mismatch"):
        StoryStateProposal.model_validate({**proposal.model_dump(), "next_record_hash": "0" * 64})


def test_date_precision_survives_and_unknown_has_no_time() -> None:
    source = record().source_refs[0]
    point = StoryTransitionTime(value=NOW.date(), precision="date", evidence_refs=(source,))
    restored = StoryTransitionTime.model_validate_json(point.model_dump_json())
    assert restored.value == NOW.date() and type(restored.value) is type(NOW.date())
    with pytest.raises(ValidationError):
        StoryTransitionTime(value=NOW, precision="unknown")


def test_terminal_state_requires_evidence_and_a_fixed_closure_clock() -> None:
    current = record()
    with pytest.raises(ValidationError, match="closure_unbound"):
        StoryRecord.model_validate(
            {
                **current.model_dump(),
                "latest_state": "resolved",
                "disposition": "closed",
                "closed_at": NOW,
            }
        )
    closed = StoryRecord.model_validate(
        {
            **current.model_dump(),
            "latest_state": "resolved",
            "disposition": "closed",
            "closed_at": NOW,
            "resolution_evidence": current.source_refs,
        }
    )
    assert closed.closed_at == NOW
    with pytest.raises(ValidationError, match="clock_invalid"):
        StoryRecord.model_validate({**closed.model_dump(), "closed_at": NOW + timedelta(seconds=1)})


def test_scheduled_and_linked_release_checks_cannot_invent_missing_evidence() -> None:
    source = record().source_refs[0]
    with pytest.raises(ValidationError, match="next_check_unbound"):
        NextCheck(kind="scheduled_fact", text="발표 확인", fact_id="c" * 64, source_refs=(source,))
    with pytest.raises(ValidationError, match="resolution_unbound"):
        ResolutionTarget(
            kind="linked_release_result",
            subject_ids=("d" * 64,),
            expected_status="actual",
            source_refs=(source,),
        )
