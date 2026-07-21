"""u70 — gate precise body claims on canonical anchor availability.

A reviewed failure: the domestic status block reported the core price
source as missing/empty, yet the body prose still asserted a precise
KOSPI direction and move ("코스피 1.8% 급락"). u55 verifies numeric
*freshness* and *facts*, but it does not block a directional claim about
a core index when the matching anchor never made it into the canonical
payload at all. u70 closes that gap.

This module is the cross-surface guard, not a new numeric validator:

* It consumes the *prepared* set of canonical anchor symbols the
  orchestrator already reconciled (the single anchor payload). It does
  NOT re-fetch, re-verify, or re-decide a numeric truth — if a symbol's
  anchor is absent, the body cannot assert a precise move about it.
* For an **isolated** offending sentence (its own paragraph / line) the
  gate rewrites it to a deterministic data-limited callout, so a
  same-day re-run is byte-stable.
* When the offending sentence is part of a multi-sentence prose line, the
  gate rewrites only the offending sentence and preserves the neighboring
  supported sentences. Structural lines still fail closed.

Module boundary
~~~~~~~~~~~~~~~
Pure string + symbol-set logic. Imports only
:mod:`investo.briefing.market_anchor` (canonical labels, a shared type
the publisher already depends on via the anchor table) and
:mod:`investo.briefing.segments` (segment enum). No I/O, no clock, no
env reads — same inputs → identical output (FR-006 idempotency).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from investo.models.market_anchor import anchor_label
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

# Core anchor symbols whose precise body claims u70 guards, per segment.
# These mirror the anchor-table priority basket; a body claim about one of
# these labels with NO matching canonical anchor present is gated.
_SEGMENT_CORE_SYMBOLS: Final[dict[MarketSegment, tuple[str, ...]]] = {
    DOMESTIC_EQUITY: ("^KOSPI", "^KOSDAQ", "KRW=X", "005930.KS", "000660.KS"),
    US_EQUITY: ("^GSPC", "^IXIC", "^DJI"),
    CRYPTO: ("BTC-USD", "ETH-USD"),
}

# Movement verbs / direction tokens that turn a mention into a *precise
# market-move claim*. Korean reader vocabulary plus a signed-number guard
# applied separately so "코스피는 약세였다" (vague) does not trip while
# "코스피 1.8% 급락" (precise) does.
_MOVE_VERBS: Final[tuple[str, ...]] = (
    "급등",
    "급락",
    "상승",
    "하락",
    "반등",
    "폭락",
    "폭등",
    "강세",
    "약세",
    "치솟",
)
_MOVE_VERB_RE: Final[re.Pattern[str]] = re.compile("|".join(_MOVE_VERBS))

# A signed / explicit magnitude: percent, point (포인트/pt), or a price
# figure. Presence of a magnitude token alongside a move verb + a core
# label is what makes the sentence "precise" (and therefore gateable).
_MAGNITUDE_RE: Final[re.Pattern[str]] = re.compile(
    r"[+\-]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|p|pt|포인트|원|달러|\$)",  # noqa: RUF001
)
_EXTRA_SYMBOL_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "005930.KS": ("삼성전자", "005930", "005930.KS"),
    "000660.KS": ("SK하이닉스", "000660", "000660.KS"),
}
_EXTRA_SYMBOL_LABELS: Final[dict[str, str]] = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
}

# Deterministic replacement for an isolated gated sentence.
_DATA_LIMITED_TEMPLATE: Final[str] = (
    "{label} 관련 정밀 수치는 이번 회차 코어 데이터 미수집으로 확정할 수 없습니다."
)


class NumericAnchorReconciliationError(RuntimeError):
    """A precise body claim references a core symbol with no canonical anchor.

    Raised when the gate finds an un-rewritable (non-isolated) precise
    move claim about a core index/asset whose anchor is missing/stale.
    The orchestrator's publish-stage handler catches this alongside the
    other reader-format gates, rolls back this run's writes, and fails the
    publish rather than shipping a body that contradicts the status block.
    """


@dataclass(frozen=True, slots=True)
class AnchorAssertionFinding:
    """One body sentence that asserts a precise move without an anchor."""

    segment: MarketSegment
    symbol: str
    label: str
    sentence: str
    isolated: bool


@dataclass(frozen=True, slots=True)
class AnchorGateResult:
    """Outcome of gating one segment's body prose."""

    markdown: str
    findings: tuple[AnchorAssertionFinding, ...]

    @property
    def has_blocking_finding(self) -> bool:
        """True when a non-isolated (un-rewritable) claim remains."""
        return any(not f.isolated for f in self.findings)


def _label_aliases(symbol: str) -> tuple[str, ...]:
    """Reader-facing strings that denote ``symbol`` in body prose."""
    label = anchor_label(symbol)
    aliases = {label.ko, label.short, label.display, symbol}
    aliases.update(_EXTRA_SYMBOL_ALIASES.get(symbol, ()))
    return tuple(a for a in aliases if a)


def _sentence_targets_symbol(sentence: str, symbol: str) -> bool:
    return any(alias in sentence for alias in _label_aliases(symbol))


