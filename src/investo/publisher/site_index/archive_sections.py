"""Archive-index 최신/과거 sections + publish-calendar heatmap (u29).

The Archive index (``site_docs/archive/index.md``) keeps its 최신 시황 /
과거 단일 시황 sections refreshed and additionally embeds a
deterministic publish calendar heatmap (see
:func:`update_archive_heatmap_section` and the
:mod:`investo.visuals.calendar_heatmap` renderer).

Also home to the bundle-state model and the shared segment-href helpers
used by both the Home hero cards and the archive section lines.

Move-only split out of the original ``site_index.py`` module (u82).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from investo.briefing.segments import SEGMENT_LABELS, MarketSegment
from investo.models import Briefing

from ._blocks import _replace_marker_block
from ._constants import (
    _SEGMENTS,
    ARCHIVE_INDEX_PATH,
    HEATMAP_BEGIN,
    HEATMAP_END,
)
from .segment_archives import _segment_entries


@dataclass(frozen=True, slots=True)
class SegmentBundleState:
    """Reader-facing state for one segment in a dated bundle."""

    segment: MarketSegment
    target_date: date
    generated: bool
    href: str
    fallback_date: date | None = None
    fallback_href: str | None = None

    @property
    def label(self) -> str:
        return SEGMENT_LABELS[self.segment]


def update_archive_heatmap_section(
    heatmap_svg: str,
    *,
    archive_index_path: Path = ARCHIVE_INDEX_PATH,
) -> Path:
    """Replace the marker-bracketed publish-calendar SVG on Archive index."""
    body = _render_heatmap_block(heatmap_svg)
    _replace_marker_block(
        archive_index_path,
        begin_marker=HEATMAP_BEGIN,
        end_marker=HEATMAP_END,
        replacement=body,
    )
    return archive_index_path


def _render_heatmap_block(heatmap_svg: str) -> str:
    return (
        "## 발행 캘린더\n\n"
        "지난 주차별 게시 일자와 데이터 신뢰도(정상·부분·부족)를 "
        "한눈에 표시합니다.\n\n"
        '<figure class="u29-heatmap" markdown="1">\n'
        f"{heatmap_svg.strip()}\n"
        "<figcaption>발행 캘린더 — 색상은 데이터 신뢰도 정책을 따릅니다.</figcaption>\n"
        "</figure>\n"
    )


def _build_bundle_states(
    target_date: date,
    *,
    archive_root: Path,
    segment_briefings: dict[MarketSegment, Briefing] | None,
) -> tuple[SegmentBundleState, ...]:
    generated = (
        frozenset(segment_briefings) if segment_briefings is not None else frozenset(_SEGMENTS)
    )
    states: list[SegmentBundleState] = []
    for segment in _SEGMENTS:
        if segment in generated:
            states.append(
                SegmentBundleState(
                    segment=segment,
                    target_date=target_date,
                    generated=True,
                    href=_archive_segment_href(target_date, segment),
                )
            )
            continue
        fallback = _latest_segment_entry_before(
            archive_root / segment,
            before=target_date,
        )
        fallback_date = date.fromisoformat(fallback.stem) if fallback is not None else None
        states.append(
            SegmentBundleState(
                segment=segment,
                target_date=target_date,
                generated=False,
                href=_archive_segment_href(target_date, segment),
                fallback_date=fallback_date,
                fallback_href=(
                    f"{segment}/{fallback.parent.parent.name}/{fallback.parent.name}/{fallback.name}"
                    if fallback is not None
                    else None
                ),
            )
        )
    return tuple(states)


def _site_latest_section(
    target_date: date,
    states: tuple[SegmentBundleState, ...] | None = None,
) -> str:
    bundle_states = (
        states
        if states is not None
        else _build_bundle_states(
            target_date,
            archive_root=ARCHIVE_INDEX_PATH.parent,
            segment_briefings=None,
        )
    )
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(_render_bundle_state_line(state, site=True) for state in bundle_states)
        + "\n\n[전체 Archive 보기](archive/index.md)"
    )


def _archive_latest_section(
    target_date: date,
    states: tuple[SegmentBundleState, ...] | None = None,
) -> str:
    bundle_states = (
        states
        if states is not None
        else _build_bundle_states(
            target_date,
            archive_root=ARCHIVE_INDEX_PATH.parent,
            segment_briefings=None,
        )
    )
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(_render_bundle_state_line(state, site=False) for state in bundle_states)
    )


def _render_bundle_state_line(state: SegmentBundleState, *, site: bool) -> str:
    if state.generated:
        href = f"archive/{state.href}" if site else state.href
        return f"- [{state.label}]({href})"
    if state.fallback_date is not None and state.fallback_href is not None:
        href = f"archive/{state.fallback_href}" if site else state.fallback_href
        return (
            f"- {state.label}: {state.target_date.isoformat()} 미발행 · "
            f"[최근 {state.fallback_date.isoformat()}]({href})"
        )
    return f"- {state.label}: {state.target_date.isoformat()} 미발행 · 이전 발행 없음"


def _legacy_section(archive_root: Path) -> str:
    legacy_paths = sorted(
        path for path in archive_root.glob("[0-9][0-9][0-9][0-9]/*/*.md") if path.name != "index.md"
    )
    body = (
        "과거 단일 시황은 세그먼트 분리 이전 형식입니다. 최신 탐색은 위의 "
        "국내 증시·미국 증시·크립토 링크를 우선 사용하세요."
    )
    if not legacy_paths:
        return f"## 과거 단일 시황\n\n{body}\n\n- 현재 표시할 레거시 단일 시황이 없습니다."
    links = "\n".join(
        f"- [{path.stem} 단일 시황 (레거시)]({path.relative_to(archive_root).as_posix()})"
        for path in legacy_paths
    )
    return f"## 과거 단일 시황\n\n{body}\n\n{links}"


def _site_segment_href(target_date: date, segment: str) -> str:
    return f"archive/{_archive_segment_href(target_date, segment)}"


def _archive_segment_href(target_date: date, segment: str) -> str:
    return f"{segment}/{target_date.year:04d}/{target_date.month:02d}/{target_date.isoformat()}.md"


def _latest_segment_entry_before(archive_dir: Path, *, before: date) -> Path | None:
    for entry in _segment_entries(archive_dir):
        try:
            entry_date = date.fromisoformat(entry.stem)
        except ValueError:
            continue
        if entry_date < before:
            return entry
    return None
