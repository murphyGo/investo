"""Terminal reader-visible public-language projection for u144."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from investo._internal.public_quality_language import (
    first_forbidden_public_evidence,
    project_public_quality_language,
)

if TYPE_CHECKING:
    from investo.publisher._public_document_policy import PublicBlockKind
    from investo.publisher.public_document import (
        PublicDocumentLayout,
        PublicLimitationReason,
    )

_FENCE_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<suffix>.*)$"
)


@dataclass(frozen=True, slots=True)
class PublicLabelLeakage:
    """One bounded u108 evidence match in a reader-visible owned region."""

    region_id: str
    block: PublicBlockKind
    evidence: str


def _line_content_and_ending(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith(("\r", "\n")):
        return raw_line[:-1], raw_line[-1]
    return raw_line, ""


def _opening_fence(line: str) -> tuple[str, int] | None:
    match = _FENCE_LINE_RE.match(line)
    if match is None:
        return None
    fence = match.group("fence")
    if fence[0] == "`" and "`" in match.group("suffix"):
        return None
    return fence[0], len(fence)


def _is_closing_fence(line: str, marker: tuple[str, int]) -> bool:
    match = _FENCE_LINE_RE.match(line)
    if match is None or match.group("suffix").strip():
        return False
    fence = match.group("fence")
    return fence[0] == marker[0] and len(fence) >= marker[1]


def _project_reader_visible_region(markdown: str) -> str:
    projected: list[str] = []
    fence_marker: tuple[str, int] | None = None
    for raw_line in markdown.splitlines(keepends=True):
        line, ending = _line_content_and_ending(raw_line)
        if fence_marker is None:
            opening = _opening_fence(line)
            if opening is not None:
                fence_marker = opening
                projected.append(raw_line)
                continue
        elif _is_closing_fence(line, fence_marker):
            fence_marker = None
            projected.append(raw_line)
            continue
        if fence_marker is not None or first_forbidden_public_evidence(line) is None:
            projected.append(raw_line)
            continue
        projected.append(project_public_quality_language(line) + ending)
    return "".join(projected)


def _iter_unfenced_reader_lines(markdown: str) -> Iterator[str]:
    fence_marker: tuple[str, int] | None = None
    for raw_line in markdown.splitlines(keepends=True):
        line, _ending = _line_content_and_ending(raw_line)
        if fence_marker is None:
            opening = _opening_fence(line)
            if opening is not None:
                fence_marker = opening
                continue
            yield line
            continue
        if _is_closing_fence(line, fence_marker):
            fence_marker = None


def find_reader_visible_public_label_leaks(
    layout: PublicDocumentLayout,
) -> tuple[PublicLabelLeakage, ...]:
    """Read every reader-visible owned region through the u108 predicate.

    Protected diagnostics, exact disclaimer bytes, and fenced code are outside
    this public-language check by their existing typed policies. Reader-visible
    tables and arbitrary details receive no blanket exemption. The traversal
    never repairs, reindexes, or mutates the supplied layout.
    """

    leaks: list[PublicLabelLeakage] = []
    for region in layout.regions:
        if region.projection_policy != "reader_visible":
            continue
        fragment = layout.markdown[region.start : region.end]
        for line in _iter_unfenced_reader_lines(fragment):
            evidence = first_forbidden_public_evidence(line)
            if evidence is not None:
                leaks.append(
                    PublicLabelLeakage(
                        region_id=region.region_id,
                        block=region.block,
                        evidence=evidence,
                    )
                )
    return tuple(leaks)


def project_public_markdown(
    layout: PublicDocumentLayout,
    *,
    limitation_reasons: tuple[PublicLimitationReason, ...],
) -> PublicDocumentLayout:
    """Project only reader-visible regions, preserving owned protected bytes.

    The typed reasons are already rendered by their owning producers.  This
    terminal pass keeps them explicit on the phase boundary while providing
    defense in depth for any direct raw diagnostic fragment that survives
    assembly.
    """

    if tuple(dict.fromkeys(limitation_reasons)) != limitation_reasons:
        raise ValueError("limitation_reasons must be unique and ordered")
    fragments: list[str] = []
    for region in layout.regions:
        fragment = layout.markdown[region.start : region.end]
        if region.projection_policy == "reader_visible":
            fragment = _project_reader_visible_region(fragment)
        fragments.append(fragment)
    markdown = "".join(fragments)
    if markdown == layout.markdown:
        return layout
    return type(layout).reindex(markdown, expectation=layout.expectation)


__all__ = [
    "PublicLabelLeakage",
    "find_reader_visible_public_label_leaks",
    "project_public_markdown",
]
