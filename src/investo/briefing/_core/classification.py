"""Stage 1 classification: output model + JSON load / recovery / parse.

References:
    Functional Design E2 (`domain-entities.md`) — ClassificationResult
    Functional Design R10 — LLM-decided section assignment (category as hint)

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``ClassificationResult`` keeps its
import path via re-export from ``briefing/pipeline.py``.
"""

from __future__ import annotations

import ast
import json
import logging
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from investo.models.events import EventCandidateDraft, EventFactDraft, EvidenceRef

_logger = logging.getLogger("investo.briefing.pipeline")

# Closed set of section IDs that Stage 1 may assign to (FD R10).
_VALID_SECTION_IDS: Final[frozenset[int]] = frozenset({2, 3, 4, 5})

# Upper bound for Stage 1 stdout before JSON parsing. Classification
# should be tiny; over-cap output is malformed LLM output and should
# enter the normal classification retry path instead of stressing the
# JSON parser.
_STAGE1_STDOUT_MAX_BYTES: Final[int] = 64 * 1024


class ClassificationResult(BaseModel):
    """Stage 1 LLM output (FD E2).

    ``assignments`` maps synthetic item id → section id ∈ {2, 3, 4, 5}.
    ``unassigned`` lists item ids the LLM judged not section-worthy
    (Stage 2 uses these for context for sections ① and ⑥ only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignments: dict[int, int] = Field(default_factory=dict)
    unassigned: list[int] = Field(default_factory=list)

    @field_validator("assignments")
    @classmethod
    def _validate_section_ids(cls, value: dict[int, int]) -> dict[int, int]:
        valid_str = "{" + ", ".join(str(s) for s in sorted(_VALID_SECTION_IDS)) + "}"
        for k, v in value.items():
            if v not in _VALID_SECTION_IDS:
                raise ValueError(f"assignments value {v!r} for item id {k} not in {valid_str}")
        return value


class EventClassificationResult(ClassificationResult):
    """Explicit v2; a missing events field is unavailable, never zero events."""

    schema_version: Literal[2]
    assignments: dict[int, int]
    unassigned: list[int]
    events: tuple[EventCandidateDraft, ...] = Field(max_length=12)


_DIAGNOSTIC_FIELDS = frozenset(
    {"envelope"}
    | set(EventClassificationResult.model_fields)
    | set(EventCandidateDraft.model_fields)
    | set(EventFactDraft.model_fields)
    | set(EvidenceRef.model_fields)
)
_DIAGNOSTIC_TYPES = frozenset(
    {
        "json_invalid",
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
_EVIDENCE_DIAGNOSTICS = {
    "event reference has an unknown document or revision": "evidence.unknown_document",
    "event span exceeds the transmitted evidence buffer": "evidence.span_out_of_bounds",
    "event evidence span must not be whitespace-only": "evidence.blank_span",
    "event reference does not belong to its item_ids": "evidence.item_mismatch",
    "event relation requires source evidence": "evidence.relation_missing",
    "event impact requires source evidence": "evidence.impact_missing",
    "product event identity requires an object": "evidence.object_missing",
    "event identity_conflict: source event dates disagree": "evidence.date_conflict",
    "future scheduled evidence cannot be an occurred event": "evidence.future_occurred",
    "event fact period/unit must be present in its source": "evidence.fact_metadata_missing",
}
_FIXED_DIAGNOSTICS = frozenset(_EVIDENCE_DIAGNOSTICS.values()) | {
    "evidence.invalid",
    "classification.invalid_items",
}


class EventClassificationError(ValueError):
    """Preserve the public error while carrying only closed diagnostic tokens."""

    def __init__(self, message: str, diagnostics: tuple[str, ...]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def event_classification_diagnostics(exc: BaseException | None) -> tuple[str, ...]:
    """Never return raw errors, input values, item IDs, or arbitrary field paths."""
    if not isinstance(exc, EventClassificationError) or type(exc.diagnostics) is not tuple:
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


def invalid_event_evidence(exc: BaseException) -> EventClassificationError:
    return EventClassificationError(
        "event_classification_unavailable: invalid_evidence",
        (_EVIDENCE_DIAGNOSTICS.get(str(exc), "evidence.invalid"),),
    )


def parse_event_classification(
    stdout: str, item_count: int, *, required_item_ids: frozenset[int] = frozenset()
) -> EventClassificationResult:
    """Validate the versioned envelope and both legacy and event item IDs."""
    if len(stdout.encode("utf-8")) > _STAGE1_STDOUT_MAX_BYTES:
        raise ValueError("event_classification_unavailable: response_budget")
    try:
        # No prose/Python-literal recovery in the explicit JSON v2 contract.
        result = EventClassificationResult.model_validate_json(stdout)
        _parse_classification(
            json.dumps({"assignments": result.assignments, "unassigned": result.unassigned}),
            item_count,
            required_item_ids=required_item_ids,
        )
        for event in result.events:
            if any(item_id < 1 or item_id > item_count for item_id in event.item_ids):
                raise ValueError("invalid event item id")
    except ValidationError as exc:
        diagnostics = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False)[:8]:
            kind = error["type"] if error["type"] in _DIAGNOSTIC_TYPES else "other"
            field = next(
                (part for part in reversed(error["loc"]) if part in _DIAGNOSTIC_FIELDS),
                "envelope",
            )
            diagnostics.append(f"schema.{kind}.{field}")
        raise EventClassificationError(
            "event_classification_unavailable: invalid_schema_or_item", tuple(diagnostics)
        ) from None
    except (ValueError, TypeError):
        # Pydantic errors contain the input value. Never carry source prose
        # into the exception/logging boundary.
        raise EventClassificationError(
            "event_classification_unavailable: invalid_schema_or_item",
            ("classification.invalid_items",),
        ) from None
    return result


def _extract_braced_object(text: str, start: int) -> str | None:
    """Return the balanced ``{...}`` slice starting at ``start``."""
    depth = 0
    in_string = False
    quote = ""
    escaped = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _load_classification_payload(stdout: str) -> object:
    """Load the first JSON value from Claude's Stage 1 stdout.

    The prompt asks for JSON only, but production LLMs sometimes wrap
    the object in prose or a Markdown code fence. Recover a single JSON
    value when it is still unambiguous. Claude may also emit a Python-
    dict-like object with integer keys (``{1: 5}``) even after being
    asked for JSON; accept that literal shape and let pydantic validate
    it. Malformed output still raises ``JSONDecodeError`` and remains
    retryable.
    """
    stripped = stdout.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as original:
        decoder = json.JSONDecoder()
        for start, char in enumerate(stripped):
            if char != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(stripped[start:])
            except json.JSONDecodeError:
                braced = _extract_braced_object(stripped, start)
                if braced is None:
                    continue
                try:
                    return ast.literal_eval(braced)
                except (SyntaxError, ValueError):
                    continue
            return payload
        raise original


def _maybe_flip_inverted_assignments(data: object) -> object | None:
    """Detect and flip an inverted Stage 1 ``assignments`` payload.

    Production LLMs occasionally emit the schema upside-down — using
    ``section_id`` as the key and a list of ``item_ids`` as the value
    (e.g., ``{"3": [9, 10, 11], "5": [2, 7]}``) instead of the spec'd
    ``{<item_id>: <section_id>}`` shape. The drift burns through the
    retry budget on the same misread, so this helper offers a single
    auto-recovery: when ``assignments`` matches the inverted shape, flip
    it to the canonical orientation and let pydantic re-validate.

    Returns the flipped payload (a fresh dict) when the inversion is
    unambiguous, or ``None`` when any of the safety conditions fail —
    in which case the caller re-raises the original ``ValidationError``
    rather than papering over a different malformation:

    1. ``data["assignments"]`` is a dict (else nothing to flip).
    2. Every key parses to an int in ``{2, 3, 4, 5}`` (the closed Stage 1
       section-id set; key=1 is treated as a regular item-id payload
       and rejected so the original error surfaces).
    3. Every value is a list whose elements all parse to int.
    4. No item-id appears under more than one section (a true ambiguity
       that we refuse to silently resolve).
    """
    if not isinstance(data, dict):
        return None
    assignments = data.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        return None

    flipped: dict[str, int] = {}
    for raw_key, raw_value in assignments.items():
        try:
            section_id = int(raw_key)
        except (TypeError, ValueError):
            return None
        if section_id not in _VALID_SECTION_IDS:
            return None
        if not isinstance(raw_value, list) or not raw_value:
            return None
        for raw_item in raw_value:
            try:
                item_id = int(raw_item)
            except (TypeError, ValueError):
                return None
            key = str(item_id)
            if key in flipped:
                # Same item assigned to multiple sections — refuse to pick.
                return None
            flipped[key] = section_id

    rebuilt = dict(data)
    rebuilt["assignments"] = flipped
    return rebuilt


def _parse_classification(
    stdout: str, item_count: int, *, required_item_ids: frozenset[int] = frozenset()
) -> ClassificationResult:
    """Parse Stage 1 stdout as JSON → ``ClassificationResult``.

    Performs both structural validation (via pydantic) and id-set
    validation (every key + every unassigned element must be a valid
    item id in ``1..item_count``).

    Raises ``ValueError`` (or wrapped ``ValidationError`` /
    ``json.JSONDecodeError``) on any structural or semantic mismatch;
    the caller catches and routes to retry.

    Inverted-schema auto-recovery: production LLMs sometimes emit the
    schema upside-down (``{"<section_id>": [<item_ids>, ...]}``). When
    pydantic rejects the original payload, :func:`_maybe_flip_inverted_assignments`
    is given exactly one chance to flip the orientation; the flipped
    payload is then re-validated. The original ``ValidationError`` is
    re-raised when the flip is not unambiguously safe (overlap between
    sections, non-integer values, keys outside ``{2, 3, 4, 5}``).
    """
    stdout_size = len(stdout.encode("utf-8"))
    if stdout_size > _STAGE1_STDOUT_MAX_BYTES:
        raise ValueError(f"Stage 1 stdout exceeds {_STAGE1_STDOUT_MAX_BYTES} bytes: {stdout_size}")

    data = _load_classification_payload(stdout)
    try:
        result = ClassificationResult.model_validate(data)
    except ValidationError as original_validation_error:
        flipped = _maybe_flip_inverted_assignments(data)
        if flipped is None:
            raise
        try:
            result = ClassificationResult.model_validate(flipped)
        except ValidationError:
            # Flip looked plausible structurally but still failed validation
            # (e.g., a section-id leaked into the value list). Surface the
            # original error so callers see the real schema mismatch.
            raise original_validation_error from None
        _logger.info(
            "classification: recovered from inverted schema (auto-flip)",
            extra={"item_count": item_count},
        )
    valid_ids = set(range(1, item_count + 1))
    seen_ids = set(result.assignments.keys()) | set(result.unassigned)
    invalid = seen_ids - valid_ids
    if invalid:
        raise ValueError(
            f"Stage 1 referenced item id(s) outside 1..{item_count}: {sorted(invalid)}"
        )
    unassigned_required = required_item_ids & set(result.unassigned)
    if unassigned_required:
        raise ValueError(
            f"Stage 1 placed required macro item id(s) in unassigned: {sorted(unassigned_required)}"
        )
    missing_required = required_item_ids - set(result.assignments.keys())
    if missing_required:
        raise ValueError(f"Stage 1 omitted required macro item id(s): {sorted(missing_required)}")
    return result


__all__ = [
    "ClassificationResult",
    "_extract_braced_object",
    "_load_classification_payload",
    "_maybe_flip_inverted_assignments",
    "_parse_classification",
]
