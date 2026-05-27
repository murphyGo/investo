"""u54 — Citation-cardinality WARN (Finding #4, AC-6).

When a single source URL is attributed to ≥ ``N=3`` distinct
ticker/entity claims in a single segment briefing, this module emits
a structured WARNING log and exposes the count for the trace table.

The check is *non-blocking* — it surfaces a flag, not a gate. The
WARN extra carries an ``url_hash`` (sha1[:12]) rather than the full
URL so the log line is free of secret-shape risk (R13) even when an
upstream URL embeds tokens.

Threshold N=3 matches the persona evidence: subagent #4 flagged a
single 연합뉴스 URL attributed to 5 distinct ticker/entity claims in
the domestic 2026-05-11 briefing as the canonical over-attribution
pattern. The threshold is a frozen module constant; tuning happens
here, not at call sites.

Pure function — no I/O, no external state. The orchestrator passes
the briefing text + the citation list (URL strings) and receives a
``url → count`` mapping plus a sequence of WARN events ready to emit.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from investo.briefing._text.patterns import (
    CRYPTO_TICKER as _CRYPTO_TICKER,
)
from investo.briefing._text.patterns import (
    KOREAN_EXCHANGE_TICKER as _KOREAN_EXCHANGE_TICKER,
)
from investo.briefing._text.patterns import (
    US_TICKER as _US_TICKER,
)

_logger = logging.getLogger(__name__)

# Threshold for the WARN signal. Frozen — tune here, not at the call
# site. Co-located with the helper to keep the policy auditable.
CARDINALITY_THRESHOLD: Final[int] = 3

# u79 — ticker regexes now single-sourced in
# :mod:`investo.briefing._text.patterns`; imported above under the
# historic local aliases so the call sites below are unchanged.


@dataclass(frozen=True, slots=True)
class CardinalityWarning:
    """One over-attribution event ready for logging / trace surfacing.

    ``url_hash`` is sha1[:12] of the URL — the raw URL never appears
    on this dataclass so a leak guard scan of the trace surface
    cannot accidentally emit secret-shaped substrings.
    """

    url_hash: str
    claim_count: int
    segment: str


def hash_url(url: str) -> str:
    """Public sha1[:12] hash used in the WARN extra payload."""
    return hashlib.sha1(url.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def count_claims_per_link(
    briefing_text: str,
    citations: Sequence[str],
    *,
    extra_terms: Iterable[str] = (),
) -> dict[str, int]:
    """Return ``{url → number of distinct entity claims}``.

    A *claim entity* is one of:

    * a Korean exchange-ticker token matched by :data:`_KOREAN_EXCHANGE_TICKER`
    * a US ticker from the curated list
    * a crypto ticker (BTC / ETH / SOL)
    * any string in ``extra_terms`` (e.g. user-watchlist Korean
      종목명) — used by the orchestrator to pass in the watchlist
      vocabulary at call time so this helper stays I/O-free.

    For each ``url`` in ``citations`` (dedup-preserving), the count is
    the size of the distinct-entity set that appears on the same
    *line* as the URL in ``briefing_text``. Same-line co-occurrence
    is the strictest possible proxy for "this URL was cited *to
    support* these entity claims" without parsing the body's
    markdown structure.

    Generic country / Fed / FOMC keywords are intentionally *not*
    treated as claim entities — see Open Question #5 in the plan.
    Promotion to a richer vocabulary is a follow-up.
    """
    extra_set = {term for term in extra_terms if term}
    counts: dict[str, int] = {}
    lines = briefing_text.splitlines()
    for raw_url in citations:
        url = raw_url.strip()
        if not url or url in counts:
            continue
        entities: set[str] = set()
        for line in lines:
            if url not in line:
                continue
            entities.update(match.group(0) for match in _KOREAN_EXCHANGE_TICKER.finditer(line))
            entities.update(match.group(0) for match in _US_TICKER.finditer(line))
            entities.update(match.group(0) for match in _CRYPTO_TICKER.finditer(line))
            for term in extra_set:
                if term in line:
                    entities.add(term)
        counts[url] = len(entities)
    return counts


def detect_cardinality_warnings(
    briefing_text: str,
    citations: Sequence[str],
    *,
    segment: str,
    extra_terms: Iterable[str] = (),
    threshold: int = CARDINALITY_THRESHOLD,
) -> tuple[CardinalityWarning, ...]:
    """u54 AC-6 — Emit WARN events for URLs at or above the threshold.

    Logs each event at WARNING level under
    ``reader.citation_cardinality_exceeded`` with structured ``extra``
    carrying only ``url_hash`` (sha1[:12]), ``claim_count``, and
    ``segment``. The raw URL is never logged — R13 secret hygiene.

    Returns the ordered tuple of warnings so the caller can render
    them into the trace table without re-emitting the log line.
    """
    counts = count_claims_per_link(briefing_text, citations, extra_terms=extra_terms)
    warnings: list[CardinalityWarning] = []
    for url, count in counts.items():
        if count < threshold:
            continue
        url_hash = hash_url(url)
        warning = CardinalityWarning(url_hash=url_hash, claim_count=count, segment=segment)
        warnings.append(warning)
        _logger.warning(
            "reader.citation_cardinality_exceeded url_hash=%s claim_count=%d segment=%s",
            url_hash,
            count,
            segment,
            extra={
                "event": "reader.citation_cardinality_exceeded",
                "url_hash": url_hash,
                "claim_count": count,
                "segment": segment,
            },
        )
    return tuple(warnings)


__all__ = [
    "CARDINALITY_THRESHOLD",
    "CardinalityWarning",
    "count_claims_per_link",
    "detect_cardinality_warnings",
    "hash_url",
]
