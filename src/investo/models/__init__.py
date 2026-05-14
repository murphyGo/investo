"""Investo shared data models (pydantic v2).

Foundation library — every other unit imports from here. The names
listed in :data:`__all__` constitute this package's stable public API;
anything else (e.g. the ``_validators`` helpers) is internal and must
not be relied on by sibling units.

Reference: aidlc-docs/inception/application-design/component-methods.md
"""

from investo.models.briefing import (
    TELEGRAM_MESSAGE_LIMIT,
    Briefing,
    BriefingNotification,
)
from investo.models.carryover import (
    BriefingCarryover,
    CarryoverEventType,
    CarryoverItem,
    CarryoverStatus,
    status_label_kr,
)
from investo.models.coverage import (
    SourceCollectionReport,
    SourceOutcome,
    SourceStatus,
    SourceTier,
    sanitize_source_error_message,
)
from investo.models.items import Category, NormalizedItem
from investo.models.results import (
    FailureContext,
    FailureStage,
    PipelineResult,
    PipelineStatus,
    SendResult,
)
from investo.models.segments import (
    SEGMENT_MARKET_TZ,
    SEGMENT_MARKET_TZ_LABEL,
    MarketSegment,
)

__all__ = [
    "SEGMENT_MARKET_TZ",
    "SEGMENT_MARKET_TZ_LABEL",
    "TELEGRAM_MESSAGE_LIMIT",
    "Briefing",
    "BriefingCarryover",
    "BriefingNotification",
    "CarryoverEventType",
    "CarryoverItem",
    "CarryoverStatus",
    "Category",
    "FailureContext",
    "FailureStage",
    "MarketSegment",
    "NormalizedItem",
    "PipelineResult",
    "PipelineStatus",
    "SendResult",
    "SourceCollectionReport",
    "SourceOutcome",
    "SourceStatus",
    "SourceTier",
    "sanitize_source_error_message",
    "status_label_kr",
]
