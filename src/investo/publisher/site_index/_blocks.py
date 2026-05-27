"""Shared block-replacement / escape / atomic-write helpers for site_index.

These are the move-only primitives reused by all four site-discovery
surfaces (hero / archive_sections / segment_archives / quality_dashboard).
They were colocated in the original ``site_index.py`` module; the u82
split lifts them here so each surface module imports from one place.

``_write_text_atomic`` delegates to the shared u78 primitive
(:func:`investo._internal._io.write_atomic`) — there is no second
atomic-write implementation in the site_index package.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from investo._internal._io import write_atomic

# Match a markdown header line that *immediately* starts a top-level
# section (## 헤딩). Used to find the next section heading when
# refreshing the older ``## 최신 시황`` block-level sections (legacy
# behavior preserved alongside the new marker-bracketed hero block).
_NEXT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^## ", re.MULTILINE)


def _replace_section(path: Path, heading: str, replacement: str) -> None:
    """Replace a top-level ``## `` section between two H2 headings."""
    content = path.read_text(encoding="utf-8")
    if heading not in content:
        return  # Section was removed by a future rewrite — leave file alone.
    start = content.index(heading)
    next_heading_match = _NEXT_HEADING_RE.search(content, start + len(heading))
    end = len(content) if next_heading_match is None else next_heading_match.start()
    updated = content[:start] + replacement.rstrip() + "\n" + content[end:]
    _write_text_atomic(path, updated)


def _replace_marker_block(
    path: Path,
    *,
    begin_marker: str,
    end_marker: str,
    replacement: str,
) -> None:
    """Replace the bytes between two marker comments idempotently.

    When either marker is missing, the markers + replacement are
    appended to the file so a fresh page can bootstrap the block on
    first publish. When both markers are present the block is
    rewritten in place.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        new_content = f"{begin_marker}\n{replacement.strip()}\n{end_marker}\n"
        _write_text_atomic(path, new_content)
        return

    content = path.read_text(encoding="utf-8")
    begin_idx = content.find(begin_marker)
    end_idx = content.find(end_marker)
    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        # Append a fresh block at the end of the file. A trailing
        # newline ensures the marker is on its own line even when the
        # file ends mid-line.
        suffix = "" if content.endswith("\n") else "\n"
        new_content = (
            content + suffix + "\n" + f"{begin_marker}\n{replacement.strip()}\n{end_marker}\n"
        )
        _write_text_atomic(path, new_content)
        return

    new_block = f"{begin_marker}\n{replacement.strip()}\n{end_marker}"
    end_marker_end = end_idx + len(end_marker)
    updated = content[:begin_idx] + new_block + content[end_marker_end:]
    _write_text_atomic(path, updated)


def _escape_inline(text: str) -> str:
    """Escape characters that would break a single-line markdown blockquote."""
    return text.replace("\n", " ").replace("\r", " ").strip()


def _write_text_atomic(path: Path, content: str) -> None:
    write_atomic(path, content)
