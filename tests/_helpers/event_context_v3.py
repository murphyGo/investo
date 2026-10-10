"""Synthetic source-addressed v3 context fixtures, without network calls."""

from datetime import UTC, datetime

from investo.models.event_context import (
    ContextEventDraft,
    ContextFactDraft,
    ContextRef,
    EventContextDocument,
)
from investo.models.event_evidence import make_event_context_document, make_evidence_document

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
TITLE = "Acme announced Widget"
FACT = "Acme revenue actual 1200 USD FY2026"
DETAIL = "The service expands access. Prices rose 2% during the observed hour."


def document(path: str = "one", *, detail: str = DETAIL) -> EventContextDocument:
    evidence = make_evidence_document(
        source_name="official",
        title=TITLE,
        summary=FACT,
        detail_excerpt=detail,
        url=f"https://example.com/{path}",
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    return make_event_context_document(evidence)


def ref(doc: EventContextDocument, text: str) -> ContextRef:
    chunk = next(chunk for chunk in doc.chunks if text in chunk.text)
    start = chunk.text.index(text)
    return ContextRef(
        document_id=doc.document_id,
        revision_id=doc.revision_id,
        chunk_id=chunk.chunk_id,
        start=start,
        end=start + len(text),
    )


def draft(doc: EventContextDocument, item_id: int = 1) -> ContextEventDraft:
    return ContextEventDraft(
        item_ids=(item_id,),
        event_kind="earnings_result",
        actor_refs=(ref(doc, "Acme"),),
        action_refs=(ref(doc, "announced"),),
        object_refs=(ref(doc, "Widget"),),
        relation_refs=(ref(doc, "revenue"),),
        impact_refs=(ref(doc, "revenue"),),
        facts=(
            ContextFactDraft(
                predicate="result",
                status="actual",
                value_kind="numeric",
                subject_refs=(ref(doc, "Acme"),),
                predicate_refs=(ref(doc, "revenue"),),
                metric_refs=(ref(doc, "revenue"),),
                value_refs=(ref(doc, "1200"),),
                unit_refs=(ref(doc, "USD"),),
                period_refs=(ref(doc, "FY2026"),),
                status_refs=(ref(doc, "actual"),),
            ),
        ),
        meaning_refs=(ref(doc, "The service expands access."),)
        if "The service" in doc.chunks[-1].text
        else (),
        reaction_refs=(ref(doc, "Prices rose 2% during the observed hour."),)
        if "Prices rose" in doc.chunks[-1].text
        else (),
        timing="announced",
        relation="direct",
        impact="company",
    )


def metadata_ref(doc: EventContextDocument, key: str) -> ContextRef:
    import json

    chunk = next(chunk for chunk in doc.chunks if chunk.source_locator == "source_metadata")
    value = json.loads(chunk.text)[key]
    encoded = json.dumps(value, ensure_ascii=False)
    text = encoded[1:-1] if isinstance(value, str) else encoded
    prefix = json.dumps(key) + ":"
    start = chunk.text.index(prefix) + len(prefix) + int(isinstance(value, str))
    return ContextRef(
        document_id=doc.document_id,
        revision_id=doc.revision_id,
        chunk_id=chunk.chunk_id,
        start=start,
        end=start + len(text),
    )
