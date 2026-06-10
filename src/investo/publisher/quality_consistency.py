"""u69 — cross-surface canonical quality-snapshot consistency validator.

The public quality surfaces for one ``(date)`` are derived from several
artifacts that are produced by different stages:

* per-segment markdown status blocks in
  ``archive/{segment}/YYYY/MM/YYYY-MM-DD.md`` (``**데이터 상태**`` line),
* the append-only ``archive/_meta/quality_history.jsonl`` row,
* the rendered ``site_docs/quality.md`` dashboard,
* the latest / archive index status cards.

Before u69 these could silently disagree: a segment body could declare
``실패`` / ``제한`` / ``[데이터부족]`` while the public dashboard rendered
``0`` failed sources or ``n/a`` liveness, implying a healthier run than
the archive actually recorded. That is a reader-trust defect.

This module does **not** redefine severity tiers, KPI families, or
collection (u54 / u62 / u65 own those). It only validates that all
public surfaces agree on the *same* canonical snapshot for a date and
returns deterministic, stable error codes when they do not.

Canonical snapshot definition for a date:

* **worst status** — the worst (highest ranked) of the per-segment
  statuses parsed from segment markdown status blocks, reconciled with
  ``quality_history.jsonl.worst_severity`` when present. ``failed`` >
  ``limited`` > ``partial`` > ``normal``.
* **has failed evidence** — any segment markdown status block reports a
  non-zero ``실패`` source count, or the history row carries
  ``total_failed_sources > 0``.

Pure functions — callers (replay harness, publish boundary) supply the
artifact text / paths; nothing here mutates the archive or hits a
network / LLM.
"""

from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final

from investo.briefing.segments import (
    COVERAGE_STATUS_LABELS,
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    CoverageStatus,
    MarketSegment,
)

if TYPE_CHECKING:
    from investo.briefing.quality_eval import QualityKPIs

# Severity ranking — identical ordering to u54's ``_SEVERITY_RANK`` but
# kept local so this module does not depend on quality_history internals.
# A divergence between the two would be caught by the unit tests that
# pin both maps.
_SEVERITY_RANK: Final[dict[str, int]] = {
    "normal": 0,
    "partial": 1,
    "limited": 2,
    "failed": 3,
}

# Reverse-map the Korean status label rendered in the segment status
# block (``**데이터 상태**: 실패 — ...``) back to the canonical tier.
_LABEL_TO_STATUS: Final[dict[str, CoverageStatus]] = {
    label: status for status, label in COVERAGE_STATUS_LABELS.items()
}

_STATUS_BLOCK_RE: Final[re.Pattern[str]] = re.compile(r"\*\*데이터 상태\*\*\s*:\s*([^\s—·\n]+)")
# ``> **소스 카운트**: 수집 대상 5 / 성공 1 / 0건 0 / 실패 3 / 본문 사용 2``
_FAILED_COUNT_RE: Final[re.Pattern[str]] = re.compile(r"실패\s+(\d+)")
_DATA_LIMITED_MARKERS: Final[tuple[str, ...]] = (
    "[데이터부족]",
    "데이터 부족 안내",
    "실시간 안내",
)

_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)

# Error codes — stable, machine-greppable.
CODE_STATUS_MISMATCH: Final[str] = "quality.status_mismatch"
CODE_FAILED_COUNT_MISMATCH: Final[str] = "quality.failed_count_mismatch"
CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE: Final[str] = (
    "quality.denominator_unknown_but_evidence_present"
)
CODE_QUALITY_PAGE_MISSING: Final[str] = "quality.quality_page_missing"
CODE_CURRENT_RUN_UNDERSTATED: Final[str] = "quality.current_run_understated"


@dataclass(frozen=True, slots=True)
class ConsistencyFinding:
    """One canonical-consistency violation for a ``(date)``.

    ``skipped=True`` marks a surface that could not be compared because
    its artifact was not generated in this run (e.g. ``site_docs/quality.md``
    is absent). A skipped finding is *not* a pass and *not* a failure —
    callers record it but it never causes the gate to fail.
    """

    code: str
    segment: MarketSegment | None
    message: str
    skipped: bool = False

    @property
    def is_failure(self) -> bool:
        return not self.skipped


