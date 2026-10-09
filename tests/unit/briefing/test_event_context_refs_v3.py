"""Independent explanation refs, source ownership and distinct quality axes."""

from datetime import timedelta

import pytest

from investo.briefing.event_context import (
    ContextEvidenceError,
    build_protected_context_buffer,
    parse_context_classification,
    resolve_context_ref,
    support_vector,
    validate_context_event,
)
from investo.models.event_context import (
    ContextClassificationResult,
    EventContextDocument,
    EventTimeValue,
)
from tests._helpers.event_context_v3 import NOW, document, draft, metadata_ref, ref


def test_meaning_and_reaction_need_not_be_identity_fact_subsets() -> None:
    doc = document()
    proposed = draft(doc)
    validate_context_event(proposed, (doc,), observed_at=NOW)
    identity_refs = {*proposed.actor_refs, *proposed.action_refs, *proposed.object_refs}
    assert not set(proposed.meaning_refs) <= identity_refs
    assert (
        resolve_context_ref(proposed.reaction_refs[0], (doc,))
        == "Prices rose 2% during the observed hour."
    )


def test_cross_event_and_failed_source_refs_are_rejected() -> None:
    one, two = document(), document("two")
    proposed = draft(one).model_copy(update={"meaning_refs": (ref(two, "Acme"),)})
    with pytest.raises(ContextEvidenceError, match="item_mismatch"):
        validate_context_event(proposed, (one, two), observed_at=NOW)
    failed = EventContextDocument.model_validate({**one.model_dump(), "source_status": "failed"})
    with pytest.raises(ContextEvidenceError, match="source_unavailable"):
        validate_context_event(draft(one), (failed,), observed_at=NOW)


def test_unknown_revision_and_untransmitted_span_fail_closed() -> None:
    doc = document()
    original = ref(doc, "Acme")
    with pytest.raises(ContextEvidenceError, match="unknown_document"):
        resolve_context_ref(original.model_copy(update={"revision_id": "f" * 64}), (doc,))
    with pytest.raises(ContextEvidenceError, match="span_out_of_bounds"):
        resolve_context_ref(original.model_copy(update={"start": 1190, "end": 1200}), (doc,))


def test_content_time_history_and_locator_are_independent() -> None:
    doc = document()
    vector = support_vector(draft(doc), (doc,), baseline_available=False)
    assert vector.facts == "complete" and vector.time == "publication_only"
    assert vector.novelty == "unknown" and vector.locator == "complete"
    assert (
        "history.unavailable" in vector.reason_codes
        and "facts.content_shallow" not in vector.reason_codes
    )
    missing = support_vector(
        draft(doc).model_copy(update={"facts": ()}), (doc,), baseline_available=True
    )
    assert missing.facts == "missing" and missing.novelty == "known"


def test_parser_checks_required_assignments_and_redacts_bad_input() -> None:
    doc = document()
    payload = ContextClassificationResult(schema_version=3, events=(draft(doc),)).model_dump_json()
    assert parse_context_classification(
        payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
    ).events
    with pytest.raises(ContextEvidenceError, match="required_missing"):
        parse_context_classification(
            '{"schema_version":3,"events":[]}',
            (doc,),
            observed_at=NOW,
            required_item_ids=frozenset({1}),
        )
    sentinel = "PRIVATE_MODEL_SECRET_abc"
    with pytest.raises(ContextEvidenceError) as captured:
        parse_context_classification(sentinel, (doc,), observed_at=NOW)
    assert sentinel not in str(captured.value)


def test_protected_buffer_validates_owners_and_unused_failed_document() -> None:
    one, two = document(), document("two")
    foreign = draft(one).model_copy(update={"meaning_refs": (ref(two, "Acme"),)})
    with pytest.raises(ContextEvidenceError, match="item_mismatch"):
        build_protected_context_buffer((foreign,), (one, two))
    failed = two.model_copy(update={"source_status": "failed"})
    merged = draft(one).model_copy(update={"item_ids": (1, 2)})
    with pytest.raises(ContextEvidenceError, match="source_unavailable"):
        validate_context_event(merged, (one, failed), observed_at=NOW)


