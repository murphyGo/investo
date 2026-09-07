"""Shared deterministic surface-quality repairs and issue detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from investo._internal.briefing_extract import WATERMARK_PREFIX
from investo._internal.public_quality_language import first_forbidden_public_evidence
from investo._internal.text import bound_at_sentence

SurfaceIssueSeverity = Literal["warn", "block"]
SurfaceIssueRegion = Literal[
    "first_viewport",
    "segment_first_viewport",
    "segment_body",
    "body",
    "protected",
]
SurfaceLinkShape = Literal[
    "inline_link",
    "image",
    "autolink",
    "reference_definition",
    "incomplete_inline",
    "unmatched_residual",
]

_FIRST_SECTION_RE = re.compile(r"(?m)^## ①")
_ANY_H2_RE = re.compile(r"(?m)^## ")
_BAD_TOKEN = "불강한성"
_BAD_TOKEN_REPAIR = "불확실성"
_BAD_PARTICLE = "민감도을"
_BAD_PARTICLE_REPAIR = "민감도를"
_TRACE_RE = re.compile(r"\b(?:input(?:\\)?_hash|stage1(?:\\)?_hash|stage2(?:\\)?_hash)\b")
_WATCHLIST_MATCHER_REASON_RE = re.compile(
    r"(?:\[(?:boundary-term|structured-symbol|text-match|alias:[^\]]+)\]|"
    r"\b(?:boundary-term|structured-symbol|text-match|matched_alias)\b|"
    r"\balias:[^\s\]]+)"
)
_TRACE_ASSIGNMENT_RE = re.compile(
    r"`?(?:input(?:\\)?_hash|stage1(?:\\)?_hash|stage2(?:\\)?_hash)"
    r"`?\s*[:=]\s*`?[\w.-]+`?"
)
_RECOVERABLE_LINK_FRAGMENT_RE = re.compile(
    r"\[(?P<label>[^\]\n]+)\]\("
    r"(?P<target>(?:https?://|www\.)[^\s)\n]*)",
    re.IGNORECASE,
)
_WATERMARK_LINE_RE = re.compile(
    r"^\*\*기준 시각\*\*:\s+\d{4}-\d{2}-\d{2}\s+(?:KST|NY|UTC)\s+·\s+"
    r"수집창\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\s+~\s+"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\s+\(종료 미포함\)$"
)
_LEGACY_WATERMARK_DANGLING_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z,\s+"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\)$"
)
_BROKEN_NUMERIC_BOLD_RE = re.compile(
    r"\*\*[+-]\*\*\s*(?:\$?\d|\d+(?:\.\d+)?%)|"
    r"\$\d+(?:\.\d+)?\*\*[A-Za-z]\*\*|"
    r"\*\*[+-]?\d+(?:\.\d+)?달러\(\*\*[+-]?\d+(?:\.\d+)?%\*\*\)\*\*"
)
_BROKEN_SIGN_UNIT_BOLD_RE = re.compile(
    r"\*\*([+-])\*\*\s*(\d+(?:\.\d+)?%)(?:\*\*([A-Za-z가-힣]+)\*\*)"
)
_BROKEN_DOLLAR_UNIT_BOLD_RE = re.compile(r"(\$\d+(?:\.\d+)?)\*\*([TMB])(?:\*\*)?")
_BROKEN_NESTED_DOLLAR_PERCENT_RE = re.compile(
    r"\*\*([+-]?\d+(?:\.\d+)?달러)\(\*\*([+-]?\d+(?:\.\d+)?%)\*\*\)\*\*"
)
_INLINE_CODE_RE = re.compile(
    r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)",
    re.DOTALL,
)
_INLINE_ATOMIC_BLOCK_RE = re.compile(
    r"^ {0,3}(?:"
    r"#{1,6}(?:\s|$)|"
    r"</?details(?:\s|>|$)|(?:=+|-+)\s*$|"
    r"(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$"
    r")",
    re.IGNORECASE,
)
_LIST_ITEM_RE = re.compile(r"^ {0,3}(?:[-+*]|\d+[.)])\s+")
_ESCAPED_MARKDOWN_PUNCTUATION_RE = re.compile(r"\\[\\`*_\[\]()!<>]")
_MARKDOWN_MASK_CHARACTER = "\ufffc"
_INLINE_LINK_OPENER_RE = re.compile(r"(?P<image>!)?\[")
_REFERENCE_DEFINITION_RE = re.compile(r"^\s*\[[^\]\n]+\]:\s*(?P<body>.*)$")
_AUTOLINK_RE = re.compile(
    r"<(?P<target>https?://[^>\s]*(?:\.{3}|…)[^>\s]*)>",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<rest>.*)$")
_TABLE_DELIMITER_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_DANGLING_ELLIPSIS_RE = re.compile(r"(?:^|\s)\.\.\.$")
_TRUNCATED_KOREAN_ELLIPSIS_RE = re.compile(r"[가-힣](?:\.{3}|…)$")
_TRUNCATED_DENYLIST_RE = re.compile(r"[채확민관]$")
_BODY_BOUNDED_LINE_RE = re.compile(
    r"^(?:>\s*\*\*그래서 의미는\?\*\*|####\s+관찰 신호\s*:)",
)
_CAUTION_LINE_RE = re.compile(r"^>\s*\*\*주의할 점\*\*\s*:\s*(?P<body>.+)$")
_BOUNDED_LINE_ELLIPSIS_RE = re.compile(r"(?:\.{3}|…)$")
_SUMMARY_LIST_RE = re.compile(r"^(?:[-*+]|\d+[.)])[^\S\n]+(.*)$")
_SUMMARY_REFERENCE_RE = re.compile(r"^\[[^\]\n]+\]:\s*\S")
_SUMMARY_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_SUMMARY_CONTINUATION_CALLOUT_RE = re.compile(
    r"^>[^\S\n]*\*\*(?:오늘의 결론|핵심 동인)\*\*[^\S\n]*:[^\S\n]*(.*)$"
)
_REPEATED_PHRASES = (
    "본문을 참고하세요",
    "데이터가 제한적입니다",
    "추가 확인이 필요합니다",
)
_GLOSSARY_COLLISION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?<![A-Za-z0-9])ESMA\s*\([^)\n]*(?:미니\s*S&P\s*500\s*선물|미니S&P선물|미니S&P500선물)[^)\n]*\)"
    ),
    re.compile(
        r"(?<![A-Za-z0-9])(?:E-mini\s+S&P\s+500|ES[A-Z]\d{2,})\s*\([^)\n]*유럽증권시장청[^)\n]*\)",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True, slots=True)
class SurfaceQualityIssue:
    code: str
    severity: SurfaceIssueSeverity
    evidence: str
    region: SurfaceIssueRegion
    link_shape: SurfaceLinkShape | None = None

    def __post_init__(self) -> None:
        if self.link_shape is None:
            return
        if self.code == "markdown.href_ellipsis" and self.link_shape in {
            "inline_link",
            "image",
            "autolink",
            "reference_definition",
        }:
            return
        if self.code == "markdown.unmatched_link" and self.link_shape in {
            "incomplete_inline",
            "unmatched_residual",
        }:
            return
        raise ValueError("link_shape must be compatible with the surface issue code")


@dataclass(frozen=True, slots=True)
class _SurfaceLinkMatch:
    start: int
    end: int
    target_start: int
    target_end: int
    shape: SurfaceLinkShape
    evidence: str
    replacement: str | None


@dataclass(slots=True)
class _SummaryContinuationScope:
    """Select u153-owned values during the existing scanner's line traversal.

    This state only gates the new continuation rule; legacy issue checks and
    their protected-region behavior remain unchanged.
    """

    before_h2: bool = True
    in_tldr: bool = False
    fence: str = ""
    details_depth: int = 0

    def value(self, line: str) -> str | None:
        stripped = line.strip()
        if line.startswith(("    ", "\t")) and not self.details_depth:
            return None
        if self.fence:
            if stripped and set(stripped) == {self.fence[0]} and len(stripped) >= len(self.fence):
                self.fence = ""
            return None
        if self.details_depth or "<details" in stripped:
            self.details_depth = max(
                0, self.details_depth + stripped.count("<details") - stripped.count("</details>")
            )
            return None
        fence = _SUMMARY_FENCE_RE.match(stripped)
        if fence is not None and not (fence.group(1).startswith("`") and "`" in fence.group(2)):
            self.fence = fence.group(1)
            return None
        if re.match(r"^##(?:\s|$)", stripped):
            self.in_tldr = self.before_h2 and stripped == "## 한눈에 보기"
            self.before_h2 = False
            return None
        if _is_protected_line(line, in_code=False, in_details=False):
            return None
        if self.before_h2 or self.in_tldr:
            callout = _SUMMARY_CONTINUATION_CALLOUT_RE.fullmatch(stripped)
            if callout is not None:
                return callout.group(1).strip()
        if not self.in_tldr:
            return None
        item = _SUMMARY_LIST_RE.match(stripped)
        if item is not None:
            return item.group(1).strip()
        if stripped.startswith(("#", "|", ">", "<", "!", WATERMARK_PREFIX, "**세그먼트**:")):
            return None
        if _SUMMARY_REFERENCE_RE.match(stripped):
            return None
        return stripped


def extract_first_viewport(text: str) -> str:
    """Return text from document start through the first section-① anchor."""

    match = _FIRST_SECTION_RE.search(text)
    if match is not None:
        return text[: match.start()]
    fallback = _ANY_H2_RE.search(text)
    if fallback is not None:
        return text[: fallback.start()]
    return text


def repair_surface_artifacts(text: str) -> str:
    """Repair non-link deterministic artifacts outside protected regions."""

    first_viewport_len = len(extract_first_viewport(text))
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    offset = 0
    fence_state: tuple[str, int] | None = None
    in_details = False
    for raw_line in lines:
        line, newline = _split_line_ending(raw_line)
        fence_marker = _fence_marker(line)
        protected = (
            fence_state is not None
            or fence_marker is not None
            or _is_protected_line(
                line,
                in_code=False,
                in_details=in_details,
            )
        )
        fence_state = _advance_fence_state(fence_state, fence_marker)
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False

        if protected or not line.strip():
            # Preserve existing separators. Only a nonempty artifact line
            # emptied by repair may disappear; otherwise a later navigation
            # insertion loses its blank line on repeated finalization.
            out.append(raw_line)
            offset += len(raw_line)
            continue

        inline_scan_line = _mask_inline_code(line)
        link_scan_line = _mask_escaped_markdown_punctuation(inline_scan_line)
        if _closed_link_matches(line, masked_line=link_scan_line) or _looks_like_unmatched_link(
            inline_scan_line
        ):
            out.append(raw_line)
            offset += len(raw_line)
            continue

        repaired = line.replace(_BAD_TOKEN, _BAD_TOKEN_REPAIR).replace(
            _BAD_PARTICLE,
            _BAD_PARTICLE_REPAIR,
        )
        repaired = _repair_broken_numeric_bold(repaired)
        if offset < first_viewport_len:
            repaired = _repair_trace_fragments(repaired)
            if not repaired.strip():
                offset += len(raw_line)
                continue
            stripped = repaired.strip()
            if stripped == "...":
                offset += len(raw_line)
                continue
            if repaired.endswith(" ..."):
                repaired = repaired[:-4].rstrip()
        out.append(repaired + newline)
        offset += len(raw_line)
    return "".join(out)


def repair_surface_link_targets(text: str) -> str:
    """Remove recoverable invalid link targets outside protected regions.

    This transform is deliberately independent of region policy. Callers must
    first classify the original bytes and authorize an owned-region ``repair``
    action. Reference definitions and residual unmatched syntax are left
    unchanged for region replacement or fail-closed handling.
    """

    out: list[str] = []
    fence_state: tuple[str, int] | None = None
    in_details = False
    in_disclaimer = False
    raw_lines = text.splitlines(keepends=True)
    masked_raw_lines = _mask_inline_code(text).splitlines(keepends=True)
    table_line_indices = _markdown_table_line_indices(raw_lines)
    for line_index, (raw_line, masked_raw_line) in enumerate(
        zip(raw_lines, masked_raw_lines, strict=True)
    ):
        line, newline = _split_line_ending(raw_line)
        masked_line, _ = _split_line_ending(masked_raw_line)
        fence_marker = _fence_marker(line)
        protected = (
            line_index in table_line_indices
            or in_disclaimer
            or fence_state is not None
            or fence_marker is not None
            or _is_protected_line(
                line,
                in_code=False,
                in_details=in_details,
            )
        )
        fence_state = _advance_fence_state(fence_state, fence_marker)
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False
        if line.strip().startswith("## ⑦"):
            in_disclaimer = True

        if protected:
            out.append(raw_line)
            continue

        out.append(_repair_surface_link_line(line, masked_line=masked_line) + newline)
    return "".join(out)


def find_surface_quality_issues(text: str) -> tuple[SurfaceQualityIssue, ...]:
    """Find reader-visible surface-quality warnings and blockers."""

    issues: list[SurfaceQualityIssue] = []
    first = extract_first_viewport(text)
    summary_scope = _SummaryContinuationScope()
    body = text[len(first) :]
    # Keep the legacy 1,600-character split for all old rules, but inspect a
    # crossing summary line once in full so its continuation cannot disappear.
    split_line = bool(first and body and not first.endswith(("\n", "\r")))
    continuation_tail = body.splitlines()[0] if split_line else ""
    issues.extend(
        _scan_lines(
            first,
            region="segment_first_viewport",
            summary_scope=summary_scope,
            continuation_tail=continuation_tail,
        )
    )
    issues.extend(_repeated_phrase_warnings(first))
    if body:
        issues.extend(
            _scan_lines(
                body,
                region="segment_body",
                summary_scope=summary_scope,
                skip_first_continuation=split_line,
            )
        )
    return tuple(issues)


def find_glossary_collision_issues(text: str) -> tuple[SurfaceQualityIssue, ...]:
    """Find public glossary parentheticals that attach another entry's gloss."""

    return tuple(
        SurfaceQualityIssue("glossary.collision.forbidden_pair", "block", evidence, "body")
        for evidence in _glossary_collision_evidence(text)
    )


