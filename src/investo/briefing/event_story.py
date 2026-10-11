"""Generation owner for source-backed story proposals and bounded follow-ups."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from investo._internal.event_story import (
    advance_story as advance_story,
)
from investo._internal.event_story import (
    link_story as link_story,
)
from investo._internal.event_story import (
    observe_story as observe_story,
)
from investo._internal.event_story import (
    propose_story,
)
from investo.models.event_document import EventEditionDraft, FollowUpEntry
from investo.models.event_story import StoryRecord, StoryStateProposal


def attach_story_follow_ups(
    draft: EventEditionDraft, baseline: Sequence[StoryRecord], *, observed_at: datetime
) -> EventEditionDraft:
    proposals: list[StoryStateProposal] = []
    follow_ups: list[FollowUpEntry] = []
    for plan, binding in zip(draft.editorial_plan.events, draft.bindings, strict=True):
        if binding.story_hint.story_key_hash in {f.story_id for f in follow_ups}:
            continue
        result = propose_story(
            binding,
            plan.source_event,
            draft.documents,
            baseline,
            segment=draft.segment,
            observed_at=observed_at,
        )
        proposal = result.proposed_delta
        if proposal is None:
            record = result.record
            if (
                result.disposition != "unchanged"
                or record is None
                or binding.identity.event_id not in record.event_ids
                or record.subject_ids != binding.identity.actor_ids
                or record.object_ids != binding.identity.object_ids
            ):
                continue
        else:
            record = proposal.next_record
            proposals.append(proposal)
        follow_ups.append(
            FollowUpEntry(
                kind="scheduled"
                if record.next_check is not None and record.next_check.kind == "scheduled_fact"
                else "event",
                event_id=binding.identity.event_id,
                story_id=record.story_id,
                reader_state=record.latest_state,
                basis="current_delta" if proposal is not None else "committed_history",
                last_evidence_at=record.last_evidence_at,
                verified_delta_text=record.verified_delta.reader_text
                if record.verified_delta
                else None,
                question=record.open_question.text if record.open_question else None,
                next_check=record.next_check,
                source_refs=proposal.evidence_refs if proposal is not None else plan.assigned_refs,
            )
        )
        if len(follow_ups) == 3:
            break
    return draft.model_copy(
        update={"story_proposals": tuple(proposals), "follow_ups": tuple(follow_ups)}
    )