def test_future_announcement_is_not_an_occurrence() -> None:
    doc = document()
    future = EventTimeValue(
        value=NOW + timedelta(days=1), precision="exact", source_refs=(ref(doc, "Acme"),)
    )
    doc = doc.model_copy(update={"time": doc.time.model_copy(update={"announced_at": future})})
    with pytest.raises(ContextEvidenceError, match="future_occurred"):
        validate_context_event(
            draft(doc).model_copy(update={"timing": "occurred"}), (doc,), observed_at=NOW
        )


@pytest.mark.parametrize(
    "component,text,rule",
    [("value_refs", "Widget", "fact_invalid"), ("status_refs", "USD", "status_unbound")],
)
def test_component_presence_does_not_prove_numeric_or_actual(
    component: str, text: str, rule: str
) -> None:
    doc = document()
    proposed = draft(doc)
    fact = proposed.facts[0].model_copy(update={component: (ref(doc, text),)})
    proposed = proposed.model_copy(update={"facts": (fact,)})
    payload = ContextClassificationResult(schema_version=3, events=(proposed,)).model_dump_json()
    with pytest.raises(ContextEvidenceError, match=rule):
        parse_context_classification(payload, (doc,), observed_at=NOW)
    with pytest.raises(ContextEvidenceError, match=rule):
        support_vector(proposed, (doc,), baseline_available=True)


def test_required_actual_cannot_be_an_event_without_a_fact() -> None:
    doc = document()
    payload = ContextClassificationResult(
        schema_version=3, events=(draft(doc).model_copy(update={"facts": ()}),)
    ).model_dump_json()
    with pytest.raises(ContextEvidenceError, match="required_missing"):
        parse_context_classification(
            payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
        )


def test_metadata_metric_or_key_cannot_supply_fact_status() -> None:
    from investo.models.event_evidence import make_event_context_document, make_evidence_document

    evidence = make_evidence_document(
        source_name="official",
        title="Acme announced Widget",
        summary="Acme revenue forecast 1200 USD FY2026",
        published_at=NOW,
        received_at=NOW,
    )
    doc = make_event_context_document(
        evidence, metadata={"fact_status": "forecast", "fact_metric": "actual"}
    )
    proposed = draft(doc)
    # Here the fixture's actual word exists only in the wrong metadata field.
    payload = ContextClassificationResult(schema_version=3, events=(proposed,)).model_dump_json()
    with pytest.raises(ContextEvidenceError, match="status_unbound"):
        parse_context_classification(payload, (doc,), observed_at=NOW)
    chunk = doc.chunks[-1]
    key_start = chunk.text.index('"fact_status"') + 6
    wrong_key = ref(doc, "actual").model_copy(update={"start": key_start, "end": key_start + 6})
    fact = proposed.facts[0].model_copy(update={"status_refs": (wrong_key,)})
    payload = ContextClassificationResult(
        schema_version=3, events=(proposed.model_copy(update={"facts": (fact,)}),)
    ).model_dump_json()
    with pytest.raises(ContextEvidenceError, match="fact_invalid"):
        parse_context_classification(payload, (doc,), observed_at=NOW)


