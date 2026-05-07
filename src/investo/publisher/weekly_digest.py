"""Saturday-cron weekly retrospective publisher (u29 site-discovery-v2).

The Saturday 09:00 KST cron resolves ``target_date`` to the prior Friday
(US trading day). After the segmented publish for that Friday lands,
this module aggregates the prior 5 business days (Mon-Fri ending on
``target_date``) into a single retrospective markdown page at
``archive/weekly/YYYY-WNN.md`` (ISO-8601 week number).

The retrospective is text-only — no LLM call. Each day's row pulls the
``> **오늘의 결론**:`` blockquote line from the corresponding
``archive/{segment}/YYYY/MM/YYYY-MM-DD.md`` for each of the three
segments. Days with no archived briefing show "(미발행)" so weeks with
holidays / outages render gracefully instead of failing silently.

The page footer includes the standard project disclaimer because the
retrospective surfaces conclusion bullets verbatim from the segmented
archives — those have already been disclaimer-validated, but we
re-attach the disclaimer so the page itself satisfies NFR-004 when
read in isolation (e.g. someone landing on it from a Telegram preview).

Idempotent: same archive state → byte-identical retrospective. The
publisher writes via the same atomic tmp-then-replace pattern as
``writer.write_briefing``.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
)
from investo.publisher.errors import PublisherDisclaimerError
from investo.publisher.paths import ARCHIVE_ROOT, archive_path
from investo.publisher.verifier import verify_disclaimer

WEEKLY_ARCHIVE_ROOT: Final[Path] = ARCHIVE_ROOT / "weekly"
WEEKLY_INDEX_PATH: Final[Path] = WEEKLY_ARCHIVE_ROOT / "index.md"
_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
_CONCLUSION_PREFIX: Final[str] = "> **오늘의 결론**:"
_FALLBACK_NOT_PUBLISHED: Final[str] = "(미발행)"


_WEEKLY_OPT_IN_VAR: Final[str] = "INVESTO_PUBLISH_WEEKLY"


def weekly_digest_opt_in(env: dict[str, str] | None = None) -> bool:
    """Return True when the Saturday GHA cron has opted in to weekly publish.

    The two crons (KST Mon-Fri 07:00 vs KST Sat 09:00) both resolve the
    same ``target_date`` (Friday) when invoked at the start of a week,
    so ``target_date.weekday()`` alone cannot disambiguate them. The
    GHA workflow therefore sets ``INVESTO_PUBLISH_WEEKLY=1`` only on
    the Saturday cron path; this helper is the orchestrator's reading
    of that signal.

    ``env`` is a test seam — production callers pass ``None`` to read
    from :data:`os.environ`.
    """
    source: dict[str, str] | os._Environ[str] = env if env is not None else os.environ
    return source.get(_WEEKLY_OPT_IN_VAR, "").strip() == "1"


def publish_weekly_digest(
    week_end_date: date,
    *,
    archive_root: Path | None = None,
) -> Path:
    """Render and atomically write the weekly retrospective markdown.

    Parameters
    ----------
    week_end_date:
        The Friday closing the retrospective week. The aggregation
        spans Mon-Fri ending on this date (5 business days).
    archive_root:
        Override hook for tests. Production passes ``None`` so this
        defaults to :data:`investo.publisher.paths.ARCHIVE_ROOT`.

    Returns
    -------
    Path
        Absolute / repo-relative path to the written
        ``archive/weekly/YYYY-WNN.md`` file. Caller (orchestrator) is
        responsible for staging it in the same git commit as the
        Friday segmented publish.
    """
    root = archive_root if archive_root is not None else ARCHIVE_ROOT
    weekly_root = root / "weekly"
    week_path = _weekly_path(week_end_date, weekly_root=weekly_root)
    body = _render_weekly_digest(week_end_date, archive_root=root)
    # NFR-004 / CLAUDE.md #2 — the weekly retrospective is published
    # alongside the daily archive and is reachable from Telegram link
    # previews directly (mkdocs ``nav: 주차별 회고``). It must satisfy the
    # same publisher disclaimer gate as ``write_briefing``; relying on the
    # underlying segmented archives' disclaimer status is insufficient
    # because the rendered weekly page exists in isolation.
    if not verify_disclaimer(body):
        raise PublisherDisclaimerError(target_date=week_end_date)
    _write_text_atomic(week_path, body)
    return week_path


def update_weekly_index(
    *,
    archive_root: Path | None = None,
) -> Path:
    """Rewrite the weekly archive index with all known retrospective files."""
    root = archive_root if archive_root is not None else ARCHIVE_ROOT
    weekly_root = root / "weekly"
    weekly_root.mkdir(parents=True, exist_ok=True)
    index_path = weekly_root / "index.md"
    entries = sorted(
        (p for p in weekly_root.glob("*.md") if p.name != "index.md"),
        key=lambda p: p.stem,
        reverse=True,
    )
    lines = [
        "# 주차별 회고",
        "",
        "토요일 09:00 KST cron이 직전 5영업일(월~금)의 결론을 모아 발행합니다. "
        "각 페이지는 세그먼트별 결론 인용을 한 화면에서 비교할 수 있도록 정리되어 있습니다.",
        "",
        "- [Archive로 돌아가기](../index.md)",
        "",
    ]
    if not entries:
        lines.append(
            "아직 발행된 회고가 없습니다. 다음 토요일 09:00 KST 이후에 자동으로 채워집니다."
        )
        lines.append("")
    else:
        for entry in entries:
            lines.append(f"- [{entry.stem}]({entry.name})")
        lines.append("")
    _write_text_atomic(index_path, "\n".join(lines))
    return index_path


def weekly_path(week_end_date: date) -> Path:
    """Public version of :func:`_weekly_path` for orchestrator use."""
    return _weekly_path(week_end_date, weekly_root=WEEKLY_ARCHIVE_ROOT)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _weekly_path(week_end_date: date, *, weekly_root: Path) -> Path:
    iso_year, iso_week, _ = week_end_date.isocalendar()
    return weekly_root / f"{iso_year:04d}-W{iso_week:02d}.md"


def _render_weekly_digest(
    week_end_date: date,
    *,
    archive_root: Path,
) -> str:
    iso_year, iso_week, _ = week_end_date.isocalendar()
    week_start = week_end_date - timedelta(days=4)
    days = [week_start + timedelta(days=i) for i in range(5)]

    lines: list[str] = [
        f"# {iso_year}-W{iso_week:02d} 주차별 회고",
        "",
        f"이 페이지는 **{week_start.isoformat()} ~ {week_end_date.isoformat()}** "
        "(5영업일) 의 세그먼트별 결론 요약을 모은 자동 생성 회고입니다.",
        "",
        "- [주차별 회고 색인](index.md) · [Archive](../index.md) · [About](../../about.md)",
        "",
    ]

    for day in days:
        lines.extend(_render_day_block(day, archive_root=archive_root))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


def _render_day_block(day: date, *, archive_root: Path) -> list[str]:
    iso = day.isoformat()
    weekday_kor = ["월", "화", "수", "목", "금", "토", "일"][day.weekday()]
    block: list[str] = [f"## {iso} ({weekday_kor})"]
    block.append("")
    for segment in _SEGMENTS:
        label = SEGMENT_LABELS[segment]
        rel_path = archive_path(day, segment=segment)
        absolute_candidate = (
            archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{iso}.md"
        )
        if absolute_candidate.exists():
            conclusion = _extract_conclusion(absolute_candidate.read_text(encoding="utf-8"))
            link_target = f"../{segment}/{day.year:04d}/{day.month:02d}/{iso}.md"
            block.append(f"- **[{label}]({link_target})** — {conclusion}")
        else:
            block.append(f"- **{label}** — {_FALLBACK_NOT_PUBLISHED}")
        # ``rel_path`` is referenced for tooling consistency but the link
        # target above is computed relative to the weekly page location.
        del rel_path
    return block


def _extract_conclusion(rendered_markdown: str) -> str:
    for line in rendered_markdown.splitlines():
        if line.startswith(_CONCLUSION_PREFIX):
            value = line.removeprefix(_CONCLUSION_PREFIX).strip()
            if value:
                return value
    return "(결론 인용을 추출하지 못함)"


def _write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


__all__ = [
    "WEEKLY_ARCHIVE_ROOT",
    "WEEKLY_INDEX_PATH",
    "publish_weekly_digest",
    "update_weekly_index",
    "weekly_digest_opt_in",
    "weekly_path",
]
