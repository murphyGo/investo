"""Wire evidence is exact source text with deduplicated locators and a real UTF-8 cap."""

import json

import pytest

from investo._internal.event_article_packet import packet_payload
from investo._internal.event_context import resolve_context_ref
from investo.models.event_context import ContextRef
from tests._helpers.event_article_v2 import article_case


def test_numeric_source_summary_keeps_prior_context_without_a_body():
    from investo._internal.event_article_packet import build_article_packets
    from investo.briefing.editorial_plan import build_editorial_plan
    from investo.briefing.event_identity import canonical_event_binding
    from investo.models.event_evidence import make_event_context_document, make_evidence_document
    from tests._helpers.event_context_v3 import NOW
    from tests._helpers.event_context_v3 import draft as source_draft

    summary = "Acme revenue actual 1200 USD FY2026; prior 1100 USD FY2025."
    doc = make_event_context_document(
        make_evidence_document(
            source_name="official",
            title="Acme announced Widget",
            summary=summary,
            published_at=NOW,
            received_at=NOW,
        ),
        article_passages=True,
    )
    event = source_draft(doc)
    binding = canonical_event_binding(event, (doc,), (), observed_at=NOW, baseline_available=False)
    plan, bindings, _ = build_editorial_plan((event,), (binding,), (doc,), observed_at=NOW)
    packet = build_article_packets(plan, bindings, (doc,))[0]
    assert len(packet.passages) == 1
    assert packet.passages[0].text == summary
    assert "1100" not in {fact.original_value for fact in packet.facts}
    wire = json.loads(packet_payload((packet,), (doc,)))
    passage = wire["packets"][0]["passages"][0]
    assert "".join(wire["spans"][ref]["text"] for ref in passage["refs"]) == summary


def test_four_source_packet_retains_six_body_passages_and_each_summary():
    from investo._internal.event_article_packet import build_article_packets
    from investo.briefing.editorial_plan import build_editorial_plan
    from investo.briefing.event_identity import canonical_event_binding
    from investo.models.event_evidence import make_event_context_document, make_evidence_document
    from tests._helpers.event_context_v3 import NOW
    from tests._helpers.event_context_v3 import draft as source_draft

    documents = tuple(
        make_event_context_document(
            make_evidence_document(
                source_name="official",
                title="Acme announced Widget",
                summary=f"Acme revenue actual 1200 USD FY2026; source {i} comparison.",
                detail_excerpt="\n\n".join(f"Source {i} paragraph {j}." for j in range(6)),
                url=f"https://example.com/source-{i}",
                published_at=NOW,
                received_at=NOW,
            ),
            article_passages=True,
        )
        for i in range(4)
    )
    event = source_draft(documents[0]).model_copy(update={"item_ids": (1, 2, 3, 4)})
    binding = canonical_event_binding(
        event, documents, (), observed_at=NOW, baseline_available=False
    )
    plan, bindings, _ = build_editorial_plan((event,), (binding,), documents, observed_at=NOW)
    packet = build_article_packets(plan, bindings, documents)[0]
    assert len(packet.passages) == 28
    assert sum(p.source_locator.startswith("summary:") for p in packet.passages) == 4
    assert len(packet.allowed_refs) <= 64
    assert len(packet_payload((packet,), documents).encode()) <= 48 * 1024


def test_compact_packet_has_literal_text_for_every_transmitted_ref():
    _, draft, _, _ = article_case()
    packet = draft.article_readiness[0].packet
    text = packet_payload((packet,), draft.documents)
    wire = json.loads(text)
    assert len(text.encode("utf-8")) <= 48 * 1024
    refs = wire["packets"][0]["allowed_refs"]
    assert len(set(refs)) == len(refs)
    assert all(isinstance(ref, str) and ref in wire["spans"] for ref in refs)
    for span in wire["spans"].values():
        assert span["text"] == resolve_context_ref(
            ContextRef.model_validate(span["ref"]), draft.documents
        )
    assert wire["packets"][0]["packet_hash"] == packet.packet_hash


def test_unicode_evidence_overflow_cannot_be_hidden_by_reference_compaction():
    detail = "Acme explained that Widget revenue reflects expanded service access.\n"
    detail += "\n".join(
        ("조건과 적용 범위는 공식 발표에서 확인합니다. " * 30) + f"문단 {i}." for i in range(5)
    )
    _, draft, _, _ = article_case(detail=detail)
    packet = draft.article_readiness[0].packet
    packets = tuple(packet.model_copy(update={"event_id": f"{i:024x}"}) for i in range(5))
    with pytest.raises(ValueError, match="budget_exhausted"):
        packet_payload(packets, draft.documents)
    # Packing a rejected batch cannot mutate the canonical source buffers.
    assert draft.documents[0].chunks[-1].text in detail


def test_private_source_passages_are_not_short_ref_substrings():
    detail = (
        "Acme explained that Widget revenue reflects expanded service access. "
        + "Additional context. " * 40
    )
    _, draft, _, _ = article_case(detail=detail)
    packet = draft.article_readiness[0].packet
    assert len(packet.passages[0].text) > 240
    assert all(ref.end - ref.start <= 240 for ref in packet.passages[0].refs)
    assert (
        "".join(resolve_context_ref(ref, draft.documents) for ref in packet.passages[0].refs)
        == detail.strip()
    )
