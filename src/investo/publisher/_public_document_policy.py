"""Closed u144 surface-issue disposition policy.

This module contains policy only. Detection remains owned by
``investo._internal.surface_quality``; the finalizer consumes this table rather
than duplicating scanner regexes or repairing by unowned text search.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final, Literal

from investo._internal.surface_quality import SurfaceLinkShape

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

FINALIZATION_DISPOSITION_PRECEDENCE: Final[tuple[FinalizationIssueDisposition, ...]] = (
    "block_segment",
    "omit_optional_block",
    "replace_block",
    "repair",
    "record_warning",
)

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

SURFACE_LINK_SHAPES_BY_CODE: Final[Mapping[str, tuple[SurfaceLinkShape, ...]]] = MappingProxyType(
    {
        "markdown.href_ellipsis": (
            "inline_link",
            "image",
            "autolink",
            "reference_definition",
        ),
        "markdown.unmatched_link": (
            "incomplete_inline",
            "unmatched_residual",
        ),
    }
)

_RECOVERABLE_LINK_SHAPES: Final[frozenset[SurfaceLinkShape]] = frozenset(
    {"inline_link", "image", "autolink", "incomplete_inline"}
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
    if issue_code in SURFACE_LINK_SHAPES_BY_CODE:
        # Link policy requires the canonical scanner-owned shape. The legacy
        # two-key lookup remains fail-closed for callers that omit it.
        return "block_segment"
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


def _link_disposition_for(
    block: PublicBlockKind,
    link_shape: SurfaceLinkShape,
) -> FinalizationIssueDisposition:
    if block in {"first_viewport", "section_body"}:
        return "repair" if link_shape in _RECOVERABLE_LINK_SHAPES else "replace_block"
    if block in OPTIONAL_BLOCK_DISPOSITIONS:
        return OPTIONAL_BLOCK_DISPOSITIONS[block]
    return "block_segment"


SURFACE_LINK_ISSUE_DISPOSITION_TABLE: Final[
    MappingProxyType[
        tuple[str, PublicBlockKind, SurfaceLinkShape],
        FinalizationIssueDisposition,
    ]
] = MappingProxyType(
    {
        (issue_code, block, link_shape): _link_disposition_for(block, link_shape)
        for issue_code, link_shapes in SURFACE_LINK_SHAPES_BY_CODE.items()
        for block in PUBLIC_BLOCK_KINDS
        for link_shape in link_shapes
    }
)


def surface_issue_disposition(
    issue_code: str,
    block: PublicBlockKind,
    *,
    link_shape: SurfaceLinkShape | None = None,
) -> FinalizationIssueDisposition:
    """Return the closed policy or fail a missing code/block/shape safely."""

    if issue_code in SURFACE_LINK_SHAPES_BY_CODE:
        if link_shape is None:
            return "block_segment"
        return SURFACE_LINK_ISSUE_DISPOSITION_TABLE.get(
            (issue_code, block, link_shape),
            "block_segment",
        )
    if link_shape is not None:
        return "block_segment"

    return SURFACE_ISSUE_DISPOSITION_TABLE.get((issue_code, block), "block_segment")


def strongest_surface_disposition(
    issue_codes: Sequence[str],
    block: PublicBlockKind,
) -> FinalizationIssueDisposition:
    """Resolve one grouped region action through the fixed R10 precedence."""

    codes = tuple(issue_codes)
    if not codes:
        raise ValueError("issue_codes must not be empty")
    dispositions = {surface_issue_disposition(code, block) for code in codes}
    return next(
        disposition
        for disposition in FINALIZATION_DISPOSITION_PRECEDENCE
        if disposition in dispositions
    )


__all__ = [
    "FINALIZATION_DISPOSITION_PRECEDENCE",
    "OPTIONAL_BLOCK_DISPOSITIONS",
    "PUBLIC_BLOCK_KINDS",
    "SURFACE_ISSUE_CODES",
    "SURFACE_ISSUE_DISPOSITION_TABLE",
    "SURFACE_LINK_ISSUE_DISPOSITION_TABLE",
    "SURFACE_LINK_SHAPES_BY_CODE",
    "FinalizationIssueDisposition",
    "PublicBlockKind",
    "strongest_surface_disposition",
    "surface_issue_disposition",
]
