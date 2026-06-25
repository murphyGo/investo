"""Compatibility exports for first-viewport summary quality validation."""

from __future__ import annotations

from investo._internal.summary_quality import (
    CAUTION_PREFIX,
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    WATERMARK_PREFIX,
    SummaryQualityError,
    repair_first_viewport_summary,
    validate_first_viewport_summary,
)
from investo._internal.text import MEANINGFUL_TEXT as _MEANINGFUL_TEXT_RE  # noqa: F401

__all__ = [
    "CAUTION_PREFIX",
    "CONCLUSION_PREFIX",
    "DRIVER_PREFIX",
    "WATERMARK_PREFIX",
    "SummaryQualityError",
    "repair_first_viewport_summary",
    "validate_first_viewport_summary",
]
