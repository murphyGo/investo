"""Source packets, claim-linked reader prose and private review records (u184-186)."""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictInt, model_validator

from investo.models.event_context import ContextRef, ReactionContext
from investo.models.event_identity import EntityBinding, FactBinding
from investo.models.events import Digest, EventId, EventModel

ARTICLE_POLICY = (
    "article-v2-20261027:literal-frame-hints:observation-reference:source-summary:"
    "literal-proof:explicit-linked-evidence:reported-metadata:review:600,900,600,900,600:3900"
)
ARTICLE_POLICY_HASH = sha256(ARTICLE_POLICY.encode()).hexdigest()
ARTICLE_FAILURE_CODES = frozenset(
    {
        "article.budget_exhausted",
        "article.prompt_budget_exhausted",
        "article.response_unavailable",
        "article.composition_invalid",
        "article.review_invalid",
        "article.content_not_ready",
        "article.repair_invalid",
    }
)


LocalId = Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
Refs = Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=64)]


class EvidencePassage(EventModel):
    passage_id: Digest
    document_id: Digest
    revision_id: Digest
    chunk_id: Digest
    source_locator: str
    text: Annotated[str, Field(strict=True, min_length=1, max_length=1200, repr=False)]
    text_sha256: Digest
    refs: Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=5)]

    @model_validator(mode="after")
    def exact_buffer(self) -> Self:
        if sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("article.passage_hash_mismatch")
        position = 0
        for ref in self.refs:
            if (
                (ref.document_id, ref.revision_id, ref.chunk_id)
                != (self.document_id, self.revision_id, self.chunk_id)
                or ref.start != position
                or ref.end > len(self.text)
            ):
                raise ValueError("article.passage_span_mismatch")
            position = ref.end
        if position != len(self.text):
            raise ValueError("article.passage_span_mismatch")
        return self


class ArticleQuestion(EventModel):
    question_id: Literal["what", "when", "why", "reaction"]
    text: Annotated[str, Field(strict=True, min_length=1, max_length=240)]
    required: bool = True


