"""Build bounded event packets and parse source-grounded Korean composition."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from investo._internal.event_context import resolve_context_ref
from investo.models.event_article import (
    ArticleQuestion,
    EventEvidencePacket,
    EvidencePassage,
)
from investo.models.event_context import ContextRef, EventContextDocument
from investo.models.event_document import EditorialPlan
from investo.models.event_evidence import event_digest
from investo.models.event_identity import CanonicalEventBinding


def classification_documents(
    documents: Sequence[EventContextDocument],
) -> tuple[EventContextDocument, ...]:
    """Only the first body passage enters Stage1; retain exact source revisions."""
    result = []
    for document in documents:
        first_body = next((c.chunk_id for c in document.chunks if c.role == "background"), None)
        result.append(
            document.model_copy(
                update={
                    "chunks": tuple(
                        c
                        for c in document.chunks
                        if c.role != "background" or c.chunk_id == first_body
                    )
                }
            )
        )
    return tuple(result)


def build_article_packets(
    plan: EditorialPlan,
    bindings: Sequence[CanonicalEventBinding],
    documents: Sequence[EventContextDocument],
) -> tuple[EventEvidencePacket, ...]:
    by_id = {b.identity.event_id: b for b in bindings}
    if (
        len(by_id) != len(bindings)
        or set(by_id) != {p.event_id for p in plan.events}
        or any(
            not p.source_event.item_ids
            or any(not 1 <= i <= len(documents) for i in p.source_event.item_ids)
            for p in plan.events
        )
    ):
        raise ValueError("article.packet_identity_invalid")
    packets = []
    for event in plan.events:
        if event.placement != "article":
            continue
        passages = []
        refs = list(event.assigned_refs)
        for item_id in event.source_event.item_ids:
            doc = documents[item_id - 1]
            for chunk in doc.chunks:
                if chunk.role not in {"background", "meaning", "comparison", "reaction"}:
                    continue
                chunk_refs = tuple(
                    ContextRef(
                        document_id=doc.document_id,
                        revision_id=doc.revision_id,
                        chunk_id=chunk.chunk_id,
                        start=start,
                        end=min(start + 240, len(chunk.text)),
                    )
                    for start in range(0, len(chunk.text), 240)
                )
                if len(set((*refs, *chunk_refs))) > 64:
                    continue
                passage = EvidencePassage(
                    passage_id=event_digest(doc.document_id, doc.revision_id, chunk.chunk_id),
                    document_id=doc.document_id,
                    revision_id=doc.revision_id,
                    chunk_id=chunk.chunk_id,
                    source_locator=chunk.source_locator,
                    text=chunk.text,
                    text_sha256=chunk.text_sha256,
                    refs=chunk_refs,
                )
                passages.append(passage)
                refs.extend(chunk_refs)
                for numeric in re.finditer(
                    r"(?<![0-9.])([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:%|[A-Z]{3}\b)", chunk.text
                ):
                    start, end = numeric.span(1)
                    numeric_ref = ContextRef(
                        document_id=doc.document_id,
                        revision_id=doc.revision_id,
                        chunk_id=chunk.chunk_id,
                        start=start,
                        end=end,
                    )
                    if len(set((*refs, numeric_ref))) <= 64:
                        refs.append(numeric_ref)
        for ref in refs:
            resolve_context_ref(ref, documents)
        why = {
            "earnings_result": "기간·비교 기준과 결과를 설명하는 공식 구성 항목은 무엇인가?",
            "monetary_policy": "적용 대상·효력과 기존 조치 대비 변경 범위·공식 이유는 무엇인가?",
            "regulation": "적용 범위와 절차, 확정된 내용과 남은 조건은 무엇인가?",
        }.get(
            event.source_event.event_kind,
            "변경의 구체적 적용 범위와 확인된 맥락 또는 실행 조건은 무엇인가?",
        )
        packets.append(
            EventEvidencePacket(
                event_id=event.event_id,
                entities=by_id[event.event_id].entities,
                facts=by_id[event.event_id].facts,
                expected_detail=event.source_event.impact != "context",
                required_fact_ids=event.required_fact_ids,
                passages=tuple(passages),
                allowed_refs=tuple(dict.fromkeys(refs)),
                questions=(
                    ArticleQuestion(question_id="what", text="무엇이 실제로 달라졌는가?"),
                    ArticleQuestion(question_id="when", text="언제 발생했으며 현재 어떤 상태인가?"),
                    ArticleQuestion(
                        question_id="why", text=why, required=event.source_event.impact != "context"
                    ),
                    ArticleQuestion(
                        question_id="reaction",
                        text="근거가 있는 반응과 그 시점은 무엇인가?",
                        required=False,
                    ),
                ),
            )
        )
    return tuple(packets)


def packet_payload(
    packets: Sequence[EventEvidencePacket], documents: Sequence[EventContextDocument]
) -> str:
    """Transmit every allowed ref once with its literal bytes, never locator alone."""

    def compact(value: object) -> object:
        if isinstance(value, dict):
            if set(value) == {"document_id", "revision_id", "chunk_id", "start", "end"}:
                return event_digest(value)[:24]
            return {key: compact(child) for key, child in value.items()}
        if isinstance(value, list):
            return [compact(child) for child in value]
        return value

    payload = {
        "ref_format": "packet refs are span IDs; output ContextRefs must copy spans[id].ref",
        "packets": [
            compact({**p.model_dump(mode="json"), "packet_hash": p.packet_hash}) for p in packets
        ],
        "spans": {
            event_digest(ref.model_dump(mode="json"))[:24]: {
                "ref": ref.model_dump(mode="json"),
                "text": resolve_context_ref(ref, documents),
            }
            for ref in dict.fromkeys(r for p in packets for r in p.allowed_refs)
        },
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode()) > 48 * 1024:
        raise ValueError("context.budget_exhausted")
    return text
