"""Pure claim and exact-review invariants shared by generator and finalizer."""

from __future__ import annotations

import re
from datetime import datetime

from investo._internal.event_context import resolve_context_ref
from investo.models.event_article import ArticleComposition, ArticleReview, EventEvidencePacket
from investo.models.event_context import ContextRef
from investo.models.event_document import EventEditionDraft


def validate_composition(
    composition: ArticleComposition,
    packet: EventEvidencePacket,
    draft: EventEditionDraft,
    *,
    observed_at: datetime,
) -> None:
    """Refs/atoms are hard checks; Korean entailment needs a separate review."""
    from investo._internal.event_v3_contract import validate_claim, validate_fact_roles

    if composition.event_id != packet.event_id or composition.packet_hash != packet.packet_hash:
        raise ValueError("article.packet_mismatch")
    plan = next(p for p in draft.editorial_plan.events if p.event_id == packet.event_id)
    binding = next(b for b in draft.bindings if b.identity.event_id == packet.event_id)
    if (
        packet.facts != binding.facts
        or packet.entities != binding.entities
        or packet.required_fact_ids != plan.required_fact_ids
    ):
        raise ValueError("article.fact_mismatch")
    owners = {
        (draft.documents[i - 1].document_id, draft.documents[i - 1].revision_id)
        for i in plan.source_event.item_ids
    }
    for ref in packet.allowed_refs:
        if (ref.document_id, ref.revision_id) not in owners:
            raise ValueError("article.evidence_owner_mismatch")
        resolve_context_ref(ref, draft.documents)
    for passage in packet.passages:
        literal = "".join(resolve_context_ref(ref, draft.documents) for ref in passage.refs)
        if literal != passage.text:
            raise ValueError("article.passage_mismatch")
    facts = {f.fact_id: f for f in packet.facts}
    claims = {claim.claim_id: claim for claim in composition.claims}
    covered = {fact_id for claim in claims.values() for fact_id in claim.fact_ids}
    if not set(packet.required_fact_ids) <= covered:
        raise ValueError("article.required_fact_missing")
    for claim in claims.values():
        if (
            not set(claim.source_refs) <= set(packet.allowed_refs)
            or not set(claim.fact_ids) <= facts.keys()
        ):
            raise ValueError("article.unassigned_evidence")
        if any(
            not set(facts[fact_id].source_refs) <= set(claim.source_refs)
            for fact_id in claim.fact_ids
        ):
            raise ValueError("article.fact_proof_missing")
        if claim.kind == "observation":
            observation = claim.observation
            assert observation is not None
            if (
                not set(observation.refs) <= set(claim.source_refs)
                or observation.baseline_ref not in observation.refs
                or observation.value_ref not in observation.refs
            ):
                raise ValueError("article.observation_unbound")
            proof = " ".join(resolve_context_ref(r, draft.documents) for r in observation.refs)
            if observation.observed_at is None or observation.observed_at > observed_at:
                raise ValueError("article.observation_unbound")
            if observation.asset_id is None or observation.asset_id not in proof:
                raise ValueError("article.observation_unbound")
            for stamp in (
                observation.window_start,
                observation.window_end,
                observation.observed_at,
            ):
                if stamp is None or not any(
                    value in proof
                    for value in (stamp.isoformat(), stamp.isoformat().replace("+00:00", "Z"))
                ):
                    raise ValueError("article.observation_unbound")

            def observed_unit(ref: ContextRef) -> str | None:
                doc = next(
                    d
                    for d in draft.documents
                    if (d.document_id, d.revision_id) == (ref.document_id, ref.revision_id)
                )
                chunk = next(c for c in doc.chunks if c.chunk_id == ref.chunk_id)
                literal = chunk.text[ref.start : min(len(chunk.text), ref.end + 16)]
                match = re.match(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?\s*(%|[A-Z]{3}\b)", literal)
                return match.group(1) if match else None

            baseline_unit = observed_unit(observation.baseline_ref)
            if baseline_unit is None or baseline_unit != observed_unit(observation.value_ref):
                raise ValueError("article.observation_unbound")
    for sentence in composition.narrative.sentences:
        refs = tuple(
            dict.fromkeys(
                r for claim_id in sentence.claim_ids for r in claims[claim_id].source_refs
            )
        )
        validate_claim(sentence.text, refs, draft)
        validate_fact_roles(
            sentence.text,
            binding,
            plan.source_event,
            draft.documents,
            check_actions=False,
        )
        for claim_id in sentence.claim_ids:
            claim = claims[claim_id]
            if claim.kind == "conditional_analysis" and not re.search(
                r"경우|라면|한다면|전제|조건|가능성", sentence.text
            ):
                raise ValueError("article.condition_missing")
            if claim.kind == "attributed_explanation":
                assert claim.attributed_actor_ref is not None
                actor = resolve_context_ref(claim.attributed_actor_ref, draft.documents)
                if actor not in sentence.text or not re.search(
                    r"설명|밝혔|언급|따르면|평가|말했|전했|주장|명시(?:돼|되|됐|했)|기재(?:돼|되|됐|했)",
                    sentence.text,
                ):
                    raise ValueError("article.attribution_missing")
            if claim.kind == "observation":
                if "인과관계는 확인되지" not in sentence.text:
                    raise ValueError("article.causality_unbound")
                if claim.observation is None or claim.observation.text != sentence.text:
                    raise ValueError("article.observation_unbound")
    headline_refs = tuple(
        dict.fromkeys(
            r for c in composition.narrative.headline_claim_ids for r in claims[c].source_refs
        )
    )
    validate_claim(composition.headline, headline_refs, draft)
    validate_fact_roles(
        composition.headline,
        binding,
        plan.source_event,
        draft.documents,
        check_actions=False,
    )
    if set(a.question_id for a in composition.answers) != {q.question_id for q in packet.questions}:
        raise ValueError("article.question_mismatch")
    for block in composition.narrative.blocks:
        if not set(block.fact_ids) <= facts.keys():
            raise ValueError("article.fact_table_unbound")


def review_gaps(
    composition: ArticleComposition,
    packet: EventEvidencePacket,
    review: ArticleReview,
) -> tuple[str, ...]:
    """Validate a complete review before interpreting supported/coverage results."""
    if (
        review.event_id != composition.event_id
        or review.draft_hash != composition.draft_hash
        or review.packet_hash != packet.packet_hash
    ):
        raise ValueError("article.stale_review")
    claims = {c.claim_id: c for c in composition.claims}
    if len(review.claims) != len(claims) or {r.claim_id for r in review.claims} != set(claims):
        raise ValueError("article.review_coverage_invalid")
    questions = {q.question_id: q for q in packet.questions}
    if len(review.questions) != len(questions) or {q.question_id for q in review.questions} != set(
        questions
    ):
        raise ValueError("article.review_coverage_invalid")
    gaps = []
    for result in review.claims:
        if not set(result.source_refs) <= set(claims[result.claim_id].source_refs):
            raise ValueError("article.review_evidence_invalid")
        if (result.verdict == "supported") != (result.reason == "supported"):
            raise ValueError("article.review_verdict_invalid")
        if result.verdict != "supported":
            gaps.append("claim:" + result.claim_id + ":" + result.reason)
    answers = {answer.question_id: answer for answer in composition.answers}
    for question_result in review.questions:
        if (
            questions[question_result.question_id].required
            or answers[question_result.question_id].sentence_ids
        ) and (
            question_result.verdict != "answered"
            or not answers[question_result.question_id].sentence_ids
        ):
            gaps.append("question:" + question_result.question_id)
        elif (
            question_result.verdict == "answered"
            and not answers[question_result.question_id].sentence_ids
        ):
            raise ValueError("article.review_answer_unbound")
    return tuple(gaps)


def validate_terminal_articles(draft: EventEditionDraft, *, observed_at: datetime) -> None:
    from investo._internal.event_article_packet import build_article_packets
    from investo.models.event_article import ARTICLE_POLICY_HASH

    expected_packets = build_article_packets(draft.editorial_plan, draft.bindings, draft.documents)
    if tuple(r.packet for r in draft.article_readiness) != expected_packets:
        raise ValueError("article.packet_mismatch")
    if tuple(r.composition.event_id for r in draft.article_readiness) != tuple(
        a.event_id for a in draft.articles
    ):
        raise ValueError("article.readiness_missing")
    for article, readiness in zip(draft.articles, draft.article_readiness, strict=True):
        if (
            article.narrative != readiness.composition.narrative
            or article.headline != readiness.composition.headline
            or article.what_changed != readiness.composition.narrative.lead
            or readiness.policy_hash != ARTICLE_POLICY_HASH
            or set(article.fact_ids) != set(readiness.packet.required_fact_ids)
            or set(article.source_refs) != set(readiness.packet.allowed_refs)
        ):
            raise ValueError("article.stale_review")
        validate_composition(
            readiness.composition, readiness.packet, draft, observed_at=observed_at
        )
        if review_gaps(readiness.composition, readiness.packet, readiness.review):
            raise ValueError("article.content_not_ready")