@dataclass(frozen=True, slots=True)
class SegmentStatusBlock:
    """Parsed view of one segment markdown status block."""

    segment: MarketSegment
    status: CoverageStatus | None
    failed_count: int
    data_limited: bool


@dataclass(frozen=True, slots=True)
class CanonicalQualitySnapshot:
    """The one snapshot every public surface for a date must agree with.

    Built from segment markdown status blocks reconciled with the
    quality-history row. ``worst_status`` is ``None`` only when no
    segment artifact and no history row exist for the date (genuinely
    unknown).
    """

    target_date: date
    worst_status: CoverageStatus | None
    has_failed_evidence: bool
    history_worst_severity: str | None
    history_total_failed_sources: int | None
    segment_blocks: tuple[SegmentStatusBlock, ...]
    current_run_zero_item_sources: int
    current_run_core_missing_segments: int
    current_run_segments_limited_or_worse: int
    current_run_data_limited_briefings: int
    current_run_briefings_observed: int


def parse_segment_status_block(text: str, segment: MarketSegment) -> SegmentStatusBlock:
    """Extract the canonical status + failed-source count from one segment body."""
    status: CoverageStatus | None = None
    match = _STATUS_BLOCK_RE.search(text)
    if match is not None:
        status = _LABEL_TO_STATUS.get(match.group(1).strip())
    failed_match = _FAILED_COUNT_RE.search(text)
    failed_count = int(failed_match.group(1)) if failed_match is not None else 0
    return SegmentStatusBlock(
        segment=segment,
        status=status,
        failed_count=failed_count,
        data_limited=any(marker in text for marker in _DATA_LIMITED_MARKERS),
    )


def load_quality_history_row(target_date: date, history_path: Path) -> dict[str, object] | None:
    """Return the JSONL row for ``target_date`` (or ``None``)."""
    if not history_path.exists():
        return None
    wanted = target_date.isoformat()
    with history_path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("date") == wanted:
                return parsed
    return None


def build_canonical_snapshot(
    target_date: date,
    *,
    segment_texts: dict[MarketSegment, str],
    history_row: dict[str, object] | None,
) -> CanonicalQualitySnapshot:
    """Derive the canonical snapshot from segment bodies + history row."""
    blocks: list[SegmentStatusBlock] = []
    for segment in _SEGMENTS:
        text = segment_texts.get(segment)
        if text is None:
            continue
        blocks.append(parse_segment_status_block(text, segment))

    worst_rank = -1
    worst_status: CoverageStatus | None = None
    for block in blocks:
        if block.status is None:
            continue
        rank = _SEVERITY_RANK.get(block.status, -1)
        if rank > worst_rank:
            worst_rank = rank
            worst_status = block.status

    history_worst: str | None = None
    history_failed: int | None = None
    current_run_zero_item_sources = 0
    current_run_core_missing_segments = 0
    current_run_segments_limited_or_worse = 0
    current_run_data_limited_briefings = sum(1 for block in blocks if block.data_limited)
    current_run_briefings_observed = len(blocks)
    if history_row is not None:
        raw_worst = history_row.get("worst_severity")
        if isinstance(raw_worst, str):
            history_worst = raw_worst
        raw_failed = history_row.get("total_failed_sources")
        if isinstance(raw_failed, int) and not isinstance(raw_failed, bool):
            history_failed = raw_failed
        current_run_zero_item_sources = _non_negative_int(
            history_row.get("current_run_zero_item_sources")
        )
        current_run_core_missing_segments = _non_negative_int(
            history_row.get("current_run_core_missing_segments")
        )
        current_run_segments_limited_or_worse = _non_negative_int(
            history_row.get("current_run_segments_limited_or_worse")
        )
        current_run_data_limited_briefings = max(
            current_run_data_limited_briefings,
            _non_negative_int(history_row.get("current_run_data_limited_briefings")),
        )
        current_run_briefings_observed = max(
            current_run_briefings_observed,
            _non_negative_int(history_row.get("current_run_briefings_observed")),
        )

    current_run_segments_limited_or_worse = max(
        current_run_segments_limited_or_worse,
        sum(1 for block in blocks if block.status in ("limited", "failed")),
    )

    # Reconcile worst status with the history severity (worst-wins, u54).
    if history_worst is not None:
        history_rank = _SEVERITY_RANK.get(history_worst, -1)
        if history_rank > worst_rank:
            worst_rank = history_rank
            # history_worst is one of the known severities by construction.
            worst_status = history_worst  # type: ignore[assignment]

    has_failed_evidence = any(block.failed_count > 0 for block in blocks) or (
        history_failed is not None and history_failed > 0
    )

    return CanonicalQualitySnapshot(
        target_date=target_date,
        worst_status=worst_status,
        has_failed_evidence=has_failed_evidence,
        history_worst_severity=history_worst,
        history_total_failed_sources=history_failed,
        segment_blocks=tuple(blocks),
        current_run_zero_item_sources=current_run_zero_item_sources,
        current_run_core_missing_segments=current_run_core_missing_segments,
        current_run_segments_limited_or_worse=current_run_segments_limited_or_worse,
        current_run_data_limited_briefings=current_run_data_limited_briefings,
        current_run_briefings_observed=current_run_briefings_observed,
    )


