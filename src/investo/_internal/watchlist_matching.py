"""Pure watchlist term-matching primitives shared by briefing and visuals."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, Literal

from investo.models.items import NormalizedItem
from investo.models.watchlist import WatchlistTermKind

_SHORT_TICKER_THRESHOLD: Final[int] = 2
_HANGUL_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")


def match_term_with_aliases(
    *,
    term: str,
    kind: WatchlistTermKind,
    aliases: Mapping[str, tuple[str, ...]],
    item: NormalizedItem,
    text_cf: str,
    text_raw: str,
    exact_only: bool,
) -> tuple[str | None, str | None, Literal["structured", "strict", "alias", "text"], str]:
    """Return ``(term, alias)`` if matched; ``alias`` is non-None only for alias hits."""
    if matches_structured_term(term, item):
        return term, None, "structured", "structured-symbol"
    if matches_term(term, kind=kind, text_cf=text_cf, text_raw=text_raw, exact_only=exact_only):
        confidence: Literal["structured", "strict", "alias", "text"] = (
            "strict" if kind in {"ticker", "asset"} and term.isascii() else "text"
        )
        return term, None, confidence, "boundary-term"
    if exact_only:
        return None, None, "text", "no-match"
    canonical_key = term.upper() if term.isascii() else term
    alt_forms = aliases.get(canonical_key, ())
    for alt in alt_forms:
        if matches_term(alt, kind=kind, text_cf=text_cf, text_raw=text_raw, exact_only=False):
            return term, alt, "alias", f"alias:{alt}"
    return None, None, "text", "no-match"


def matches_structured_term(term: str, item: NormalizedItem) -> bool:
    """Match against structured symbol metadata before free text."""
    if not term:
        return False
    wanted = term.casefold()
    keys = ("ticker", "symbol", "asset", "base_asset", "coin", "slug")
    for key in keys:
        raw = item.raw_metadata.get(key)
        if not isinstance(raw, str):
            continue
        candidates = {raw.casefold()}
        if raw.endswith("-USD"):
            candidates.add(raw.removesuffix("-USD").casefold())
        if raw.endswith("USDT"):
            candidates.add(raw.removesuffix("USDT").casefold())
        if wanted in candidates:
            return True
    return False


def matches_term(
    term: str,
    *,
    kind: WatchlistTermKind,
    text_cf: str,
    text_raw: str,
    exact_only: bool,
) -> bool:
    """Check ``term`` against an item's text with watchlist boundary heuristics."""
    if not term:
        return False
    normalized = term.casefold()

    if exact_only:
        return any(token.strip(".,!?;:()[]{}") == normalized for token in text_cf.split())

    if term.isascii() and term.replace("-", "").isalnum():
        if len(term) <= _SHORT_TICKER_THRESHOLD and kind in {"ticker", "asset"}:
            return matches_short_ticker(term, text_raw)
        pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])"
        return re.search(pattern, text_cf) is not None

    return matches_korean_term(normalized, text_cf)


def matches_short_ticker(term: str, text_raw: str) -> bool:
    """Strict original-case boundary match for 1-2 character ASCII tickers."""
    pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
    return re.search(pattern, text_raw) is not None


def matches_korean_term(term_cf: str, text_cf: str) -> bool:
    """Substring match with Hangul-syllable word-boundary heuristic."""
    if not term_cf:
        return False
    start = 0
    term_len = len(term_cf)
    while True:
        idx = text_cf.find(term_cf, start)
        if idx < 0:
            return False
        before_ok = idx == 0 or not _HANGUL_CHAR_RE.match(text_cf[idx - 1])
        after_idx = idx + term_len
        after_ok = after_idx >= len(text_cf) or not _HANGUL_CHAR_RE.match(text_cf[after_idx])
        if before_ok and after_ok:
            return True
        start = idx + 1


__all__ = [
    "match_term_with_aliases",
    "matches_korean_term",
    "matches_short_ticker",
    "matches_structured_term",
    "matches_term",
]
