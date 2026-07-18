"""u71 reader-first viewport reflow pass.

Move-only extraction from the pre-split ``reader_format`` module (u81).

Problem (2026-05-24 review): the first viewport reads like an operations
log — the coverage badge's raw source counts / per-source status / KPI
explanations land *above* the useful summary, and long ``주의할 점``
lines are hard to scan on mobile.

u71 is NOT a new summary-quality gate (u51 owns TL;DR / H3 / bold; u61
owns malformed-summary validation/repair; u54/u62 own status values and
public quality truth; u56 owns compliance). u71 only controls *ordering*,
*compactness*, and *diagnostic collapse*. It is a pure ``str -> str``
transform that runs AFTER the u51/u61/u56 chain so it reflows already-
cleaned values — it never re-validates or regenerates them.

Reflow contract (stable order, reader-facing lead):
  1. title + watermark + segment nav            (untouched, stays first)
  2. ``## 한눈에 보기`` TL;DR bullets             (u51, untouched)
  3. ``> **오늘의 결론/핵심 동인/주의할 점**``       (summary callouts, bounded)
  4. ``## ①`` ... body
  5. compact status chip + collapsed diagnostics before the disclaimer

The compact status chip and raw diagnostics are useful audit information,
but they should not lead the market note. They move behind the main
sections, immediately before the disclaimer footer.
"""

from __future__ import annotations

import re
from typing import Final

from investo._internal.public_quality_language import (
    PUBLIC_LOW_COVERAGE_TEXT,
    PUBLIC_SOURCE_DETAIL_TEXT,
)
from investo.publisher.reader_format._constants import (
    _DISCLAIMER_FOOTER_ANCHOR,
    _FIRST_SECTION_MARKER,
    _logger,
)

# Coverage-badge blockquote line prefixes emitted by
# ``investo.briefing.pipeline._render_coverage_badge``. The status line is
# the chip source; the remaining four lines are the raw diagnostics body.
_BADGE_STATUS_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*데이터 상태\*\*\s*:\s*(?P<label>[^—·\n]+?)\s*(?:—|·|$)", re.MULTILINE
)
_BADGE_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*소스 카운트\*\*\s*:.*?실패\s*(?P<failed>\d+)\s*/\s*본문 사용\s*(?P<body>\S+)",
    re.MULTILINE,
)
_BADGE_COUNT_ZERO_RE: Final[re.Pattern[str]] = re.compile(r"0건\s*(?P<zero>\d+)")
# All five badge blockquote lines (status + the four diagnostic lines).
_BADGE_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*(?:데이터 상태|소스 카운트|소스 등급 분포|상세 사유|소스별 상태)\*\*.*$",
    re.MULTILINE,
)

DIAGNOSTICS_SUMMARY_LABEL: Final[str] = "수집/품질 진단"
_DIAGNOSTICS_DETAILS_OPEN: Final[str] = f"<details><summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>"
_DIAGNOSTICS_DETAILS_OPEN_EXPANDED: Final[str] = (
    f"<details open><summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>"
)
_DIAGNOSTICS_DETAILS_CLOSE: Final[str] = "</details>"

# First-viewport caution/watchpoint snippet bound (Korean-visible chars).
SNIPPET_MAX_CHARS: Final[int] = 90
_SNIPPET_CONTINUATION: Final[str] = " 본문 참고."
# Word-boundary characters we may truncate at (whitespace + sentence punct).
# The set intentionally includes Korean / typographic punctuation glyphs;
# these are the literal boundary characters we cut at, not lookalikes.
_SNIPPET_BOUNDARY_CHARS: Final[str] = " \t,.;:!?·…—)]」』"
_SNIPPET_TRUNCATED_KOREAN_ELLIPSIS_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣](?:\.{3}|…)$")
_SNIPPET_TRUNCATED_DENYLIST_RE: Final[re.Pattern[str]] = re.compile(r"[채확민관]$")