_CLAUSE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)[.!?。](?!\d)|(?<!\d),(?!\d)|;|(?:\s+[-—]\s+)"
)


def _is_precise_move_claim_for_symbol(sentence: str, symbol: str) -> bool:
    """True when a symbol-local clause has both movement and magnitude.

    A long watchpoint line can mention multiple markets and numbers in one
    markdown block. Keep unrelated numbers, such as KRX flows or bond yields,
    from turning a vague FX mention into a gated precise FX claim.
    """
    for clause in _CLAUSE_SPLIT_RE.split(sentence):
        if not _sentence_targets_symbol(clause, symbol):
            continue
        if _MOVE_VERB_RE.search(clause) and _MAGNITUDE_RE.search(clause):
            return True
    return False


def gate_body_assertions(
    markdown: str,
    *,
    segment: MarketSegment,
    available_symbols: Iterable[str],
) -> AnchorGateResult:
    """Block precise body claims about core symbols lacking an anchor.

    ``available_symbols`` is the set of symbols present in the canonical
    reconciled anchor payload for this segment. A core symbol absent from
    that set is "missing/stale" — the body may not assert a precise move
    about it.

    Behaviour:

    * An offending prose sentence is replaced with a deterministic
      data-limited callout (idempotent), even when it shares a line with
      other sentences.
    * An offending structural line is left in place and surfaced as a
      *blocking* finding so the publish path can reject the bundle.

    Sentences are split on Korean/Latin sentence terminators while leaving
    markdown structure (headers, list bullets, table rows) intact — those
    lines are scanned but never rewritten so the gate cannot corrupt the
    anchor table or chart block.
    """
    available = set(available_symbols)
    gated_symbols = [sym for sym in _SEGMENT_CORE_SYMBOLS.get(segment, ()) if sym not in available]
    if not gated_symbols:
        return AnchorGateResult(markdown=markdown, findings=())

    findings: list[AnchorAssertionFinding] = []
    out_lines: list[str] = []
    for line in markdown.split("\n"):
        rewritten, line_findings = _gate_line(line, segment=segment, gated_symbols=gated_symbols)
        out_lines.append(rewritten)
        findings.extend(line_findings)
    return AnchorGateResult(markdown="\n".join(out_lines), findings=tuple(findings))


# Structural lines we scan-but-never-rewrite: headers, table rows, chart /
# HTML blocks, and the legacy market-anchor blockquote. Rewriting these
# would damage the anchor table or chart placeholder the gate protects.
_STRUCTURAL_PREFIXES: Final[tuple[str, ...]] = ("#", "|", "<", "```")
_PROTECTED_BLOCKQUOTE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*>\s*\*\*시장 anchor\*\*:",
    re.IGNORECASE,
)
_PROSE_BLOCKQUOTE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\s*>\s*(?:\*\*[^*\n]+\*\*:\s*)?)(.*)$"
)
_TRACEABILITY_ITEM_ROW_RE: Final[re.Pattern[str]] = re.compile(
    r"^\|\s*\d+\s*\|\s*[-a-z0-9_]+\s*\|\s*[a-z_]+\s*\|\s*(?:\d+|—)\s*\|",
    re.IGNORECASE,
)


def scan_anchor_assertions(
    markdown: str,
    *,
    segment: MarketSegment,
    available_symbols: Iterable[str],
) -> tuple[AnchorAssertionFinding, ...]:
    """Return exact unsupported numeric claims without rewriting Markdown."""

    available = set(available_symbols)
    gated_symbols = tuple(
        symbol for symbol in _SEGMENT_CORE_SYMBOLS.get(segment, ()) if symbol not in available
    )
    if not gated_symbols:
        return ()
    findings: list[AnchorAssertionFinding] = []
    for line in markdown.split("\n"):
        findings.extend(
            _scan_line_assertions(
                line,
                segment=segment,
                gated_symbols=gated_symbols,
            )
        )
    return tuple(findings)


def _scan_line_assertions(
    line: str,
    *,
    segment: MarketSegment,
    gated_symbols: Sequence[str],
) -> tuple[AnchorAssertionFinding, ...]:
    stripped = line.lstrip()
    if _is_traceability_table_line(stripped) or _PROTECTED_BLOCKQUOTE_RE.match(line):
        return ()
    structural = stripped.startswith(_STRUCTURAL_PREFIXES)
    content = line
    if not structural:
        match = _PROSE_BLOCKQUOTE_RE.match(line)
        if match is None:
            match = re.match(r"^(\s*(?:[-*]|\d+\.)\s+)(.*)$", line)
        if match is not None:
            content = match.group(2)

    if structural:
        for symbol in gated_symbols:
            if _is_precise_move_claim_for_symbol(content, symbol):
                return (
                    AnchorAssertionFinding(
                        segment=segment,
                        symbol=symbol,
                        label=_public_label(symbol),
                        sentence=line.strip(),
                        isolated=False,
                    ),
                )
        return ()

    findings: list[AnchorAssertionFinding] = []
    for unit in _sentence_units(content):
        sentence = unit.strip()
        if not sentence:
            continue
        for symbol in gated_symbols:
            if not _is_precise_move_claim_for_symbol(sentence, symbol):
                continue
            findings.append(
                AnchorAssertionFinding(
                    segment=segment,
                    symbol=symbol,
                    label=_public_label(symbol),
                    sentence=sentence,
                    isolated=True,
                )
            )
            break
    return tuple(findings)


