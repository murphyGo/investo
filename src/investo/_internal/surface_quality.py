"""Shared deterministic surface-quality repairs and issue detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from investo._internal.public_quality_language import first_forbidden_public_evidence

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


def extract_first_viewport(text: str) -> str:
    """Return text from document start through the first section-① anchor."""

    match = _FIRST_SECTION_RE.search(text)
    if match is not None:
        return text[: match.start()]
    fallback = _ANY_H2_RE.search(text)
    if fallback is not None:
        return text[: fallback.start()]
    return text[:1600]


def repair_surface_artifacts(
    text: str,
    *,
    treat_all_as_first_viewport: bool = False,
) -> str:
    """Repair known deterministic artifacts outside protected regions.

    ``treat_all_as_first_viewport`` is reserved for callers that already
    sliced an owned first-viewport region from a larger document.  Such a
    slice may itself contain an ``##`` heading, so deriving the viewport from
    the fragment would incorrectly make the remainder ineligible for the
    first-viewport-only repairs.
    """

    first_viewport_len = (
        len(text) if treat_all_as_first_viewport else len(extract_first_viewport(text))
    )
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

        repaired, protected_inline = _mask_inline_code(line)
        repaired = repaired.replace(_BAD_TOKEN, _BAD_TOKEN_REPAIR).replace(
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
        repaired = _restore_inline_code(repaired, protected_inline)
        newline = "\n" if raw_line.endswith("\n") else ""
        out.append(repaired + newline)
        offset += len(raw_line)
    return "".join(out)


def find_surface_quality_issues(text: str) -> tuple[SurfaceQualityIssue, ...]:
    """Find reader-visible surface-quality warnings and blockers."""

    issues: list[SurfaceQualityIssue] = []
    first = extract_first_viewport(text)
    issues.extend(_scan_lines(first, region="segment_first_viewport"))
    issues.extend(_repeated_phrase_warnings(first))
    body = text[len(first) :]
    if body:
        issues.extend(_scan_lines(body, region="segment_body"))
    return tuple(issues)


def find_glossary_collision_issues(text: str) -> tuple[SurfaceQualityIssue, ...]:
    """Find public glossary parentheticals that attach another entry's gloss."""

    return tuple(
        SurfaceQualityIssue("glossary.collision.forbidden_pair", "block", evidence, "body")
        for evidence in _glossary_collision_evidence(text)
    )


def has_blocking_surface_issue(text: str) -> bool:
    return any(issue.severity == "block" for issue in find_surface_quality_issues(text))


def _scan_lines(text: str, *, region: SurfaceIssueRegion) -> list[SurfaceQualityIssue]:
    issues: list[SurfaceQualityIssue] = []
    in_code = False
    in_details = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        protected = _is_protected_line(line, in_code=in_code, in_details=in_details)
        if line.strip().startswith("```"):
            in_code = not in_code
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False
        if protected:
            continue
        scan_line = _strip_inline_code(line)
        if _BAD_TOKEN in scan_line:
            issues.append(
                SurfaceQualityIssue(
                    "bad_token.bulganghanseong",
                    "warn",
                    _BAD_TOKEN,
                    region,
                )
            )
        if _BAD_PARTICLE in scan_line:
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
        if region == "segment_first_viewport" and looks_truncated_mid_token(scan_line):
            issues.append(
                SurfaceQualityIssue(
                    "summary.truncated_mid_token",
                    "block",
                    line,
                    region,
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


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub("", line)


def _mask_inline_code(line: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Replace balanced inline-code spans with inert, reversible sentinels."""

    protected: list[tuple[str, str]] = []

    def replace_match(match: re.Match[str]) -> str:
        index = len(protected)
        token = f"\x00investo_inline_{index}\x00"
        while token in line or any(existing == token for existing, _ in protected):
            index += 1
            token = f"\x00investo_inline_{index}\x00"
        protected.append((token, match.group(0)))
        return token

    return _INLINE_CODE_RE.sub(replace_match, line), tuple(protected)


def _restore_inline_code(
    line: str,
    protected: tuple[tuple[str, str], ...],
) -> str:
    for token, original in protected:
        line = line.replace(token, original)
    return line


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
    if without_assignments == line.strip():
        return line
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
    "looks_truncated_mid_token",
    "repair_surface_artifacts",
]