def check_quality_consistency(
    snapshot: CanonicalQualitySnapshot,
    *,
    quality_page_text: str | None,
) -> tuple[ConsistencyFinding, ...]:
    """Compare every public surface against the canonical snapshot.

    Returns deterministic findings. An empty tuple means all compared
    surfaces agree. ``quality_page_text=None`` records a skipped finding
    for the dashboard surface rather than failing.
    """
    findings: list[ConsistencyFinding] = []

    # 1. Per-segment status block vs quality-history worst severity.
    #    History must not present a *better* worst severity than any
    #    segment body declares.
    if snapshot.worst_status is not None and snapshot.history_worst_severity is not None:
        canonical_rank = _SEVERITY_RANK.get(snapshot.worst_status, -1)
        history_rank = _SEVERITY_RANK.get(snapshot.history_worst_severity, -1)
        if history_rank < canonical_rank:
            findings.append(
                ConsistencyFinding(
                    CODE_STATUS_MISMATCH,
                    None,
                    f"{snapshot.target_date.isoformat()}: quality_history worst_severity="
                    f"{snapshot.history_worst_severity!r} is better than worst segment status="
                    f"{snapshot.worst_status!r}",
                )
            )

    # 2. failed-source count: any segment body declares failed sources but
    #    the history row records zero / omits the field.
    if snapshot.has_failed_evidence and (
        snapshot.history_total_failed_sources is not None
        and snapshot.history_total_failed_sources == 0
    ):
        findings.append(
            ConsistencyFinding(
                CODE_FAILED_COUNT_MISMATCH,
                None,
                f"{snapshot.target_date.isoformat()}: segment bodies report failed sources but "
                "quality_history total_failed_sources=0",
            )
        )

    # 3. quality.md dashboard surface.
    if quality_page_text is None:
        findings.append(
            ConsistencyFinding(
                CODE_QUALITY_PAGE_MISSING,
                None,
                f"{snapshot.target_date.isoformat()}: site_docs/quality.md not generated this run",
                skipped=True,
            )
        )
    else:
        findings.extend(_check_quality_page(snapshot, quality_page_text))

    return tuple(findings)


