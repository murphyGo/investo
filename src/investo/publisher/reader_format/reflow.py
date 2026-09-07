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
transform that runs AFTER the u51/u61/u56 chain. u153 delegates bounded
candidate safety to the existing canonical predicate; it adds no new validator
or summary generator.

Reflow contract (stable order, reader-facing lead):
  1. title + watermark + segment nav            (untouched, stays first)
  2. ``## 한눈에 보기`` TL;DR values              (u51 structure, u153 bounded)
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

from investo._internal.briefing_extract import (
    CONCLUSION_PREFIX,
    FALLBACK_BY_PREFIX,
    WATERMARK_PREFIX,
)
from investo._internal.public_quality_language import (
    PUBLIC_LOW_COVERAGE_TEXT,
    PUBLIC_SOURCE_DETAIL_TEXT,
    first_forbidden_public_evidence,
    project_public_quality_language,
)
from investo._internal.summary_quality import is_unsafe_summary_value
from investo._internal.surface_quality import (
    find_surface_quality_issues,
    has_blocking_surface_issue,
    looks_truncated_caution_continuation,
    looks_truncated_mid_token,
)
from investo._internal.text import bound_at_sentence
from investo.publisher.reader_format._constants import (
    _DISCLAIMER_FOOTER_ANCHOR,
    _FIRST_SECTION_MARKER,
    _SECTION_HEADER_RE,
    TLDR_HEADER,
    _logger,
)
from investo.publisher.reader_format.public_projection import (
    _is_closing_fence,
    _line_content_and_ending,
    _opening_fence,
)

# Coverage-badge blockquote line prefixes emitted by
# ``investo.briefing.pipeline._render_coverage_badge``. The status line is
# the chip source; the remaining four lines are the raw diagnostics body.
_BADGE_STATUS_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*데이터 상태\*\*\s*:\s*(?P<label>[^—·\n]+?)\s*(?:—|·|$)", re.MULTILINE
)
_BADGE_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*소스 카운트\*\*\s*:\s*"
    r"수집 대상\s*(?P<targeted>\d+)\s*/\s*"
    r"성공\s*(?P<succeeded>\d+)\s*/\s*"
    r"0건\s*(?P<zero>\d+)\s*/\s*"
    r"실패\s*(?P<failed>\d+)\s*/\s*"
    r"본문 사용\s*(?P<body>미집계|\d+)[^\S\n]*$",
    re.MULTILINE,
)
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
_CAUTION_SNIPPET_FALLBACK: Final[str] = "본문 §②·§④ 참조"
_TLDR_SNIPPET_FALLBACK: Final[str] = "요약은 본문을 참고하세요."


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
    zero = count.group("zero")
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
    lines: list[str] = []
    for match in _BADGE_LINE_RE.finditer(text):
        line = match.group(0).rstrip()
        count = _BADGE_COUNT_RE.fullmatch(line)
        lines.append(_compose_diagnostic_source_count(count) if count is not None else line)
    without = _BADGE_LINE_RE.sub("", text)
    return without, lines


def _compose_diagnostic_source_count(match: re.Match[str]) -> str:
    """Render the five canonical diagnostic slots from numeric captures."""
    return (
        "> **소스 카운트**: "
        f"수집 대상 {match.group('targeted')} / "
        f"성공 {match.group('succeeded')} / "
        f"0건 {match.group('zero')} / "
        f"실패 {match.group('failed')} / "
        f"본문 사용 {match.group('body')}"
    )


def is_diagnostic_source_count_line(line: str) -> bool:
    """Return whether ``line`` is the canonical pre-collapse count record."""
    return _BADGE_COUNT_RE.fullmatch(line.strip()) is not None


