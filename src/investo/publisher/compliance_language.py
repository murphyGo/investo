"""u56 — compliance-language gate at the publish boundary.

Public surface:

* :class:`ComplianceLanguageError` — subclass of
  :class:`PublisherError`. Raised when a P0 phrase survives the
  context-aware demote pass. The orchestrator treats this exactly like
  a disclaimer block (publish does NOT happen).
* :func:`scan_compliance` — pure ``(markdown, segment) -> ComplianceReport``.
  Detects P0 / P1 / demoted-INFO hits and either raises (P0) or returns
  the report (P1 / INFO observed but non-blocking).

Module boundary: imports only ``models.compliance_phrases`` (data) and
``publisher.errors`` (own error hierarchy). Does NOT import from
``briefing/`` / ``sources/`` / ``notifier/``.

The P0 catalogue lives in ``investo.models.compliance_phrases`` so the
Stage-2 prompt (briefing-side) and this gate (publisher-side) read the
same list — drift is prevented by single-source.

R13 hygiene: WARN extras carry only ``segment / phrase / count /
line_no``. The phrase value is from the LLM-generated body, not from
``NormalizedItem.raw_metadata``; secret-bearing metadata cannot leak
into this surface by construction.

Out-of-scope for P0 detection:
* Markdown code blocks (triple-backtick fences) — LLM is highly unlikely
  to emit P0 phrases inside code, and false-positive risk is high (code
  snippets may quote forbidden terms).
* Table cells (``|...|``) — same reasoning.
* The disclaimer footer — the canonical text deliberately mentions
  "매매 권유" which would otherwise look adjacent to action verbs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final, Literal

from investo.models.compliance_phrases import (
    BANNED_P0_ACTION,
    BANNED_P0_CERTAINTY,
    BANNED_P0_CRYPTO_ONLY,
    BANNED_P0_QUANTIFIED_OUTCOME,
    CONTEXT_DEMOTE_NEIGHBORS,
    WARN_P1,
    WARN_P1_CLOSED_CAUSATION,
)
from investo.models.segments import MarketSegment
from investo.publisher.errors import PublisherError

_logger = logging.getLogger(__name__)

Severity = Literal["P0", "P1", "INFO"]


@dataclass(frozen=True, slots=True)
class ComplianceHit:
    """One detected phrase occurrence."""

    phrase: str
    severity: Severity
    line_no: int  # 1-based
    category: str  # "action" | "certainty" | "quantified" | "crypto" | "p1"


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Aggregate report from a :func:`scan_compliance` pass."""

    segment: MarketSegment
    p0_hits: tuple[ComplianceHit, ...] = field(default_factory=tuple)
    p1_hits: tuple[ComplianceHit, ...] = field(default_factory=tuple)
    info_hits: tuple[ComplianceHit, ...] = field(default_factory=tuple)


class ComplianceLanguageError(PublisherError):
    """Pre-publish P0 compliance-language hit (u56 / NFR-004 hardening).

    Raised by ``scan_compliance`` when a P0 phrase survives the
    context-aware demote pass. The orchestrator must NOT publish.
    """

    segment: MarketSegment
    hits: tuple[ComplianceHit, ...]

    def __init__(self, *, segment: MarketSegment, hits: tuple[ComplianceHit, ...]) -> None:
        phrases = sorted({h.phrase for h in hits})
        super().__init__(
            f"refusing to publish {segment} briefing: compliance-language P0 hit(s): {phrases}"
        )
        self.segment = segment
        self.hits = hits


# ---------------------------------------------------------------------------
# Block-scope masking — strip code blocks & table cells before scan
# ---------------------------------------------------------------------------

_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"`[^`\n]+`")
_TABLE_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|.*\|\s*$")
_DISCLAIMER_ANCHOR: Final[str] = "## ⑦ 면책조항"
_REPAIR_REPLACEMENTS: Final[dict[str, str]] = {
    "매수 검토": "거래 판단 점검",
    "매도 검토": "거래 판단 점검",
    "비중 축소": "노출 변화 점검",
    "비중 확대": "노출 변화 점검",
    "편입": "포함",
    "차익실현": "거래 리스크 관리",
    "익절": "거래 리스크 관리",
    "손절매": "거래 리스크 관리",
    "손절": "거래 리스크 관리",
    "리밸런싱": "구성 변화",
    "진입": "접근",
    "청산": "정리",
    "목표가": "전망치",
    "평단가": "평균 단가",
    "추격매수": "추가 거래",
    "물타기": "추가 거래",
    "반드시": "가능성이 있어",
    "확실": "강한",
    "보장": "확인 필요",
    "급등 예상": "상승 가능성",
    "급락 임박": "하락 압력",
    "불가피": "가능성이 커",
    "필연": "개연성",
    "세력": "대형 참여자",
    "김프 진입": "김프 확대",
    "상폐 임박": "상장폐지 리스크",
    "에어드랍 확정": "에어드랍 관련 기대",
    "펌핑": "단기 급등",
}
_REPAIR_QUANTIFIED_OUTCOME_REPLACEMENTS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(
            r"\d+\s*%\s*(이상\s*)?\s*(수익|상승|하락|손실)\s*"
            r"(예상|가능|기대|보장|확실|불가피)"
        ),
        "수익률 변동 가능성",
    ),
    (re.compile(r"\d+\s*배\s*(수익|상승)"), "큰 변동 가능성"),
)


