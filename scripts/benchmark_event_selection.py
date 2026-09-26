"""Synthetic NF3 benchmark: 1000 inputs, bounded deterministic event pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from time import perf_counter

from investo.briefing.event_evidence import (
    build_event_candidates,
    make_evidence_document,
    prepare_evidence_documents,
    resolve_evidence_ref,
)
from investo.briefing.event_input import select_event_input_items
from investo.briefing.event_narrative import assemble_event_synthesis, parse_event_synthesis
from investo.briefing.event_selection import select_events
from investo.models import NormalizedItem
from investo.models.event_narratives import (
    EventGenerationPayload,
    EventMeaning,
    EventNarrative,
    EventReaction,
    Stage2OutputV2,
    Stage2Sections,
)
from investo.models.events import EventCandidateDraft, EventFactDraft, EvidenceDocument, EvidenceRef
from investo.publisher.event_blocks import event_hard_issue_codes, terminal_events


def benchmark() -> dict[str, object]:
    observed = datetime(2026, 9, 27, 12, tzinfo=UTC)
    rows: list[NormalizedItem] = []
    for i in range(1000):
        is_news = i >= 950
        doc = make_evidence_document(
            source_name=f"news-{i % 4}" if is_news else f"price-{i % 6}",
            title=f"Company{i} launches Product{i}",
            summary=f"Product{i} is available.",
            url=f"https://example.invalid/{i}",
            published_at=observed - timedelta(hours=1),
            received_at=observed,
            event_time=observed.date(),
            event_time_basis="source_date",
        )
        rows.append(
            NormalizedItem(
                source_name=doc.source_name,
                title=doc.title,
                summary=doc.summary,
                url=doc.url,
                published_at=doc.published_at,
                category="news" if is_news else "price",
                event_evidence=doc,
            )
        )

    def run_once() -> tuple[int, int]:
        items = select_event_input_items(rows, target_date=observed.date())
        documents = prepare_evidence_documents(items, received_at=observed)
        drafts: list[EventCandidateDraft] = []
        for index, (item, doc) in enumerate(zip(items, documents, strict=True), 1):
            if item.category != "news" or len(drafts) >= 12:
                continue
            actor, _, product = doc.title.split()

            def ref(text: str, field: str = "title", doc: EvidenceDocument = doc) -> EvidenceRef:
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

            drafts.append(
                EventCandidateDraft(
                    item_ids=(index,),
                    event_kind="product_service",
                    actor_refs=(ref(actor),),
                    action_refs=(ref("launches"),),
                    object_refs=(ref(product),),
                    relation_refs=(ref(actor),),
                    impact_refs=(ref(actor),),
                    timing="announced",
                    relation="direct",
                    impact="company",
                    facts=(
                        EventFactDraft(
                            predicate="launch", evidence_ref=ref(doc.summary, "summary")
                        ),
                    ),
                )
            )
        candidates = build_event_candidates(drafts, items, documents, observed_at=observed)
        plan = select_events(
            candidates,
            documents,
            segment="us-equity",
            window_start=observed - timedelta(days=1),
            window_end=observed,
        )
        narratives = tuple(
            EventNarrative(
                event_id=event.event_id,
                headline=resolve_evidence_ref(event.actor_refs[0], plan.evidence_documents),
                what_happened=(
                    resolve_evidence_ref(event.actor_refs[0], plan.evidence_documents)
                    + "는 "
                    + resolve_evidence_ref(event.object_refs[0], plan.evidence_documents)
                    + "를 출시했습니다."
                ),
                fact_ids=event.required_fact_ids,
                source_refs=event.evidence_refs,
                meaning=EventMeaning(text=None, mode="unavailable"),
                reaction=EventReaction(text=None, status="unavailable"),
            )
            for event in plan.selected
        )
        output = Stage2OutputV2(
            schema_version=2,
            sections=Stage2Sections(
                market_summary="합성 성능 검증용 발표입니다.",
                sector_flow="추가 자료는 확인하지 못했습니다.",
                indicators_events="추가 일정은 확인하지 못했습니다.",
                notable_tickers="추가 기업 자료는 확인하지 못했습니다.",
                today_watch="공식 후속 발표를 확인합니다.",
            ),
            events=narratives,
        )
        parsed = parse_event_synthesis(output.model_dump_json(), plan)
        markdown = assemble_event_synthesis(parsed, plan)
        payload = EventGenerationPayload(plan=plan, narratives=parsed.events)
        if event_hard_issue_codes(markdown, payload) or len(
            terminal_events(markdown, payload)
        ) != len(plan.selected):
            raise ValueError("synthetic event validation failed")
        return len(items), len(plan.selected)

    run_once()
    timings = []
    for _ in range(10):
        started = perf_counter()
        candidate_count, selected_count = run_once()
        timings.append((perf_counter() - started) * 1000)
    # Nearest-rank p95 for ten observations is the maximum.
    p95 = max(timings)
    return {
        "input_count": 1000,
        "candidate_count": candidate_count,
        "selected_count": selected_count,
        "iterations": 10,
        "scope": "selection, v2 parser, event renderer and terminal validation",
        "p95_ms": round(p95, 3),
        "limit_ms": 200,
        "passed": p95 <= 200,
    }


if __name__ == "__main__":
    result = benchmark()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
