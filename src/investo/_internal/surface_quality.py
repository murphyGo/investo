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

_FIRST_SECTION_RE = re.compile(r"(?m)^## ①")
_ANY_H2_RE = re.compile(r"(?m)^## ")
_BAD_TOKEN = "불강한성"
_BAD_TOKEN_REPAIR = "불확실성"
_BAD_PARTICLE = "민감도을"
_BAD_PARTICLE_REPAIR = "민감도를"
_TRACE_RE = re.compile(r"\b(?:input_hash|stage1_hash|stage2_hash)\b")
_WATCHLIST_MATCHER_REASON_RE = re.compile(
    r"(?:\[(?:boundary-term|structured-symbol|text-match|alias:[^\]]+)\]|"
    r"\b(?:boundary-term|structured-symbol|text-match|matched_alias)\b|"
    r"\balias:[^\s\]]+)"
)
_TRACE_ASSIGNMENT_RE = re.compile(
    r"`?(?:input_hash|stage1_hash|stage2_hash)`?\s*[:=]\s*`?[\w.-]+`?"
)
_RECOVERABLE_LINK_FRAGMENT_RE = re.compile(r"\[([^\]\n]+)\]\((?:https?://|www\.)[^\s)\n]*")
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
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]*(?:\.{3}|…)[^)\n]*)\)")
_REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]\n]+\]:\s*(\S*(?:\.{3}|…)\S*)")
_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]*(?:\.{3}|…)[^>\s]*)>")
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
    return text[:1600]


def repair_surface_artifacts(text: str) -> str:
    """Repair known deterministic artifacts outside protected regions."""

    first_viewport_len = len(extract_first_viewport(text))
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    offset = 0
    in_code = False
    in_details = False
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        protected = _is_protected_line(line, in_code=in_code, in_details=in_details)
        if line.strip().startswith("```"):
            in_code = not in_code
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False

        if protected:
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
            if _looks_like_unmatched_link(repaired):
                repaired = _repair_recoverable_link_fragments(repaired)
            repaired = _repair_unmatched_markdown_markers(repaired)
            stripped = repaired.strip()
            if stripped == "...":
                offset += len(raw_line)
                continue
            if repaired.endswith(" ..."):
                repaired = repaired[:-4].rstrip()
        newline = "\n" if raw_line.endswith("\n") else ""
        out.append(repaired + newline)
        offset += len(raw_line)
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
    in_code = False
    in_details = False
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        summary_line = (
            raw_line + continuation_tail if index == len(lines) - 1 else raw_line
        ).rstrip()
        summary_value = (
            None if index == 0 and skip_first_continuation else summary_scope.value(summary_line)
        )
        summary_truncated = summary_value is not None and looks_truncated_caution_continuation(
            summary_value, require_complete=True
        )
        protected = _is_protected_line(line, in_code=in_code, in_details=in_details)
        if line.strip().startswith("```"):
            in_code = not in_code
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False
        if protected:
            # The legacy scanner's boolean fence/details guards are retained
            # for its old rules. The new rule uses its own ownership state,
            # so a shorter nested fence cannot hide resumed summary prose.
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
        scan_line = _strip_inline_code(line)
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
        href_ellipsis = _href_ellipsis_evidence(scan_line)
        if href_ellipsis is not None:
            issues.append(
                SurfaceQualityIssue(
                    "markdown.href_ellipsis",
                    "block",
                    href_ellipsis,
                    region,
                )
            )
        body_bounded_line = _BODY_BOUNDED_LINE_RE.match(scan_line.strip()) is not None
        caution_line = _CAUTION_LINE_RE.match(scan_line.strip()) is not None
        caution_truncated = caution_line and (
            looks_truncated_caution_continuation(scan_line)
            or _BOUNDED_LINE_ELLIPSIS_RE.search(scan_line.strip()) is not None
        )
        bounded_line_truncated = body_bounded_line and (
            looks_truncated_mid_token(scan_line)
            or _BOUNDED_LINE_ELLIPSIS_RE.search(scan_line.strip()) is not None
        )
        if (
            (region == "segment_first_viewport" and looks_truncated_mid_token(scan_line))
            or caution_truncated
            or bounded_line_truncated
            or summary_truncated
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
        if _looks_like_unmatched_link(scan_line):
            issues.append(SurfaceQualityIssue("markdown.unmatched_link", "block", line, region))
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
    if line.count("[") != line.count("]"):
        return True
    return line.count("](") > line.count(")")


def _bad_watermark_window(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("**기준 시각**:"):
        return False
    if stripped.count("(") != stripped.count(")"):
        return True
    if _LEGACY_WATERMARK_DANGLING_RE.search(stripped) is not None:
        return True
    return _WATERMARK_LINE_RE.fullmatch(stripped) is None


def _href_ellipsis_evidence(line: str) -> str | None:
    for pattern in (_INLINE_LINK_RE, _REFERENCE_LINK_RE, _AUTOLINK_RE):
        match = pattern.search(line)
        if match is not None:
            return match.group(1)
    return None


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


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub("", line)


def _repair_broken_numeric_bold(line: str) -> str:
    repaired = _BROKEN_SIGN_UNIT_BOLD_RE.sub(r"**\1\2\3**", line)
    repaired = _BROKEN_DOLLAR_UNIT_BOLD_RE.sub(r"**\1\2**", repaired)
    return _BROKEN_NESTED_DOLLAR_PERCENT_RE.sub(r"**\1(\2)**", repaired)


def _repair_recoverable_link_fragments(line: str) -> str:
    """Preserve link text when a first-viewport URL was cut before ``)``."""

    return _RECOVERABLE_LINK_FRAGMENT_RE.sub(r"\1", line)


def _repair_unmatched_markdown_markers(line: str) -> str:
    """Strip broken markdown delimiters while preserving readable text."""

    if not _looks_like_unmatched_link(line):
        return line
    return line.replace("[", "").replace("]", "").replace("](", " ").strip()


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
        or stripped.startswith("|")
        or stripped.startswith("## ⑦")
        or "투자 자문이 아닙니다" in stripped
        or "수집/품질 진단" in stripped
    )


__all__ = [
    "SurfaceIssueSeverity",
    "SurfaceQualityIssue",
    "extract_first_viewport",
    "find_glossary_collision_issues",
    "find_surface_quality_issues",
    "has_blocking_surface_issue",
    "looks_truncated_caution_continuation",
    "looks_truncated_mid_token",
    "repair_surface_artifacts",
]