def _check_quality_page(
    snapshot: CanonicalQualitySnapshot,
    quality_page_text: str,
) -> tuple[ConsistencyFinding, ...]:
    """Dashboard must not render n/a / 0 where the snapshot carries evidence."""
    findings: list[ConsistencyFinding] = []
    failed_line = _dashboard_metric_value(quality_page_text, "실패한 소스 누적")
    if snapshot.has_failed_evidence and failed_line is not None and _is_zero_or_na(failed_line):
        findings.append(
            ConsistencyFinding(
                CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE,
                None,
                f"{snapshot.target_date.isoformat()}: quality.md renders 실패한 소스 누적="
                f"{failed_line!r} but segment/history evidence shows failed sources",
            )
        )
    metric_floors = (
        ("0건 반환 소스 누적", snapshot.current_run_zero_item_sources),
        ("핵심 소스 결손 세그먼트", snapshot.current_run_core_missing_segments),
        ("제한/실패 세그먼트", snapshot.current_run_segments_limited_or_worse),
    )
    for label, floor in metric_floors:
        rendered = _dashboard_metric_value(quality_page_text, label)
        if floor > 0 and rendered is not None and _metric_int(rendered) < floor:
            findings.append(
                ConsistencyFinding(
                    CODE_CURRENT_RUN_UNDERSTATED,
                    None,
                    f"{snapshot.target_date.isoformat()}: quality.md renders {label}="
                    f"{rendered!r} below current-run evidence {floor}",
                )
            )
    fallback_line = _dashboard_metric_value(quality_page_text, "데이터 부족 폴백")
    fallback_denominator = _dashboard_metric_denominator(quality_page_text, "데이터 부족 폴백")
    if (
        snapshot.current_run_data_limited_briefings > 0
        and fallback_line is not None
        and _metric_pct(fallback_line) <= 0.0
    ):
        findings.append(
            ConsistencyFinding(
                CODE_CURRENT_RUN_UNDERSTATED,
                None,
                f"{snapshot.target_date.isoformat()}: quality.md renders 데이터 부족 폴백="
                f"{fallback_line!r} below current-run evidence "
                f"{snapshot.current_run_data_limited_briefings}",
            )
        )
    if (
        snapshot.current_run_briefings_observed > 0
        and fallback_denominator is not None
        and _metric_int(fallback_denominator) < snapshot.current_run_briefings_observed
    ):
        findings.append(
            ConsistencyFinding(
                CODE_CURRENT_RUN_UNDERSTATED,
                None,
                f"{snapshot.target_date.isoformat()}: quality.md renders 데이터 부족 폴백 "
                f"denominator={fallback_denominator!r} below current-run observed "
                f"{snapshot.current_run_briefings_observed}",
            )
        )
    return tuple(findings)


