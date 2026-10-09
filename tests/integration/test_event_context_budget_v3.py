"""Exercise actual JSON bytes, transmitted IDs and mandatory evidence priority."""

import json

import pytest

from investo.briefing.event_context import (
    ContextEvidenceError,
    build_context_prompt_buffer,
    build_protected_context_buffer,
    parse_context_classification,
)
from investo.models.event_context import ContextClassificationResult
from tests._helpers.event_context_v3 import DETAIL, NOW, document, draft, ref


def test_stage_one_counts_entire_unicode_json_and_remaps_required_ids() -> None:
    docs = tuple(document(str(i), detail="설명 근거 " * 250) for i in range(30))
    buffer = build_context_prompt_buffer(docs, required_item_ids=frozenset({30}))
    assert len(buffer.text.encode("utf-8")) <= 24 * 1024
    assert 30 in buffer.item_ids and buffer.deferred_item_ids
    rows = json.loads(buffer.text)["documents"]
    assert [row["item_id"] for row in rows] == list(range(1, len(rows) + 1))
    assert buffer.required_prompt_item_ids == frozenset({1})
    payload = ContextClassificationResult(schema_version=3, events=(draft(buffer.documents[0]),))
    parsed = parse_context_classification(
        payload.model_dump_json(),
        buffer.documents,
        observed_at=NOW,
        required_item_ids=buffer.required_prompt_item_ids,
    )
    assert parsed.events[0].actor_refs[0].document_id == docs[29].document_id


def test_stage_two_transmits_independent_meaning_reaction_and_required_facts() -> None:
    doc = document()
    proposed = draft(doc)
    buffer = build_protected_context_buffer(
        (proposed,), (doc,), required_event_indices=frozenset({0})
    )
    assert len(buffer.text.encode()) <= 16 * 1024
    assert buffer.event_indices == (0,) and not buffer.deferred_event_indices
    assert "The service expands access." in buffer.text
    assert "Prices rose 2%" in buffer.text and "1200" in buffer.text
    assert {*proposed.meaning_refs, *proposed.reaction_refs} <= set(buffer.refs)
    assert buffer.drafts == (proposed,)
    assert buffer.text == build_protected_context_buffer((proposed,), (doc,)).text


def test_required_stage_one_source_overflow_is_not_quiet_or_silent_loss() -> None:
    docs = tuple(document(str(i), detail="설명 " * 400) for i in range(30))
    with pytest.raises(ContextEvidenceError, match="budget_exhausted"):
        build_context_prompt_buffer(docs, required_item_ids=frozenset(range(1, 31)))


def test_large_background_does_not_remove_meaning_or_reaction() -> None:
    doc = document(detail=DETAIL + "가" * 1120)
    proposed = draft(doc)
    chunk = doc.chunks[-1]
    background = tuple(
        ref(doc, chunk.text[100 + i : 340 + i]).model_copy(
            update={"start": 100 + i, "end": 340 + i}
        )
        for i in range(16)
    )
    proposed = proposed.model_copy(update={"background_refs": background})
    buffer = build_protected_context_buffer(
        (proposed,), (doc,), required_event_indices=frozenset({0})
    )
    assert buffer.drafts[0].meaning_refs == proposed.meaning_refs
    assert buffer.drafts[0].reaction_refs == proposed.reaction_refs
    assert len(buffer.drafts[0].background_refs) < len(background)
    assert len(buffer.text.encode()) <= 16 * 1024
