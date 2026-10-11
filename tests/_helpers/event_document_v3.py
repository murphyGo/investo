"""Native synthetic edition fixtures with real source preparation and finalizer E1."""

from datetime import date

from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import prepare_context_documents, support_vector
from investo.briefing.event_identity import canonical_event_binding
from investo.briefing.fact_context import build_verified_fact_bundle
from investo.briefing.segments import build_segment_coverage
from investo.models.event_document import EditionAvailability, EventArticle, EventEditionDraft
from investo.models.event_evidence import make_evidence_document
from investo.models.items import NormalizedItem
from investo.models.segments import MarketSegment
from investo.publisher.public_document import PublicDocumentContext
from tests._helpers.event_context_v3 import DETAIL, FACT, NOW, TITLE, draft

TARGET = date(2026, 10, 10)


def native_case(segment: MarketSegment = "us-equity") -> tuple[NormalizedItem, EventEditionDraft]:
    evidence = make_evidence_document(
        source_name="official",
        title=TITLE,
        summary=FACT,
        detail_excerpt=DETAIL,
        url="https://example.com/one",
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    item = NormalizedItem(
        source_name="official",
        category="news",
        title=TITLE,
        summary=FACT,
        url="https://example.com/one",
        published_at=NOW,
        event_evidence=evidence,
        raw_metadata={"official_source": "true"},
    )
    documents = prepare_context_documents((item,), received_at=NOW)
    event = draft(documents[0])
    binding = canonical_event_binding(
        event, documents, (), observed_at=NOW, baseline_available=True
    )
    plan, bindings, _ = build_editorial_plan((event,), (binding,), documents, observed_at=NOW)
    article = EventArticle(
        event_id=binding.identity.event_id,
        headline="Acme Widget 실적 발표",
        what_changed="Acme가 Widget의 FY2026 실제 revenue 1200 USD를 발표했습니다.",
        fact_ids=tuple(f.fact_id for f in binding.facts),
        source_refs=tuple(
            dict.fromkeys(
                (
                    *event.actor_refs,
                    *event.action_refs,
                    *event.object_refs,
                    *(r for f in binding.facts for r in f.source_refs),
                )
            )
        ),
    )
    edition = EventEditionDraft(
        segment=segment,
        target_date=TARGET,
        availability=EditionAvailability(status="normal"),
        editorial_plan=plan,
        bindings=bindings,
        documents=documents,
        articles=(article,),
        support=(support_vector(event, documents, baseline_available=True),),
    )
    return item, edition


def native_context(*cases: tuple[NormalizedItem, EventEditionDraft]) -> PublicDocumentContext:
    items = {edition.segment: (item,) for item, edition in cases}
    segments = tuple(s for s in ("domestic-equity", "us-equity", "crypto") if s in items)
    return PublicDocumentContext(
        target_date=TARGET,
        expected_segments=segments,
        input_absences={},
        anchors_by_segment={s: () for s in segments},
        items_by_segment=items,
        coverage_by_segment={s: build_segment_coverage(s, items[s]) for s in segments},
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=build_verified_fact_bundle(tuple(item for item, _ in cases), TARGET, NOW),
        entity_observed_at_utc=NOW,
    )
