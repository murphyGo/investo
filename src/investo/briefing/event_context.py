"""Generation preparation and compatibility exports for neutral context validation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from investo._internal.event_context import (
    STAGE_ONE_CONTEXT_BYTES as STAGE_ONE_CONTEXT_BYTES,
)
from investo._internal.event_context import (
    STAGE_TWO_CONTEXT_BYTES as STAGE_TWO_CONTEXT_BYTES,
)
from investo._internal.event_context import (
    ContextEvidenceError as ContextEvidenceError,
)
from investo._internal.event_context import (
    ContextLookup as ContextLookup,
)
from investo._internal.event_context import (
    ContextPromptBuffer as ContextPromptBuffer,
)
from investo._internal.event_context import (
    ProtectedContextBuffer as ProtectedContextBuffer,
)
from investo._internal.event_context import (
    build_context_prompt_buffer as build_context_prompt_buffer,
)
from investo._internal.event_context import (
    build_protected_context_buffer as build_protected_context_buffer,
)
from investo._internal.event_context import (
    context_lookup as context_lookup,
)
from investo._internal.event_context import (
    event_context_refs as event_context_refs,
)
from investo._internal.event_context import (
    fact_context_refs as fact_context_refs,
)
from investo._internal.event_context import (
    metadata_ref_field as metadata_ref_field,
)
from investo._internal.event_context import (
    normalized_context_literal as normalized_context_literal,
)
from investo._internal.event_context import (
    normalized_numeric_literal as normalized_numeric_literal,
)
from investo._internal.event_context import (
    parse_context_classification as parse_context_classification,
)
from investo._internal.event_context import (
    resolve_context_ref as resolve_context_ref,
)
from investo._internal.event_context import (
    support_vector as support_vector,
)
from investo._internal.event_context import (
    validate_context_event as validate_context_event,
)
from investo._internal.event_context import (
    validate_context_fact as validate_context_fact,
)
from investo.briefing.event_evidence import evidence_document_from_item
from investo.models.event_context import EventContextDocument
from investo.models.event_evidence import make_event_context_document
from investo.models.items import NormalizedItem


def prepare_context_documents(
    items: Sequence[NormalizedItem], *, received_at: datetime
) -> tuple[EventContextDocument, ...]:
    return tuple(
        make_event_context_document(
            evidence_document_from_item(item, received_at=received_at),
            metadata=item.raw_metadata,
            item=item,
        )
        for item in items
    )
