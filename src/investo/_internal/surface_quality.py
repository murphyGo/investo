"""Shared deterministic surface-quality repairs and issue detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SurfaceIssueSeverity = Literal["warn", "block"]
SurfaceIssueRegion = Literal["first_viewport", "body", "protected"]

_FIRST_SECTION_RE = re.compile(r"(?m)^## ①")
_ANY_H2_RE = re.compile(r"(?m)^## ")
_BAD_TOKEN = "불강한성"
_BAD_TOKEN_REPAIR = "불확실성"
_TRACE_RE = re.compile(r"\b(?:input_hash|stage1_hash|stage2_hash)\b")
_RECOVERABLE_LINK_FRAGMENT_RE = re.compile(
    r"\[([^\]\n]+)\]\((?:https?://|www\.)[^\s)\n]*"
)
_DANGLING_ELLIPSIS_RE = re.compile(r"(?:^|\s)\.\.\.$")
_REPEATED_PHRASES = (
    "본문을 참고하세요",
    "데이터가 제한적입니다",
    "추가 확인이 필요합니다",
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

        repaired = line.replace(_BAD_TOKEN, _BAD_TOKEN_REPAIR)
        if offset < first_viewport_len:
            repaired = _repair_recoverable_link_fragments(repaired)
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
    """Find first-viewport surface-quality warnings and blockers."""

    issues: list[SurfaceQualityIssue] = []
    first = extract_first_viewport(text)
    issues.extend(_scan_lines(first, region="first_viewport"))
    issues.extend(_repeated_phrase_warnings(first))
    return tuple(issues)


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
        if _BAD_TOKEN in line:
            issues.append(
                SurfaceQualityIssue(
                    "bad_token.bulganghanseong",
                    "warn",
                    _BAD_TOKEN,
                    region,
                )
            )
        if _DANGLING_ELLIPSIS_RE.search(line.strip()):
            issues.append(SurfaceQualityIssue("ellipsis.dangling_line", "warn", line, region))
        if _TRACE_RE.search(line):
            issues.append(SurfaceQualityIssue("trace.fragment", "block", line, region))
        if _looks_like_unmatched_link(line):
            issues.append(SurfaceQualityIssue("markdown.unmatched_link", "block", line, region))
    return issues


def _repeated_phrase_warnings(text: str) -> list[SurfaceQualityIssue]:
    return [
        SurfaceQualityIssue("template.repeated_phrase", "warn", phrase, "first_viewport")
        for phrase in _REPEATED_PHRASES
        if text.count(phrase) >= 3
    ]


def _looks_like_unmatched_link(line: str) -> bool:
    if line.count("[") != line.count("]"):
        return True
    return line.count("](") > line.count(")")


def _repair_recoverable_link_fragments(line: str) -> str:
    """Preserve link text when a first-viewport URL was cut before ``)``."""

    return _RECOVERABLE_LINK_FRAGMENT_RE.sub(r"\1", line)


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
    "find_surface_quality_issues",
    "has_blocking_surface_issue",
    "repair_surface_artifacts",
]
