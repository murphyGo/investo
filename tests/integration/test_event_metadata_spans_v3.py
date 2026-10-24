"""Copy source metadata coordinates without relaxing field-role or byte gates."""

import json

import pytest

from investo._internal.event_context import context_lookup, metadata_ref_field
from investo.briefing.event_context import (
    ContextEvidenceError,
    build_context_prompt_buffer,
    parse_context_classification,
    resolve_context_ref,
)
from investo.models.event_context import (
    ContextClassificationResult,
    ContextRef,
    EventContextDocument,
)
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from tests._helpers.event_context_v3 import DETAIL, FACT, NOW, TITLE, draft


def _document(**metadata: object) -> EventContextDocument:
    evidence = make_evidence_document(
        source_name="official",
        title=TITLE,
        summary=FACT,
        detail_excerpt=DETAIL,
        published_at=NOW,
        received_at=NOW,
    )
    return make_event_context_document(evidence, metadata=metadata)


def _refs(doc: EventContextDocument) -> dict[str, ContextRef]:
    buffer = build_context_prompt_buffer((doc,), required_item_ids=frozenset({1}))
    assert buffer.documents == (doc,)
    assert json.loads(buffer.text)["documents"][0]["context"] == doc.model_dump(mode="json")
    return {
        field: ContextRef(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            chunk_id=chunk["chunk_id"],
            start=span[0],
            end=span[1],
        )
        for chunk in json.loads(buffer.text)["documents"][0]["metadata_spans"]
        for field, span in chunk["fields"].items()
    }


def test_metadata_coordinates_preserve_unicode_escapes_and_duplicate_value_ownership() -> None:
    doc = _document(fact_metric="USD", fact_unit="USD", official_release_id='한글 "공시"\n번호')
    refs = _refs(doc)
    assert resolve_context_ref(refs["fact_metric"], (doc,)) == "USD"
    assert resolve_context_ref(refs["fact_unit"], (doc,)) == "USD"
    assert refs["fact_metric"].start != refs["fact_unit"].start
    assert resolve_context_ref(refs["official_release_id"], (doc,)) == '한글 \\"공시\\"\\n번호'
    for field, ref in refs.items():
        assert metadata_ref_field(ref, context_lookup((doc,))) == field


def test_metadata_coordinates_offer_only_nonblank_bounded_reference_spans() -> None:
    doc = _document(fact_unit="", unit="   ", macro_event_unit="U" * 241, series_id="S" * 240)
    refs = _refs(doc)
    assert set(refs) == {"series_id"}
    assert resolve_context_ref(refs["series_id"], (doc,)) == "S" * 240


@pytest.mark.parametrize("damage", [None, "before", "after", "wrong_field", "missing_unit"])
async def test_copied_metadata_coordinates_reach_classifier_with_existing_gates(
    damage: str | None,
) -> None:
    from investo.briefing._core.orchestration import GenerationPolicy, classify_context
    from investo.briefing.claude_code import RetryBudget
    from tests.integration.test_event_generation import _ReplayRunner

    doc = _document(
        fact_metric="revenue", fact_unit="USD", fact_period="FY2026", fact_status="actual"
    )
    refs = _refs(doc)
    proposed = draft(doc)
    fact = proposed.facts[0].model_copy(
        update={
            "metric_refs": (refs["fact_metric"],),
            "unit_refs": (refs["fact_unit"],),
            "period_refs": (refs["fact_period"],),
            "status_refs": (refs["fact_status"],),
        }
    )
    if damage in {"before", "after"}:
        delta = -1 if damage == "before" else 1
        ref = refs["fact_unit"]
        fact = fact.model_copy(
            update={
                "unit_refs": (
                    ref.model_copy(update={"start": ref.start + delta, "end": ref.end + delta}),
                )
            }
        )
    elif damage == "wrong_field":
        fact = fact.model_copy(update={"unit_refs": (refs["fact_metric"],)})
    elif damage == "missing_unit":
        fact = fact.model_copy(update={"unit_refs": ()})
    proposed = proposed.model_copy(update={"facts": (fact,)})
    payload = ContextClassificationResult(schema_version=3, events=(proposed,)).model_dump_json()
    required = frozenset({1})
    if damage is not None:
        rule = "required_missing" if damage == "missing_unit" else "fact_invalid"
        with pytest.raises(ContextEvidenceError, match=rule):
            parse_context_classification(
                payload, (doc,), observed_at=NOW, required_item_ids=required
            )
        return
    buffer = build_context_prompt_buffer((doc,), required_item_ids=required)
    runner = _ReplayRunner([payload])
    result = await classify_context(
        buffer,
        runner=runner,
        budget=RetryBudget(total_budget_s=30),
        policy=GenerationPolicy(timeout_s=3, max_attempts=1),
        segment="us-equity",
        observed_at=NOW,
    )
    assert result.events == (proposed,)
    assert len(runner.prompts) == 1
    assert buffer.text in runner.prompts[0]
    assert "metadata_spans" in runner.prompts[0]


def test_span_maps_share_the_existing_whole_row_budget_and_required_reservation() -> None:
    docs = tuple(
        _document(official_release_id=str(i), fact_metric="매출", fact_unit="USD")
        for i in range(30)
    )
    buffer = build_context_prompt_buffer(docs, required_item_ids=frozenset({30}))
    assert len(buffer.text.encode("utf-8")) <= 24 * 1024
    assert buffer.item_ids[0] == 30 and buffer.required_prompt_item_ids == frozenset({1})
    assert buffer.deferred_item_ids
    rows = json.loads(buffer.text)["documents"]
    assert [row["item_id"] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row["metadata_spans"] for row in rows)
    assert buffer.text == build_context_prompt_buffer(docs, required_item_ids=frozenset({30})).text
    with pytest.raises(ContextEvidenceError, match="budget_exhausted"):
        build_context_prompt_buffer(docs, required_item_ids=frozenset(range(1, 31)))
