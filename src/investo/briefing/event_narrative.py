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
from investo.models.event_narratives import (
    EventGenerationPayload,
    EventMeaning,
    EventNarrative,
    EventReaction,
    Stage2OutputV2,
    Stage2Sections,
)
from investo.models.events import EventSelectionPlan, EvidenceRef

# A defensive parser allocation bound; unrelated to the 64KiB Stage 1 and
# 8KiB protected-input budgets. Normal v2 narratives occupy a small fraction.
_MAX_SYNTHESIS_BYTES = 1024 * 1024
_OWNED_HEADER = re.compile(r"^\s*#{1,2}\s", re.MULTILINE)
_DIAGNOSTIC_FIELDS = frozenset(
    {"envelope"}
    | set(Stage2OutputV2.model_fields)
    | set(Stage2Sections.model_fields)
    | set(EventNarrative.model_fields)
    | set(EventMeaning.model_fields)
    | set(EventReaction.model_fields)
    | set(EvidenceRef.model_fields)
)
_DIAGNOSTIC_TYPES = frozenset(
    {
        "missing",
        "extra_forbidden",
        "literal_error",
        "string_type",
        "string_pattern_mismatch",
        "int_type",
        "int_parsing",
        "dict_type",
        "tuple_type",
        "list_type",
        "too_long",
        "too_short",
        "greater_than",
        "greater_than_equal",
        "value_error",
        "other",
    }
)
_FIXED_DIAGNOSTICS = frozenset(
    {
        "synthesis.invalid_json",
        "synthesis.duplicate_json_field",
        "synthesis.invalid_schema",
        "synthesis.response_budget",
        "synthesis.invalid_sections",
        "synthesis.required_macro_missing",
    }
)


class EventSynthesisError(ValueError):
    """Keep the existing public failure while carrying closed diagnostic tokens."""

    def __init__(self, message: str, diagnostics: tuple[str, ...]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def event_synthesis_diagnostics(exc: BaseException | None) -> tuple[str, ...]:
    if not isinstance(exc, EventSynthesisError) or type(exc.diagnostics) is not tuple:
        return ()
    result: set[str] = set()
    for code in exc.diagnostics[:8]:
        if type(code) is not str:
            continue
        parts = code.split(".")
        if code in _FIXED_DIAGNOSTICS or (
            len(parts) == 3
            and parts[0] == "schema"
            and parts[1] in _DIAGNOSTIC_TYPES
            and parts[2] in _DIAGNOSTIC_FIELDS
        ):
            result.add(code)
    return tuple(sorted(result))


class _DuplicateJsonFieldError(ValueError):
    pass


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonFieldError("duplicate JSON field")
        result[key] = value
    return result


def _validate_sections(output: Stage2OutputV2) -> None:
    for text in output.sections.model_dump().values():
        if not text.strip() or _OWNED_HEADER.search(text) or "investo:" in text:
            raise EventNarrativeValidationError("event.narrative_invalid")


def parse_event_synthesis(stdout: str, plan: EventSelectionPlan) -> Stage2OutputV2:
    """Parse one v2 JSON object; no format inference, prose recovery or v1 fallback."""
    if len(stdout.encode("utf-8")) > _MAX_SYNTHESIS_BYTES:
        raise EventSynthesisError(
            "event_synthesis_unavailable: response_budget", ("synthesis.response_budget",)
        )
    try:
        output = Stage2OutputV2.model_validate(
            json.loads(stdout, object_pairs_hook=_unique_json_keys)
        )
        _validate_sections(output)
        validate_event_payload(EventGenerationPayload(plan=plan, narratives=output.events))
    except EventNarrativeValidationError:
        raise
    except ValidationError as exc:
        diagnostics = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False)[:8]:
            kind = error["type"] if error["type"] in _DIAGNOSTIC_TYPES else "other"
            field = next(
                (part for part in reversed(error["loc"]) if part in _DIAGNOSTIC_FIELDS),
                "envelope",
            )
            diagnostics.append(f"schema.{kind}.{field}")
        raise EventSynthesisError(
            "event_synthesis_unavailable: invalid_schema", tuple(diagnostics)
        ) from None
    except (ValueError, TypeError) as exc:
        # Pydantic includes input values in its errors. Source/model prose must
        # never reach the retry/logging exception boundary.
        code = (
            "synthesis.invalid_json"
            if isinstance(exc, json.JSONDecodeError)
            else "synthesis.duplicate_json_field"
            if isinstance(exc, _DuplicateJsonFieldError)
            else "synthesis.invalid_schema"
        )
        raise EventSynthesisError("event_synthesis_unavailable: invalid_schema", (code,)) from None
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
