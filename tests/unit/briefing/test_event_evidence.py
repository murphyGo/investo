"""Source identity and exact transmitted-buffer evidence tests."""

from datetime import UTC, date, datetime, timedelta

import pytest

from investo.briefing.event_evidence import (
    build_event_candidates,
    canonical_evidence_url,
    event_digest,
    make_evidence_document,
    make_identity_receipt,
    prepare_evidence_documents,
    resolve_evidence_ref,
)
from investo.models.events import EventCandidateDraft, EventFactDraft, EvidenceDocument, EvidenceRef
from investo.models.items import NormalizedItem

NOW = datetime(2026, 9, 21, 12, tzinfo=UTC)


def document(*, source: str = "news", path: str = "one", detail: str = "") -> EvidenceDocument:
    return make_evidence_document(
        source_name=source,
        title="Acme launches Product A and Product B",
        summary="Product A is available. Product B is available.",
        detail_excerpt=detail,
        url=f"https://example.invalid/{path}",
        published_at=NOW - timedelta(hours=1),
        received_at=NOW,
        event_time=date(2026, 9, 21),
        event_time_basis="source_date",
        source_tier="official" if source == "official" else "secondary",
    )


def item(doc: EvidenceDocument) -> NormalizedItem:
    return NormalizedItem(
        source_name=doc.source_name,
        title=doc.title,
        summary=doc.summary,
        category="news",
        url=doc.url,
        published_at=doc.published_at,
        event_evidence=doc,
    )


def ref(doc: EvidenceDocument, text: str, field: str = "title") -> EvidenceRef:
    start = getattr(doc, field).index(text)
    return EvidenceRef.model_validate(
        dict(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            field=field,
            start=start,
            end=start + len(text),
        )
    )


def draft(doc: EvidenceDocument, product: str = "A", item_id: int = 1) -> EventCandidateDraft:
    actor = ref(doc, "Acme")
    return EventCandidateDraft(
        item_ids=(item_id,),
        event_kind="product_service",
        actor_refs=(actor,),
        action_refs=(ref(doc, "launches"),),
        object_refs=(ref(doc, f"Product {product}"),),
        relation_refs=(actor,),
        impact_refs=(actor,),
        timing="announced",
        relation="direct",
        impact="company",
        facts=(
            EventFactDraft(
                predicate="launch",
                evidence_ref=ref(doc, f"Product {product} is available.", "summary"),
            ),
        ),
    )


def test_two_products_same_document_have_distinct_identity() -> None:
    doc = document()
    candidates = build_event_candidates(
        [draft(doc), draft(doc, "B")], [item(doc)], [doc], observed_at=NOW
    )
    assert len({event.event_id for event in candidates}) == 2
    assert all(event.required_fact_ids for event in candidates)
    assert all(event.evidence_state == "supported" for event in candidates)


def test_late_official_source_retains_identity_and_hashed_aliases() -> None:
    old = document()
    candidate = build_event_candidates([draft(old)], [item(old)], [old], observed_at=NOW)[0]
    receipt = make_identity_receipt(candidate, published_at=NOW)
    official = document(source="official", path="release")
    later = build_event_candidates(
        [draft(official)],
        [item(official)],
        [official],
        observed_at=NOW + timedelta(days=1),
        baseline=[receipt],
    )[0]
    assert later.event_id == candidate.event_id
    assert set(later.document_aliases) == {old.document_id, official.document_id}
    assert later.novelty == "repeat"
    assert "Acme" not in receipt.model_dump_json()
    assert "https://" not in receipt.model_dump_json()


