"""Pure u149 planning/application for owned domestic numeric claims."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from itertools import pairwise
from typing import TYPE_CHECKING, Literal

from investo.models.public_document_outcome import (
    NumericContainmentAction,
    NumericContainmentOutcome,
)
from investo.publisher.anchor_assertion_gate import (
    AnchorAssertionFinding,
    render_data_limited_anchor_claim,
)

if TYPE_CHECKING:
    from investo.publisher._public_document_policy import PublicBlockKind
    from investo.publisher.public_document import PublicDocumentLayout, PublicDocumentRegion

_OPTIONAL_BLOCKS = frozenset({"visual", "chart", "carryover", "cause_map"})
_REPLACEABLE_BLOCKS = frozenset(
    {
        "shared_macro",
        "crypto_indicators",
        "channel_anchors",
        "daily_thesis",
    }
)
_EDITABLE_BLOCKS = frozenset({"section_body", "watchpoints", "first_viewport"})
_PROTECTED_BLOCKS = frozenset({"header", "navigation", "diagnostics", "disclaimer"})


@dataclass(frozen=True, slots=True)
class NumericRegionPlan:
    region_id: str
    operation: Literal["replace", "omit"]
    replacement_body: str | None
    outcomes: tuple[NumericContainmentOutcome, ...]


@dataclass(frozen=True, slots=True)
class NumericContainmentPlan:
    region_plans: tuple[NumericRegionPlan, ...]
    requires_minimal: bool = False


@dataclass(frozen=True, slots=True)
class NumericContainmentResult:
    layout: PublicDocumentLayout
    outcomes: tuple[NumericContainmentOutcome, ...]


def plan_numeric_containment(
    layout: PublicDocumentLayout,
    findings: Sequence[AnchorAssertionFinding],
    *,
    target_date: date,
    fallback_text_by_block: Mapping[PublicBlockKind, str],
) -> NumericContainmentPlan:
    """Build immutable per-region operations from original indexed bytes."""

    if target_date != layout.expectation.target_date or any(
        finding.segment != layout.expectation.segment for finding in findings
    ):
        return NumericContainmentPlan((), requires_minimal=True)
    canonical_findings = tuple(findings)
    if any(
        (left.start, left.end) > (right.start, right.end)
        for left, right in pairwise(canonical_findings)
    ):
        return NumericContainmentPlan((), requires_minimal=True)
    if any(left.end > right.start for left, right in pairwise(canonical_findings)):
        return NumericContainmentPlan((), requires_minimal=True)

    grouped: dict[str, list[AnchorAssertionFinding]] = defaultdict(list)
    region_index = 0
    for finding in canonical_findings:
        observed = layout.markdown[finding.start : finding.end]
        if finding.start >= finding.end or (
            observed.strip() != finding.sentence
            if finding.line_kind in {"table_row", "h3_subtree", "structural_region"}
            else observed != finding.sentence
        ):
            return NumericContainmentPlan((), requires_minimal=True)
        while (
            region_index < len(layout.regions) and layout.regions[region_index].end <= finding.start
        ):
            region_index += 1
        if region_index >= len(layout.regions):
            return NumericContainmentPlan((), requires_minimal=True)
        owner = layout.regions[region_index]
        if not (owner.start <= finding.start < finding.end <= owner.end):
            return NumericContainmentPlan((), requires_minimal=True)
        grouped[owner.region_id].append(finding)

    plans: list[NumericRegionPlan] = []
    for region in layout.regions:
        region_findings = tuple(grouped.get(region.region_id, ()))
        if not region_findings:
            continue
        if region.block in _PROTECTED_BLOCKS or region.block == "anchor_table":
            return NumericContainmentPlan((), requires_minimal=True)
        if region.block in _OPTIONAL_BLOCKS:
            plans.append(
                NumericRegionPlan(
                    region_id=region.region_id,
                    operation="omit",
                    replacement_body=None,
                    outcomes=_outcomes(
                        target_date,
                        region.region_id,
                        region_findings,
                        action="omitted",
                    ),
                )
            )
            continue
        fallback = fallback_text_by_block.get(region.block)
        if region.block in _REPLACEABLE_BLOCKS:
            if fallback is None:
                return NumericContainmentPlan((), requires_minimal=True)
            plans.append(
                NumericRegionPlan(
                    region_id=region.region_id,
                    operation="replace",
                    replacement_body=f"\n{fallback}\n\n",
                    outcomes=_outcomes(
                        target_date,
                        region.region_id,
                        region_findings,
                        action="replaced",
                    ),
                )
            )
            continue
        if region.block not in _EDITABLE_BLOCKS:
            return NumericContainmentPlan((), requires_minimal=True)
        planned = _plan_editable_region(
            layout,
            region,
            region_findings,
            target_date=target_date,
            fallback=fallback,
        )
        if planned is None:
            return NumericContainmentPlan((), requires_minimal=True)
        plans.append(planned)

    if set(grouped) != {plan.region_id for plan in plans}:
        return NumericContainmentPlan((), requires_minimal=True)
    return NumericContainmentPlan(tuple(plans))


def apply_numeric_containment_plan(
    layout: PublicDocumentLayout,
    plan: NumericContainmentPlan,
) -> NumericContainmentResult:
    """Apply one original-byte transaction, then reindex exactly once."""

    if plan.requires_minimal:
        raise ValueError("minimal-required plan cannot be applied")
    regions_by_id = {region.region_id: region for region in layout.regions}
    if any(region_plan.region_id not in regions_by_id for region_plan in plan.region_plans):
        raise ValueError("numeric containment plan references an unknown region")
    region_ids = tuple(region_plan.region_id for region_plan in plan.region_plans)
    if len(set(region_ids)) != len(region_ids):
        raise ValueError("numeric containment plan repeats a region")

    edits: list[tuple[int, int, str]] = []
    omitted_cause_ids: set[str] = set()
    for region_plan in plan.region_plans:
        region = regions_by_id[region_plan.region_id]
        if region_plan.operation == "omit":
            if region.block in {"visual", "chart", "carryover"}:
                if region.content_start == region.content_end:
                    raise ValueError("marker-backed region is already omitted")
                edits.append((region.content_start, region.content_end, ""))
            elif region.block == "cause_map" and not region.required:
                edits.append((region.start, region.end, ""))
                omitted_cause_ids.add(region.region_id)
            else:
                raise ValueError("region is not an optional omittable block")
        else:
            if region_plan.replacement_body is None:
                raise ValueError("replace plan requires replacement_body")
            edits.append(
                (
                    region.content_start,
                    region.content_end,
                    region_plan.replacement_body,
                )
            )

    ordered_edits = edits
    if any((left[0], left[1]) > (right[0], right[1]) for left, right in pairwise(ordered_edits)):
        raise ValueError("numeric containment plan regions must use source order")
    if any(left[1] > right[0] for left, right in pairwise(ordered_edits)):
        raise ValueError("numeric containment plan contains overlapping regions")
    pieces: list[str] = []
    cursor = 0
    for start, end, replacement in ordered_edits:
        pieces.extend((layout.markdown[cursor:start], replacement))
        cursor = end
    pieces.append(layout.markdown[cursor:])
    updated = type(layout).reindex("".join(pieces), expectation=layout.expectation)

    expected_non_viewport_ids = tuple(
        region.region_id
        for region in layout.regions
        if region.block != "first_viewport" and region.region_id not in omitted_cause_ids
    )
    actual_non_viewport_ids = tuple(
        region.region_id for region in updated.regions if region.block != "first_viewport"
    )
    if actual_non_viewport_ids != expected_non_viewport_ids:
        raise ValueError("region IDs changed outside omitted optional blocks")
    outcomes = tuple(
        outcome for region_plan in plan.region_plans for outcome in region_plan.outcomes
    )
    return NumericContainmentResult(updated, outcomes)


def _plan_editable_region(
    layout: PublicDocumentLayout,
    region: PublicDocumentRegion,
    findings: Sequence[AnchorAssertionFinding],
    *,
    target_date: date,
    fallback: str | None,
) -> NumericRegionPlan | None:
    region_id = region.region_id
    if any(finding.line_kind == "structural_region" for finding in findings):
        if fallback is None:
            return None
        return NumericRegionPlan(
            region_id=region_id,
            operation="replace",
            replacement_body=f"\n{fallback}\n\n",
            outcomes=_outcomes(target_date, region_id, findings, action="replaced"),
        )

    edits: list[tuple[int, int, str, NumericContainmentAction, AnchorAssertionFinding]] = []
    for finding in findings:
        if not (region.content_start <= finding.start < finding.end <= region.content_end):
            return None
        if finding.line_kind == "table_row":
            start, end = _whole_line_span(layout.markdown, finding.start, finding.end)
            replacement = ""
            action: NumericContainmentAction = "excluded"
        elif finding.line_kind == "h3_subtree":
            start, end = _h3_subtree_span(
                layout.markdown,
                finding.start,
                region.content_end,
            )
            replacement = ""
            action = "excluded"
        else:
            start, end = finding.start, finding.end
            replacement = render_data_limited_anchor_claim(finding.symbol)
            action = "rewritten"
        if not (region.content_start <= start < end <= region.content_end):
            return None
        edits.append((start, end, replacement, action, finding))

    ordered = edits
    if any(left[1] > right[0] for left, right in pairwise(ordered)):
        return None
    pieces: list[str] = []
    cursor = region.content_start
    outcomes: list[NumericContainmentOutcome] = []
    for start, end, replacement, action, finding in ordered:
        pieces.extend((layout.markdown[cursor:start], replacement))
        cursor = end
        outcomes.append(_outcome(target_date, region_id, finding, action=action))
    pieces.append(layout.markdown[cursor : region.content_end])
    return NumericRegionPlan(
        region_id=region_id,
        operation="replace",
        replacement_body="".join(pieces),
        outcomes=tuple(outcomes),
    )


def _whole_line_span(markdown: str, start: int, end: int) -> tuple[int, int]:
    if end < len(markdown) and markdown[end] == "\r":
        end += 1
    if end < len(markdown) and markdown[end] == "\n":
        end += 1
    return start, end


def _h3_subtree_span(markdown: str, start: int, region_end: int) -> tuple[int, int]:
    line_start = start
    cursor = _line_end(markdown, start, region_end)
    while cursor < region_end:
        line_end = _line_end(markdown, cursor, region_end)
        line = markdown[cursor:line_end].lstrip()
        if line.startswith(("### ", "## ")):
            return line_start, cursor
        cursor = line_end
    return line_start, region_end


def _line_end(markdown: str, start: int, limit: int) -> int:
    cursor = start
    while cursor < limit and markdown[cursor] not in "\r\n":
        cursor += 1
    if cursor >= limit:
        return limit
    if markdown[cursor] == "\r" and cursor + 1 < limit and markdown[cursor + 1] == "\n":
        return cursor + 2
    return cursor + 1


def _outcomes(
    target_date: date,
    region_id: str,
    findings: Sequence[AnchorAssertionFinding],
    *,
    action: NumericContainmentAction,
) -> tuple[NumericContainmentOutcome, ...]:
    return tuple(_outcome(target_date, region_id, finding, action=action) for finding in findings)


def _outcome(
    target_date: date,
    region_id: str,
    finding: AnchorAssertionFinding,
    *,
    action: NumericContainmentAction,
) -> NumericContainmentOutcome:
    return NumericContainmentOutcome(
        target_date=target_date,
        segment=finding.segment,
        symbol=finding.symbol,
        region_id=region_id,
        line_kind=finding.line_kind,
        action=action,
        issue_codes=("numeric.anchor_assertion",),
        claim_digest=sha256(finding.sentence.encode("utf-8")).hexdigest(),
    )


__all__ = [
    "NumericContainmentPlan",
    "NumericContainmentResult",
    "NumericRegionPlan",
    "apply_numeric_containment_plan",
    "plan_numeric_containment",
]