def has_blocking_surface_issue(text: str) -> bool:
    return any(issue.severity == "block" for issue in find_surface_quality_issues(text))


def _scan_lines(
    text: str,
    *,
    region: SurfaceIssueRegion,
    summary_scope: _SummaryContinuationScope,
    continuation_tail: str = "",
    skip_first_continuation: bool = False,
) -> list[SurfaceQualityIssue]:
    issues: list[SurfaceQualityIssue] = []
    fence_state: tuple[str, int] | None = None
    in_details = False
    raw_lines = text.splitlines(keepends=True)
    masked_raw_lines = _mask_inline_code(text).splitlines(keepends=True)
    table_line_indices = _markdown_table_line_indices(raw_lines)
    for line_index, (raw_line, masked_raw_line) in enumerate(
        zip(raw_lines, masked_raw_lines, strict=True)
    ):
        line, _ = _split_line_ending(raw_line)
        summary_line = (
            line + continuation_tail if line_index == len(raw_lines) - 1 else line
        ).rstrip()
        summary_value = (
            None
            if line_index == 0 and skip_first_continuation
            else summary_scope.value(summary_line)
        )
        summary_truncated = summary_value is not None and looks_truncated_caution_continuation(
            summary_value, require_complete=True
        )
        inline_scan_line, _ = _split_line_ending(masked_raw_line)
        fence_marker = _fence_marker(line)
        protected_by_fence = fence_state is not None or fence_marker is not None
        protected = (
            protected_by_fence
            or line_index in table_line_indices
            or _is_protected_line(
                line,
                in_code=False,
                in_details=in_details,
            )
        )
        fence_state = _advance_fence_state(fence_state, fence_marker)
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False
        if protected:
            # Protected reader surfaces are immutable, not exempt from the
            # terminal link gate. Code fences and their delimiters remain
            # literal examples rather than Markdown link candidates.
            if not protected_by_fence:
                issues.extend(
                    _scan_link_issues(
                        line,
                        region="protected",
                        masked_line=inline_scan_line,
                    )
                )
            # u153 ownership is independent of the legacy protected-region
            # flags; retain explicit continuation residue alongside link findings.
            if summary_truncated:
                issues.append(
                    SurfaceQualityIssue(
                        "summary.truncated_mid_token",
                        "block",
                        summary_line,
                        "segment_first_viewport",
                    )
                )
            continue
        scan_line = inline_scan_line
        link_scan_line = _mask_escaped_markdown_punctuation(scan_line)
        if _BAD_TOKEN in line:
            issues.append(
                SurfaceQualityIssue(
                    "bad_token.bulganghanseong",
                    "warn",
                    _BAD_TOKEN,
                    region,
                )
            )
        if _BAD_PARTICLE in line:
            issues.append(
                SurfaceQualityIssue(
                    "korean.bad_particle.mingamdo_eul",
                    "warn",
                    _BAD_PARTICLE,
                    region,
                )
            )
        if _DANGLING_ELLIPSIS_RE.search(scan_line.strip()):
            issues.append(SurfaceQualityIssue("ellipsis.dangling_line", "warn", line, region))
        if _TRACE_RE.search(scan_line):
            issues.append(SurfaceQualityIssue("trace.fragment", "block", line, region))
        if _bad_watermark_window(scan_line):
            issues.append(SurfaceQualityIssue("watermark.window_bracket", "block", line, region))
        numeric_bold = _BROKEN_NUMERIC_BOLD_RE.search(scan_line)
        if numeric_bold is not None:
            issues.append(
                SurfaceQualityIssue(
                    "markdown.broken_numeric_bold",
                    "block",
                    numeric_bold.group(0),
                    region,
                )
            )
        link_issues = _scan_link_issues(line, region=region, masked_line=scan_line)
        issues.extend(link_issues)
        body_bounded_line = _BODY_BOUNDED_LINE_RE.match(scan_line.strip()) is not None
        caution_line = _CAUTION_LINE_RE.match(scan_line.strip()) is not None
        caution_truncated = caution_line and (
            looks_truncated_caution_continuation(scan_line)
            or _BOUNDED_LINE_ELLIPSIS_RE.search(scan_line.strip()) is not None
        )
        bounded_line_truncated = body_bounded_line and (
            looks_truncated_mid_token(link_scan_line)
            or _BOUNDED_LINE_ELLIPSIS_RE.search(scan_line.strip()) is not None
        )
        if summary_truncated or (
            not link_issues
            and (
                (region == "segment_first_viewport" and looks_truncated_mid_token(link_scan_line))
                or caution_truncated
                or bounded_line_truncated
            )
        ):
            issues.append(
                SurfaceQualityIssue(
                    "summary.truncated_mid_token",
                    "block",
                    summary_line if summary_truncated else line,
                    # E3 filters summary-only findings outside its indexed
                    # viewport. The artificial split is not body ownership.
                    "segment_body"
                    if body_bounded_line
                    else "segment_first_viewport"
                    if summary_truncated
                    else region,
                )
            )
        matcher_reason = _WATCHLIST_MATCHER_REASON_RE.search(scan_line)
        if matcher_reason is not None:
            issues.append(
                SurfaceQualityIssue(
                    "watchlist.matcher_reason.public",
                    "block",
                    matcher_reason.group(0),
                    region,
                )
            )
        glossary_collision = _glossary_collision_evidence(scan_line)
        for evidence in glossary_collision:
            issues.append(
                SurfaceQualityIssue(
                    "glossary.collision.forbidden_pair",
                    "block",
                    evidence,
                    region,
                )
            )
        public_evidence = first_forbidden_public_evidence(scan_line)
        if public_evidence is not None:
            issues.append(
                SurfaceQualityIssue(
                    "public_diagnostic.raw_label",
                    "block",
                    public_evidence,
                    region,
                )
            )
    return issues