def test_revised_fact_is_update_not_new_event() -> None:
    old = document()
    first = build_event_candidates([draft(old)], [item(old)], [old], observed_at=NOW)[0]
    updated = make_evidence_document(
        source_name=old.source_name,
        title=old.title,
        summary="Product A is available worldwide.",
        url=old.url,
        published_at=old.published_at,
        received_at=NOW,
        event_time=old.event_time,
        event_time_basis=old.event_time_basis,
    )
    proposal = draft(old).model_copy(
        update={
            "actor_refs": (ref(updated, "Acme"),),
            "action_refs": (ref(updated, "launches"),),
            "object_refs": (ref(updated, "Product A"),),
            "relation_refs": (ref(updated, "Acme"),),
            "impact_refs": (ref(updated, "Acme"),),
            "facts": (
                EventFactDraft(
                    predicate="launch", evidence_ref=ref(updated, updated.summary, "summary")
                ),
            ),
        }
    )
    result = build_event_candidates(
        [proposal],
        [item(updated)],
        [updated],
        observed_at=NOW,
        baseline=[make_identity_receipt(first, published_at=NOW)],
    )[0]
    assert result.event_id == first.event_id
    assert result.novelty == "material_update"


def test_merged_fact_set_recomputes_novelty_against_committed_receipt() -> None:
    doc = document(detail="Product A reaches Europe.")
    proposals = [
        draft(doc),
        draft(doc).model_copy(
            update={
                "facts": (
                    EventFactDraft(
                        predicate="status_change",
                        evidence_ref=ref(doc, doc.detail_excerpt, "detail_excerpt"),
                    ),
                )
            }
        ),
    ]
    standalone = [
        build_event_candidates([proposal], [item(doc)], [doc], observed_at=NOW)[0]
        for proposal in proposals
    ]
    # Ensure the repeat sorts first: the old implementation retained its
    # novelty and incorrectly discarded the merged material update.
    first = min(standalone, key=lambda candidate: candidate.fact_hashes)
    baseline = [make_identity_receipt(first, published_at=NOW)]
    forward = build_event_candidates(
        proposals, [item(doc)], [doc], observed_at=NOW, baseline=baseline
    )
    reverse = build_event_candidates(
        list(reversed(proposals)), [item(doc)], [doc], observed_at=NOW, baseline=baseline
    )
    assert forward == reverse
    assert len(forward) == 1
    assert len(forward[0].change_facts) == 2
    assert forward[0].event_id == first.event_id
    assert forward[0].novelty == "material_update"


def test_same_document_date_enrichment_keeps_committed_identity() -> None:
    known = document()
    unknown = known.model_copy(update={"event_time": None, "event_time_basis": "unknown"})
    first = build_event_candidates([draft(unknown)], [item(unknown)], [unknown], observed_at=NOW)[0]
    result = build_event_candidates(
        [draft(known)],
        [item(known)],
        [known],
        observed_at=NOW,
        baseline=[make_identity_receipt(first, published_at=NOW)],
    )[0]
    assert result.event_id == first.event_id
    assert result.event_key_hash != first.event_key_hash
    assert result.effective_date == NOW.date()
    assert result.novelty == "repeat"


def test_document_alias_does_not_merge_changed_object_or_conflicting_date() -> None:
    doc = document()
    first = build_event_candidates([draft(doc)], [item(doc)], [doc], observed_at=NOW)[0]
    baseline = [make_identity_receipt(first, published_at=NOW)]
    other_object = build_event_candidates(
        [draft(doc, "B")], [item(doc)], [doc], observed_at=NOW, baseline=baseline
    )[0]
    other_date = doc.model_copy(update={"event_time": NOW.date() - timedelta(days=1)})
    changed_time = build_event_candidates(
        [draft(other_date)],
        [item(other_date)],
        [other_date],
        observed_at=NOW,
        baseline=baseline,
    )[0]
    assert other_object.event_id != first.event_id
    assert changed_time.event_id != first.event_id
    assert other_object.novelty == changed_time.novelty == "new"


