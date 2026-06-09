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

from investo.briefing.market_anchor import anchor_label
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

# Core anchor symbols whose precise body claims u70 guards, per segment.
# These mirror the anchor-table priority basket; a body claim about one of
# these labels with NO matching canonical anchor present is gated.
_SEGMENT_CORE_SYMBOLS: Final[dict[MarketSegment, tuple[str, ...]]] = {
    DOMESTIC_EQUITY: ("^KOSPI", "^KOSDAQ", "KRW=X"),
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
    return tuple(a for a in aliases if a)


def _sentence_targets_symbol(sentence: str, symbol: str) -> bool:
    return any(alias in sentence for alias in _label_aliases(symbol))


def _is_precise_move_claim(sentence: str) -> bool:
    return bool(_MOVE_VERB_RE.search(sentence) and _MAGNITUDE_RE.search(sentence))


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
# HTML blocks, blockquote callouts. Rewriting these would damage the
# anchor table or chart placeholder the gate is meant to protect.
_STRUCTURAL_PREFIXES: Final[tuple[str, ...]] = ("#", "|", "<", ">", "```")


def _gate_line(
    line: str,
    *,
    segment: MarketSegment,
    gated_symbols: Sequence[str],
) -> tuple[str, list[AnchorAssertionFinding]]:
    stripped = line.lstrip()
    structural = stripped.startswith(_STRUCTURAL_PREFIXES)
    # List bullets are prose-bearing; treat the content after the marker
    # as a candidate isolated sentence.
    bullet_prefix = ""
    content = line
    if not structural:
        m = re.match(r"^(\s*(?:[-*]|\d+\.)\s+)(.*)$", line)
        if m is not None:
            bullet_prefix = m.group(1)
            content = m.group(2)

    findings: list[AnchorAssertionFinding] = []
    for symbol in gated_symbols:
        if not _sentence_targets_symbol(content, symbol):
            continue
        if not _is_precise_move_claim(content):
            continue
        label = anchor_label(symbol).ko
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
            if not _is_precise_move_claim(stripped):
                continue
            label = anchor_label(symbol).ko
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
    result = gate_body_assertions(markdown, segment=segment, available_symbols=available_symbols)
    if result.has_blocking_finding:
        blocking = next(f for f in result.findings if not f.isolated)
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
]
