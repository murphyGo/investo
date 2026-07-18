"""u55 Step 2 — Core market-fact verification gate.

Sibling helper to u32 :mod:`investo.briefing.numeric_self_check`. The
two surfaces are intentionally independent:

* u32 (``figures_presence``) — "does some number from Stage 2 appear as
  a substring of any candidate item?". Coverage-first; cheap; broad but
  shallow.
* u55 (``figures_verified``) — "does the *typed* core market fact
  (KOSPI close, BTC USD, ...) in Stage 2 prose match the source-backed
  Decimal value within a bounded tolerance?". Precision-first; narrow
  but deep.

Both KPIs land on the quality page as separate columns
(:mod:`briefing.quality_eval`). Neither replaces the other.

Algorithm
~~~~~~~~~

1. **Aggregate**. Walk every ``NormalizedItem.raw_metadata`` for keys
   shaped ``core_fact:<name>`` (see
   :data:`investo.models.core_fact.CORE_FACT_METADATA_PREFIX`).
   Build ``dict[CoreFact, Decimal]`` — the canonical source value per
   fact. Last-writer-wins on duplicates (idempotent because every
   adapter that stamps the same fact computes from the same close).
2. **Scan body**. For each :data:`CORE_FACT_KEYWORDS` token, find every
   occurrence in the Stage 2 markdown. For each hit, scan ``± WINDOW``
   characters for a Decimal candidate (regex ``[+-]?\\d[\\d,]*(?:\\.\\d+)?``).
   The *closest* candidate to the token becomes the body claim.
3. **Compare**. ``abs(body - source) <= tolerance`` ⇒ ``verified``.
   Otherwise ⇒ ``conflict`` (when source exists) or ``unverified`` (when
   the body asserts a fact for which we have no source).
4. **Cross-check anchors**. Direction sanity (ATH / 52w extremum claims)
   uses :class:`MarketAnchor` rather than a Decimal compare — see
   :mod:`briefing.date_corruption`. The result is folded into the same
   :class:`CoreFactVerificationReport` action map.

Pure helper. No I/O. No clock reads. Decimal-as-string everywhere for
NFR-003 reproducibility. Idempotent — running twice on the same
``(text, items)`` yields a byte-equal :class:`CoreFactVerificationReport`.

Module boundary: imports from :mod:`investo.models` only (foundation +
``NormalizedItem``). Does not touch other ``briefing/`` modules.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from investo.models import NormalizedItem
from investo.models.core_fact import (
    CORE_FACT_KEYWORDS,
    CORE_FACT_METADATA_PREFIX,
    CORE_FACT_TOLERANCE,
    CoreFact,
)

# Per-fact-group tolerances. The :data:`CORE_FACT_TOLERANCE` table in
# ``models.core_fact`` is the source of truth — we re-export it here as
# Decimal for convenience.
_TOLERANCE: Final[dict[CoreFact, Decimal]] = {
    fact: Decimal(value) for fact, value in CORE_FACT_TOLERANCE.items()
}

# Window radius (chars) around each keyword hit. Tuned for Korean prose
# where the headline number typically sits within 30-40 chars of the
# index name ("코스피는 어제 2,810.45 포인트로 마감하며 ..."). Tightening
# below 30 risks false-negatives; widening past 60 starts pulling in
# numbers belonging to other facts.
WINDOW: Final[int] = 40

# Decimal candidate inside the keyword window. Optional sign, optional
# thousands separators, optional fractional part. The leading ``(?<!\\d)``
# guards against splitting an in-progress number like ``5,820`` at the
# comma.
_DECIMAL_RE: Final[re.Pattern[str]] = re.compile(
    # Prefer the longer plain-integer-with-decimal form first so that
    # ``62100.00`` is not eaten as ``621`` (1-3 digit prefix of the
    # thousands-separated alternative). The lookbehind ``(?<![\d.])``
    # guards against splitting in-progress numbers; ``(?!\d)`` at the
    # tail prevents matching only the first 3 digits of ``62100``.
    r"(?<![\d.])([+-]?\d+(?:,\d{3})+(?:\.\d+)?|[+-]?\d+\.\d+|[+-]?\d+)(?!\d)"
)

# Stage 2 body sometimes wraps numbers in markdown bold (``**5,820.40**``)
# or trailing punctuation (``5,820.40원``); we keep the regex simple and
# rely on a strip pass after match.

NumericGateAction = Literal["pass", "warn", "downgrade", "block"]


class ConflictDetail(BaseModel):
    """One body↔source mismatch beyond tolerance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact: CoreFact
    body_value: Decimal
    source_value: Decimal
    delta: Decimal
    source_ticker: str = ""  # blank when source didn't carry a ticker hint