def test_merged_date_enrichment_retains_dated_key_for_later_official_source() -> None:
    unknown = document().model_copy(update={"event_time": None, "event_time_basis": "unknown"})
    known = document(detail="The company confirms the launch date.")
    first = build_event_candidates([draft(unknown)], [item(unknown)], [unknown], observed_at=NOW)[0]
    baseline = [make_identity_receipt(first, published_at=NOW)]
    proposals = [draft(unknown), draft(known, item_id=2)]
    docs = [unknown, known]
    merged = build_event_candidates(
        proposals, [item(doc) for doc in docs], docs, observed_at=NOW, baseline=baseline
    )[0]
    assert merged.event_id == first.event_id
    assert merged.effective_date == NOW.date()
    official = document(source="official", path="later-official-release")
    later = build_event_candidates(
        [draft(official)],
        [item(official)],
        [official],
        observed_at=NOW + timedelta(hours=1),
        baseline=[make_identity_receipt(merged, published_at=NOW)],
    )[0]
    assert later.event_id == first.event_id


@pytest.mark.parametrize(
    "change", [{"status": "forecast"}, {"period": "Product A"}, {"unit": "Product A"}]
)
@pytest.mark.parametrize("within_draft", [False, True])
def test_same_fact_id_conflicting_payload_is_rejected_in_any_order(
    change: dict[str, str], within_draft: bool
) -> None:
    doc = document()
    proposal = draft(doc)
    fact = proposal.facts[0]
    conflicting = EventFactDraft.model_validate({**fact.model_dump(), **change})
    for pair in ((fact, conflicting), (conflicting, fact)):
        proposals = (
            [proposal.model_copy(update={"facts": pair})]
            if within_draft
            else [proposal.model_copy(update={"facts": (value,)}) for value in pair]
        )
        with pytest.raises(ValueError, match="fact_conflict"):
            build_event_candidates(proposals, [item(doc)], [doc], observed_at=NOW)


def test_identical_facts_collapse_within_and_across_drafts() -> None:
    doc = document()
    proposal = draft(doc)
    duplicated = proposal.model_copy(update={"facts": proposal.facts * 2})
    result = build_event_candidates([duplicated, proposal], [item(doc)], [doc], observed_at=NOW)
    assert len(result) == 1
    assert len(result[0].change_facts) == len(result[0].required_fact_ids) == 1
    assert len(result[0].fact_hashes) == 1


def test_unknown_time_and_unavailable_baseline_are_limited() -> None:
    original = document()
    doc = original.model_copy(update={"event_time": None, "event_time_basis": "unknown"})
    result = build_event_candidates(
        [draft(doc)], [item(doc)], [doc], observed_at=NOW, baseline_available=False
    )[0]
    assert result.effective_date is None
    assert result.novelty == "unknown"
    assert result.evidence_state == "detail_limited"


def test_future_and_wrong_document_claims_rejected() -> None:
    doc = document().model_copy(update={"event_time": NOW.date() + timedelta(days=1)})
    with pytest.raises(ValueError, match="future scheduled"):
        build_event_candidates(
            [draft(doc).model_copy(update={"timing": "occurred"})],
            [item(doc)],
            [doc],
            observed_at=NOW,
        )
    bad = draft(doc).model_copy(update={"item_ids": (2,)})
    with pytest.raises(ValueError, match="item_id"):
        build_event_candidates([bad], [item(doc)], [doc], observed_at=NOW)
    other = document(path="other")
    with pytest.raises(ValueError, match="does not belong"):
        build_event_candidates([draft(other)], [item(doc)], [doc], observed_at=NOW)


def test_exact_revision_codepoints_and_whitespace() -> None:
    doc = make_evidence_document(
        source_name="x", title="가😀 나", summary="   ", published_at=NOW, received_at=NOW
    )
    assert resolve_evidence_ref(ref(doc, "😀"), [doc]) == "😀"
    with pytest.raises(ValueError, match="revision"):
        resolve_evidence_ref(ref(doc, "😀").model_copy(update={"revision_id": "f" * 64}), [doc])
    with pytest.raises(ValueError, match="exceeds"):
        resolve_evidence_ref(ref(doc, "😀").model_copy(update={"end": 20}), [doc])
    with pytest.raises(ValueError, match="whitespace"):
        resolve_evidence_ref(ref(doc, "   ", "summary"), [doc])


