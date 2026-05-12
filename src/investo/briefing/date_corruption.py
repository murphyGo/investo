"""u55 Step 3 — Date corruption + direction sanity gates.

Two unrelated-looking checks share this module because they both run
on the post-LLM Stage 2 markdown as cheap regex-and-anchor passes
before publish.

Why u51 ``reader_format.wrap_numbers_bold`` does not catch this:

* u51 operates *post-format*: it wraps decimal-with-percent (``+0.85%``)
  and currency-prefixed (``$5,820``) tokens in markdown bold for reader
  emphasis. Its regex deliberately ignores slash-delimited date tokens
  (``5/65/7``) because those land inside section headings where bold
  would conflict with markdown header syntax.
* This unit's gate runs *immediately before* the publish call as a
  separate pass. ``find_corrupt_date_tokens`` is a producer of
  :class:`CorruptDate` results, not a text transformer.

Module boundary: foundation under ``briefing/`` consumed by
``orchestrator/pipeline.py``. Imports only :mod:`investo.briefing.market_anchor`
(sibling within the same unit, for direction-sanity cross-check).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from investo.briefing.market_anchor import MarketAnchor

# Slash-delimited date tokens. The leading ``(?<!\\d)`` guard prevents
# splitting in-progress numbers like ``2026/05/11`` where the leading
# ``2026`` is a year (handled below by length check). Matches:
#
# * ``5/11``      → MM/DD (2 groups)
# * ``05/11/26``  → MM/DD/YY (3 groups)
# * ``5/65/7``    → corrupt (day = 65 invalid)
_SLASH_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{1,2}))?(?![\d/])"
)

# Markdown code-fence detector — corrupt tokens *inside* fenced code
# blocks are operator-supplied examples (e.g. cron strings ``0 7 * * 1-5``)
# and must be ignored by this gate.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"```.*?```", re.DOTALL)


class CorruptDate(BaseModel):
    """One detected corruption in the post-LLM markdown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: str
    reason: Literal["month_out_of_range", "day_out_of_range", "all_zero", "duplicate_segment"]
    position: int  # char offset into the *stripped* text


class DirectionConflict(BaseModel):
    """One body↔anchor direction mismatch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    body_claim: Literal["bullish", "bearish", "ath", "fiftytwoweek_high"]
    anchor_pct: Decimal | None
    anchor_is_ath: bool


# --- Date corruption ------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Replace fenced code blocks with same-length whitespace.

    Preserves character offsets so the caller can still locate the hit
    in the original input if needed.
    """

    def _blank(match: re.Match[str]) -> str:
        return " " * (match.end() - match.start())

    return _CODE_FENCE_RE.sub(_blank, text)


def find_corrupt_date_tokens(text: str) -> tuple[CorruptDate, ...]:
    """Return the deterministic ordered tuple of corrupt slash-date hits.

    Detection rules:

    * ``month > 12``                  → ``month_out_of_range``
    * ``day > 31``                    → ``day_out_of_range``
    * ``0/0`` / ``0/0/0``             → ``all_zero``
    * ``5/65/7`` (3-segment + any seg invalid) → reason is the *first*
      failure encountered.
    * Duplicate-segment case ``5/5/5`` is NOT flagged (a valid May 5
      with 2-digit year is conceivable in operator notes).
    """
    stripped = _strip_code_fences(text)
    out: list[CorruptDate] = []
    for match in _SLASH_DATE_RE.finditer(stripped):
        try:
            month = int(match.group(1))
            day = int(match.group(2))
            year_segment = int(match.group(3)) if match.group(3) else None
        except ValueError:
            continue
        if month == 0 and day == 0 and (year_segment is None or year_segment == 0):
            out.append(CorruptDate(raw=match.group(0), reason="all_zero", position=match.start()))
            continue
        if month > 12:
            out.append(
                CorruptDate(
                    raw=match.group(0),
                    reason="month_out_of_range",
                    position=match.start(),
                )
            )
            continue
        if day > 31:
            out.append(
                CorruptDate(raw=match.group(0), reason="day_out_of_range", position=match.start())
            )
            continue
    return tuple(out)