def _mask_non_scan_regions(markdown: str) -> str:
    """Replace code-block / table-cell / disclaimer-footer regions with
    same-length blanks so byte offsets and line numbers stay valid.

    Idempotent: subsequent scan-side regex .finditer calls operate on
    the masked string and skip the regions cleanly.
    """
    out = markdown
    # 1. Disclaimer footer — mask from anchor to end of document. We do
    #    NOT want to flag wording inside the canonical disclaimer.
    anchor_idx = out.find(_DISCLAIMER_ANCHOR)
    if anchor_idx >= 0:
        out = out[:anchor_idx] + " " * (len(out) - anchor_idx)

    # 2. Fenced code blocks.
    def _blank_match(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    out = _CODE_FENCE_RE.sub(_blank_match, out)
    out = _INLINE_CODE_RE.sub(_blank_match, out)

    # 3. Table rows — mask line-by-line so the line counts remain stable.
    lines = out.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if _TABLE_LINE_RE.match(line):
            # Preserve newline so line numbers stay aligned.
            stripped = line.rstrip("\n")
            newline = line[len(stripped) :]
            lines[idx] = " " * len(stripped) + newline
    return "".join(lines)


def repair_compliance_language(markdown: str, segment: MarketSegment) -> str:
    """Rewrite P0 compliance phrases into neutral reader-facing wording.

    The repair pass is deliberately conservative about scope: it skips
    code blocks, table rows, and the canonical disclaimer footer, then
    the publish gate still calls :func:`scan_compliance` as the hard
    verifier.
    """
    lines = markdown.splitlines(keepends=True)
    in_code = False
    changed = False
    for index, line in enumerate(lines):
        if _DISCLAIMER_ANCHOR in line:
            break
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or _TABLE_LINE_RE.match(line):
            continue
        repaired = line
        for pattern, replacement in _REPAIR_QUANTIFIED_OUTCOME_REPLACEMENTS:
            repaired = pattern.sub(replacement, repaired)
        for phrase, replacement in _REPAIR_REPLACEMENTS.items():
            if phrase in repaired:
                repaired = repaired.replace(phrase, replacement)
        if repaired != line:
            lines[index] = repaired
            changed = True
    if not changed:
        return markdown
    return "".join(lines)


# ---------------------------------------------------------------------------
# Line / token helpers
# ---------------------------------------------------------------------------


def _line_of(text: str, offset: int) -> tuple[int, str]:
    """Return ``(1-based line number, line text)`` for ``offset``."""
    line_no = text.count("\n", 0, offset) + 1
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end < 0:
        end = len(text)
    return line_no, text[start:end]


# 6-token window: left 3 / right 3. Tokens are whitespace-separated
# runs after stripping common punctuation. Korean is mostly whitespace-
# delimited at the phrase level, which is sufficient for the demote
# decision (we are not parsing morphology).
_TOKEN_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"[\s,.;:!\?\(\)\[\]\|]+")


def _window_neighbors(line: str, phrase: str, phrase_start: int) -> tuple[list[str], list[str]]:
    """Return ``(left_tokens, right_tokens)`` around ``phrase`` in ``line``.

    ``phrase_start`` is the offset of ``phrase`` within ``line``. The
    left/right caps are 3 tokens each (6-token total window).
    """
    left_text = line[:phrase_start]
    right_text = line[phrase_start + len(phrase) :]
    left = [t for t in _TOKEN_SPLIT_RE.split(left_text) if t]
    right = [t for t in _TOKEN_SPLIT_RE.split(right_text) if t]
    return left[-3:], right[:3]


