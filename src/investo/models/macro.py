"""Macro-event metadata helpers.

u59 keeps the first implementation compatible with the existing
``NormalizedItem.raw_metadata`` contract: flat primitive keys only, no
nested dict/list values. Source adapters may stamp explicit macro keys,
while this module also infers priority for known official macro sources
that predate u59.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Final, Literal, cast

from investo.models.items import NormalizedItem

MacroEventStatus = Literal["scheduled", "actual", "unresolved", "confirmed", "stale"]
MacroImportance = Literal["P0", "P1", "P2", "P3"]

_MACRO_PRIORITIES: Final[frozenset[str]] = frozenset({"P0", "P1", "P2", "P3"})
_MACRO_STATUSES: Final[frozenset[str]] = frozenset(
    {"scheduled", "actual", "unresolved", "confirmed", "stale"}
)
_REQUIRED_SECTION_IDS: Final[frozenset[int]] = frozenset({0, 2, 3, 4, 5, 6})
_DEFAULT_REQUIRED_SECTIONS: Final[tuple[int, ...]] = (0, 2, 4)

_HIGH_IMPORTANCE_FRED_RELEASE_IDS: Final[frozenset[str]] = frozenset(
    {
        "10",  # Consumer Price Index
        "46",  # Producer Price Index
        "50",  # Employment Situation
        "53",  # Gross Domestic Product
    }
)
_HIGH_IMPORTANCE_FRED_SERIES_IDS: Final[frozenset[str]] = frozenset(
    {
        "CPIAUCSL",
        "UNRATE",
        "DFF",
        "PPIFID",
    }
)


def macro_event_key(item: NormalizedItem) -> str | None:
    """Return a stable macro event key when one can be read or inferred."""

    explicit = _metadata_str(item.raw_metadata, "macro_event_key")
    if explicit:
        return explicit

    if item.source_name == "fred-economic-calendar":
        release_id = _metadata_str(item.raw_metadata, "release_id")
        scheduled_date = _metadata_str(item.raw_metadata, "scheduled_date")
        if release_id and scheduled_date:
            return f"fred-economic-calendar:release_id={release_id}:scheduled_date={scheduled_date}"

    if item.source_name == "fred-macro":
        series_id = _metadata_str(item.raw_metadata, "series_id")
        release_date = _metadata_str(item.raw_metadata, "release_date")
        if series_id and release_date:
            return f"fred-macro:series_id={series_id}:release_date={release_date}"

    if item.source_name == "fomc-calendar":
        event_type = _metadata_str(item.raw_metadata, "event_type")
        scheduled_date = _metadata_str(item.raw_metadata, "scheduled_date")
        if event_type and scheduled_date and event_type.upper() == "FOMC":
            return f"fomc-calendar:event_type=FOMC:scheduled_date={scheduled_date}"

    return None


def macro_event_status(item: NormalizedItem) -> MacroEventStatus | None:
    """Return explicit or inferred macro event status."""

    explicit = _metadata_str(item.raw_metadata, "macro_event_status")
    if explicit in _MACRO_STATUSES:
        return cast(MacroEventStatus, explicit)

    if item.source_name in {"fred-economic-calendar", "fomc-calendar"} and macro_event_key(item):
        return "scheduled"
    if item.source_name == "fred-macro" and macro_event_key(item):
        return "actual"
    return None


def macro_priority(item: NormalizedItem) -> MacroImportance | None:
    """Return explicit or inferred macro priority.

    P0/P1 are used by candidate selection. P2/P3 remain useful metadata
    for later prompt and quality work but are not reserved by the first
    u59 slice.
    """

    explicit = _metadata_str(item.raw_metadata, "macro_priority")
    if explicit:
        normalized = explicit.upper()
        if normalized in _MACRO_PRIORITIES:
            return cast(MacroImportance, normalized)

    if item.source_name == "fred-economic-calendar":
        release_id = _metadata_str(item.raw_metadata, "release_id")
        if release_id in _HIGH_IMPORTANCE_FRED_RELEASE_IDS:
            return "P1"

    if item.source_name == "fomc-calendar":
        event_type = _metadata_str(item.raw_metadata, "event_type")
        if event_type and event_type.upper() == "FOMC":
            return "P1"

    if item.source_name == "fred-macro":
        series_id = _metadata_str(item.raw_metadata, "series_id")
        if series_id in _HIGH_IMPORTANCE_FRED_SERIES_IDS:
            return "P0"

    return None


def is_required_macro_actual(item: NormalizedItem) -> bool:
    """Return whether the item should be treated as a required macro actual."""

    explicit = _metadata_str(item.raw_metadata, "required_macro_actual")
    if explicit and explicit.lower() == "true":
        return True
    return macro_priority(item) == "P0" and macro_event_status(item) == "actual"


def macro_required_sections(item: NormalizedItem) -> tuple[int, ...]:
    """Return required output sections for a required macro item.

    Metadata uses a comma-separated string to preserve the flat
    ``raw_metadata`` contract.
    """

    raw_sections = _metadata_str(item.raw_metadata, "required_sections")
    if not raw_sections:
        return _DEFAULT_REQUIRED_SECTIONS if is_required_macro_actual(item) else ()

    section_ids: list[int] = []
    for token in raw_sections.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            section_id = int(stripped)
        except ValueError:
            continue
        if section_id in _REQUIRED_SECTION_IDS and section_id not in section_ids:
            section_ids.append(section_id)
    return tuple(section_ids)


def macro_event_date(item: NormalizedItem) -> date:
    """Return the best date for priority proximity sorting."""

    for key in ("scheduled_date", "release_date", "macro_release_date", "release_period"):
        parsed = _parse_iso_date(_metadata_str(item.raw_metadata, key))
        if parsed is not None:
            return parsed
    if item.scheduled_at is not None:
        return item.scheduled_at.astimezone(UTC).date()
    return item.published_at.astimezone(UTC).date()


def macro_prompt_payload(item: NormalizedItem) -> dict[str, str] | None:
    """Return a compact macro object for Stage 1 prompt serialization."""

    event_key = macro_event_key(item)
    priority = macro_priority(item)
    status = macro_event_status(item)
    if event_key is None and priority is None and status is None:
        return None

    payload: dict[str, str] = {}
    if event_key is not None:
        payload["event_key"] = event_key
    if priority is not None:
        payload["priority"] = priority
    if status is not None:
        payload["status"] = status

    label = _metadata_str(item.raw_metadata, "macro_event_label") or _metadata_str(
        item.raw_metadata, "release_name"
    )
    if label:
        payload["label"] = label

    for output_key, metadata_key in (
        ("actual", "macro_actual"),
        ("actual", "value"),
        ("prior", "macro_prior"),
        ("prior", "previous_value"),
        ("forecast", "macro_forecast"),
        ("consensus", "macro_consensus"),
        ("surprise", "macro_surprise"),
        ("release_period", "macro_release_period"),
        ("release_period", "release_date"),
        ("release_period", "scheduled_date"),
    ):
        if output_key in payload:
            continue
        value = _metadata_str(item.raw_metadata, metadata_key)
        if value:
            payload[output_key] = value

    required_sections = macro_required_sections(item)
    if required_sections:
        payload["required_sections"] = ",".join(str(section) for section in required_sections)

    return payload


def macro_priority_rank(priority: MacroImportance | None) -> int:
    """Return a sort rank where smaller means more important."""

    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority or "", 99)


def _metadata_str(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int | float):
        return str(value)
    return None


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


__all__ = [
    "MacroEventStatus",
    "MacroImportance",
    "is_required_macro_actual",
    "macro_event_date",
    "macro_event_key",
    "macro_event_status",
    "macro_priority",
    "macro_priority_rank",
    "macro_prompt_payload",
    "macro_required_sections",
]