def _scan_link_issues(
    line: str,
    *,
    region: SurfaceIssueRegion,
    masked_line: str | None = None,
) -> list[SurfaceQualityIssue]:
    inline_scan_line = _mask_inline_code(line) if masked_line is None else masked_line
    link_scan_line = _mask_escaped_markdown_punctuation(inline_scan_line)
    candidates = _closed_link_candidates(line, masked_line=link_scan_line)
    matches = _closed_link_matches(line, masked_line=link_scan_line)
    issues = [
        SurfaceQualityIssue(
            "markdown.href_ellipsis",
            "block",
            match.evidence,
            region,
            match.shape,
        )
        for match in matches
    ]
    unmatched_shape = _unmatched_link_shape(line, masked_line=inline_scan_line)
    if (
        unmatched_shape is None
        and matches
        and any(match.shape != "reference_definition" for match in matches)
        and (
            len(candidates) != len(matches)
            or _repair_surface_link_line(line, masked_line=inline_scan_line) == line
        )
    ):
        # Overlapping candidates and transforms that would expose a second
        # link construct are not safely attributable to one closed target.
        unmatched_shape = "unmatched_residual"
    if unmatched_shape is not None:
        issues.append(
            SurfaceQualityIssue(
                "markdown.unmatched_link",
                "block",
                line,
                region,
                unmatched_shape,
            )
        )
    return issues