def test_detail_cap_is_deterministic_and_rehashes_actual_buffers() -> None:
    docs = [document(source=f"source-{i:02}", path=str(i), detail="가😀" * 1000) for i in range(12)]
    prepared = prepare_evidence_documents([item(doc) for doc in docs], received_at=NOW)
    reverse = prepare_evidence_documents([item(doc) for doc in reversed(docs)], received_at=NOW)
    assert prepared == tuple(reversed(reverse))
    assert sum(len(doc.detail_excerpt.encode("utf-8")) for doc in prepared) <= 24 * 1024
    assert all(len(doc.detail_excerpt) <= 1200 for doc in prepared)
    assert all(
        doc.origin_revision_id == original.revision_id
        for doc, original in zip(prepared, docs, strict=True)
    )
    assert all(
        doc.revision_id == event_digest(doc.title, doc.summary, doc.detail_excerpt)
        for doc in prepared
    )
    assert any(not doc.detail_excerpt for doc in prepared)
    clipped = next(doc for doc in prepared if not doc.detail_excerpt)
    original = next(doc for doc in docs if doc.document_id == clipped.document_id)
    with pytest.raises(ValueError, match="revision"):
        resolve_evidence_ref(ref(original, "가😀", "detail_excerpt"), [clipped])


def test_url_identity_keeps_meaningful_query() -> None:
    assert canonical_evidence_url("https://example.invalid/a?id=7&utm_x=secret#frag") == (
        "https://example.invalid/a?id=7"
    )
    assert canonical_evidence_url("https://example.invalid/a?id=8") != (
        canonical_evidence_url("https://example.invalid/a?id=7")
    )
    assert canonical_evidence_url("https://example.invalid/a?q=a%20b&token=%2f&flag&utm_x=x") == (
        "https://example.invalid/a?q=a%20b&token=%2f&flag"
    )


def test_unknown_dates_do_not_merge_different_documents() -> None:
    docs = [
        document(path=path).model_copy(update={"event_time": None, "event_time_basis": "unknown"})
        for path in ("one", "two")
    ]
    proposals = [draft(doc, item_id=i + 1) for i, doc in enumerate(docs)]
    forward = build_event_candidates(proposals, [item(d) for d in docs], docs, observed_at=NOW)
    reverse = build_event_candidates(
        list(reversed(proposals)), [item(d) for d in docs], docs, observed_at=NOW
    )
    assert forward == reverse
    assert len({event.event_id for event in forward}) == 2


def test_same_day_future_exact_time_is_not_occurred() -> None:
    doc = document().model_copy(
        update={"event_time": NOW + timedelta(hours=1), "event_time_basis": "source_exact"}
    )
    with pytest.raises(ValueError, match="future scheduled"):
        build_event_candidates(
            [draft(doc).model_copy(update={"timing": "occurred"})],
            [item(doc)],
            [doc],
            observed_at=NOW,
        )


def test_required_facts_cannot_be_supplied_or_emptied_by_model() -> None:
    doc = document()
    with pytest.raises(ValueError):
        EventCandidateDraft.model_validate({**draft(doc).model_dump(), "required_fact_ids": []})
    no_fact = draft(doc).model_copy(update={"facts": ()})
    candidate = build_event_candidates([no_fact], [item(doc)], [doc], observed_at=NOW)[0]
    assert candidate.evidence_state == "detail_limited"
    assert candidate.required_fact_ids == ()


def test_expired_receipt_cannot_suppress_new_event() -> None:
    doc = document()
    candidate = build_event_candidates([draft(doc)], [item(doc)], [doc], observed_at=NOW)[0]
    old = make_identity_receipt(candidate, published_at=NOW - timedelta(days=8))
    current = build_event_candidates(
        [draft(doc)], [item(doc)], [doc], observed_at=NOW, baseline=[old]
    )[0]
    assert current.novelty == "new"


def test_attached_evidence_cannot_impersonate_another_source() -> None:
    doc = document()
    forged = item(doc).model_copy(update={"event_evidence": document(source="official")})
    with pytest.raises(ValueError, match="routed source item"):
        prepare_evidence_documents([forged], received_at=NOW)
