"""State changes bind affirmative actual source claims and never refresh repeats."""

from datetime import timedelta

import pytest

from investo._internal.event_story import propose_story
from investo.briefing.event_context import prepare_context_documents
from investo.briefing.event_identity import canonical_event_binding
from investo.briefing.event_story import attach_story_follow_ups
from investo.models.event_context import ContextEventDraft, ContextFactDraft
from investo.models.event_story import StoryLedger
from investo.models.items import NormalizedItem
from investo.orchestrator.event_story import story_ledger_bytes
from investo.publisher.public_document import finalize_public_bundle
from tests._helpers.event_context_v3 import NOW, ref
from tests._helpers.event_document_v3 import native_case, native_context


@pytest.mark.parametrize(
    "sentence,value",
    [
        ("Acme Widget actual status is not cancelled.", "cancelled"),
        ("Acme Widget actual status was never completed.", "completed"),
        ("Acme Widget actual status will be cancelled if approval fails.", "cancelled"),
        ("Acme Widget actual status may be completed after approval.", "completed"),
        ("Acme Widget 실제 상태는 취소되지 않았다.", "취소"),
        ("Acme Widget 실제 상태는 완료 예정이다.", "완료"),
    ],
    ids=["not", "never", "conditional", "may", "korean-negation", "scheduled"],
)
def test_negative_or_conditional_status_never_closes_a_story(sentence, value):
    item = NormalizedItem(
        source_name="official",
        category="news",
        title="Acme announced Widget",
        summary=sentence,
        url="https://example.com/one",
        published_at=NOW,
    )
    docs = prepare_context_documents((item,), received_at=NOW)
    doc = docs[0]
    fact = ContextFactDraft(
        predicate="status_change",
        status="actual",
        value_kind="text",
        subject_refs=(ref(doc, "Acme"),),
        object_refs=(ref(doc, "Widget"),),
        value_refs=(ref(doc, value),),
        status_refs=(ref(doc, "actual" if "actual" in sentence else "실제"),),
    )
    source = ContextEventDraft(
        item_ids=(1,),
        event_kind="product_service",
        actor_refs=(ref(doc, "Acme"),),
        action_refs=(ref(doc, "announced"),),
        object_refs=(ref(doc, "Widget"),),
        facts=(fact,),
        timing="announced",
        relation="direct",
        impact="company",
    )
    with pytest.raises(ValueError):
        canonical_event_binding(source, docs, (), observed_at=NOW, baseline_available=True)


def test_committed_repeat_ttl_and_prior_hash_do_not_create_new_evidence():
    item, draft = native_case()
    draft = attach_story_follow_ups(draft, (), observed_at=NOW)
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    prior = sealed.story_publication_deltas[0].next_record
    source = draft.editorial_plan.events[0].source_event
    binding = canonical_event_binding(
        source,
        draft.documents,
        sealed.canonical_event_receipts,
        observed_at=NOW + timedelta(days=1),
        baseline_available=True,
    )
    result = propose_story(
        binding,
        source,
        draft.documents,
        (prior,),
        segment=draft.segment,
        observed_at=NOW + timedelta(days=1),
    )
    assert result.disposition == "unchanged" and result.record.last_evidence_at == NOW
    retained = StoryLedger.model_validate_json(
        story_ledger_bytes((prior,), (), observed_at=NOW + timedelta(days=181))
    ).records[0]
    assert retained.disposition == "archived_unknown" and retained.closed_at is None
    assert retained.last_evidence_at == NOW
    assert retained.latest_state == prior.latest_state
    with pytest.raises(ValueError, match="baseline_conflict"):
        story_ledger_bytes((prior,), sealed.story_publication_deltas, observed_at=NOW)
