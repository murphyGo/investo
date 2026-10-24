"""Ordinary Korean component nouns retain all native fact and identity checks."""

import json

import pytest

from investo._internal.event_v3_contract import EventEditionValidationError, validate_event_edition
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import support_vector
from investo.briefing.event_identity import canonical_event_binding
from investo.models.event_context import ContextRef
from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import native_case, native_context

_PROSE = "Acme가 Widget의 FY2026 실제 revenue 관측값은 1200이며 단위는 USD입니다."


@pytest.mark.parametrize(
    "before,after",
    [
        (None, None),
        ("1200", "9999"),
        ("USD", "KRW"),
        ("실제", "전망"),
        ("FY2026", "FY2027"),
        ("Acme", "Beta"),
        ("Acme", "관측값"),
        ("Widget", "단위"),
        ("Acme가", "미확인회사가 Acme가"),
        ("Acme가", "관측값테크가 Acme가"),
    ],
)
def test_component_prose_seals_without_admitting_factual_or_entity_mutations(
    before: str | None, after: str | None
) -> None:
    item, edition = native_case()
    text = _PROSE if before is None else _PROSE.replace(before, after)
    changed = edition.model_copy(
        update={"articles": (edition.articles[0].model_copy(update={"what_changed": text}),)}
    )
    if before is not None:
        with pytest.raises(
            PublicDocumentFinalizationError, match=r"event\.(fact|entity)_unsupported"
        ):
            finalize_public_bundle(
                {changed.segment: changed}, context=native_context((item, changed))
            )
        return
    sealed = finalize_public_bundle(
        {changed.segment: changed}, context=native_context((item, changed))
    ).documents[0]
    assert _PROSE in sealed.rendered_markdown


def test_parent_plan_supplies_every_fact_ref_including_distinct_subject_span() -> None:
    item, edition = native_case()
    doc = edition.documents[0]
    summary = next(chunk for chunk in doc.chunks if chunk.source_locator.startswith("summary:"))
    subject = ContextRef(
        document_id=doc.document_id,
        revision_id=doc.revision_id,
        chunk_id=summary.chunk_id,
        start=0,
        end=4,
    )
    source = edition.editorial_plan.events[0].source_event
    source = source.model_copy(
        update={"facts": (source.facts[0].model_copy(update={"subject_refs": (subject,)}),)}
    )
    binding = canonical_event_binding(
        source, edition.documents, (), observed_at=NOW, baseline_available=True
    )
    plan, bindings, payload = build_editorial_plan(
        (source,), (binding,), edition.documents, required_item_ids=frozenset({1}), observed_at=NOW
    )
    wire = json.loads(payload)
    assert wire["events"][0]["fact_ids"] == [fact.fact_id for fact in binding.facts]
    assert plan.evidence_bytes == len(payload.encode("utf-8")) <= 16384
    copied = tuple(
        ContextRef.model_validate(wire["context"]["spans"][ref_id]["ref"])
        for fact in wire["context"]["events"][0]["draft"]["facts"]
        for component, ids in fact.items()
        if component.endswith("_refs")
        for ref_id in ids
    )
    assert set(copied) == {ref for fact in binding.facts for ref in fact.source_refs}
    assert subject in copied
    article = edition.articles[0].model_copy(
        update={
            "event_id": binding.identity.event_id,
            "fact_ids": tuple(f.fact_id for f in binding.facts),
            "source_refs": tuple(dict.fromkeys((*edition.articles[0].source_refs, *copied))),
            "what_changed": _PROSE,
        }
    )
    changed = edition.model_copy(
        update={
            "editorial_plan": plan,
            "bindings": bindings,
            "articles": (article,),
            "support": (support_vector(source, edition.documents, baseline_available=True),),
        }
    )
    assert finalize_public_bundle(
        {changed.segment: changed}, context=native_context((item, changed))
    ).documents
    incomplete = changed.model_copy(
        update={
            "articles": (
                article.model_copy(
                    update={"source_refs": tuple(r for r in article.source_refs if r != subject)}
                ),
            )
        }
    )
    with pytest.raises(EventEditionValidationError, match=r"event\.evidence_invalid"):
        validate_event_edition(incomplete, observed_at=NOW)
