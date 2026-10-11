"""Source-bound event relationships; matching is a generation responsibility."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from investo.models.event_context import RequiredContextRefs
from investo.models.events import Digest, EventId, EventModel


class EventAssetImpact(EventModel):
    event_id: EventId
    asset_id: Annotated[str, Field(min_length=1, max_length=80)]
    relation: Literal["direct", "related"]
    mechanism: Annotated[str, Field(min_length=1, max_length=180)]
    condition: Annotated[str, Field(min_length=1, max_length=180)] | None = None
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: RequiredContextRefs
