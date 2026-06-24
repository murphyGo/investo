"""Compatibility re-export for first-viewport briefing extraction helpers."""

from __future__ import annotations

from investo._internal.briefing_extract import (
    CAUTION_PREFIX,
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    WATERMARK_PREFIX,
    extract_caution,
    extract_conclusion,
    extract_key_drivers,
    extract_watermark,
)

__all__ = [
    "CAUTION_PREFIX",
    "CONCLUSION_PREFIX",
    "DRIVER_PREFIX",
    "WATERMARK_PREFIX",
    "extract_caution",
    "extract_conclusion",
    "extract_key_drivers",
    "extract_watermark",
]
