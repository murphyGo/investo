"""Update public site discovery pages for the latest segmented briefing."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Final

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, SEGMENT_LABELS, US_EQUITY

SITE_INDEX_PATH: Final[Path] = Path("site_docs/index.md")
ARCHIVE_INDEX_PATH: Final[Path] = Path("archive/index.md")
_SEGMENTS = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)


def update_latest_index_pages(
    target_date: date,
    *,
    site_index_path: Path = SITE_INDEX_PATH,
    archive_index_path: Path = ARCHIVE_INDEX_PATH,
) -> tuple[Path, ...]:
    """Refresh Home and Archive latest-link sections for ``target_date``."""
    _replace_section(
        site_index_path,
        "## 최신 시황",
        _site_latest_section(target_date),
    )
    _replace_section(
        archive_index_path,
        "## 최신 시황",
        _archive_latest_section(target_date),
    )
    _replace_section(
        archive_index_path,
        "## 과거 단일 시황",
        _legacy_section(archive_index_path.parent),
    )
    return (site_index_path, archive_index_path)


def _site_latest_section(target_date: date) -> str:
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(
            f"- [{SEGMENT_LABELS[segment]}]({_site_segment_href(target_date, segment)})"
            for segment in _SEGMENTS
        )
        + "\n\n[전체 Archive 보기](archive/index.md)"
    )


def _archive_latest_section(target_date: date) -> str:
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(
            f"- [{SEGMENT_LABELS[segment]}]({_archive_segment_href(target_date, segment)})"
            for segment in _SEGMENTS
        )
    )


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


def _replace_section(path: Path, heading: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    start = content.index(heading)
    next_heading = content.find("\n## ", start + len(heading))
    end = len(content) if next_heading == -1 else next_heading
    updated = content[:start] + replacement.rstrip() + "\n" + content[end:]
    _write_text_atomic(path, updated)


def _write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


__all__ = ["ARCHIVE_INDEX_PATH", "SITE_INDEX_PATH", "update_latest_index_pages"]
