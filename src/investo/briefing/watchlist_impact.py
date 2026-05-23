"""u73 — watchlist impact center v2.

A grouping / workflow layer on top of the u64 entity matcher
(:mod:`investo.briefing.watchlist`). u64 already produces
:class:`WatchlistMatch` records carrying ``confidence`` (one of
``structured`` / ``strict`` / ``alias`` / ``text``) and a ``reason``
code. This module does NOT re-implement matching — it consumes those
records and answers the reader's daily question: *what affected my
watchlist today, and what was intentionally ignored?*

Four impact groups (plan decision table, precedence Direct > Related >
Uncertain > Rejected):

* ``direct``    — high-confidence asset/ticker hit. u64 ``structured``
  confidence, ``strict`` ASCII ticker/asset boundary match, or an
  ``alias`` hit on a ticker/asset term. Public-facing.
* ``related``   — configured sector / keyword relation with source
  evidence but no exact asset/ticker hit. Public-facing (briefing
  body; Telegram only as labelled macro/sector context).
* ``uncertain`` — low-confidence free-text match (``text`` confidence
  on a sector/keyword, or an ambiguous short-ticker text hit).
  Collapsed diagnostics only.
* ``rejected``  — a configured short ticker that *looked* like it could
  hit an item but was correctly suppressed by u64 boundary / structured
  rules (e.g. ``BTC`` vs ``BTM`` / ``BTCS``, ``SOL`` vs ``SLGL`` /
  generic "Solana Inc"). Collapsed diagnostics / operator artifact only.
  Surfacing rejections builds operator trust that short-ticker noise was
  handled, not silently swallowed.

Public/diagnostic boundary (plan §Goal):

* ``direct`` and ``related`` are public-eligible.
* ``uncertain`` and ``rejected`` are diagnostics-only: they appear on the
  static watchlist page solely inside a collapsed
  ``<details><summary>진단: 보류/제외된 후보</summary>`` block with source
  titles redacted to source-name + short reason. They never reach
  Telegram or the briefing first viewport.

Pure helpers — no I/O, deterministic given the same matcher output and
config. This module never relaxes a u64 rejection; an explicit u64
rejection reason always wins over a text-only match.

NOTE (u56 invariant): grouping is *observational*. No buy/sell/hold
signal, no position sizing, no P&L. "내 관심 자산 영향" stays a
"what did I see today?" surface.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from investo.briefing.watchlist import (
    WatchlistConfig,
    WatchlistImpact,
    WatchlistImpactStatus,
    WatchlistMatch,
    WatchlistTermKind,
)
from investo.models import NormalizedItem

ImpactGroup = Literal["direct", "related", "uncertain", "rejected"]

# Reason codes for the rejected group. Kept terse + non-PII so they are
# safe to render inside the collapsed public diagnostics block.
RejectReason = Literal[
    "short-ticker-boundary",
    "conflicting-symbol",
    "no-source-evidence",
]

# Short ticker classes whose false positives reviewers flagged (SOL/BTC-
# like). A configured ASCII ticker at or below this length is checked for
# a near-miss "looks like it should have hit but didn't" candidate so the
# rejection is made visible.
_SHORT_TICKER_MAX_LEN: Final[int] = 4

# Reason-prefix → group routing for u64 reason codes that already encode a
# rejection or low-confidence judgement.
_REJECTION_REASON_PREFIXES: Final[tuple[str, ...]] = (
    "reject",
    "false-positive",
    "boundary-fail",
    "conflict",
)

# Cap rejected records so a noisy day cannot balloon the diagnostics block
# / operator artifact. Deterministic ordering keeps the kept subset stable.
_MAX_REJECTED: Final[int] = 25

# An ASCII alphanumeric token regex used to scan item text for near-miss
# short-ticker candidates (e.g. a configured ``BTC`` against a ``BTM`` /
# ``BTCS`` token). Word-boundary anchored exactly like the u64 matcher so
# we never claim a rejection u64 itself would have accepted.
_ASCII_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    """A configured term that *resembled* an item but was suppressed.

    Redaction-safe by construction: stores the configured ``term``
    (user's own), the offending ``token`` it could have been confused
    with, the ``source_name`` (never the full title), and a short
    ``reason`` code. ``title_hash`` is a short stable digest of the item
    title for dedup / operator correlation without leaking the title.
    """

    term: str
    kind: WatchlistTermKind
    token: str
    source_name: str
    reason: RejectReason
    title_hash: str

    def redacted_line(self) -> str:
        """Render a redaction-safe one-line diagnostic.

        Shape: ``BTC ⊘ BTM [short-ticker-boundary] · yahoo-finance-news
        #ab12cd``. No item title, no summary, no URL — only the user's
        own configured term, the offending token, the reason code, the
        source name, and a short title hash.
        """
        return f"{self.term} ⊘ {self.token} [{self.reason}] · {self.source_name} #{self.title_hash}"


@dataclass(frozen=True, slots=True)
class WatchlistImpactCenter:
    """Daily impact center — u64 matches grouped into four buckets."""

    configured: bool
    direct: tuple[WatchlistMatch, ...] = ()
    related: tuple[WatchlistMatch, ...] = ()
    uncertain: tuple[WatchlistMatch, ...] = ()
    rejected: tuple[RejectedCandidate, ...] = ()
    # Carried through from the source impact so renderers can branch on
    # coverage-hold / unconfigured exactly like the legacy surface.
    status: WatchlistImpactStatus = "matched"
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_public_impacts(self) -> bool:
        """True iff a public-eligible (direct/related) impact exists."""
        return bool(self.direct or self.related)

    @property
    def has_diagnostics(self) -> bool:
        """True iff a diagnostics-only (uncertain/rejected) record exists."""
        return bool(self.uncertain or self.rejected)

    def public_matches(self) -> tuple[WatchlistMatch, ...]:
        """Direct first, then related — the public-eligible ordering."""
        return (*self.direct, *self.related)


def _short_title_hash(title: str) -> str:
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:6]


def _classify_match(match: WatchlistMatch) -> ImpactGroup:
    """Map one u64 :class:`WatchlistMatch` to a public/diagnostic group.

    Precedence Direct > Related > Uncertain. An explicit u64 rejection
    reason never reaches here (rejections are not emitted as matches);
    rejected candidates are computed separately in :func:`_reject_*`.
    """
    reason_lower = match.reason.lower()
    # Defensive: if a future u64 build ever emits a rejection-shaped
    # reason as a match, treat it as uncertain (never public).
    if any(reason_lower.startswith(prefix) for prefix in _REJECTION_REASON_PREFIXES):
        return "uncertain"

    if match.confidence == "structured":
        return "direct"
    if match.confidence in ("strict", "alias"):
        # High-confidence asset/ticker hit → Direct. Sector/keyword aliases
        # are relations, not asset hits → Related.
        if match.kind in ("ticker", "asset"):
            return "direct"
        return "related"
    # confidence == "text" — free-text boundary match.
    if match.kind in ("sector", "keyword"):
        # Configured sector/keyword with source evidence (the matched item)
        # → Related when the term is long enough to be a real concept, else
        # Uncertain (ambiguous short token).
        if len(match.term) > _SHORT_TICKER_MAX_LEN or not match.term.isascii():
            return "related"
        return "uncertain"
    # text-confidence ticker/asset hit — these only survive the u64
    # matcher for length>2 ASCII or non-ASCII terms; treat as uncertain
    # because a text hit without structured evidence is the lowest tier
    # for an asset/ticker.
    return "uncertain"


def _ascii_short_tickers(config: WatchlistConfig) -> tuple[tuple[str, WatchlistTermKind], ...]:
    """Configured ASCII ticker/asset terms in the short-ticker noise band."""
    out: list[tuple[str, WatchlistTermKind]] = []
    for kind, terms in (("ticker", config.tickers), ("asset", config.assets)):
        for term in terms:
            if (
                term.isascii()
                and term.replace("-", "").isalnum()
                and len(term) <= _SHORT_TICKER_MAX_LEN
            ):
                out.append((term, kind))  # type: ignore[arg-type]
    return tuple(out)


def _matched_keys(matches: Sequence[WatchlistMatch]) -> set[tuple[str, str, str]]:
    """(term_cf, source_name, title) keys for items that DID match a term."""
    return {(m.term.casefold(), m.item.source_name, m.item.title) for m in matches}


def _detect_rejected(
    items: Sequence[NormalizedItem],
    config: WatchlistConfig,
    accepted: Sequence[WatchlistMatch],
) -> tuple[RejectedCandidate, ...]:
    """Surface short-ticker near-misses u64 correctly suppressed.

    For each configured short ASCII ticker/asset, scan every item's text
    for a token that *starts with* or *contains* the ticker but is not an
    exact boundary match (so u64 did not accept it). The canonical
    examples are ``BTC`` against ``BTM`` / ``BTCS`` and ``SOL`` against
    ``SLGL`` / "Solana Inc"-style references — short, similar tokens that
    a keyword scanner would mis-fire on.

    We only emit a rejection when the term did NOT already produce an
    accepted match for that same item (an explicit u64 acceptance always
    wins). Deterministic ordering + a hard cap keep the output bounded
    and redaction-safe.
    """
    short_terms = _ascii_short_tickers(config)
    if not short_terms:
        return ()
    accepted_keys = _matched_keys(accepted)
    rejected: list[RejectedCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        text = f"{item.title} {item.summary or ''}"
        tokens = _ASCII_TOKEN_RE.findall(text)
        for term, kind in short_terms:
            term_cf = term.casefold()
            if (term_cf, item.source_name, item.title) in accepted_keys:
                # u64 accepted this term for this item — never reject it.
                continue
            offending = _near_miss_token(term_cf, tokens)
            if offending is None:
                continue
            dedupe = (term_cf, item.source_name, offending.casefold())
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rejected.append(
                RejectedCandidate(
                    term=term,
                    kind=kind,
                    token=offending,
                    source_name=item.source_name,
                    reason="short-ticker-boundary",
                    title_hash=_short_title_hash(item.title),
                )
            )
    rejected.sort(
        key=lambda r: (r.term.casefold(), r.token.casefold(), r.source_name, r.title_hash)
    )
    return tuple(rejected[:_MAX_REJECTED])


def _near_miss_token(term_cf: str, tokens: Sequence[str]) -> str | None:
    """Return the first token that resembles ``term_cf`` but is not it.

    Two near-miss classes are recognised (both require sharing the
    leading character and being within a ±2 length band — the short-
    ticker confusion zone — and NOT being an exact match, which u64
    would have accepted as a real hit):

    1. **Shared-prefix family** — the classic ``BTC`` → ``BTCS`` / ``BTM``
       case where the offending token shares ≥2 leading characters with
       the configured ticker.
    2. **Ticker-shaped lookalike** — an ALL-UPPERCASE token (a ticker /
       symbol shape, e.g. ``SLGL`` vs configured ``SOL``) sharing the
       first letter. Restricting class 2 to uppercase tokens keeps
       lowercase prose words (``solana``, ``software``) from flagging
       every same-initial word.

    Returns the original-case token (deterministic: first in scan order).
    """
    for token in tokens:
        tok_cf = token.casefold()
        if tok_cf == term_cf:
            continue
        if tok_cf[:1] != term_cf[:1]:
            continue
        if abs(len(tok_cf) - len(term_cf)) > 2:
            continue
        shared_prefix = _common_prefix_len(tok_cf, term_cf)
        # Class 1 — shared prefix family.
        if shared_prefix >= 2 or (len(term_cf) <= 2 and shared_prefix >= len(term_cf) - 1):
            return token
        # Class 2 — ticker-shaped uppercase lookalike (>=3 chars so single
        # capitals in prose like "S&P" fragments don't flag).
        if token.isupper() and token.isalpha() and len(token) >= 3:
            return token
    return None


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b, strict=False):
        if ca != cb:
            break
        n += 1
    return n


def build_impact_center(
    impact: WatchlistImpact,
    *,
    items: Sequence[NormalizedItem] = (),
    config: WatchlistConfig | None = None,
) -> WatchlistImpactCenter:
    """Group a u64 :class:`WatchlistImpact` into the four impact buckets.

    ``items`` + ``config`` are optional — when both are supplied the
    short-ticker rejection scan runs (it needs the raw item text and the
    configured short tickers). Without them the rejected group is empty
    but direct/related/uncertain grouping still works from the matches
    alone.

    Carries through ``unconfigured`` / ``coverage_hold`` / ``no_match``
    statuses untouched so downstream renderers branch exactly as they did
    on the legacy :class:`WatchlistImpact`.
    """
    if not impact.configured:
        return WatchlistImpactCenter(configured=False, status=impact.status)

    direct: list[WatchlistMatch] = []
    related: list[WatchlistMatch] = []
    uncertain: list[WatchlistMatch] = []
    for match in impact.matches:
        group = _classify_match(match)
        if group == "direct":
            direct.append(match)
        elif group == "related":
            related.append(match)
        else:
            uncertain.append(match)

    rejected: tuple[RejectedCandidate, ...] = ()
    if items and config is not None and config.is_configured:
        rejected = _detect_rejected(items, config, impact.matches)

    return WatchlistImpactCenter(
        configured=True,
        direct=tuple(direct),
        related=tuple(related),
        uncertain=tuple(uncertain),
        rejected=rejected,
        status=impact.status,
    )


def public_impact(center: WatchlistImpactCenter) -> WatchlistImpact:
    """Project a center back to a public-eligible :class:`WatchlistImpact`.

    Contains only Direct + Related matches (Uncertain / Rejected are
    diagnostics-only and never reach a public surface). Reuses the legacy
    :func:`render_watchlist_impact` / Telegram path so the briefing first
    viewport and Telegram one-liner cannot leak diagnostics. Carries
    through non-matched statuses (``unconfigured`` / ``coverage_hold`` /
    ``no_match``) untouched.
    """
    if not center.configured:
        return WatchlistImpact(configured=False, matches=(), status=center.status)
    public = center.public_matches()
    if center.status in ("coverage_hold", "unconfigured"):
        return WatchlistImpact(configured=center.configured, matches=(), status=center.status)
    if not public:
        # No public-eligible impact — present as no_match so the renderer
        # uses the "직접 연결 없음" branch rather than surfacing diagnostics.
        status: WatchlistImpactStatus = (
            center.status if center.status == "default_bundle" else "no_match"
        )
        return WatchlistImpact(configured=True, matches=(), status=status)
    return WatchlistImpact(configured=True, matches=public, status=center.status)


__all__ = [
    "ImpactGroup",
    "RejectReason",
    "RejectedCandidate",
    "WatchlistImpactCenter",
    "build_impact_center",
    "public_impact",
]