def _glossary_collision_evidence(text: str) -> tuple[str, ...]:
    evidence: list[str] = []
    for pattern in _GLOSSARY_COLLISION_PATTERNS:
        evidence.extend(match.group(0) for match in pattern.finditer(text))
    return tuple(evidence)


def _repeated_phrase_warnings(text: str) -> list[SurfaceQualityIssue]:
    return [
        SurfaceQualityIssue("template.repeated_phrase", "warn", phrase, "segment_first_viewport")
        for phrase in _REPEATED_PHRASES
        if text.count(phrase) >= 3
    ]


def _looks_like_unmatched_link(line: str) -> bool:
    open_brackets = 0
    open_link_targets = 0
    escaped_literal_brackets = 0
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line):
            escaped = line[index + 1]
            if escaped == "[" and open_brackets == 0:
                escaped_literal_brackets += 1
            index += 2
            continue
        if char == "[":
            open_brackets += 1
        elif char == "]":
            if open_brackets > 0:
                open_brackets -= 1
                if index + 1 < len(line) and line[index + 1] == "(":
                    open_link_targets += 1
                    index += 1
            elif escaped_literal_brackets > 0:
                escaped_literal_brackets -= 1
            else:
                return True
        elif char == "(" and open_link_targets > 0:
            open_link_targets += 1
        elif char == ")" and open_link_targets > 0:
            open_link_targets -= 1
        index += 1
    return open_brackets > 0 or open_link_targets > 0


