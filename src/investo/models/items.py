"""Normalized data items produced by Source Adapters.

Every adapter (US-001, US-008) returns ``list[NormalizedItem]``. The
common shape lets the briefing generator (US-002) treat heterogeneous
sources uniformly.

Reference: aidlc-docs/inception/application-design/component-methods.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)

from investo.models._validators import reject_blank_strict

Category = Literal["news", "price", "macro", "calendar", "earnings"]

# Strict union for raw_metadata values: rejects silent coercion such as
# ``"42" -> 42`` or ``True -> 1``. Without this, provenance bag values can
# be quietly mangled by pydantic v2's default lax mode. ``StrictInt`` also
# rejects ``bool`` (which is an ``int`` subclass), so booleans are excluded.
_MetadataValue = StrictStr | StrictInt | StrictFloat


class NormalizedItem(BaseModel):
    """Common shape produced by every Source Adapter.

    Frozen (immutable) so values cannot be mutated after a source returns
    them. ``extra="forbid"`` blocks silent ingestion of unknown fields,
    which would otherwise be a data-quality landmine.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: str = Field(min_length=1, max_length=100)
    category: Category
    title: str = Field(min_length=1)
    summary: str | None = None
    url: HttpUrl | None = None
    published_at: datetime
    raw_metadata: dict[str, _MetadataValue] = Field(default_factory=dict)

    @field_validator("source_name", "title")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # ``min_length=1`` rejects ``""`` but lets whitespace-only strings
        # through. Strip-then-check ensures these required identifiers carry
        # actual content. Shared helper keeps the rule consistent across
        # sibling models.
        return reject_blank_strict(value)

    @field_validator("summary")
    @classmethod
    def _normalize_optional_summary(cls, value: str | None) -> str | None:
        # Adapters sometimes hand back ``""`` or ``"  "`` for "no summary".
        # Normalize to ``None`` so consumers only see one absence sentinel.
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("published_at")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        # Naive datetimes lead to silent KST/UTC drift in cron-driven date
        # math (US-005 resolves target_date from now_utc). Reject upfront.
        # The double check handles custom tzinfo subclasses that exist but
        # return ``None`` from ``utcoffset()``.
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("published_at must be timezone-aware")
        return value