def test_required_actual_value_must_bind_actual_metadata_slot() -> None:
    from investo.briefing.event_context import prepare_context_documents
    from investo.models.items import NormalizedItem

    item = NormalizedItem(
        source_name="official",
        category="macro",
        title="Acme announced Widget",
        summary="Acme revenue forecast 1200 USD FY2026",
        published_at=NOW,
        raw_metadata={
            "macro_event_key": "revenue",
            "macro_event_status": "actual",
            "macro_actual": "1000",
            "macro_forecast": "1200",
            "macro_release_period": "FY2026",
            "unit": "USD",
        },
    )
    doc = prepare_context_documents((item,), received_at=NOW)[0]
    proposed = draft(doc)
    proposed = proposed.model_copy(
        update={
            "facts": (
                proposed.facts[0].model_copy(
                    update={"status_refs": (metadata_ref(doc, "macro_status"),)}
                ),
            )
        }
    )
    payload = ContextClassificationResult(schema_version=3, events=(proposed,)).model_dump_json()
    with pytest.raises(ContextEvidenceError, match=r"fact_invalid|required_missing"):
        parse_context_classification(
            payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
        )
    fact = proposed.facts[0].model_copy(update={"value_refs": (metadata_ref(doc, "macro_actual"),)})
    payload = ContextClassificationResult(
        schema_version=3, events=(proposed.model_copy(update={"facts": (fact,)}),)
    ).model_dump_json()
    assert parse_context_classification(
        payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
    ).events


def test_plain_text_reported_cannot_override_typed_forecast_status() -> None:
    from investo.models.event_evidence import make_event_context_document, make_evidence_document

    evidence = make_evidence_document(
        source_name="official",
        title="Acme announced Widget and reported projections",
        summary="Acme revenue forecast 1200 USD FY2026",
        published_at=NOW,
        received_at=NOW,
    )
    doc = make_event_context_document(evidence, metadata={"fact_status": "forecast"})
    original = draft(document())
    fact = original.facts[0].model_copy(
        update={
            "subject_refs": (ref(doc, "Acme"),),
            "predicate_refs": (ref(doc, "revenue"),),
            "metric_refs": (ref(doc, "revenue"),),
            "value_refs": (ref(doc, "1200"),),
            "unit_refs": (ref(doc, "USD"),),
            "period_refs": (ref(doc, "FY2026"),),
            "status_refs": (ref(doc, "reported"),),
        }
    )
    proposed = original.model_copy(
        update={
            "actor_refs": (ref(doc, "Acme"),),
            "action_refs": (ref(doc, "announced"),),
            "object_refs": (),
            "relation_refs": (),
            "impact_refs": (),
            "facts": (fact,),
            "meaning_refs": (),
            "reaction_refs": (),
        }
    )
    payload = ContextClassificationResult(schema_version=3, events=(proposed,)).model_dump_json()
    with pytest.raises(ContextEvidenceError, match="status_unbound"):
        parse_context_classification(
            payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
        )


def test_mixed_actual_and_forecast_keep_each_source_slot_status() -> None:
    from investo.briefing.event_context import prepare_context_documents
    from investo.models.items import NormalizedItem

    item = NormalizedItem(
        source_name="official",
        category="macro",
        title="Acme announced Widget",
        summary="Acme revenue actual 1000 USD FY2026; Acme revenue forecast 1200 USD FY2026",
        published_at=NOW,
        raw_metadata={
            "macro_event_key": "revenue",
            "macro_event_status": "actual",
            "macro_actual": "1000",
            "macro_forecast": "1200",
            "macro_release_period": "FY2026",
            "unit": "USD",
        },
    )
    doc = prepare_context_documents((item,), received_at=NOW)[0]
    proposed = draft(doc)
    actual = proposed.facts[0].model_copy(
        update={
            "value_refs": (metadata_ref(doc, "macro_actual"),),
            "status_refs": (metadata_ref(doc, "macro_actual_status"),),
        }
    )
    for typed in (False, True):
        forecast = actual.model_copy(
            update={
                "status": "forecast",
                "value_refs": (metadata_ref(doc, "macro_forecast") if typed else ref(doc, "1200"),),
                "status_refs": (
                    metadata_ref(doc, "macro_forecast_status") if typed else ref(doc, "forecast"),
                ),
            }
        )
        payload = ContextClassificationResult(
            schema_version=3, events=(proposed.model_copy(update={"facts": (actual, forecast)}),)
        ).model_dump_json()
        parsed = parse_context_classification(
            payload, (doc,), observed_at=NOW, required_item_ids=frozenset({1})
        )
        assert [fact.status for fact in parsed.events[0].facts] == ["actual", "forecast"]