def _bad_watermark_window(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("**기준 시각**:"):
        return False
    if stripped.count("(") != stripped.count(")"):
        return True
    if _LEGACY_WATERMARK_DANGLING_RE.search(stripped) is not None:
        return True
    return _WATERMARK_LINE_RE.fullmatch(stripped) is None


def _closed_link_candidates(
    line: str,
    *,
    masked_line: str | None = None,
) -> tuple[_SurfaceLinkMatch, ...]:
    scan_line = _mask_scannable_markdown(line) if masked_line is None else masked_line
    candidates: list[_SurfaceLinkMatch] = []
    inline_body_spans: list[tuple[int, int]] = []
    for match in _INLINE_LINK_OPENER_RE.finditer(scan_line):
        label_start = match.end()
        label_end = _balanced_inline_label_end(scan_line, start=label_start)
        if label_end is None or label_end + 1 >= len(scan_line):
            continue
        if scan_line[label_end + 1] != "(":
            continue
        inline_body_start = label_end + 2
        link_end = _balanced_inline_target_end(scan_line, start=inline_body_start)
        if link_end is None:
            continue
        target_span = _inline_destination_span(
            scan_line,
            start=inline_body_start,
            link_end=link_end,
        )
        if target_span is None:
            continue
        target_start, target_end = target_span
        target = line[target_start:target_end]
        if _has_valid_optional_title(
            scan_line,
            destination_end=target_end,
            container_end=link_end,
        ):
            # Angle-looking text in an optional title is owned by the outer
            # inline construct, not by the top-level autolink scanner.
            inline_body_spans.append((inline_body_start, link_end))
        if "..." not in target and "…" not in target:
            continue
        is_image = match.group("image") is not None
        label = line[label_start:label_end]
        candidates.append(
            _SurfaceLinkMatch(
                start=match.start(),
                end=link_end + 1,
                target_start=target_start,
                target_end=target_end,
                shape="image" if is_image else "inline_link",
                evidence=target,
                replacement=_escape_plain_image_alt(label) if is_image else label,
            )
        )
    for match in _REFERENCE_DEFINITION_RE.finditer(scan_line):
        body_start, body_end = match.span("body")
        target_span = _inline_destination_span(
            scan_line,
            start=body_start,
            link_end=body_end,
        )
        if target_span is None:
            continue
        target_start, target_end = target_span
        if _has_valid_optional_title(
            scan_line,
            destination_end=target_end,
            container_end=body_end,
        ):
            inline_body_spans.append((body_start, body_end))
        target = line[target_start:target_end]
        if "..." not in target and "…" not in target:
            continue
        candidates.append(
            _SurfaceLinkMatch(
                start=match.start(),
                end=match.end(),
                target_start=target_start,
                target_end=target_end,
                shape="reference_definition",
                evidence=target,
                replacement=None,
            )
        )
    autolink_scan_line = _restore_escaped_autolink_closers(line, scan_line)
    for match in _AUTOLINK_RE.finditer(autolink_scan_line):
        if _is_backslash_escaped(scan_line, match.start()):
            continue
        if any(
            owner_start <= match.start() and match.end() <= owner_end
            for owner_start, owner_end in inline_body_spans
        ):
            continue
        target_start, target_end = match.span("target")
        candidates.append(
            _SurfaceLinkMatch(
                start=match.start(),
                end=match.end(),
                target_start=target_start,
                target_end=target_end,
                shape="autolink",
                evidence=line[target_start:target_end],
                replacement="",
            )
        )

    return tuple(candidates)


def _restore_escaped_autolink_closers(line: str, scan_line: str) -> str:
    """Keep legacy escaped-close autolink detection without confusing E3 ownership."""

    restored = list(scan_line)
    for index, char in enumerate(line):
        if (
            char == ">"
            and scan_line[index] == _MARKDOWN_MASK_CHARACTER
            and _is_backslash_escaped(line, index)
        ):
            restored[index] = ">"
    return "".join(restored)


def _balanced_inline_label_end(line: str, *, start: int) -> int | None:
    nested_brackets = 0
    for index in range(start, len(line)):
        char = line[index]
        if char in "\r\n":
            return None
        if char == "[":
            nested_brackets += 1
        elif char == "]":
            if nested_brackets == 0:
                return index
            nested_brackets -= 1
    return None


def _inline_destination_span(
    line: str,
    *,
    start: int,
    link_end: int,
) -> tuple[int, int] | None:
    if start >= link_end:
        return start, start
    if line[start] == "<":
        angle_end = line.find(">", start + 1, link_end)
        if angle_end == -1:
            return None
        if line[angle_end + 1 : link_end] and not line[angle_end + 1].isspace():
            return None
        return start, angle_end + 1

    nested_parentheses = 0
    for index in range(start, link_end):
        char = line[index]
        if char.isspace() and nested_parentheses == 0:
            return start, index
        if char == "(":
            nested_parentheses += 1
        elif char == ")" and nested_parentheses > 0:
            nested_parentheses -= 1
    return start, link_end


def _has_valid_optional_title(
    line: str,
    *,
    destination_end: int,
    container_end: int,
) -> bool:
    tail = line[destination_end:container_end]
    if not tail:
        return True
    if not tail[0].isspace():
        return False
    title = tail.strip()
    if not title:
        return True
    opener = title[0]
    closer = {'"': '"', "'": "'", "(": ")"}.get(opener)
    if closer is None or title[-1] != closer:
        return False
    return not _is_backslash_escaped(title, len(title) - 1)


def _balanced_inline_target_end(line: str, *, start: int) -> int | None:
    """Return the closing parenthesis for one Markdown inline destination."""

    nested_parentheses = 0
    for index in range(start, len(line)):
        char = line[index]
        if char in "\r\n":
            return None
        if char == "(":
            nested_parentheses += 1
        elif char == ")":
            if nested_parentheses == 0:
                return index
            nested_parentheses -= 1
    return None


def _closed_link_matches(
    line: str,
    *,
    masked_line: str | None = None,
) -> tuple[_SurfaceLinkMatch, ...]:
    scan_line = _mask_scannable_markdown(line) if masked_line is None else masked_line
    candidates = _closed_link_candidates(line, masked_line=scan_line)

    selected = [candidate for candidate in candidates if candidate.shape == "reference_definition"]
    for candidate in sorted(
        (candidate for candidate in candidates if candidate.shape != "reference_definition"),
        key=lambda item: (item.end - item.start, item.start, item.end),
    ):
        if any(
            candidate.start < existing.end and existing.start < candidate.end
            for existing in selected
        ):
            continue
        selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end)))