def bound_summary_snippet(
    value: str, *, max_chars: int = SNIPPET_MAX_CHARS, final_assembly: bool = False
) -> str:
    """Bound a non-caution summary snippet for the first viewport.

    u153 / FR-009: retain a complete safe sentence or return ``""`` for the
    caller's canonical fallback. Short valid headings remain unchanged.
    Existing link findings stay verbatim with their dedicated repair owner;
    length bounding must not hide them by discarding the defective tail.
    """
    stripped = value.strip()
    issues = tuple(
        issue
        # Preserve both anchored reference definitions and values which only
        # resemble protected tables/headings outside their callout/list context.
        for context in (stripped, f"{CONCLUSION_PREFIX} {stripped}")
        for issue in find_surface_quality_issues(f"{context}\n{_FIRST_SECTION_MARKER}")
    )
    if any(
        issue.code in {"markdown.href_ellipsis", "markdown.unmatched_link"}
        or (
            final_assembly
            and issue.severity == "block"
            and issue.code not in {"summary.truncated_mid_token", "public_diagnostic.raw_label"}
        )
        for issue in issues
    ):
        return stripped
    if final_assembly and first_forbidden_public_evidence(stripped) is not None:
        # Repair can expose a diagnostic fragment hidden inside Markdown.
        # Resolve it with its existing canonical projector before bounding;
        # the later public projection must not expand this summary again.
        # Mixed hard/link defects returned above remain with their owner.
        stripped = project_public_quality_language(stripped)

    content = stripped
    continuation_count = 0
    while content.endswith(_SNIPPET_CONTINUATION.strip()):
        content = content[: -len(_SNIPPET_CONTINUATION.strip())].rstrip()
        continuation_count += 1
    valid_continuation = continuation_count == 1 and (
        not content.endswith(("...", "…"))
        and not is_unsafe_summary_value(content)
        and bound_at_sentence(content, len(content), require_complete=True) == content
    )
    if (
        len(stripped) <= max_chars
        and not _looks_like_truncated_summary_snippet(stripped)
        and not looks_truncated_caution_continuation(stripped)
        and (not continuation_count or valid_continuation)
    ):
        return stripped

    budget = max_chars - len(_SNIPPET_CONTINUATION)
    while budget > 0:
        head = bound_at_sentence(content, budget, require_complete=True)
        if head is None:
            break
        omitted = stripped[len(head) :].strip()
        candidate = f"{head}{_SNIPPET_CONTINUATION}" if omitted else head
        if (
            not head.endswith((_SNIPPET_CONTINUATION.strip(), "...", "…"))
            and not is_unsafe_summary_value(head)
            and not is_unsafe_summary_value(candidate)
        ):
            return candidate
        # Keep the original input for lookahead: slicing at the new cap could
        # manufacture a terminator inside a decimal or a Markdown token.
        budget = len(head) - 1
    return ""