def _dashboard_metric_value(text: str, label: str) -> str | None:
    """Return the value cell of a ``| label | value | denom |`` table row."""
    pattern = re.compile(
        rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|",
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _dashboard_metric_denominator(text: str, label: str) -> str | None:
    pattern = re.compile(
        rf"\|\s*{re.escape(label)}\s*\|\s*[^|]+?\s*\|\s*([^|]+?)\s*\|",
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _metric_int(value: str) -> int:
    match = re.search(r"\d+", value)
    if match is None:
        return 0
    return int(match.group(0))


def _metric_pct(value: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value)
    if match is None:
        return 0.0
    return float(match.group(0))


def _non_negative_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return 0
    return value


def _is_zero_or_na(value: str) -> bool:
    cleaned = value.strip().rstrip("회건%").strip()
    if cleaned in ("n/a", "0", "0.0", "0.0%"):
        return True
    return cleaned in ("0회", "0건")


def reconcile_kpis_with_history(
    kpis: QualityKPIs,
    *,
    target_date: date,
    history_path: Path,
) -> QualityKPIs:
    """u69 — raise the dashboard failed-source floor to canonical evidence.

    The trailing-window KPIs are computed from ``coverage.jsonl``, which
    can be empty / lagging while the canonical ``quality_history.jsonl``
    row for ``target_date`` already records ``total_failed_sources > 0``.
    Rendering ``실패한 소스 누적 = 0`` in that case is the contradiction
    u69 closes: the public dashboard would look healthier than the
    archive. When the history evidence exceeds the coverage-derived
    count we bump ``failed_sources`` (and, when zero, ``runs_observed``
    + ``runs_with_failed_source`` so the liveness rate also reflects the
    failure) so the rendered dashboard agrees with the same canonical
    snapshot the publish-boundary gate validates against.

    Returns the KPIs unchanged when no reconciliation is needed (pure,
    idempotent).
    """
    row = load_quality_history_row(target_date, history_path)
    if row is None:
        return kpis
    raw_failed = _non_negative_int(row.get("total_failed_sources"))
    current_run_zero_item_sources = _non_negative_int(row.get("current_run_zero_item_sources"))
    current_run_core_missing_segments = _non_negative_int(
        row.get("current_run_core_missing_segments")
    )
    current_run_segments_limited_or_worse = _non_negative_int(
        row.get("current_run_segments_limited_or_worse")
    )
    current_run_data_limited_briefings = _non_negative_int(
        row.get("current_run_data_limited_briefings")
    )
    current_run_briefings_observed = _non_negative_int(
        row.get("current_run_briefings_observed")
    )
    if (
        raw_failed <= 0
        and current_run_zero_item_sources <= 0
        and current_run_core_missing_segments <= 0
        and current_run_segments_limited_or_worse <= 0
        and current_run_data_limited_briefings <= 0
        and current_run_briefings_observed <= 0
    ):
        return kpis
    if (
        kpis.failed_sources >= raw_failed
        and kpis.zero_item_sources >= current_run_zero_item_sources
        and kpis.core_missing_segments >= current_run_core_missing_segments
        and kpis.segments_limited_or_worse >= current_run_segments_limited_or_worse
        and kpis.briefings_data_limited >= current_run_data_limited_briefings
        and kpis.briefings_observed >= current_run_briefings_observed
    ):
        return kpis
    runs_observed = max(kpis.runs_observed, 1)
    runs_with_failed = max(kpis.runs_with_failed_source, 1 if raw_failed > 0 else 0)
    return dataclasses.replace(
        kpis,
        failed_sources=max(kpis.failed_sources, raw_failed),
        zero_item_sources=max(kpis.zero_item_sources, current_run_zero_item_sources),
        core_missing_segments=max(kpis.core_missing_segments, current_run_core_missing_segments),
        segments_limited_or_worse=max(
            kpis.segments_limited_or_worse,
            current_run_segments_limited_or_worse,
        ),
        briefings_data_limited=max(
            kpis.briefings_data_limited,
            current_run_data_limited_briefings,
        ),
        briefings_observed=max(kpis.briefings_observed, current_run_briefings_observed),
        runs_observed=runs_observed,
        runs_with_failed_source=runs_with_failed,
    )


def validate_date_quality_consistency(
    target_date: date,
    *,
    segment_texts: dict[MarketSegment, str],
    history_path: Path,
    quality_page_text: str | None,
) -> tuple[ConsistencyFinding, ...]:
    """End-to-end convenience: load history row, build snapshot, validate."""
    history_row = load_quality_history_row(target_date, history_path)
    snapshot = build_canonical_snapshot(
        target_date,
        segment_texts=segment_texts,
        history_row=history_row,
    )
    return check_quality_consistency(snapshot, quality_page_text=quality_page_text)


__all__ = [
    "CODE_CURRENT_RUN_UNDERSTATED",
    "CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE",
    "CODE_FAILED_COUNT_MISMATCH",
    "CODE_QUALITY_PAGE_MISSING",
    "CODE_STATUS_MISMATCH",
    "CanonicalQualitySnapshot",
    "ConsistencyFinding",
    "SegmentStatusBlock",
    "build_canonical_snapshot",
    "check_quality_consistency",
    "load_quality_history_row",
    "parse_segment_status_block",
    "reconcile_kpis_with_history",
    "validate_date_quality_consistency",
]