def _compact_status_chip(text: str) -> str | None:
    """Derive the one-line compact status chip from the coverage badge.

    Returns ``None`` when no ``데이터 상태`` badge line exists (data-limited
    legacy runs that never rendered a badge — the reflow then leaves the
    document's status surface untouched). The chip format is fixed:

        > **데이터 상태**: {label} · 본문 사용 {n|미집계} · 실패 {n} · 0건 {n}

    All values are read from the already-rendered badge text — u71 never
    recomputes coverage; it only re-presents it compactly.
    """
    status = _BADGE_STATUS_RE.search(text)
    if status is None:
        return None
    label = status.group("label").strip()
    count = _BADGE_COUNT_RE.search(text)
    if count is None:
        # Status present but no count line (targeted_count == 0). Chip
        # carries only the tier — still useful, still first-viewport.
        return f"> **데이터 상태**: {label}"
    body_used = count.group("body").strip()
    failed = count.group("failed")
    count_line = count.group(0)
    zero_match = _BADGE_COUNT_ZERO_RE.search(count_line)
    zero = zero_match.group("zero") if zero_match is not None else "0"
    _ = (failed, zero, body_used)
    if label == "정상":
        return f"> **데이터 상태**: {label}"
    return f"> **데이터 상태**: {label} · {PUBLIC_LOW_COVERAGE_TEXT} · {PUBLIC_SOURCE_DETAIL_TEXT}"


def _badge_is_failed(text: str) -> bool:
    """True when the badge status tier is the fully-failed tier (실패)."""
    status = _BADGE_STATUS_RE.search(text)
    return status is not None and status.group("label").strip() == "실패"


def _extract_badge_lines(text: str) -> tuple[str, list[str]]:
    """Remove all badge blockquote lines; return ``(text_without, lines)``.

    ``lines`` preserves source order (status first, then the diagnostic
    lines) so the collapsed block reproduces the original badge body.
    """
    lines = [m.group(0).rstrip() for m in _BADGE_LINE_RE.finditer(text)]
    without = _BADGE_LINE_RE.sub("", text)
    return without, lines