def _recoverable_incomplete_matches(
    line: str,
    *,
    masked_line: str | None = None,
) -> tuple[_SurfaceLinkMatch, ...]:
    scan_line = _mask_scannable_markdown(line) if masked_line is None else masked_line
    matches: list[_SurfaceLinkMatch] = []
    for match in _RECOVERABLE_LINK_FRAGMENT_RE.finditer(scan_line):
        if match.end() < len(scan_line) and scan_line[match.end()] == ")":
            continue
        if match.start() > 0 and scan_line[match.start() - 1] == "!":
            # An incomplete image is not an inline-link fragment: consuming
            # only ``[alt](target`` would leak a stray image delimiter.
            continue
        target_start, target_end = match.span("target")
        target = line[target_start:target_end]
        if any(
            char in "[]" and not _is_backslash_escaped(target, index)
            for index, char in enumerate(target)
        ):
            continue
        label_start, label_end = match.span("label")
        matches.append(
            _SurfaceLinkMatch(
                start=match.start(),
                end=match.end(),
                target_start=target_start,
                target_end=target_end,
                shape="incomplete_inline",
                evidence=target,
                replacement=line[label_start:label_end],
            )
        )
    return tuple(matches)


def _unmatched_link_shape(
    line: str,
    *,
    masked_line: str | None = None,
) -> SurfaceLinkShape | None:
    scan_line = _mask_inline_code(line) if masked_line is None else masked_line
    if not _looks_like_unmatched_link(scan_line):
        return None
    incomplete_scan_line = _mask_escaped_markdown_punctuation(scan_line)
    matches = _recoverable_incomplete_matches(line, masked_line=incomplete_scan_line)
    if not matches:
        return "unmatched_residual"
    trial = _apply_link_replacements(line, matches)
    if _looks_like_unmatched_link(_mask_inline_code(trial)):
        return "unmatched_residual"
    return "incomplete_inline"