class EventEvidencePacket(EventModel):
    entities: Annotated[tuple[EntityBinding, ...], Field(max_length=16)] = ()
    event_id: EventId
    facts: Annotated[tuple[FactBinding, ...], Field(min_length=1, max_length=8)]
    required_fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    # Four source documents, each with six body passages and its original summary.
    passages: Annotated[tuple[EvidencePassage, ...], Field(max_length=28, repr=False)]
    allowed_refs: Refs
    questions: Annotated[tuple[ArticleQuestion, ...], Field(min_length=1, max_length=6)]
    expected_detail: bool = True

    @model_validator(mode="after")
    def coherent_packet(self) -> Self:
        if not set(self.required_fact_ids) <= {f.fact_id for f in self.facts}:
            raise ValueError("article.required_fact_missing")
        if len({(r.document_id, r.revision_id) for r in self.allowed_refs}) > 4:
            raise ValueError("article.source_limit")
        if len({q.question_id for q in self.questions}) != len(self.questions):
            raise ValueError("article.question_duplicate")
        for passage in self.passages:
            if not set(passage.refs) <= set(self.allowed_refs):
                raise ValueError("article.passage_unassigned")
        return self

    @property
    def packet_hash(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()


class NarrativeSentence(EventModel):
    sentence_id: LocalId
    text: Annotated[str, Field(strict=True, min_length=1, max_length=600)]
    claim_ids: Annotated[tuple[LocalId, ...], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def plain_sentence(self) -> Self:
        if not self.text.strip() or any(c in self.text for c in "\n\r<>"):
            raise ValueError("article.plain_text_required")
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("article.claim_duplicate")
        return self


class NarrativeBlock(EventModel):
    kind: Literal["paragraph", "bullets", "fact_table"] = "paragraph"
    sentences: Annotated[tuple[NarrativeSentence, ...], Field(max_length=24)] = ()
    fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def block_shape(self) -> Self:
        if self.kind == "fact_table":
            if self.sentences or not self.fact_ids or len(set(self.fact_ids)) != len(self.fact_ids):
                raise ValueError("article.invalid_fact_table")
        elif not self.sentences or self.fact_ids:
            raise ValueError("article.invalid_prose_block")
        return self


class ArticleNarrative(EventModel):
    blocks: Annotated[tuple[NarrativeBlock, ...], Field(min_length=1, max_length=8)]
    lead_sentence_id: LocalId
    headline_claim_ids: Annotated[tuple[LocalId, ...], Field(min_length=1, max_length=8)]

    @property
    def sentences(self) -> tuple[NarrativeSentence, ...]:
        return tuple(s for block in self.blocks for s in block.sentences)

    @property
    def lead(self) -> str:
        return next(s.text for s in self.sentences if s.sentence_id == self.lead_sentence_id)

    @model_validator(mode="after")
    def bounded_narrative(self) -> Self:
        sentences = self.sentences
        table_fact_ids = tuple(fact_id for block in self.blocks for fact_id in block.fact_ids)
        if len(set(table_fact_ids)) != len(table_fact_ids):
            raise ValueError("article.duplicate_fact_table_row")
        if (
            not 1 <= len(sentences) <= 24
            or len({s.sentence_id for s in sentences}) != len(sentences)
            or self.lead_sentence_id != sentences[0].sentence_id
            or sum(len(s.text) for s in sentences) > 3200
        ):
            raise ValueError("article.invalid_narrative")
        return self


class SentenceClaim(EventModel):
    # Expose the existing conditional requirements to the writer's JSON schema.
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "fact"}}},
                    "then": {"required": ["fact_ids"], "properties": {"fact_ids": {"minItems": 1}}},
                },
                {
                    "if": {"properties": {"kind": {"const": "attributed_explanation"}}},
                    "then": {
                        "required": ["attributed_actor_ref"],
                        "properties": {"attributed_actor_ref": {"not": {"type": "null"}}},
                    },
                },
                {
                    "if": {"properties": {"kind": {"const": "conditional_analysis"}}},
                    "then": {
                        "required": ["mechanism_refs", "assumption_refs"],
                        "properties": {
                            "mechanism_refs": {"minItems": 1},
                            "assumption_refs": {"minItems": 1},
                        },
                    },
                },
                {
                    "if": {"properties": {"kind": {"const": "observation"}}},
                    "then": {
                        "required": ["observation"],
                        "properties": {
                            "observation": {
                                "not": {"type": "null"},
                                "properties": {
                                    "status": {"const": "observed"},
                                    "attribution": {"const": "coincidence_only"},
                                },
                            }
                        },
                    },
                },
            ]
        }
    )
    claim_id: LocalId
    kind: Literal["fact", "attributed_explanation", "conditional_analysis", "observation"]
    fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()
    source_refs: Refs
    attributed_actor_ref: ContextRef | None = None
    mechanism_refs: Annotated[tuple[ContextRef, ...], Field(max_length=16)] = ()
    assumption_refs: Annotated[tuple[ContextRef, ...], Field(max_length=16)] = ()
    observation: ReactionContext | None = None

    @model_validator(mode="after")
    def typed_evidence(self) -> Self:
        if self.kind != "observation" and self.observation is not None:
            raise ValueError("article.observation_unbound")
        if self.kind == "fact" and not self.fact_ids:
            raise ValueError("article.fact_binding_required")
        if self.kind == "attributed_explanation" and self.attributed_actor_ref is None:
            raise ValueError("article.attribution_required")
        if self.kind == "conditional_analysis" and (
            not self.mechanism_refs or not self.assumption_refs
        ):
            raise ValueError("article.condition_required")
        if self.kind == "observation" and (
            self.observation is None
            or self.observation.status != "observed"
            or self.observation.attribution != "coincidence_only"
        ):
            raise ValueError("article.observation_required")
        extra = (*self.mechanism_refs, *self.assumption_refs)
        if self.attributed_actor_ref is not None:
            extra += (self.attributed_actor_ref,)
        if not set(extra) <= set(self.source_refs):
            raise ValueError("article.unassigned_evidence")
        return self