def bound_summary_snippet(value: str, *, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Bound a single caution/watchpoint snippet for the first viewport.

    u71 only reflows/truncates *valid* values; malformed-summary repair is
    u61's job (we never add a parallel validator here). A too-long but valid
    snippet is truncated at the last word boundary before ``max_chars`` and
    suffixed with a complete continuation note. If no boundary exists before
    ``max_chars`` (a single unbroken token), the snippet is omitted by
    returning ``""`` — a mid-token cut would risk the malformed concatenation
    u71 must prevent.

    Idempotent: a valid value already ``<= max_chars`` is returned unchanged.
    Short values that still look truncated are completed with the same safe
    continuation note used for over-long values.
    """
    stripped = value.strip()
    if len(stripped) <= max_chars and not _looks_like_truncated_summary_snippet(stripped):
        return stripped
    window = stripped[: max_chars - len(_SNIPPET_CONTINUATION)]
    cut = max(window.rfind(ch) for ch in _SNIPPET_BOUNDARY_CHARS)
    if cut <= 0:
        return ""
    head = window[:cut].rstrip(_SNIPPET_BOUNDARY_CHARS).rstrip()
    if not head:
        return ""
    return f"{head}{_SNIPPET_CONTINUATION}"


def _looks_like_truncated_summary_snippet(value: str) -> bool:
    if not value:
        return False
    if _SNIPPET_TRUNCATED_KOREAN_ELLIPSIS_RE.search(value):
        return True
    if _SNIPPET_TRUNCATED_DENYLIST_RE.search(value) is not None:
        return True
    # A viewport cut can leave Markdown or a parenthetical claim open even
    # when no explicit ellipsis survived. Treat those lines as candidates for
    # the same word-boundary repair instead of publishing malformed evidence.
    return value.count("(") > value.count(")")


_SUMMARY_CALLOUT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>>[^\S\n]*\*\*"
    r"(?:오늘의 결론|핵심 동인|주의할 점)"
    r"\*\*[^\S\n]*:[^\S\n]*)(?P<body>[^\n]+?)[^\S\n]*$",
    re.MULTILINE,
)
_FIRST_VIEWPORT_BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>-[^\S\n]+)(?P<body>[^\n]+?)[^\S\n]*$",
    re.MULTILINE,
)


def _bound_first_viewport_summary_lines(text: str) -> str:
    """Bound first-viewport TL;DR bullets and summary callout bodies.

    When the bounded body is empty (an unbreakable over-long token), the line
    falls back to a fixed safe message rather than emitting an empty line.
    """
    split_at = text.find(_FIRST_SECTION_MARKER)
    if split_at == -1:
        head = text
        tail = ""
    else:
        head = text[:split_at]
        tail = text[split_at:]

    def _summary_repl(match: re.Match[str]) -> str:
        bounded = bound_summary_snippet(match.group("body"))
        if not bounded:
            bounded = (
                "주요 주의 사항은 본문을 참고하세요."
                if "주의할 점" in match.group("prefix")
                else "요약은 본문을 참고하세요."
            )
        return f"{match.group('prefix')}{bounded}"

    def _bullet_repl(match: re.Match[str]) -> str:
        bounded = bound_summary_snippet(match.group("body"))
        if not bounded:
            bounded = "요약은 본문을 참고하세요."
        return f"{match.group('prefix')}{bounded}"

    head = _SUMMARY_CALLOUT_LINE_RE.sub(_summary_repl, head)
    head = _FIRST_VIEWPORT_BULLET_RE.sub(_bullet_repl, head)
    return f"{head}{tail}"


# Anchor used to locate the end of the summary callout block (after which
# the chip + collapsed diagnostics are inserted). ``오늘의 결론`` /
# ``핵심 동인`` / ``주의할 점`` callouts precede ``## ①``.
_SUMMARY_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*(?:오늘의 결론|핵심 동인|주의할 점)\*\*.*$", re.MULTILINE
)


def reflow_first_viewport(text: str, *, segment: str | None = None) -> str:
    """Reorder the first viewport so the summary precedes diagnostics (u71).

    Pure ``str -> str``. Idempotent: a second pass over already-reflowed
    text is a no-op (the ``<details>`` block is detected and the badge
    lines are already gone). Preserves the disclaimer (anchored at the tail
    / footer; this transform only touches the header region) and the u51
    TL;DR / u56 short-disclaimer placement.

    Steps:
      1. Bound first-viewport TL;DR/callout snippets (≤ 90 chars, word boundary).
      2. Extract the coverage-badge blockquote lines from wherever they sit.
      3. Build a compact status chip from the status/count lines.
      4. Re-insert the chip + a collapsed ``<details>`` diagnostics block
         immediately AFTER the summary callouts (or before ``## ①`` when no
         callouts are present). The block is expanded by default only when
         the segment status is the fully-failed tier.
    """
    text = _bound_first_viewport_summary_lines(text)

    # Already reflowed? The collapsed diagnostics block exists — the chip
    # and the moved badge lines are in place, so a second pass is a no-op
    # (idempotent). We must check this *before* parsing the chip, because
    # the reflowed chip line itself matches the badge-status regex.
    if _DIAGNOSTICS_SUMMARY_PRESENT_RE.search(text) is not None:
        return text

    chip = _compact_status_chip(text)
    if chip is None:
        # No badge rendered (data-limited legacy run). Nothing to reflow.
        return text

    expanded = _badge_is_failed(text)
    without_badge, badge_lines = _extract_badge_lines(text)
    diagnostics = "\n".join(badge_lines)
    open_tag = _DIAGNOSTICS_DETAILS_OPEN_EXPANDED if expanded else _DIAGNOSTICS_DETAILS_OPEN
    block = f"{chip}\n\n{open_tag}\n\n{diagnostics}\n\n{_DIAGNOSTICS_DETAILS_CLOSE}\n\n"

    out = _insert_after_main_body(without_badge, block)
    if out is None:
        _logger.warning(
            "reader_format.reflow_no_anchor",
            extra={"segment": segment},
        )
        return text
    # Collapse any blank-line runs the badge removal may have left.
    return _MULTI_BLANK_RE.sub("\n\n", out)


_DIAGNOSTICS_SUMMARY_PRESENT_RE: Final[re.Pattern[str]] = re.compile(
    re.escape(f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
)
_MULTI_BLANK_RE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


def _insert_after_main_body(text: str, block: str) -> str | None:
    """Insert ``block`` before the disclaimer footer, else before ``## ①``.

    Returns ``None`` when neither anchor exists (a malformed header the
    caller should leave untouched). The block lands on its own paragraph.
    """
    footer = text.find(_DISCLAIMER_FOOTER_ANCHOR)
    if footer != -1:
        before = text[:footer].rstrip()
        after = text[footer:].lstrip("\n")
        return f"{before}\n\n{block}{after}"

    callouts = list(_SUMMARY_CALLOUT_RE.finditer(text))
    if callouts:
        last = callouts[-1]
        # Advance to the end of the callout line's paragraph.
        insertion = last.end()
        # Skip the trailing newline(s) after the last callout.
        tail = text[insertion:]
        lead = len(tail) - len(tail.lstrip("\n"))
        insertion += lead
        return f"{text[:insertion]}\n{block}{text[insertion:]}"
    marker = text.find(_FIRST_SECTION_MARKER)
    if marker == -1:
        return None
    return f"{text[:marker]}{block}{text[marker:]}"
