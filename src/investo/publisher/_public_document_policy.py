"""Closed u144 surface-issue disposition policy.

This module contains policy only. Detection remains owned by
``investo._internal.surface_quality``; the finalizer consumes this table rather
than duplicating scanner regexes or repairing by unowned text search.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

PublicBlockKind = Literal[
    "header",
    "navigation",
    "first_viewport",
    "visual",
    "anchor_table",
    "shared_macro",
    "crypto_indicators",
    "channel_anchors",
    "cause_map",
    "daily_thesis",
    "carryover",
    "chart",
    "section_body",
    "watchpoints",
    "diagnostics",
    "disclaimer",
]

FinalizationIssueDisposition = Literal[
    "record_warning",
    "repair",
    "replace_block",
    "omit_optional_block",
    "block_segment",
]

PUBLIC_BLOCK_KINDS: Final[tuple[PublicBlockKind, ...]] = (
    "header",
    "navigation",
    "first_viewport",
    "visual",
    "anchor_table",
    "shared_macro",
    "crypto_indicators",
    "channel_anchors",
    "cause_map",
    "daily_thesis",
    "carryover",
    "chart",
    "section_body",
    "watchpoints",
    "diagnostics",
    "disclaimer",
)

SURFACE_ISSUE_CODES: Final[frozenset[str]] = frozenset(
    {
        "bad_token.bulganghanseong",
        "ellipsis.dangling_line",
        "glossary.collision.forbidden_pair",
        "korean.bad_particle.mingamdo_eul",
        "markdown.broken_numeric_bold",
        "markdown.href_ellipsis",
        "markdown.unmatched_link",
        "public_diagnostic.raw_label",
        "summary.truncated_mid_token",
        "template.repeated_phrase",
        "trace.fragment",
        "watchlist.matcher_reason.public",
        "watermark.window_bracket",
    }
)

OPTIONAL_BLOCK_DISPOSITIONS: Final[Mapping[PublicBlockKind, FinalizationIssueDisposition]] = (
    MappingProxyType(
        {
            "visual": "omit_optional_block",
            "chart": "omit_optional_block",
            "carryover": "omit_optional_block",
            "cause_map": "omit_optional_block",
            "shared_macro": "replace_block",
            "crypto_indicators": "replace_block",
            "channel_anchors": "replace_block",
            "daily_thesis": "replace_block",
            "watchpoints": "replace_block",
        }
    )
)

_OPTIONAL_AUGMENTATION_BLOCKS: Final[frozenset[PublicBlockKind]] = frozenset(
    {
        "visual",
        "chart",
        "carryover",
        "cause_map",
        "shared_macro",
        "crypto_indicators",
        "channel_anchors",
        "daily_thesis",
    }
)

_REPAIR_ANY_VISIBLE: Final[frozenset[str]] = frozenset(
    {
        "bad_token.bulganghanseong",
        "korean.bad_particle.mingamdo_eul",
        "markdown.broken_numeric_bold",
        "glossary.collision.forbidden_pair",
    }
)


def _optional_augmentation_disposition(
    block: PublicBlockKind,
    *,
    default: FinalizationIssueDisposition,
) -> FinalizationIssueDisposition:
    if block in _OPTIONAL_AUGMENTATION_BLOCKS:
        return OPTIONAL_BLOCK_DISPOSITIONS[block]
    return default


def _disposition_for(
    issue_code: str,
    block: PublicBlockKind,
) -> FinalizationIssueDisposition:
    # Protected diagnostics are never a reader-visible repair target. If a
    # scanner finding is incorrectly assigned there, ownership fails closed.
    if block == "diagnostics":
        return "block_segment"
    if issue_code in _REPAIR_ANY_VISIBLE:
        return "repair"
    if issue_code == "ellipsis.dangling_line":
        if block == "first_viewport":
            return "repair"
        return _optional_augmentation_disposition(block, default="record_warning")
    if issue_code == "trace.fragment":
        if block == "first_viewport":
            return "repair"
        return _optional_augmentation_disposition(block, default="block_segment")
    if issue_code == "watermark.window_bracket":
        return "replace_block" if block in {"header", "first_viewport"} else "block_segment"
    if issue_code in {"markdown.href_ellipsis", "markdown.unmatched_link"}:
        if block == "first_viewport":
            return "repair"
        return _optional_augmentation_disposition(block, default="block_segment")
    if issue_code == "summary.truncated_mid_token":
        return "replace_block" if block == "first_viewport" else "block_segment"
    if issue_code == "watchlist.matcher_reason.public":
        if block == "watchpoints":
            return OPTIONAL_BLOCK_DISPOSITIONS[block]
        return "block_segment"
    if issue_code == "public_diagnostic.raw_label":
        if block == "watchpoints":
            return OPTIONAL_BLOCK_DISPOSITIONS[block]
        return _optional_augmentation_disposition(block, default="block_segment")
    if issue_code == "template.repeated_phrase":
        return "record_warning" if block == "first_viewport" else "block_segment"
    raise AssertionError(f"registered surface issue code has no explicit policy: {issue_code}")


SURFACE_ISSUE_DISPOSITION_TABLE: Final[
    MappingProxyType[tuple[str, PublicBlockKind], FinalizationIssueDisposition]
] = MappingProxyType(
    {
        (issue_code, block): _disposition_for(issue_code, block)
        for issue_code in sorted(SURFACE_ISSUE_CODES)
        for block in PUBLIC_BLOCK_KINDS
    }
)


def surface_issue_disposition(
    issue_code: str,
    block: PublicBlockKind,
) -> FinalizationIssueDisposition:
    """Return the closed policy or fail a missing code/block pair safely."""

    return SURFACE_ISSUE_DISPOSITION_TABLE.get((issue_code, block), "block_segment")


__all__ = [
    "OPTIONAL_BLOCK_DISPOSITIONS",
    "PUBLIC_BLOCK_KINDS",
    "SURFACE_ISSUE_CODES",
    "SURFACE_ISSUE_DISPOSITION_TABLE",
    "FinalizationIssueDisposition",
    "PublicBlockKind",
    "surface_issue_disposition",
]
