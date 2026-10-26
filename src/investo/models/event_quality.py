"""Nullable event measurements; private traces never enter public serialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    computed_field,
    model_serializer,
    model_validator,
)

from investo.models.event_context import EventSupportVector
from investo.models.event_document import EditionNewsWindow
from investo.models.events import Digest, EventId, EventModel
from investo.models.segments import MarketSegment

EventStage = Literal[
    "collected",
    "routed",
    "candidate",
    "classified",
    "selected",
    "prompted",
    "generated",
    "finalized",
    "published",
    "summary",
    "structure_checked",
]
EventCoverageState = Literal[
    "hard_trust_blocked",
    "classification_unavailable",
    "finalization_unavailable",
    "source_limited",
    "detail_limited",
    "no_qualifying_event",
    "qualified",
]
EventReason = Literal[
    "source_unavailable",
    "outside_window",
    "routing_rejected",
    "candidate_cap",
    "low_importance",
    "duplicate",
    "background",
    "evidence_conflict",
    "budget_deferred",
    "classification_unavailable",
    "llm_omitted",
    "detail_limited",
    "finalization_removed",
    "published",
    "hard_trust_blocked",
    "finalization_unavailable",
    "source_limited",
    "no_qualifying_event",
    "qualified",
]
Count = Annotated[int, Field(strict=True, ge=0)]
EventCount = Annotated[int, Field(strict=True, ge=0, le=5)]
EventIssueCode = Literal[
    "event.narrative_invalid",
    "event.selection_mismatch",
    "event.fact_unsupported",
    "event.entity_unsupported",
    "event.evidence_invalid",
    "event.summary_reexposure",
    "event.terminal_mismatch",
    "event.seal_mismatch",
    "event.stage_receipt_invalid",
]
_STATE_PRIORITY: tuple[EventCoverageState, ...] = (
    "hard_trust_blocked",
    "classification_unavailable",
    "finalization_unavailable",
    "source_limited",
    "detail_limited",
    "no_qualifying_event",
    "qualified",
)


class EventTraceEntry(EventModel):
    hash_id: Annotated[str, Field(strict=True, pattern=r"^(?:[0-9a-f]{24}|[0-9a-f]{64})$")]
    stage: EventStage
    reason: EventReason | None = None
    source_name: Annotated[str, Field(strict=True, pattern=r"^[a-zA-Z0-9_-]{1,80}$")] | None = None


class EventStageReceipt(EventModel):
    stage: EventStage
    status: Literal["completed", "failed", "not_run"]
    count: Count | None = None
    trace: Annotated[tuple[EventTraceEntry, ...], Field(max_length=1000)] = ()

    @model_validator(mode="after")
    def completed_counts_only(self) -> Self:
        if self.status != "completed" and self.count is not None:
            raise ValueError("uncompleted event stage must have unknown count")
        if any(entry.stage != self.stage for entry in self.trace):
            raise ValueError("event trace stage must match receipt")
        return self


class EventQualityAxes(EventModel):
    """Separate v3 axis observations; never relabel the v2 qualified counter."""

    schema_version: Literal[3] = 3
    vectors: Annotated[tuple[EventSupportVector, ...], Field(max_length=5)] | None = None


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator else None


class EventCoverage(EventModel):
    collected_candidate_count: Count | None = None
    selected_count: EventCount | None = None
    prompted_count: EventCount | None = None
    terminal_event_count: EventCount | None = None
    qualified_event_count: EventCount | None = None
    details_limited_count: EventCount | None = None
    summary_event_count: Annotated[int, Field(strict=True, ge=0, le=3)] | None = None
    omitted_count: EventCount | None = None
    unsupported_count: EventCount | None = None
    state: EventCoverageState | None = None
    reasons: Annotated[tuple[EventReason, ...], Field(max_length=20)] = ()
    issue_codes: Annotated[tuple[EventIssueCode, ...], Field(max_length=9)] = ()
    receipts: Annotated[tuple[EventStageReceipt, ...], Field(max_length=32, exclude=True)] = ()

    @model_validator(mode="after")
    def coherent_counts(self) -> Self:
        selected, terminal = self.selected_count, self.terminal_event_count
        for child, parent in (
            (self.prompted_count, selected),
            (terminal, selected),
            (self.qualified_event_count, terminal),
            (self.details_limited_count, terminal),
            (self.summary_event_count, terminal),
        ):
            if child is not None and parent is not None and child > parent:
                raise ValueError("event child count exceeds observed parent")
        if (
            terminal is not None
            and self.qualified_event_count is not None
            and self.details_limited_count is not None
            and self.qualified_event_count + self.details_limited_count > terminal
        ):
            raise ValueError("qualified and limited events must be disjoint")
        omitted = selected - terminal if selected is not None and terminal is not None else None
        if self.omitted_count is not None and self.omitted_count != omitted:
            raise ValueError("event omission requires known matching counts")
        object.__setattr__(self, "omitted_count", omitted)
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        return self

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        states = set(self.reasons) & set(_STATE_PRIORITY)
        if "source_unavailable" in self.reasons:
            states.add("source_limited")
        if self.issue_codes or self.unsupported_count:
            states.add("hard_trust_blocked")
        if self.state is not None:
            states.add(self.state)
        required = next((state for state in _STATE_PRIORITY if state in states), None)
        if self.state != required:
            raise ValueError("event coverage state contradicts observed reasons or issues")
        if self.state == "hard_trust_blocked" and any(
            value is not None
            for value in (
                self.terminal_event_count,
                self.qualified_event_count,
                self.details_limited_count,
                self.summary_event_count,
            )
        ):
            raise ValueError("hard-blocked event terminal counts must remain unknown")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def selection_coverage(self) -> float | None:
        return _ratio(self.terminal_event_count, self.selected_count)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qualified_coverage(self) -> float | None:
        return (
            _ratio(self.qualified_event_count, self.selected_count)
            if self.terminal_event_count is not None
            else None
        )


class PublishedEventCoverage(EventModel):
    """Post-push aggregate only; never persisted in the precommit history row."""

    basis: Literal["remote_confirmed"] = "remote_confirmed"
    included_segments: tuple[MarketSegment, ...] = ()
    excluded_segments: tuple[MarketSegment, ...] = ()
    selected_count: Count | None = None
    terminal_event_count: Count | None = None
    qualified_event_count: Count | None = None

    @model_validator(mode="after")
    def coherent_aggregate(self) -> Self:
        included, excluded = set(self.included_segments), set(self.excluded_segments)
        if (
            included & excluded
            or len(included) != len(self.included_segments)
            or len(excluded) != len(self.excluded_segments)
        ):
            raise ValueError("aggregate segments must be unique and disjoint")
        counts = (self.selected_count, self.terminal_event_count, self.qualified_event_count)
        if not included and any(count is not None for count in counts):
            raise ValueError("empty published aggregate must remain unknown")
        if included and any(count is None for count in counts):
            raise ValueError("published aggregate requires known counts")
        if (
            self.selected_count is not None
            and self.terminal_event_count is not None
            and self.qualified_event_count is not None
            and not self.qualified_event_count <= self.terminal_event_count <= self.selected_count
        ):
            raise ValueError("aggregate child counts exceed parent")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def selection_coverage(self) -> float | None:
        return _ratio(self.terminal_event_count, self.selected_count)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qualified_coverage(self) -> float | None:
        return _ratio(self.qualified_event_count, self.selected_count)


def aggregate_published_event_coverage(
    coverages: Mapping[MarketSegment, EventCoverage | None],
    *,
    remote_confirmed_segments: Sequence[MarketSegment],
) -> PublishedEventCoverage:
    """Include only confirmed, measured segments, independent of notification results."""
    confirmed = set(remote_confirmed_segments)
    included: list[MarketSegment] = []
    excluded: list[MarketSegment] = []
    counts = [0, 0, 0]
    for segment in sorted(set(coverages) | confirmed):
        coverage = coverages.get(segment)
        if coverage is not None:
            # model_copy/model_construct bypass Pydantic validation. The public
            # aggregation boundary must revalidate before trusting any numbers.
            try:
                coverage = EventCoverage.model_validate(
                    {
                        name: getattr(coverage, name)
                        for name in EventCoverage.model_fields
                        if name != "receipts"
                    }
                )
            except ValidationError:
                coverage = None
        if (
            segment not in confirmed
            or coverage is None
            or coverage.state
            in (
                None,
                "hard_trust_blocked",
                "classification_unavailable",
                "finalization_unavailable",
            )
            or coverage.selected_count is None
            or coverage.terminal_event_count is None
            or coverage.qualified_event_count is None
        ):
            excluded.append(segment)
            continue
        included.append(segment)
        counts[0] += coverage.selected_count
        counts[1] += coverage.terminal_event_count
        counts[2] += coverage.qualified_event_count
    return PublishedEventCoverage(
        included_segments=tuple(included),
        excluded_segments=tuple(excluded),
        selected_count=counts[0] if included else None,
        terminal_event_count=counts[1] if included else None,
        qualified_event_count=counts[2] if included else None,
    )


def parse_public_event_coverage(value: object) -> dict[MarketSegment, EventCoverage] | None:
    """Read optional public metadata without coercing absent/corrupt data into zeros."""
    if not isinstance(value, dict):
        return None
    result: dict[MarketSegment, EventCoverage] = {}
    for segment, raw in value.items():
        if segment not in ("domestic-equity", "us-equity", "crypto") or not isinstance(raw, dict):
            return None
        data = dict(raw)
        rates = {
            name: data.pop(name)
            for name in ("selection_coverage", "qualified_coverage")
            if name in data
        }
        if "receipts" in data:
            return None
        try:
            coverage = EventCoverage.model_validate(data)
        except ValidationError:
            return None
        if any(
            isinstance(value, bool) or value != getattr(coverage, name)
            for name, value in rates.items()
        ):
            return None
        result[segment] = coverage
    return result


GitSha = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
SemanticCode = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")]
SemanticId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,95}$")]


class EventSemanticAnnotation(EventModel):
    content_contract_version: Literal[1, 2] = 1
    article_policy_hash: Digest | None = None
    expected_detailed_event_ids: tuple[EventId, ...] = ()
    case_id: SemanticId
    segment: MarketSegment
    document_schema: Literal[3] = 3
    origin: Literal["synthetic_oracle", "real_human_annotation"]
    reviewed_code_sha: GitSha
    remote_data_baseline_sha: GitSha
    target_date: date
    news_window: EditionNewsWindow | None = None
    source_availability: Literal["normal", "source_limited", "unknown"]
    news_rich: bool = False
    expected_event_ids: Annotated[tuple[EventId, ...], Field(max_length=5)] = ()
    expected_story_ids: tuple[Digest, ...] = ()
    must_include: Annotated[tuple[EventId, ...], Field(max_length=5)] = ()
    required_fact_ids: tuple[Digest, ...] = ()
    forbidden_claims: tuple[SemanticCode, ...] = ()
    allowed_uncertainty: tuple[SemanticCode, ...] = ()
    expected_support: Annotated[tuple[EventSupportVector, ...], Field(max_length=5)] = ()
    expected_outcome: Literal[
        "normal", "quiet", "source_limited", "trust_blocked", "generation_failed"
    ]
    external_baseline_event_ids: Annotated[tuple[EventId, ...], Field(max_length=96)] | None = None

    @model_validator(mode="after")
    def oracle_identity(self) -> Self:
        from investo.models.event_article import ARTICLE_POLICY_HASH

        if (
            self.content_contract_version == 2 and self.article_policy_hash != ARTICLE_POLICY_HASH
        ) or (self.content_contract_version == 1 and self.article_policy_hash is not None):
            raise ValueError("semantic.article_policy_invalid")
        for values in (
            self.expected_event_ids,
            self.expected_story_ids,
            self.must_include,
            self.required_fact_ids,
            self.external_baseline_event_ids or (),
        ):
            if len(set(values)) != len(values):
                raise ValueError("semantic.annotation_invalid")
        if not set(self.expected_detailed_event_ids) <= set(self.expected_event_ids):
            raise ValueError("semantic.detailed_event_invalid")
        if (
            self.content_contract_version == 2
            and self.news_rich
            and not self.expected_detailed_event_ids
        ):
            raise ValueError("semantic.detailed_event_required")
        if not set(self.must_include) <= set(self.expected_event_ids):
            raise ValueError("semantic.annotation_invalid")
        return self

    @model_serializer(mode="wrap")
    def versioned_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if self.content_contract_version == 1:
            data.pop("content_contract_version", None)
            data.pop("article_policy_hash", None)
            data.pop("expected_detailed_event_ids", None)
        return data

    @property
    def annotation_sha256(self) -> str:
        import json
        from hashlib import sha256

        return sha256(
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()


class SemanticEventScore(EventModel):
    event_id: EventId
    what: Annotated[int, Field(strict=True, ge=0, le=1)]
    when: Annotated[int, Field(strict=True, ge=0, le=1)]
    why: Annotated[int, Field(strict=True, ge=0, le=1)]
    react: Annotated[int, Field(strict=True, ge=0, le=1)]
    source: Annotated[int, Field(strict=True, ge=0, le=1)]

    @property
    def total(self) -> int:
        return self.what + self.when + self.why + self.react + self.source


class EventSemanticReview(EventModel):
    content_contract_version: Literal[1, 2] = 1
    detailed_event_ids: tuple[EventId, ...] | None = None
    projection_sha256: Digest | None = None
    case_id: SemanticId
    annotation_sha256: Digest
    markdown_sha256: Digest
    reviewer_id: SemanticId
    reviewer_kind: Literal["human", "ai"]
    reviewed_at: datetime | None = None
    scores: Annotated[tuple[SemanticEventScore, ...], Field(max_length=5)] | None = None
    failure_codes: tuple[SemanticCode, ...] = ()
    result: Literal["pass", "fail", "pending"] = "pending"

    @model_validator(mode="after")
    def human_evidence(self) -> Self:
        if (
            self.content_contract_version == 2
            and self.result != "pending"
            and (self.detailed_event_ids is None or self.projection_sha256 is None)
        ):
            raise ValueError("semantic.article_review_binding_required")
        if self.result == "pending":
            if self.scores is not None or self.reviewed_at is not None:
                raise ValueError("semantic.pending_scores_must_be_null")
        elif self.reviewer_kind != "human" or self.reviewed_at is None or self.scores is None:
            raise ValueError("semantic.human_review_required")
        if self.reviewed_at is not None and self.reviewed_at.utcoffset() is None:
            raise ValueError("semantic.clock_invalid")
        if self.scores is not None and len({s.event_id for s in self.scores}) != len(self.scores):
            raise ValueError("semantic.review_invalid")
        if self.result == "pass" and (
            self.failure_codes or any(s.total != 5 for s in self.scores or ())
        ):
            raise ValueError("semantic.five_of_five_required")
        if self.result == "fail" and not self.failure_codes:
            raise ValueError("semantic.failure_reason_required")
        return self

    @model_serializer(mode="wrap")
    def versioned_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if self.content_contract_version == 1:
            for key in ("content_contract_version", "detailed_event_ids", "projection_sha256"):
                data.pop(key, None)
        return data


class SemanticRate(EventModel):
    numerator: Count | None = None
    denominator: Count | None = None

    @model_validator(mode="after")
    def measured_counts(self) -> Self:
        if (self.numerator is None) != (self.denominator is None) or (
            self.numerator is not None
            and self.denominator is not None
            and self.numerator > self.denominator
        ):
            raise ValueError("semantic.denominator_invalid")
        return self

    @property
    def ratio(self) -> float | None:
        return _ratio(self.numerator, self.denominator)


class EventQualityV3Measurement(EventModel):
    content_contract_version: Literal[1, 2] = 1
    detailed_article_count: Count | None = None
    segment: MarketSegment
    document_schema: Literal[3] = 3
    basis: Literal["terminal", "remote_confirmed"]
    publication_sha: GitSha | None = None
    must_include_selection: SemanticRate = SemanticRate()
    selected_survival: SemanticRate = SemanticRate()
    required_fact_preservation: SemanticRate = SemanticRate()
    external_event_capture: SemanticRate = SemanticRate()
    human_five_of_five: SemanticRate = SemanticRate()
    unsupported_event_count: Count | None = None
    unsupported_causality_count: Count | None = None
    excluded_segments: tuple[MarketSegment, ...] = ()
    support_vectors: Annotated[tuple[EventSupportVector, ...], Field(max_length=5)] | None = None
    automated_result: Literal["pass", "fail", "unobserved"]
    review_references: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def measured_authority(self) -> Self:
        if (self.basis == "remote_confirmed") != (self.publication_sha is not None):
            raise ValueError("semantic.publication_unconfirmed")
        if len(set(self.excluded_segments)) != len(self.excluded_segments):
            raise ValueError("semantic.denominator_invalid")
        if self.automated_result == "pass" and (
            self.unsupported_event_count != 0
            or self.unsupported_causality_count != 0
            or any(
                rate.numerator != rate.denominator
                for rate in (self.must_include_selection, self.required_fact_preservation)
            )
            or self.required_fact_preservation.numerator is None
            or self.must_include_selection.numerator is None
            or self.selected_survival.numerator is None
        ):
            raise ValueError("semantic.automated_result_invalid")
        return self

    @model_serializer(mode="wrap")
    def versioned_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if self.content_contract_version == 1:
            data.pop("content_contract_version", None)
            data.pop("detailed_article_count", None)
        return data


class EventScheduledObservation(EventModel):
    run_id: Annotated[str, Field(pattern=r"^[0-9]{1,24}$")]
    segment: MarketSegment
    trigger: Literal["schedule", "manual", "retry", "skipped"]
    document_schema: Literal[3] = 3
    reviewed_code_sha: GitSha
    policy_sha256: Digest
    publication_sha: GitSha | None = None
    pages_publication_sha: GitSha | None = None
    remote_confirmed: bool = False
    telegram_confirmed: bool = False
    ledger_confirmed: bool = False
    cursor_confirmed: bool = False

    @property
    def accepted(self) -> bool:
        return (
            self.trigger == "schedule"
            and self.publication_sha is not None
            and self.pages_publication_sha == self.publication_sha
            and self.remote_confirmed
            and self.telegram_confirmed
            and self.ledger_confirmed
            and self.cursor_confirmed
        )


class EventCutoverAcceptance(EventModel):
    content_contract_version: Literal[1, 2] = 1
    article_policy_hash: Digest | None = None
    document_schema: Literal[3] = 3
    status: Literal[
        "blocked", "ready", "active_observing", "accepted", "rolled_back", "cleanup_complete"
    ]
    reviewed_code_sha: GitSha
    policy_sha256: Digest
    annotation_sha256: Digest
    review_sha256: Digest
    market_allowlist: tuple[MarketSegment, ...] = ()
    annotations: Annotated[tuple[EventSemanticAnnotation, ...], Field(max_length=96)] = ()
    reviews: Annotated[tuple[EventSemanticReview, ...], Field(max_length=96)] = ()
    measurements: Annotated[tuple[EventQualityV3Measurement, ...], Field(max_length=3)] = ()
    code_ready: bool = False
    source_gate_ready: bool = False
    cursor_gate_ready: bool = False
    capability_ready: bool = False
    release_instruction_ref: SemanticId | None = None
    rollback_code_sha: GitSha | None = None
    rollback_policy_sha256: Digest | None = None
    scheduled_observations: Annotated[
        tuple[EventScheduledObservation, ...], Field(max_length=96)
    ] = ()
    reviewed_cleanup_sha: GitSha | None = None

    def human_market_ready(self, segment: MarketSegment) -> bool:
        cases = [
            a
            for a in self.annotations
            if a.segment == segment
            and a.content_contract_version == self.content_contract_version
            and a.article_policy_hash == self.article_policy_hash
            and a.origin == "real_human_annotation"
            and a.reviewed_code_sha == self.reviewed_code_sha
            and a.expected_outcome in {"normal", "quiet", "source_limited"}
        ]
        reviews = {r.case_id: r for r in self.reviews}
        accepted = [
            a
            for a in cases
            if a.case_id in reviews
            and reviews[a.case_id].annotation_sha256 == a.annotation_sha256
            and reviews[a.case_id].result == "pass"
            and reviews[a.case_id].content_contract_version == self.content_contract_version
            and (
                self.content_contract_version == 1
                or set(a.expected_detailed_event_ids)
                <= set(reviews[a.case_id].detailed_event_ids or ())
            )
            and set(s.event_id for s in reviews[a.case_id].scores or ())
            == set(a.expected_event_ids)
        ]
        return (
            len(accepted) >= 4
            and len({a.target_date for a in accepted}) >= 2
            and any(
                a.news_rich
                and a.expected_event_ids
                and a.expected_outcome == "normal"
                and a.source_availability == "normal"
                and len(a.expected_support) == len(a.expected_event_ids)
                and all(
                    v.facts == "complete" and v.locator == "complete" for v in a.expected_support
                )
                and any(v.meaning in {"source_reported", "conditional"} for v in a.expected_support)
                for a in accepted
            )
        )

    @model_validator(mode="after")
    def cutover_gates(self) -> Self:
        from investo.models.event_article import ARTICLE_POLICY_HASH

        if (
            self.content_contract_version == 2 and self.article_policy_hash != ARTICLE_POLICY_HASH
        ) or (self.content_contract_version == 1 and self.article_policy_hash is not None):
            raise ValueError("semantic.article_policy_invalid")
        if self.annotation_sha256 != semantic_records_hash(
            self.annotations
        ) or self.review_sha256 != semantic_records_hash(self.reviews):
            raise ValueError("cutover.evidence_hash_invalid")
        if len(set(self.market_allowlist)) != len(self.market_allowlist):
            raise ValueError("cutover.market_invalid")
        if (
            len({a.case_id for a in self.annotations}) != len(self.annotations)
            or len({r.case_id for r in self.reviews}) != len(self.reviews)
            or len({m.segment for m in self.measurements}) != len(self.measurements)
            or len({(o.run_id, o.segment) for o in self.scheduled_observations})
            != len(self.scheduled_observations)
        ):
            raise ValueError("cutover.evidence_duplicate")
        if self.status in {"ready", "active_observing", "accepted", "cleanup_complete"}:
            measurements = {m.segment: m for m in self.measurements}
            if (
                not self.market_allowlist
                or not self.code_ready
                or not self.source_gate_ready
                or not self.cursor_gate_ready
                or any(
                    not self.human_market_ready(s)
                    or s not in measurements
                    or measurements[s].content_contract_version != self.content_contract_version
                    or measurements[s].automated_result != "pass"
                    for s in self.market_allowlist
                )
            ):
                raise ValueError("cutover.acceptance_pending")
        if self.status in {"active_observing", "accepted", "cleanup_complete"} and (
            not self.capability_ready
            or self.release_instruction_ref is None
            or self.rollback_code_sha is None
            or self.rollback_policy_sha256 is None
        ):
            raise ValueError("cutover.release_required")
        if self.status in {"accepted", "cleanup_complete"} and any(
            len(
                {
                    o.run_id
                    for o in self.scheduled_observations
                    if o.segment == s
                    and o.accepted
                    and o.reviewed_code_sha == self.reviewed_code_sha
                    and o.policy_sha256 == self.policy_sha256
                }
            )
            < 3
            for s in self.market_allowlist
        ):
            raise ValueError("cutover.scheduled_observations_pending")
        if self.status == "cleanup_complete" and (
            set(self.market_allowlist) != {"domestic-equity", "us-equity", "crypto"}
            or self.reviewed_cleanup_sha is None
            or len(
                {
                    o.run_id
                    for o in self.scheduled_observations
                    if o.accepted
                    and o.reviewed_code_sha == self.reviewed_code_sha
                    and o.policy_sha256 == self.policy_sha256
                }
            )
            < 10
        ):
            raise ValueError("cutover.retirement_pending")
        return self


def semantic_records_hash(records: Sequence[EventSemanticAnnotation | EventSemanticReview]) -> str:
    """Bind a reviewed collection, not just individually plausible rows."""
    import json
    from hashlib import sha256

    rows = sorted((r.model_dump(mode="json") for r in records), key=lambda row: row["case_id"])
    return sha256(
        json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
