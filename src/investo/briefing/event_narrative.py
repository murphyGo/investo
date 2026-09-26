"""Explicit Stage 2 v2 parsing and deterministic six-section assembly."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from investo._internal.event_rendering import (
    EventNarrativeValidationError,
    render_event_blocks,
    validate_event_payload,
)
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.models.event_narratives import EventGenerationPayload, Stage2OutputV2
from investo.models.events import EventSelectionPlan

# A defensive parser allocation bound; unrelated to the 64KiB Stage 1 and
# 8KiB protected-input budgets. Normal v2 narratives occupy a small fraction.
_MAX_SYNTHESIS_BYTES = 1024 * 1024
_OWNED_HEADER = re.compile(r"^\s*#{1,2}\s", re.MULTILINE)


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _validate_sections(output: Stage2OutputV2) -> None:
    for text in output.sections.model_dump().values():
        if not text.strip() or _OWNED_HEADER.search(text) or "investo:" in text:
            raise EventNarrativeValidationError("event.narrative_invalid")


def parse_event_synthesis(stdout: str, plan: EventSelectionPlan) -> Stage2OutputV2:
    """Parse one v2 JSON object; no format inference, prose recovery or v1 fallback."""
    if len(stdout.encode("utf-8")) > _MAX_SYNTHESIS_BYTES:
        raise ValueError("event_synthesis_unavailable: response_budget")
    try:
        output = Stage2OutputV2.model_validate(
            json.loads(stdout, object_pairs_hook=_unique_json_keys)
        )
        _validate_sections(output)
        validate_event_payload(EventGenerationPayload(plan=plan, narratives=output.events))
    except EventNarrativeValidationError:
        raise
    except (ValidationError, ValueError, TypeError):
        # Pydantic includes input values in its errors. Source/model prose must
        # never reach the retry/logging exception boundary.
        raise ValueError("event_synthesis_unavailable: invalid_schema") from None
    return output


def assemble_event_synthesis(
    output: Stage2OutputV2,
    plan: EventSelectionPlan,
    *,
    collection_limited: bool = False,
) -> str:
    _validate_sections(output)
    issues = render_event_blocks(
        EventGenerationPayload(
            plan=plan, narratives=output.events, collection_limited=collection_limited
        )
    )
    sections = output.sections
    bodies = (
        sections.market_summary,
        issues,
        sections.sector_flow,
        sections.indicators_events,
        sections.notable_tickers,
        sections.today_watch,
    )
    return "\n\n".join(
        f"{header}\n\n{body.strip()}"
        for header, body in zip(STAGE2_SECTION_HEADERS, bodies, strict=True)
    )