def _bound_caution_snippet(value: str, *, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Bound a caution callout at a complete sentence boundary.

    The continuation consumes part of the cap and is appended only after a
    complete retained sentence when non-empty content was omitted.  A short
    value that already carries truncation residue is rejected so the caller
    can render the deterministic caution fallback instead of preserving a
    broken clause.
    """
    stripped = value.strip()
    if _has_surface_link_issue(stripped):
        return stripped
    if len(stripped) <= max_chars:
        return (
            ""
            if _looks_like_truncated_summary_snippet(stripped)
            or looks_truncated_caution_continuation(stripped)
            else stripped
        )

    budget = max_chars - len(_SNIPPET_CONTINUATION)
    if budget <= 0:
        return ""
    bounded = bound_at_sentence(stripped, budget)
    if bounded is None:
        return ""
    omitted = stripped[len(bounded) :].strip()
    if not omitted:
        return bounded
    candidate = f"{bounded}{_SNIPPET_CONTINUATION}"
    return "" if has_blocking_surface_issue(candidate) else candidate


def _has_surface_link_issue(value: str) -> bool:
    return any(issue.link_shape is not None for issue in find_surface_quality_issues(value))


def _looks_like_truncated_summary_snippet(value: str) -> bool:
    # Unmatched square brackets belong to the dedicated link/Markdown repair
    # that runs after reflow and preserves the visible link text.
    return not _has_unmatched_square_bracket(value) and looks_truncated_mid_token(value)


def _has_unmatched_square_bracket(value: str) -> bool:
    return value.count("[") > value.count("]")


_SUMMARY_CALLOUT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>>[^\S\n]*\*\*"
    r"(?P<label>오늘의 결론|핵심 동인|주의할 점)"
    r"\*\*[^\S\n]*:[^\S\n]*)(?P<body>[^\n]*?)[^\S\n]*$",
    re.MULTILINE,
)
_FIRST_VIEWPORT_BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>[-*+][^\S\n]+)(?P<body>[^\n]*?)[^\S\n]*$",
    re.MULTILINE,
)
_REFERENCE_DEFINITION_RE: Final[re.Pattern[str]] = re.compile(r"^ {0,3}\[[^\]\n]+\]:")


def bound_first_viewport_summary_lines(text: str, *, final_assembly: bool = False) -> str:
    """Bound owned summary values without reordering any document blocks.

    Original reflow callers retain caution's u131 behavior by default. The
    u153 final-assembly mode leaves caution unchanged, resolves newly exposed
    public labels before bounding, and preserves simultaneous hard/link defects
    for existing terminal owners. It never changes block layout.
    """
    out: list[str] = []
    in_tldr = False
    in_body = False
    fence: tuple[str, int] | None = None
    details_depth = 0
    for raw_line in text.splitlines(keepends=True):
        line, ending = _line_content_and_ending(raw_line)
        stripped = line.strip()
        if in_body:
            out.append(raw_line)
            continue
        if not details_depth and line.startswith(("    ", "\t")):
            out.append(raw_line)
            continue
        if fence is not None:
            if _is_closing_fence(line, fence):
                fence = None
            out.append(raw_line)
            continue
        opening = _opening_fence(line)
        if opening is not None and not details_depth:
            fence = opening
            out.append(raw_line)
            continue
        if details_depth or "<details" in line:
            details_depth = max(
                0, details_depth + line.count("<details") - line.count("</details>")
            )
            out.append(raw_line)
            continue
        if stripped == "##" or _SECTION_HEADER_RE.fullmatch(stripped):
            in_tldr = not in_tldr and stripped == TLDR_HEADER
            in_body = not in_tldr
            out.append(raw_line)
            continue
        bounded_line = _bound_owned_summary_line(
            line,
            in_tldr=in_tldr,
            final_assembly=final_assembly,
        )
        out.append(bounded_line + ending)
    return "".join(out)


def bound_first_viewport_snippets(text: str) -> str:
    """Reuse the owned summary traversal after u150's target-specific repair."""

    return bound_first_viewport_summary_lines(text)


def _bound_owned_summary_line(line: str, *, in_tldr: bool, final_assembly: bool) -> str:
    # Definitions can supply links used by the body; they are structure, not
    # plain TL;DR prose. Leave both valid and defective definitions to their owner.
    if _REFERENCE_DEFINITION_RE.match(line):
        return line
    match = _SUMMARY_CALLOUT_LINE_RE.fullmatch(line)
    if match is not None:
        is_caution = match.group("label") == "주의할 점"
        if is_caution and final_assembly:
            return line
        bounded = (
            _bound_caution_snippet(match.group("body"))
            if is_caution
            else bound_summary_snippet(match.group("body"), final_assembly=final_assembly)
        )
        if not bounded:
            bounded = (
                _CAUTION_SNIPPET_FALLBACK
                if is_caution
                else FALLBACK_BY_PREFIX[f"> **{match.group('label')}**:"]
            )
        return line if bounded == match.group("body") else f"{match.group('prefix')}{bounded}"
    if not in_tldr:
        return line
    match = _FIRST_VIEWPORT_BULLET_RE.fullmatch(line)
    if match is not None:
        body = match.group("body")
        prefix = match.group("prefix")
    else:
        body = line.strip()
        if (
            not body
            or body.startswith(("#", "|", ">", "<", "!", WATERMARK_PREFIX, "**세그먼트**:"))
            or line.startswith(("    ", "\t"))
        ):
            return line
        prefix = line[: len(line) - len(line.lstrip())]
    bounded = bound_summary_snippet(body, final_assembly=final_assembly) or _TLDR_SNIPPET_FALLBACK
    return line if bounded == body else f"{prefix}{bounded}"


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
      1. Bound owned first-viewport snippets at safe complete sentences, keeping
         each surface's fallback and existing malformed-link repair ownership.
      2. Extract the coverage-badge blockquote lines from wherever they sit.
      3. Build a compact status chip from the status/count lines.
      4. Re-insert the chip + a collapsed ``<details>`` diagnostics block
         immediately AFTER the summary callouts (or before ``## ①`` when no
         callouts are present). The block is expanded by default only when
         the segment status is the fully-failed tier.
    """
    text = bound_first_viewport_summary_lines(text)

    # Already reflowed? The collapsed diagnostics block exists — the chip
    # and the moved badge lines are in place, so a second pass is a no-op
    # (idempotent). We must check this *before* parsing the chip, because
    # the reflowed chip line itself matches the badge-status regex.
    if _DIAGNOSTICS_SUMMARY_PRESENT_RE.search(text) is not None:
        return text

    chip = _compact_status_chip(text)
    if chip is None:
        # No badge rendered (data-limited legacy run). Nothing to reflow.
        return _project_uncontained_source_counts(text)

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
        return _project_uncontained_source_counts(text)
    # Collapse any blank-line runs the badge removal may have left.
    return _MULTI_BLANK_RE.sub("\n\n", out)


_DIAGNOSTICS_SUMMARY_PRESENT_RE: Final[re.Pattern[str]] = re.compile(
    re.escape(f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
)
_MULTI_BLANK_RE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


def _project_uncontained_source_counts(text: str) -> str:
    """Restore the existing public projection when diagnostics cannot collapse."""
    return _BADGE_COUNT_RE.sub(
        lambda match: project_public_quality_language(match.group(0)),
        text,
    )


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