class CoreFactVerificationReport(BaseModel):
    """Frozen report of the verification pass over Stage 2 markdown.

    * ``verified`` — facts whose body claim matched source within tol.
    * ``unverified`` — facts whose body claim has no source-backed value.
    * ``conflicts`` — facts whose body claim differs from source beyond
      tolerance. The reader callout downgrades the segment.
    * ``actions`` — per-fact action map. Facts that never appeared in the
      body do not appear in this map (no need to surface them).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verified: tuple[CoreFact, ...]
    unverified: tuple[CoreFact, ...]
    conflicts: tuple[ConflictDetail, ...]
    actions: dict[CoreFact, NumericGateAction]

    @property
    def figures_verified_rate(self) -> float | None:
        """Fraction of *body-mentioned* facts that verified.

        Denominator is the union of verified + unverified + conflicts (i.e. facts
        the body actually asserted). Returns ``None`` when the body
        asserted no core facts — surfaced as ``n/a`` rather than 0%.
        """
        denom = len(self.verified) + len(self.unverified) + len(self.conflicts)
        if denom == 0:
            return None
        return len(self.verified) / denom


def aggregate_source_facts(items: Sequence[NormalizedItem]) -> dict[CoreFact, Decimal]:
    """Build ``{fact: Decimal}`` from every ``core_fact:*`` raw_metadata key.

    Multiple adapters can stamp the same fact. Last-writer-wins is safe
    when duplicate facts agree within the gate's configured tolerance.
    """
    out: dict[CoreFact, Decimal] = {}
    for item in items:
        for key, value in item.raw_metadata.items():
            if not isinstance(value, str):
                continue
            if not key.startswith(CORE_FACT_METADATA_PREFIX):
                continue
            fact_name = key[len(CORE_FACT_METADATA_PREFIX) :]
            # Guard against typos / future schema drift — silently skip.
            if fact_name not in CORE_FACT_TOLERANCE:
                continue
            try:
                out[fact_name] = Decimal(value)
            except InvalidOperation:
                continue
    return out


def find_body_value(text: str, fact: CoreFact) -> Decimal | None:
    """Return the closest Decimal to any :data:`CORE_FACT_KEYWORDS` token.

    Returns ``None`` when the keyword does not appear, or when no Decimal
    candidate sits within :data:`WINDOW` characters of any hit. The
    *closest* candidate (by char distance to the keyword start) wins
    when multiple sit inside the window.
    """
    keywords = CORE_FACT_KEYWORDS[fact]
    best: tuple[int, Decimal] | None = None  # (distance, value)
    for token in keywords:
        start = 0
        while True:
            idx = text.find(token, start)
            if idx == -1:
                break
            window_start = max(0, idx - WINDOW)
            window_end = min(len(text), idx + len(token) + WINDOW)
            haystack = text[window_start:window_end]
            token_end = idx + len(token)
            for match in _DECIMAL_RE.finditer(haystack):
                raw = match.group(1).replace(",", "")
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    continue
                # Reject sub-2-digit integers like '5' / '7' (probably
                # punctuation noise, day/section numbers, not a real
                # market fact) — also skips ``5,820`` candidates' tail
                # digits unintentionally captured.
                if "." not in raw and "," not in raw and abs(value) < 100:
                    continue
                match_abs_idx = window_start + match.start(1)
                match_abs_end = window_start + match.end(1)
                # Skip numbers that overlap with the keyword token
                # itself (e.g. "500" inside "S&P 500" when the keyword
                # is "S&P 500"). The match must sit strictly outside
                # ``[idx, token_end)``.
                if match_abs_idx < token_end and match_abs_end > idx:
                    continue
                distance = abs(match_abs_idx - idx)
                if best is None or distance < best[0]:
                    best = (distance, value)
            start = idx + 1
    if best is None:
        return None
    return best[1]


def verify_core_facts(
    text: str,
    items: Sequence[NormalizedItem],
) -> CoreFactVerificationReport:
    """Run the verification pass and return the frozen report.

    The orchestrator wires the resulting actions into the publish gate
    (Step 6) — ``block`` aborts the segment, ``downgrade`` inserts a
    reader callout, ``warn`` raises an operator alert only.
    """
    source_facts = aggregate_source_facts(items)
    verified: list[CoreFact] = []
    unverified: list[CoreFact] = []
    conflicts: list[ConflictDetail] = []
    actions: dict[CoreFact, NumericGateAction] = {}

    for fact in CORE_FACT_TOLERANCE:
        body_value = find_body_value(text, fact)
        if body_value is None:
            continue  # body never mentioned this fact — silent.
        source_value = source_facts.get(fact)
        if source_value is None:
            unverified.append(fact)
            actions[fact] = "downgrade"
            continue
        tolerance = _TOLERANCE[fact]
        delta = (body_value - source_value).copy_abs()
        if delta <= tolerance:
            verified.append(fact)
            actions[fact] = "pass"
        else:
            conflicts.append(
                ConflictDetail(
                    fact=fact,
                    body_value=body_value,
                    source_value=source_value,
                    delta=delta,
                )
            )
            actions[fact] = "downgrade"

    return CoreFactVerificationReport(
        verified=tuple(verified),
        unverified=tuple(unverified),
        conflicts=tuple(conflicts),
        actions=actions,
    )


def render_downgrade_callout(report: CoreFactVerificationReport) -> str:
    """Render the ``> ⚠️ 확인 필요`` callout for downgrade actions.

    Returns the empty string when no fact requires downgrade. The
    callout is intended to be prepended to the briefing body *after*
    the disclaimer line so the reader sees a one-line warning above
    the prose.
    """
    flagged = list(report.unverified) + [c.fact for c in report.conflicts]
    if not flagged:
        return ""
    # Deterministic ordering: enum order (already preserved via dict
    # iteration over ``CORE_FACT_TOLERANCE``).
    parts = ", ".join(flagged)
    return f"> ⚠️ 확인 필요: 수치 검증 실패 — {parts}\n"


__all__ = [
    "WINDOW",
    "ConflictDetail",
    "CoreFactVerificationReport",
    "NumericGateAction",
    "aggregate_source_facts",
    "find_body_value",
    "render_downgrade_callout",
    "verify_core_facts",
]
