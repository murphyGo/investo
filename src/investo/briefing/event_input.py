"""Deterministic, bounded candidate lanes for the explicit event policy."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from investo.briefing.event_evidence import evidence_document_from_item
from investo.models import NormalizedItem, SourceOutcome
from investo.models.macro import (
    is_required_macro_actual,
    macro_event_date,
    macro_event_key,
    macro_priority,
    macro_priority_rank,
)


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    input_count: int
    candidate_count: int
    news_count: int
    omitted_count: int
    reservation_starved: bool


def item_evidence_key(item: NormalizedItem) -> str:
    """Canonical document/revision identity, shared with the transmitted buffers."""
    doc = evidence_document_from_item(item, received_at=item.published_at)
    return f"{doc.document_id}:{doc.origin_revision_id or doc.revision_id}"


def event_item_sort_key(item: NormalizedItem) -> tuple[float, str, str]:
    return (-item.published_at.timestamp(), item.source_name, item_evidence_key(item))


def observe_candidates(
    items: Sequence[NormalizedItem], candidates: Sequence[NormalizedItem]
) -> CandidateObservation:
    """Shadow observes the actual v1 candidates; it never changes selection."""
    news_count = sum(_is_news(item) for item in candidates)
    return CandidateObservation(
        input_count=len(items),
        candidate_count=len(candidates),
        news_count=news_count,
        omitted_count=len(items) - len(candidates),
        reservation_starved=any(_is_news(item) for item in items) and news_count == 0,
    )


def _is_news(item: NormalizedItem) -> bool:
    # Explicit source publication metadata may describe P2/P3 actuals too.
    # Do not use inferred FRED "actual" status for an unchanged observation.
    explicit_actual = (
        item.raw_metadata.get("macro_event_status") == "actual"
        and macro_event_key(item) is not None
    )
    return item.scheduled_at is None and (
        item.category == "news" or is_required_macro_actual(item) or explicit_actual
    )


def event_collection_limited(
    items: Sequence[NormalizedItem], outcomes: Sequence[SourceOutcome]
) -> bool:
    """Describe event collection, independently of missing price/market coverage.

    The caller scopes outcomes to the recipient segment. A successful empty
    news fetch is observed zero, whereas absent input and absent collection
    evidence are unknown. No minimum number of articles implies completeness.
    """
    event_sources = {item.source_name for item in items if _is_news(item)}
    news_outcomes = tuple(
        outcome
        for outcome in outcomes
        if outcome.category in {"news", "earnings"} or outcome.source_name in event_sources
    )
    if any(outcome.status == "failed" for outcome in news_outcomes):
        return True
    return not event_sources and not news_outcomes


def select_event_input_items(
    items: Sequence[NormalizedItem], *, target_date: date | None
) -> tuple[NormalizedItem, ...]:
    """Preserve protected lanes, reserve remaining news slots, then stable fill."""
    # Compute validated identity once per input. Tracking parameters cannot
    # consume a source's entire reservation. The last tie only chooses a stable
    # representative among equivalent source rows and never changes priority.
    keyed = [(item_evidence_key(item), item) for item in items]
    ordered = sorted(
        keyed,
        key=lambda row: (
            -row[1].published_at.timestamp(),
            row[1].source_name,
            row[0],
            json.dumps(row[1].model_dump(mode="json"), sort_keys=True, ensure_ascii=False),
        ),
    )
    unique: dict[str, tuple[str, NormalizedItem]] = {}
    for row in ordered:
        unique.setdefault(row[0], row)
    ordered = list(unique.values())
    selected: list[NormalizedItem] = []
    identities: set[str] = set()
    counts: dict[str, int] = defaultdict(int)
    lookahead = 0

    def add(row: tuple[str, NormalizedItem]) -> None:
        nonlocal lookahead
        key, item = row
        future = item.scheduled_at is not None
        if (
            len(selected) >= 96
            or counts[item.source_name] >= 24
            or key in identities
            or (future and lookahead >= 12)
        ):
            return
        selected.append(item)
        identities.add(key)
        counts[item.source_name] += 1
        lookahead += int(future)

    macro = [row for row in ordered if macro_priority(row[1]) in {"P0", "P1"}]
    macro.sort(
        key=lambda row: (
            macro_priority_rank(macro_priority(row[1])),
            abs((macro_event_date(row[1]) - target_date).days) if target_date else 0,
            (-row[1].published_at.timestamp(), row[1].source_name, row[0]),
        )
    )
    for row in macro[:12]:
        add(row)
    for row in ordered:
        item = row[1]
        if (
            item.raw_metadata.get("policy_priority") == "crypto_regulation"
            and item.raw_metadata.get("official_source") == "true"
        ):
            add(row)
    by_source: dict[str, list[tuple[str, NormalizedItem]]] = defaultdict(list)
    for row in ordered:
        if _is_news(row[1]) and row[0] not in identities:
            by_source[row[1].source_name].append(row)
    offset = 0
    while any(offset < len(rows) for rows in by_source.values()):
        for source in sorted(by_source):
            for row in by_source[source][offset : offset + 4]:
                if sum(_is_news(row) for row in selected) >= 24:
                    break
                add(row)
        if len(selected) >= 96 or sum(_is_news(row) for row in selected) >= 24:
            break
        offset += 4
    for row in ordered:
        add(row)
    required = {key for key, item in keyed if is_required_macro_actual(item)}
    if required - identities:
        raise ValueError("required macro actual exceeds event candidate budget")
    return tuple(selected)