# --- Direction sanity -----------------------------------------------------

# Token catalog the body uses for direction claims. Korean prose is the
# expected input; mixed-language is also covered.
_BULLISH_TOKENS: Final[tuple[str, ...]] = (
    "[강세]",
    "[상승 관찰]",
    "상승 마감",
    "상승마감",
    "강세 마감",
)
_BEARISH_TOKENS: Final[tuple[str, ...]] = (
    "[약세]",
    "[하락 관찰]",
    "하락 마감",
    "하락마감",
    "약세 마감",
)
_ATH_TOKENS: Final[tuple[str, ...]] = (
    "ATH 갱신",
    "ATH 경신",
    "역대 최고",
    "사상 최고",
)
_FIFTYTWO_HIGH_TOKENS: Final[tuple[str, ...]] = (
    "52주 최고",
    "52주 신고가",
    "52w high",
    "52w 신고가",
)


def _anchor_for_segment(
    anchors: Sequence[MarketAnchor], segment_tickers: tuple[str, ...]
) -> MarketAnchor | None:
    """Pick the headline anchor for the segment, in priority order."""
    by_ticker = {a.ticker: a for a in anchors}
    for ticker in segment_tickers:
        if ticker in by_ticker:
            return by_ticker[ticker]
    return None


def verify_direction_against_anchor(
    text: str,
    anchors: Sequence[MarketAnchor],
    *,
    segment_priority: tuple[str, ...] = ("^GSPC", "^IXIC", "^DJI"),
) -> tuple[DirectionConflict, ...]:
    """Cross-check direction claims in ``text`` against ``anchors``.

    The check is segment-scoped: the caller supplies the priority list
    (US-equity defaults). For each direction claim found in the body,
    the headline anchor for the segment is fetched; if the anchor
    contradicts the claim, a :class:`DirectionConflict` lands.

    ATH / 52w-high tokens cross-check against ``MarketAnchor.is_ath``
    and ``pct_from_52w_high`` respectively.
    """
    anchor = _anchor_for_segment(anchors, segment_priority)
    if anchor is None:
        return ()

    out: list[DirectionConflict] = []
    has_bullish_claim = any(token in text for token in _BULLISH_TOKENS)
    has_bearish_claim = any(token in text for token in _BEARISH_TOKENS)
    has_ath_claim = any(token in text for token in _ATH_TOKENS)
    has_52w_high_claim = any(token in text for token in _FIFTYTWO_HIGH_TOKENS)

    pct = anchor.pct
    if has_bullish_claim and pct is not None and pct < 0:
        out.append(
            DirectionConflict(
                ticker=anchor.ticker,
                body_claim="bullish",
                anchor_pct=pct,
                anchor_is_ath=anchor.is_ath,
            )
        )
    if has_bearish_claim and pct is not None and pct > 0:
        out.append(
            DirectionConflict(
                ticker=anchor.ticker,
                body_claim="bearish",
                anchor_pct=pct,
                anchor_is_ath=anchor.is_ath,
            )
        )
    if has_ath_claim and not anchor.is_ath:
        out.append(
            DirectionConflict(
                ticker=anchor.ticker,
                body_claim="ath",
                anchor_pct=pct,
                anchor_is_ath=anchor.is_ath,
            )
        )
    # 52w high claim requires close ≈ 52w high (within 0.5%).
    if (
        has_52w_high_claim
        and anchor.pct_from_52w_high is not None
        and anchor.pct_from_52w_high < Decimal("-0.5")
    ):
        out.append(
            DirectionConflict(
                ticker=anchor.ticker,
                body_claim="fiftytwoweek_high",
                anchor_pct=anchor.pct_from_52w_high,
                anchor_is_ath=anchor.is_ath,
            )
        )
    return tuple(out)


__all__ = [
    "CorruptDate",
    "DirectionConflict",
    "find_corrupt_date_tokens",
    "verify_direction_against_anchor",
]
