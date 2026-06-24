"""Cross-segment narrative lint (u57 Step 3).

Deterministic post-Stage-2 lint that pins the three measurable
proxies derived from u57's untestable AC:

* **AC1 (cross-market demotion)** — :func:`lint_domestic_foreign_linkage`.
  In a domestic-segment body, any paragraph that mentions a foreign
  ticker (AAPL, NVDA, TSMC, ...) must also include either a domestic
  ticker (``\\d{6}``) or a linkage keyword (``국내 영향``,
  ``환율 경로``, ``코스피 연관`` …) in the *same* paragraph.

* **AC2 (native fact priority)** — :func:`lint_native_fact_priority`.
  Each segment's §② first H3 (or first bullet/paragraph) must lead
  with a segment-native entity.

* **AC3 (domestic watchlist strict)** — handled by the same mechanism
  as AC1 with a stricter severity tier inside the watchlist
  subsection.

* **Time-state coherence** — :func:`lint_time_state_consistency`.
  Reject "하락 출발 / 상승 출발" wording when the cited segment's
  ``close_state == "close"`` (same-page contradiction guard).

Pure module — every function takes text + context and returns a list
of :class:`LintViolation`. No I/O, no logger side effects.

References
----------

* u57 plan Step 3 — deterministic linkage lint.
* u57 DoD — "publish-gate WARNING + demote/reject when violated".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from investo.models.bundle_context import BundleContext
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)

LintSeverity = Literal["WARN", "REJECT"]

__all__ = [
    "DOMESTIC_LINKAGE_KEYWORDS",
    "DOMESTIC_TICKER_PATTERN",
    "FOREIGN_TICKER_PATTERN",
    "LintViolation",
    "lint_domestic_foreign_linkage",
    "lint_native_fact_priority",
    "lint_time_state_consistency",
    "run_all_cross_segment_lints",
]


@dataclass(frozen=True)
class LintViolation:
    """A single deterministic lint hit."""

    severity: LintSeverity
    kind: str
    paragraph: str
    evidence: str


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Well-known foreign mega-caps. Static — TECH-DEBT to auto-sync with
# the sources/ ticker registry (see u57 plan open questions).
#
# Boundary handling: ``\b`` in Python's :mod:`re` treats Hangul
# syllables as word characters, so ``\bAAPL\b`` fails to match in
# ``AAPL이`` (no boundary between the L and the syllable). We use
# explicit ASCII boundaries — the ticker must be preceded and
# followed by a non-ASCII-letter character (or start/end of string).
FOREIGN_TICKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z])(AAPL|MSFT|NVDA|GOOG|GOOGL|AMZN|META|TSLA|TSMC|AMD|INTC|NFLX|"
    r"AVGO|ORCL|CRM|ADBE|PYPL|UBER|SHOP|COIN|PLTR|RBLX|SNOW|PANW|"
    r"BABA|JD|PDD|NIO|XPEV|TM|SONY|ASML|SAP|RHHBY|NVO)(?![A-Za-z])"
)

# Domestic 6-digit KRX ticker — kept tight to avoid false positives
# against years (e.g. ``2026년``). Use ASCII-digit boundary on both
# sides so the match survives adjacency with Hangul syllables.
DOMESTIC_TICKER_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?<!\d)\d{6}(?!\d)")

# Linkage keywords that establish a domestic relevance hook in the
# same paragraph as a foreign ticker.
DOMESTIC_LINKAGE_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "국내 영향",
        "환율 경로",
        "코스피 연관",
        "코스피 영향",
        "수급 영향",
        "외국인 매매",
        "외국인 수급",
        "환율",
        "원/달러",
        "원달러",
        "원화",
    }
)

# Per-segment native entity allowlist. AC2 says the §② first H3 /
# bullet primary noun must match this for the segment.
_NATIVE_ALLOWLIST_DOMESTIC: Final[re.Pattern[str]] = re.compile(
    r"((?<!\d)\d{6}(?!\d)|KOSPI|KOSDAQ|KRX|코스피|코스닥|외국인|기관|개인|원/달러|원달러)",
    re.IGNORECASE,
)
_NATIVE_ALLOWLIST_US: Final[re.Pattern[str]] = re.compile(
    r"(SPX|SPY|NDX|QQQ|DJI|S&P|나스닥|다우|러셀|"
    r"AAPL|MSFT|NVDA|GOOG|GOOGL|AMZN|META|TSLA|AMD|"
    r"VIX|10년물|국채)",
    re.IGNORECASE,
)
_NATIVE_ALLOWLIST_CRYPTO: Final[re.Pattern[str]] = re.compile(
    r"(BTC|ETH|SOL|ADA|XRP|DOGE|MATIC|AVAX|DOT|LINK|"
    r"비트코인|이더리움|솔라나|리플|도지|체인링크|폴카닷)",
    re.IGNORECASE,
)

_NATIVE_ALLOWLISTS: Final[dict[MarketSegment, re.Pattern[str]]] = {
    DOMESTIC_EQUITY: _NATIVE_ALLOWLIST_DOMESTIC,
    US_EQUITY: _NATIVE_ALLOWLIST_US,
    CRYPTO: _NATIVE_ALLOWLIST_CRYPTO,
}

# "하락 출발" / "상승 출발" wording — same-page contradiction probe.
# When a body cites this wording about a segment whose BundleContext
# says ``close_state == "close"`` we have a self-inconsistent bundle.
_OPEN_DIRECTION_WORDING: Final[re.Pattern[str]] = re.compile(
    r"(\d+(?:\.\d+)?%?\s?(상승|하락)\s?출발|상승\s?출발|하락\s?출발)"
)

# Crude segment-citation detector. Used to figure out which segment
# the "출발" wording is referring to.
_SEGMENT_CITATION: Final[dict[MarketSegment, re.Pattern[str]]] = {
    US_EQUITY: re.compile(
        r"(미국|뉴욕|나스닥|S&P|SPX|NDX|(?<![A-Za-z])US(?![A-Za-z]))",
        re.IGNORECASE,
    ),
    DOMESTIC_EQUITY: re.compile(r"(코스피|코스닥|KOSPI|KOSDAQ|국내)", re.IGNORECASE),
    CRYPTO: re.compile(r"(비트코인|이더리움|크립토|BTC|ETH)", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, preserving paragraph content unchanged."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _paragraph_has_linkage(paragraph: str) -> bool:
    if DOMESTIC_TICKER_PATTERN.search(paragraph):
        return True
    return any(keyword in paragraph for keyword in DOMESTIC_LINKAGE_KEYWORDS)


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# Lint functions
# ---------------------------------------------------------------------------


def lint_domestic_foreign_linkage(
    text: str,
    *,
    strict_watchlist: bool = True,
) -> list[LintViolation]:
    """AC1 / AC3 — foreign-ticker paragraphs need domestic linkage.

    Returns one :class:`LintViolation` per offending paragraph. Severity
    is ``REJECT`` when the paragraph sits under a Watchlist subsection
    (``## ⑤`` / ``Watchlist`` H2/H3) and ``strict_watchlist=True``;
    otherwise ``WARN`` so the orchestrator can demote rather than drop.
    """
    if not text:
        return []
    violations: list[LintViolation] = []
    paragraphs = _split_paragraphs(text)
    in_watchlist = False
    for para in paragraphs:
        # Toggle watchlist scope on heading lines.
        if re.search(r"^(#{1,6})\s.*(워치|watch|관심|⑤)", para, re.IGNORECASE | re.MULTILINE):
            in_watchlist = True
        elif re.match(r"^#{1,6}\s", para):
            # New header that is not a watchlist header → reset.
            in_watchlist = False
        foreign_hit = FOREIGN_TICKER_PATTERN.search(para)
        if not foreign_hit:
            continue
        if _paragraph_has_linkage(para):
            continue
        severity: LintSeverity = "REJECT" if (in_watchlist and strict_watchlist) else "WARN"
        violations.append(
            LintViolation(
                severity=severity,
                kind="cross_segment_lint.foreign_ticker_no_linkage",
                paragraph=_truncate(para),
                evidence=foreign_hit.group(0),
            )
        )
    return violations


def lint_native_fact_priority(
    text: str,
    segment: MarketSegment,
) -> list[LintViolation]:
    """AC2 — §② first H3 / paragraph primary noun is segment-native.

    Returns a single ``WARN`` violation when the §② block exists but
    its first H3 (or first non-blank paragraph) does NOT match the
    segment-native allowlist. Missing §② is silent (other lints handle
    structural completeness).
    """
    if not text:
        return []
    pattern = _NATIVE_ALLOWLISTS.get(segment)
    if pattern is None:
        return []
    # Find the §② block. Tolerate the common variants ``## ②`` and
    # ``## ② 코어`` etc.
    match = re.search(r"##\s*②[^\n]*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
    if match is None:
        return []
    body = match.group(1).strip()
    if not body:
        return []
    # Look at the first H3 (``###``) if present; otherwise the first
    # non-empty line.
    first_chunk_match = re.search(r"###\s+(.+)", body)
    if first_chunk_match is not None:
        chunk = first_chunk_match.group(1)
    else:
        first_line = next((line for line in body.splitlines() if line.strip()), "")
        chunk = first_line
    if not chunk:
        return []
    if pattern.search(chunk):
        return []
    return [
        LintViolation(
            severity="WARN",
            kind="cross_segment_lint.native_priority_violated",
            paragraph=_truncate(chunk),
            evidence=segment,
        )
    ]


def lint_time_state_consistency(
    text: str,
    ctx: BundleContext,
) -> list[LintViolation]:
    """Reject "출발" wording about a segment whose close_state is ``close``.

    Severity is ``REJECT`` because this is a same-page factual
    contradiction.
    """
    if not text:
        return []
    violations: list[LintViolation] = []
    paragraphs = _split_paragraphs(text)
    for para in paragraphs:
        wording_match = _OPEN_DIRECTION_WORDING.search(para)
        if not wording_match:
            continue
        for segment_id, cite_pattern in _SEGMENT_CITATION.items():
            if not cite_pattern.search(para):
                continue
            summary = ctx.for_segment(segment_id)
            if summary is None:
                continue
            if summary.close_state == "close":
                violations.append(
                    LintViolation(
                        severity="REJECT",
                        kind="cross_segment_lint.time_state_contradiction",
                        paragraph=_truncate(para),
                        evidence=f"{segment_id}:{wording_match.group(0)}",
                    )
                )
                break  # one violation per paragraph
    return violations


def run_all_cross_segment_lints(
    text: str,
    *,
    segment: MarketSegment,
    ctx: BundleContext,
    strict_watchlist: bool = True,
) -> list[LintViolation]:
    """Aggregate runner — applies linkage / priority / time-state lints.

    The linkage lint only fires for the domestic segment per AC1; the
    other two segments still get the priority + time-state lints.
    """
    out: list[LintViolation] = []
    if segment == DOMESTIC_EQUITY:
        out.extend(lint_domestic_foreign_linkage(text, strict_watchlist=strict_watchlist))
    out.extend(lint_native_fact_priority(text, segment))
    out.extend(lint_time_state_consistency(text, ctx))
    return out
