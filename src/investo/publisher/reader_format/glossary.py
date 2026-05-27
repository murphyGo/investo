"""Glossing dedupe pass (``base(풀어쓰기)``).

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

# Match a glossing pattern: ``base(풀어쓰기)`` where:
#   - ``base`` is 1-30 chars of Korean / Latin / digits / common punctuation
#     (``&``, ``.``, space). Trailing whitespace before the paren is OK.
#   - The parenthetical is 1-40 chars, no nested parens, no newlines.
# Excluded by construction:
#   - URLs (``https://...``) — they contain ``://`` which is not in the
#     base char class.
#   - Markdown image alt-text (``![alt](url)``) — the leading ``!`` /
#     ``[`` is not in the base char class.
# Characters considered part of a "term" — Korean (가-힣), Latin, digits,
# and the two punctuation chars that often appear inside acronyms ("&" in
# "S&P", "." in "U.S."). Anything else (whitespace, period+space, comma,
# parenthesis, hangul jamo) terminates the term.
_TERM_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣A-Za-z0-9&\.]")
_GLOSS_PAREN_RE: Final[re.Pattern[str]] = re.compile(r"\(([^()\n]{1,40})\)")


def dedupe_glossings(text: str) -> str:
    """Keep the first ``base(풀어쓰기)`` occurrence, strip later glosses.

    Strategy: scan parenthetical groups (the *gloss*), then walk backward
    from each open paren to find the immediately-preceding term — the
    contiguous run of term chars (optionally with internal single spaces
    bridging acronym-shaped sub-tokens like ``S&P 500``). When that base
    has been seen earlier in the document, the parenthetical (and the
    optional single space before it) is stripped.
    """
    seen: set[str] = set()
    out: list[str] = []
    cursor = 0
    for match in _GLOSS_PAREN_RE.finditer(text):
        open_paren = match.start()
        # Walk backward to find the base — but stop at the closest
        # *previous* gloss's close-paren so two adjacent glossings like
        # ``A(가) B(나)`` don't bleed across.
        prior_close = text.rfind(")", cursor, open_paren)
        scan_floor = prior_close + 1 if prior_close >= cursor else cursor
        base = _extract_base(text, open_paren, scan_floor)
        if base is None or len(base) < 2:
            # No base / too-short — emit as-is, keep cursor at the
            # match.end so we don't re-scan the same paren.
            out.append(text[cursor : match.end()])
            cursor = match.end()
            continue
        base_norm = base
        if base_norm in seen:
            # Strip the gloss. Also strip the single optional space
            # between base and ``(`` if it exists.
            base_end_in_text = open_paren  # the ``(`` index
            # Was there a space? base_end_in_text - len(base) gives the
            # base-start; the char at base_end_in_text-1 is either part
            # of the base (no space) or the space we want to drop.
            base_start = base_end_in_text - len(base)
            if base_start > 0 and text[base_start - 1] == " ":
                # There was a space before the base — keep it.
                pass
            # Emit everything from cursor up to the end of the base,
            # skipping the gloss.
            out.append(text[cursor:base_end_in_text])
            cursor = match.end()
            continue
        seen.add(base_norm)
        out.append(text[cursor : match.end()])
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


def _extract_base(text: str, open_paren: int, floor: int) -> str | None:
    """Walk backward from ``open_paren`` to capture the preceding base term.

    Tokens are runs of term chars (see :data:`_TERM_CHAR_RE`); two tokens
    may be bridged by a single internal space — but only up to 3 such
    bridges (so a base like ``Federal Open Market Committee`` resolves
    while a sentence-long base does not). The walk stops at ``floor``
    (typically the close-paren of a preceding glossing).
    """
    i = open_paren
    # Optional single space immediately before the paren.
    if i > floor and text[i - 1] == " ":
        i -= 1
    end = i
    tokens_walked = 0
    while end > floor:
        # Collect one token.
        token_end = end
        while end > floor and _TERM_CHAR_RE.match(text[end - 1]):
            end -= 1
        if token_end == end:
            # No term chars at all — give up.
            return None
        tokens_walked += 1
        # Try to bridge a single space + next token, up to 3 times total.
        # If the char immediately before the bridge space is a `.`, that
        # signals a sentence break (e.g. "상승. S&P 500"), NOT an in-term
        # separator — stop here so the base doesn't swallow the prior
        # sentence. We accept the rare false negative for acronym phrases
        # like "U.S. dollar" (the reader will see a fully-glossed first
        # occurrence anyway).
        if (
            tokens_walked < 4
            and end > floor + 1
            and text[end - 1] == " "
            and _TERM_CHAR_RE.match(text[end - 2])
            and text[end - 2] != "."
        ):
            end -= 1  # consume the bridge space
            continue
        break
    base_start = end
    base_end = open_paren
    # Trim trailing space.
    if base_end > base_start and text[base_end - 1] == " ":
        base_end -= 1
    if base_start >= base_end:
        return None
    base = text[base_start:base_end]
    # Strip leading sentence-punctuation that snuck in via the '.' allowance.
    base = base.lstrip(".")
    return base if base else None
