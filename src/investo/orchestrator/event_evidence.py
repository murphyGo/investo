"""One collection-level enrichment owner shared by preview and production."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import httpx

from investo.models.coverage import SourceOutcome
from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification, EnrichmentResult
from investo.models.items import NormalizedItem
from investo.sources.event_evidence import enrich_event_evidence, load_enrichment_qualification


async def prepare_event_evidence(
    items: Sequence[NormalizedItem],
    outcomes: Sequence[SourceOutcome],
    *,
    policy: EnrichmentPolicy,
    qualification: EnrichmentQualification,
    received_at: datetime,
    deadline: float | None = None,
    client: httpx.AsyncClient | None = None,
) -> EnrichmentResult:
    """Call once per collection, before routing; failed sources stay failed."""
    if policy.mode in {"off", "shadow"}:
        return EnrichmentResult(items=tuple(items))
    policy.validate_activation()
    if policy.mode == "preview" and policy.qualification_sha256 != qualification.policy_hash:
        raise ValueError("event preview qualification hash mismatch")
    failed = {
        outcome.source_name for outcome in outcomes if outcome.status in {"failed", "skipped"}
    }
    indexes = [
        index
        for index, item in enumerate(items)
        if item.source_name not in failed
        and (policy.mode != "preview" or item.source_name in policy.preview_sources)
    ]
    if not indexes:
        return EnrichmentResult(items=tuple(items))
    selected = tuple(items[index] for index in indexes)
    if client is None:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as owned_client:
            result = await enrich_event_evidence(
                selected,
                client=owned_client,
                policy=policy,
                qualification=qualification,
                received_at=received_at,
                deadline=deadline,
            )
    else:
        result = await enrich_event_evidence(
            selected,
            client=client,
            policy=policy,
            qualification=qualification,
            received_at=received_at,
            deadline=deadline,
        )
    updated = list(items)
    for index, item in zip(indexes, result.items, strict=True):
        updated[index] = item
    return EnrichmentResult(
        items=tuple(updated), outcomes=result.outcomes, request_count=result.request_count
    )


def load_event_evidence_qualification(path: Path) -> EnrichmentQualification:
    """Read the caller's pinned code policy through the existing source owner."""
    return load_enrichment_qualification(path)