def _gate_line(
    line: str,
    *,
    segment: MarketSegment,
    gated_symbols: Sequence[str],
) -> tuple[str, list[AnchorAssertionFinding]]:
    stripped = line.lstrip()
    if _is_traceability_table_line(stripped):
        return line, []
    if _PROTECTED_BLOCKQUOTE_RE.match(line):
        return line, []
    structural = stripped.startswith(_STRUCTURAL_PREFIXES)
    # List bullets are prose-bearing; treat the content after the marker
    # as a candidate isolated sentence. Reader-format blockquote callouts
    # are also prose-bearing; preserve the marker/label while rewriting the
    # unsupported sentence body.
    bullet_prefix = ""
    content = line
    if not structural:
        m = _PROSE_BLOCKQUOTE_RE.match(line)
        if m is None:
            m = re.match(r"^(\s*(?:[-*]|\d+\.)\s+)(.*)$", line)
        if m is not None:
            bullet_prefix = m.group(1)
            content = m.group(2)

    findings: list[AnchorAssertionFinding] = []
    for symbol in gated_symbols:
        if not _sentence_targets_symbol(content, symbol):
            continue
        if not _is_precise_move_claim_for_symbol(content, symbol):
            continue
        label = _public_label(symbol)
        if structural:
            # Cannot rewrite structure; record as blocking.
            findings.append(
                AnchorAssertionFinding(
                    segment=segment,
                    symbol=symbol,
                    label=label,
                    sentence=line.strip(),
                    isolated=False,
                )
            )
            return line, findings
        rewritten, sentence_findings = _rewrite_sentence_claims(
            content,
            segment=segment,
            gated_symbols=gated_symbols,
        )
        findings.extend(sentence_findings)
        return bullet_prefix + rewritten, findings
    return line, findings


def _is_traceability_table_line(stripped_line: str) -> bool:
    """True for the collapsed source/classification trace footer table."""
    return bool(_TRACEABILITY_ITEM_ROW_RE.match(stripped_line))


_SENTENCE_UNIT_RE: Final[re.Pattern[str]] = re.compile(r".*?(?:[.!?。](?:\s+|$)|$)", re.DOTALL)


def _rewrite_sentence_claims(
    content: str,
    *,
    segment: MarketSegment,
    gated_symbols: Sequence[str],
) -> tuple[str, list[AnchorAssertionFinding]]:
    """Rewrite only unsupported precise-claim sentences in a prose line."""
    findings: list[AnchorAssertionFinding] = []
    out: list[str] = []
    for unit in _sentence_units(content):
        stripped = unit.strip()
        if not stripped:
            out.append(unit)
            continue
        replacement: str | None = None
        for symbol in gated_symbols:
            if not _sentence_targets_symbol(stripped, symbol):
                continue
            if not _is_precise_move_claim_for_symbol(stripped, symbol):
                continue
            label = _public_label(symbol)
            findings.append(
                AnchorAssertionFinding(
                    segment=segment,
                    symbol=symbol,
                    label=label,
                    sentence=stripped,
                    isolated=True,
                )
            )
            suffix = " " if unit.endswith(" ") else ""
            replacement = _DATA_LIMITED_TEMPLATE.format(label=label) + suffix
            break
        out.append(replacement if replacement is not None else unit)
    return "".join(out), findings


def _sentence_units(content: str) -> tuple[str, ...]:
    """Return sentence-like units while preserving terminators and spaces."""
    units = tuple(m.group(0) for m in _SENTENCE_UNIT_RE.finditer(content) if m.group(0))
    return units or (content,)


def _public_label(symbol: str) -> str:
    return _EXTRA_SYMBOL_LABELS.get(symbol, anchor_label(symbol).ko)


def enforce_anchor_assertions(
    markdown: str,
    *,
    segment: MarketSegment,
    available_symbols: Iterable[str],
) -> str:
    """Gate body claims, raising on an un-rewritable contradiction.

    Returns the (possibly rewritten) markdown when every offending claim
    was isolated and replaced with a data-limited callout. Raises
    :class:`NumericAnchorReconciliationError` when a blocking finding
    remains so the publish path fails closed.
    """
    available = tuple(available_symbols)
    result = gate_body_assertions(markdown, segment=segment, available_symbols=available)
    residual = scan_anchor_assertions(
        result.markdown,
        segment=segment,
        available_symbols=available,
    )
    if residual:
        blocking = residual[0]
        raise NumericAnchorReconciliationError(
            f"{segment}: precise move claim for {blocking.label} "
            f"({blocking.symbol}) without a canonical anchor: {blocking.sentence!r}"
        )
    return result.markdown


__all__ = [
    "AnchorAssertionFinding",
    "AnchorGateResult",
    "NumericAnchorReconciliationError",
    "enforce_anchor_assertions",
    "gate_body_assertions",
    "scan_anchor_assertions",
]
