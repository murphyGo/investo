"""Synthetic claim-grounded prose, separate from actual/human acceptance."""

from investo._internal.event_article_packet import build_article_packets
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import prepare_context_documents, support_vector
from investo.briefing.event_identity import canonical_event_binding
from investo.models.event_article import (
    ARTICLE_POLICY_HASH,
    ArticleComposition,
    ArticleNarrative,
    ArticleReadiness,
    ArticleReview,
    ClaimReview,
    NarrativeBlock,
    NarrativeSentence,
    QuestionAnswer,
    QuestionReview,
    SentenceClaim,
)
from investo.models.event_document import EventArticle, EventEditionDraft
from investo.models.event_evidence import make_evidence_document
from tests._helpers.event_context_v3 import NOW, ref
from tests._helpers.event_context_v3 import draft as source_draft
from tests._helpers.event_document_v3 import native_case


def article_case(market="us-equity", detail=None, impact="company", actor="Acme"):
    item, old = native_case(market)
    if actor != "Acme":
        from pydantic import HttpUrl

        item = item.model_copy(
            update={
                "title": item.title.replace("Acme", actor),
                "summary": item.summary.replace("Acme", actor),
                "url": HttpUrl(f"https://example.com/{actor.casefold()}"),
            }
        )
    body = detail or f"{actor} explained that Widget revenue reflects expanded service access."
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary,
        detail_excerpt=body,
        url=str(item.url),
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    item = item.model_copy(update={"event_evidence": evidence})
    docs = prepare_context_documents((item,), received_at=NOW, article_passages=True)
    if actor == "Acme":
        event = source_draft(docs[0]).model_copy(update={"impact": impact})
    else:
        from investo._internal.event_context import resolve_context_ref
        from investo.models.event_context import ContextEventDraft, ContextRef

        def translate(value):
            if isinstance(value, dict):
                if set(value) == {"document_id", "revision_id", "chunk_id", "start", "end"}:
                    literal = resolve_context_ref(
                        ContextRef.model_validate(value), old.documents
                    ).replace("Acme", actor)
                    return ref(docs[0], literal).model_dump(mode="json")
                return {key: translate(child) for key, child in value.items()}
            if isinstance(value, list):
                return [translate(child) for child in value]
            return value

        template = old.editorial_plan.events[0].source_event.model_dump(mode="json")
        for field in (
            "meaning_refs",
            "reaction_refs",
            "background_refs",
            "comparison_refs",
            "follow_up_refs",
        ):
            template[field] = []
        event = ContextEventDraft.model_validate({**translate(template), "impact": impact})
    binding = canonical_event_binding(event, docs, (), observed_at=NOW, baseline_available=True)
    plan, bindings, _ = build_editorial_plan((event,), (binding,), docs, observed_at=NOW)
    packet = build_article_packets(plan, bindings, docs)[0]
    plan = plan.model_copy(
        update={
            "events": (plan.events[0].model_copy(update={"assigned_refs": packet.allowed_refs}),)
        }
    )
    first = NarrativeSentence(
        sentence_id="lead",
        text=f"{actor}가 Widget의 FY2026 실제 revenue 1200 USD를 발표했습니다.",
        claim_ids=("core",),
    )
    why = NarrativeSentence(
        sentence_id="scope",
        text=f"{actor}는 Widget의 revenue에 서비스 접근 범위 확대가 반영됐다고 설명했습니다.",
        claim_ids=("context",),
    )
    narrative = ArticleNarrative(
        blocks=(NarrativeBlock(sentences=(first,)), NarrativeBlock(sentences=(why,))),
        lead_sentence_id="lead",
        headline_claim_ids=("core",),
    )
    core_refs = tuple(
        dict.fromkeys(
            (
                *event.actor_refs,
                *event.action_refs,
                *event.object_refs,
                *(r for f in binding.facts for r in f.source_refs),
            )
        )
    )
    context_refs = tuple(dict.fromkeys((ref(docs[0], actor), *packet.passages[0].refs)))
    composition = ArticleComposition(
        event_id=packet.event_id,
        headline=f"{actor} Widget 실적 발표",
        narrative=narrative,
        claims=(
            SentenceClaim(
                claim_id="core",
                kind="fact",
                fact_ids=packet.required_fact_ids,
                source_refs=core_refs,
            ),
            SentenceClaim(
                claim_id="context",
                kind="attributed_explanation",
                source_refs=context_refs,
                attributed_actor_ref=ref(docs[0], actor),
            ),
        ),
        answers=tuple(
            QuestionAnswer(
                question_id=q.question_id,
                sentence_ids=("scope",)
                if q.question_id == "why"
                else ()
                if q.question_id == "reaction"
                else ("lead",),
            )
            for q in packet.questions
        ),
        packet_hash=packet.packet_hash,
    )
    review = ArticleReview(
        event_id=packet.event_id,
        draft_hash=composition.draft_hash,
        packet_hash=packet.packet_hash,
        claims=tuple(
            ClaimReview(
                claim_id=c.claim_id,
                verdict="supported",
                source_refs=c.source_refs,
                reason="supported",
            )
            for c in composition.claims
        ),
        questions=tuple(
            QuestionReview(
                question_id=q.question_id,
                verdict="answered" if q.required or q.question_id == "why" else "not_applicable",
            )
            for q in packet.questions
        ),
    )
    ready = ArticleReadiness(
        composition=composition,
        packet=packet,
        review=review,
        policy_hash=ARTICLE_POLICY_HASH,
        state="detailed_ready" if packet.expected_detail else "brief_ready",
    )
    article = EventArticle(
        content_contract_version=2,
        event_id=packet.event_id,
        headline=composition.headline,
        what_changed=narrative.lead,
        fact_ids=packet.required_fact_ids,
        source_refs=packet.allowed_refs,
        narrative=narrative,
    )
    result = EventEditionDraft.model_validate(
        {
            **old.model_dump(),
            "content_contract_version": 2,
            "articles": (article,),
            "documents": docs,
            "editorial_plan": plan,
            "bindings": bindings,
            "support": (support_vector(event, docs, baseline_available=True),),
            "article_readiness": (ready,),
        }
    )
    return item, result, composition, review
