"""Wire evidence is exact source text with deduplicated locators and a real UTF-8 cap."""

import json

import pytest

from investo._internal.event_article_packet import packet_payload
from investo._internal.event_context import resolve_context_ref
from investo.models.event_context import ContextRef
from tests._helpers.event_article_v2 import article_case


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