def _classify_phrase(
    phrase: str,
    line: str,
    phrase_start: int,
) -> Severity:
    """Return ``P0`` unless the 6-token window justifies an ``INFO`` demote.

    Asymmetric for ``목표가``: only *left*-side quotative markers (증권사,
    애널리스트, 보고서, IR, 분기 — analyst-report citation) demote.
    Bare ``목표가 7만원`` stays P0 because the speaker is asserting a
    forward target, which is advice.
    """
    demote_neighbors = CONTEXT_DEMOTE_NEIGHBORS.get(phrase)
    if demote_neighbors is None:
        return "P0"
    left, right = _window_neighbors(line, phrase, phrase_start)
    if phrase == "목표가":
        # quotative source must appear on the LEFT (it's the speaker
        # being cited).
        for token in left:
            for neighbor in demote_neighbors:
                if neighbor in token:
                    return "INFO"
        return "P0"
    # Default symmetric window for other phrases (진입 / 청산 / 편입).
    for token in (*left, *right):
        for neighbor in demote_neighbors:
            if neighbor in token:
                return "INFO"
    return "P0"


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _scan_substring_list(
    masked: str,
    phrases: tuple[str, ...],
    category: str,
    *,
    fixed_severity: Severity | None = None,
) -> tuple[list[ComplianceHit], list[ComplianceHit]]:
    """Scan ``masked`` for each ``phrases`` substring; classify per hit.

    Returns ``(p0_or_p1_hits, info_hits)``. ``fixed_severity`` skips the
    context-aware classifier (used for non-demotable categories like
    certainty / crypto-only / P1).
    """
    primary: list[ComplianceHit] = []
    info: list[ComplianceHit] = []
    for phrase in phrases:
        start = 0
        while True:
            idx = masked.find(phrase, start)
            if idx < 0:
                break
            line_no, line_text = _line_of(masked, idx)
            line_start = masked.rfind("\n", 0, idx) + 1
            phrase_start_in_line = idx - line_start
            if (
                phrase == "확실"
                and phrase_start_in_line > 0
                and line_text[phrase_start_in_line - 1] == "불"
            ):
                start = idx + len(phrase)
                continue
            if fixed_severity is not None:
                severity: Severity = fixed_severity
            else:
                severity = _classify_phrase(phrase, line_text, phrase_start_in_line)
            hit = ComplianceHit(
                phrase=phrase, severity=severity, line_no=line_no, category=category
            )
            if severity == "INFO":
                info.append(hit)
            else:
                primary.append(hit)
            start = idx + len(phrase)
    return primary, info


def _scan_regex_list(
    masked: str,
    patterns: tuple[re.Pattern[str], ...],
    category: str,
    severity: Severity,
) -> list[ComplianceHit]:
    hits: list[ComplianceHit] = []
    for pattern in patterns:
        for match in pattern.finditer(masked):
            line_no, _ = _line_of(masked, match.start())
            hits.append(
                ComplianceHit(
                    phrase=match.group(0),
                    severity=severity,
                    line_no=line_no,
                    category=category,
                )
            )
    return hits


def scan_compliance(markdown: str, segment: MarketSegment) -> ComplianceReport:
    """Scan ``markdown`` for compliance-language hits.

    Raises :class:`ComplianceLanguageError` when any P0 hit survives the
    context-aware demote pass. P1 hits are logged as WARN with
    structured extras (``segment / phrase / line_no``) and returned in
    the report. INFO hits (demoted P0s) are returned for visibility but
    do not log.

    Pure function: no I/O. The masking pass strips code blocks / tables /
    disclaimer footer so the same input always produces the same report.
    """
    masked = _mask_non_scan_regions(markdown)

    action_hits, action_info = _scan_substring_list(masked, BANNED_P0_ACTION, "action")
    certainty_hits, _ = _scan_substring_list(
        masked, BANNED_P0_CERTAINTY, "certainty", fixed_severity="P0"
    )
    quantified_hits = _scan_regex_list(masked, BANNED_P0_QUANTIFIED_OUTCOME, "quantified", "P0")
    crypto_hits: list[ComplianceHit] = []
    if segment == "crypto":
        crypto_hits_raw, _ = _scan_substring_list(
            masked, BANNED_P0_CRYPTO_ONLY, "crypto", fixed_severity="P0"
        )
        crypto_hits = crypto_hits_raw

    p1_hits, _ = _scan_substring_list(masked, WARN_P1, "p1", fixed_severity="P1")
    p1_hits.extend(_scan_regex_list(masked, WARN_P1_CLOSED_CAUSATION, "p1", "P1"))

    p0_hits = tuple(action_hits + certainty_hits + quantified_hits + crypto_hits)
    p1_hits_tuple = tuple(p1_hits)
    info_hits = tuple(action_info)

    report = ComplianceReport(
        segment=segment,
        p0_hits=p0_hits,
        p1_hits=p1_hits_tuple,
        info_hits=info_hits,
    )

    if p0_hits:
        raise ComplianceLanguageError(segment=segment, hits=p0_hits)

    for hit in p1_hits_tuple:
        _logger.warning(
            "compliance_language.p1_hit",
            extra={
                "segment": segment,
                "phrase": hit.phrase,
                "category": hit.category,
                "line_no": hit.line_no,
            },
        )

    return report


__all__ = [
    "ComplianceHit",
    "ComplianceLanguageError",
    "ComplianceReport",
    "repair_compliance_language",
    "scan_compliance",
]