def _apply_link_replacements(
    line: str,
    matches: list[_SurfaceLinkMatch] | tuple[_SurfaceLinkMatch, ...],
) -> str:
    if not matches:
        return line
    ordered = sorted(matches, key=lambda item: (item.start, item.end))
    out: list[str] = []
    cursor = 0
    for match in ordered:
        if match.start < cursor or match.replacement is None:
            continue
        out.append(line[cursor : match.start])
        out.append(match.replacement)
        cursor = match.end
    out.append(line[cursor:])
    return "".join(out)


def _repair_surface_link_line(line: str, *, masked_line: str | None = None) -> str:
    inline_scan_line = _mask_inline_code(line) if masked_line is None else masked_line
    link_scan_line = _mask_escaped_markdown_punctuation(inline_scan_line)
    candidates = _closed_link_candidates(line, masked_line=link_scan_line)
    matches = _closed_link_matches(line, masked_line=link_scan_line)
    unmatched_shape = _unmatched_link_shape(line, masked_line=inline_scan_line)
    if (
        len(candidates) != len(matches)
        or any(match.shape == "reference_definition" for match in matches)
        or unmatched_shape == "unmatched_residual"
    ):
        return line

    replacements = [match for match in matches if match.replacement is not None]
    if unmatched_shape == "incomplete_inline":
        replacements.extend(_recoverable_incomplete_matches(line, masked_line=link_scan_line))
    updated = _apply_link_replacements(line, replacements)
    updated_inline_scan_line = _apply_link_replacements(inline_scan_line, replacements)
    updated_link_scan_line = _mask_escaped_markdown_punctuation(updated_inline_scan_line)
    remaining_closed = _closed_link_matches(updated, masked_line=updated_link_scan_line)
    if remaining_closed or _looks_like_unmatched_link(updated_inline_scan_line):
        return line
    return updated


def _escape_plain_image_alt(alt: str) -> str:
    escaped = alt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]()!])", r"\\\1", escaped)