class QuestionAnswer(EventModel):
    question_id: Literal["what", "when", "why", "reaction"]
    sentence_ids: Annotated[tuple[LocalId, ...], Field(max_length=24)] = ()


class ArticleComposition(EventModel):
    event_id: EventId
    headline: Annotated[str, Field(strict=True, min_length=1, max_length=120)]
    narrative: ArticleNarrative
    claims: Annotated[tuple[SentenceClaim, ...], Field(min_length=1, max_length=24)]
    answers: Annotated[tuple[QuestionAnswer, ...], Field(min_length=1, max_length=6)]
    packet_hash: Digest

    @model_validator(mode="after")
    def exact_claim_coverage(self) -> Self:
        ids = {c.claim_id for c in self.claims}
        used = {c for s in self.narrative.sentences for c in s.claim_ids}
        if (
            len(ids) != len(self.claims)
            or ids != used
            or not set(self.narrative.headline_claim_ids) <= ids
            or len({a.question_id for a in self.answers}) != len(self.answers)
            or any(
                not set(a.sentence_ids) <= {s.sentence_id for s in self.narrative.sentences}
                for a in self.answers
            )
        ):
            raise ValueError("article.claim_coverage_invalid")
        return self

    @property
    def draft_hash(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()


class ArticleCompositionBatch(EventModel):
    articles: Annotated[tuple[ArticleComposition, ...], Field(min_length=1, max_length=5)]


class ClaimReview(EventModel):
    claim_id: LocalId
    verdict: Literal["supported", "contradicted", "insufficient"]
    source_refs: Refs
    reason: Literal[
        "supported",
        "missing_evidence",
        "meaning_changed",
        "condition_missing",
        "attribution_changed",
        "unsupported_clause",
        "causality",
        "time_changed",
    ]


class QuestionReview(EventModel):
    question_id: Literal["what", "when", "why", "reaction"]
    verdict: Literal["answered", "missing", "not_applicable"]


class ArticleReview(EventModel):
    event_id: EventId
    draft_hash: Digest
    packet_hash: Digest
    claims: Annotated[tuple[ClaimReview, ...], Field(min_length=1, max_length=24)]
    questions: Annotated[tuple[QuestionReview, ...], Field(min_length=1, max_length=6)]


class ArticleReviewBatch(EventModel):
    articles: Annotated[tuple[ArticleReview, ...], Field(min_length=1, max_length=5)]


class ArticleReadiness(EventModel):
    composition: ArticleComposition
    packet: EventEvidencePacket = Field(repr=False)
    review: ArticleReview
    policy_hash: Digest
    state: Literal["detailed_ready", "brief_ready"]

    @model_validator(mode="after")
    def bound_review(self) -> Self:
        if (self.state == "detailed_ready") != self.packet.expected_detail:
            raise ValueError("article.readiness_mismatch")
        if (
            self.review.event_id != self.composition.event_id
            or self.packet.event_id != self.composition.event_id
            or self.review.draft_hash != self.composition.draft_hash
            or self.review.packet_hash != self.packet.packet_hash
            or self.composition.packet_hash != self.packet.packet_hash
        ):
            raise ValueError("article.stale_review")
        return self


class ArticleGenerationTrace(EventModel):
    calls: Annotated[StrictInt, Field(ge=1, le=5)]
    prompt_bytes: Annotated[
        tuple[Annotated[StrictInt, Field(ge=0, le=98304)], ...], Field(max_length=5)
    ]
    response_bytes: Annotated[
        tuple[Annotated[StrictInt, Field(ge=0, le=131072)], ...], Field(max_length=5)
    ]
    stage_elapsed_s: Annotated[
        tuple[Annotated[float, Field(ge=0, allow_inf_nan=False)], ...], Field(max_length=5)
    ]

    @model_validator(mode="after")
    def complete_trace(self) -> Self:
        if (
            len(self.prompt_bytes) != self.calls
            or len(self.response_bytes) != self.calls
            or len(self.stage_elapsed_s) != self.calls
        ):
            raise ValueError("article.trace_incomplete")
        return self
