"""Nullable event measurements; private traces never enter public serialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Literal, Self

from pydantic import Field, ValidationError, computed_field, model_validator

from investo.models.events import EventModel
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