def _split_line_ending(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n") or raw_line.endswith("\r"):
        return raw_line[:-1], raw_line[-1]
    return raw_line, ""


def looks_truncated_mid_token(line: str) -> bool:
    """Return whether a reader-facing line has a truncated surface shape.

    Reader-format repair imports this predicate so the repair and blocking
    gate share one structural contract.  Keep the checks here conservative:
    the caller may pass either a complete Markdown line or a summary body.
    """

    stripped = line.strip()
    if not stripped:
        return False
    if _TRUNCATED_KOREAN_ELLIPSIS_RE.search(stripped):
        return True
    if _TRUNCATED_DENYLIST_RE.search(stripped):
        return True
    return (
        stripped.endswith(("(", "["))
        or stripped.count("(") > stripped.count(")")
        or stripped.count("[") > stripped.count("]")
        or stripped.count("**") % 2 == 1
    )


def looks_truncated_caution_continuation(line: str, *, require_complete: bool = False) -> bool:
    """Check continuation residue, preserving the legacy caution default.

    u153 summary callers opt into the same complete, decimal-safe boundary
    contract as their formatter, without introducing a grammar validator.
    """

    stripped = line.strip()
    match = _CAUTION_LINE_RE.match(stripped)
    body = match.group("body").strip() if match is not None else stripped
    continuation = "본문 참고."
    if not body.endswith(continuation):
        return False
    retained = body[: -len(continuation)].rstrip()
    if require_complete:
        return (
            not retained
            or retained.endswith((continuation, "...", "…"))
            or bound_at_sentence(retained, len(retained), require_complete=True) != retained
        )
    return bool(retained) and not retained.endswith((".", "!", "?", "。"))


def _mask_inline_code(text: str) -> str:
    """Hide exact-run code spans without crossing Markdown block boundaries."""

    chunks: list[str] = []
    current: list[str] = []
    current_kind: str | None = None
    raw_lines = text.splitlines(keepends=True)
    table_line_indices = _markdown_table_line_indices(raw_lines)
    for line_index, raw_line in enumerate(raw_lines):
        line, _ = _split_line_ending(raw_line)
        if not line.strip():
            if current:
                chunks.append(_mask_inline_code_chunk("".join(current)))
                current = []
                current_kind = None
            chunks.append(raw_line)
            continue
        if line_index in table_line_indices:
            if current:
                chunks.append(_mask_inline_code_chunk("".join(current)))
                current = []
                current_kind = None
            chunks.append(_mask_inline_code_chunk(raw_line))
            continue
        is_list_item = _LIST_ITEM_RE.match(line) is not None
        if is_list_item:
            if current:
                chunks.append(_mask_inline_code_chunk("".join(current)))
            current = [raw_line]
            current_kind = "list_item"
            continue
        kind = "blockquote" if re.match(r"^ {0,3}>", line) else "paragraph"
        atomic_block_start = (
            _INLINE_ATOMIC_BLOCK_RE.match(line) is not None
            or _fence_marker(line) is not None
            or (line.startswith(("    ", "\t")) and current_kind != "list_item")
        )
        if atomic_block_start:
            if current:
                chunks.append(_mask_inline_code_chunk("".join(current)))
                current = []
                current_kind = None
            chunks.append(_mask_inline_code_chunk(raw_line))
            continue
        if current_kind == "list_item" and kind != "blockquote":
            current.append(raw_line)
            continue
        if current and kind != current_kind:
            chunks.append(_mask_inline_code_chunk("".join(current)))
            current = []
        current.append(raw_line)
        current_kind = kind
    if current:
        chunks.append(_mask_inline_code_chunk("".join(current)))
    return "".join(chunks)


def _mask_inline_code_chunk(text: str) -> str:
    return _INLINE_CODE_RE.sub(
        lambda match: "".join(char if char in "\r\n" else " " for char in match.group(0)),
        text,
    )


def _mask_scannable_markdown(line: str) -> str:
    return _mask_escaped_markdown_punctuation(_mask_inline_code(line))


def _mask_escaped_markdown_punctuation(line: str) -> str:
    return _ESCAPED_MARKDOWN_PUNCTUATION_RE.sub(
        lambda match: _MARKDOWN_MASK_CHARACTER * len(match.group(0)),
        line,
    )


def _is_backslash_escaped(line: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and line[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _markdown_table_line_indices(raw_lines: list[str]) -> frozenset[int]:
    lines = tuple(_split_line_ending(raw_line)[0] for raw_line in raw_lines)
    table_lines: set[int] = set()
    for delimiter_index, line in enumerate(lines):
        if delimiter_index == 0 or _TABLE_DELIMITER_RE.fullmatch(line) is None:
            continue
        header_index = delimiter_index - 1
        if "|" not in lines[header_index]:
            continue
        table_lines.update((header_index, delimiter_index))
        row_index = delimiter_index + 1
        while row_index < len(lines) and lines[row_index].strip() and "|" in lines[row_index]:
            table_lines.add(row_index)
            row_index += 1
    return frozenset(table_lines)


def _fence_marker(line: str) -> tuple[str, int, str] | None:
    match = _FENCE_RE.match(line)
    if match is None:
        return None
    marker = match.group("marker")
    if marker.startswith("`") and "`" in match.group("rest"):
        return None
    return marker[0], len(marker), match.group("rest")


def _advance_fence_state(
    current: tuple[str, int] | None,
    marker: tuple[str, int, str] | None,
) -> tuple[str, int] | None:
    if marker is None:
        return current
    marker_char, marker_length, rest = marker
    if current is None:
        return marker_char, marker_length
    current_char, opening_length = current
    if marker_char == current_char and marker_length >= opening_length and not rest.strip():
        return None
    return current


def _repair_broken_numeric_bold(line: str) -> str:
    repaired = _BROKEN_SIGN_UNIT_BOLD_RE.sub(r"**\1\2\3**", line)
    repaired = _BROKEN_DOLLAR_UNIT_BOLD_RE.sub(r"**\1\2**", repaired)
    return _BROKEN_NESTED_DOLLAR_PERCENT_RE.sub(r"**\1(\2)**", repaired)


def _repair_trace_fragments(line: str) -> str:
    """Remove model trace hashes from user-facing first-viewport text."""

    without_assignments = _TRACE_ASSIGNMENT_RE.sub("", line).strip()
    if _TRACE_RE.search(without_assignments):
        return ""
    return without_assignments.strip(" -·,;|")


def _is_protected_line(line: str, *, in_code: bool, in_details: bool) -> bool:
    stripped = line.strip()
    return (
        in_code
        or in_details
        or "<details" in stripped
        or "</details>" in stripped
        or stripped.startswith("|")
        or stripped.startswith("## ⑦")
        or "투자 자문이 아닙니다" in stripped
        or "수집/품질 진단" in stripped
    )


__all__ = [
    "SurfaceIssueSeverity",
    "SurfaceLinkShape",
    "SurfaceQualityIssue",
    "extract_first_viewport",
    "find_glossary_collision_issues",
    "find_surface_quality_issues",
    "has_blocking_surface_issue",
    "looks_truncated_caution_continuation",
    "looks_truncated_mid_token",
    "repair_surface_artifacts",
    "repair_surface_link_targets",
]
