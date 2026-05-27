"""u76 plain-language "그래서 의미는?" section meaning-line pass.

Move-only extraction from the pre-split ``reader_format`` module (u81).

Problem (2026-05-24 beginner/non-expert Korean reader review): sections
§②-§⑤ can be technically correct yet list macro data / tickers / source
names / jargon without saying *why the fact matters*. The reader's
question is "그래서 의미는?".

u76 adds ONE short plain-Korean meaning line per eligible section that
answers that question. It is NOT a glossary (u40) and NOT a carryover
surface (u68) — those mechanics are untouched. It is an *implication*
prose layer only.

Meaning-line contract (fixed):
  * Exact marker:  ``> **그래서 의미는?** `` (blockquote callout).
  * Placement: immediately after the first paragraph/table block of each
    eligible section §②-§⑤, before the next H3/H2.
  * Limit: one meaning line per section; max 80 Korean-visible chars
    after the marker.
  * Idempotency: a rerun REPLACES the existing meaning line in the same
    section instead of appending a second one.
  * Data-limited fallback text when section evidence is weak.

The *content* of the meaning line is produced by the Stage-2 prompt
(briefing-side; observational wording, no buy/sell/target). This module
owns the deterministic validation/repair: it bounds line length, dedupes
to one line per section, and — when the LLM omitted the line entirely —
leaves the section untouched rather than fabricating an implication
(an empty/weak section gets no invented meaning). Compliance is scanned
downstream by ``scan_compliance`` over the full markdown AFTER this pass.
"""

from __future__ import annotations

import re
from typing import Final

from investo.publisher.reader_format._constants import (
    _SECTION_HEADER_RE,
    MEANING_MARKER,
    MEANING_MAX_CHARS,
    _logger,
)

# Section markers eligible for a meaning line (§②-§⑤).
_MEANING_SECTION_MARKERS: Final[tuple[str, ...]] = ("②", "③", "④", "⑤")

# Match a meaning-line callout (marker + body) on its own line.
_MEANING_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*그래서 의미는\?\*\*\s*(?P<body>[^\n]*)$",
    re.MULTILINE,
)
# Truncation boundary characters (whitespace + sentence/clause punctuation).
_MEANING_BOUNDARY_CHARS: Final[str] = " \t,.;:!?·…—)]」』"


def _bound_meaning_body(body: str) -> str:
    """Bound a meaning-line body to ``MEANING_MAX_CHARS`` at a word boundary.

    Idempotent: a body already within the cap is returned unchanged. When
    the body is too long, it is cut at the last boundary char before the
    cap and suffixed with ``...``. If no boundary exists, a hard cut at the
    cap is used (the line is still a complete, compliance-scannable string).
    """
    stripped = body.strip()
    if len(stripped) <= MEANING_MAX_CHARS:
        return stripped
    window = stripped[:MEANING_MAX_CHARS]
    cut = max(window.rfind(ch) for ch in _MEANING_BOUNDARY_CHARS)
    head = window.rstrip() if cut <= 0 else window[:cut].rstrip(_MEANING_BOUNDARY_CHARS).rstrip()
    if not head:
        head = window.rstrip()
    return f"{head}..."


def normalize_meaning_lines(text: str, *, segment: str | None = None) -> str:
    """Validate/repair the u76 ``그래서 의미는?`` meaning lines.

    Deterministic ``str -> str`` pass over already-generated Stage-2
    markdown. For each eligible section §②-§⑤ this:

      1. Keeps at most ONE meaning line (the first), dropping any
         duplicates the LLM emitted in the same section (idempotency +
         "one per section").
      2. Bounds the kept line's body to ``MEANING_MAX_CHARS`` at a word
         boundary.

    It does NOT fabricate a meaning line for a section that has none — an
    omitted line stays omitted (empty/weak sections get no invented
    implication; the data-limited fallback is the LLM's job per the prompt
    contract). It does NOT touch glossary (u40) or carryover (u68)
    callouts, nor the TL;DR block — the marker is unique to u76.

    Idempotent: a second pass over already-normalized text is a no-op.
    """
    headers = list(_SECTION_HEADER_RE.finditer(text))
    if not headers:
        return text
    # Build (start, end) body spans per section, in source order.
    spans: list[tuple[int, int, bool]] = []
    for idx, match in enumerate(headers):
        header = match.group("header")
        eligible = any(marker in header for marker in _MEANING_SECTION_MARKERS)
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        spans.append((start, end, eligible))

    # Rebuild the document section-by-section so offsets stay valid. Each
    # iteration emits the verbatim header line (``text[cursor:start]``) and
    # then the (possibly repaired) section body — so header text is never
    # dropped (a non-§②-§⑤ ``##`` heading like ``## Watchlist Carryover``
    # stays byte-identical, AC-76.4).
    out: list[str] = [text[: spans[0][0]]] if spans else [text]
    cursor = spans[0][0] if spans else 0
    for start, end, eligible in spans:
        out.append(text[cursor:start])  # header line text (verbatim)
        body = text[start:end]
        if eligible:
            body = _repair_section_meaning(body, segment=segment)
        out.append(body)
        cursor = end
    return "".join(out)


def _repair_section_meaning(body: str, *, segment: str | None) -> str:
    matches = list(_MEANING_LINE_RE.finditer(body))
    if not matches:
        return body
    first = matches[0]
    bounded = _bound_meaning_body(first.group("body"))
    repaired_line = f"{MEANING_MARKER}{bounded}".rstrip()

    # Replace the first occurrence with the bounded line; drop the rest.
    result: list[str] = [body[: first.start()], repaired_line]
    cursor = first.end()
    for extra in matches[1:]:
        # Keep prose between the previous match end and this duplicate, but
        # drop the duplicate meaning line itself.
        result.append(body[cursor : extra.start()].rstrip("\n"))
        cursor = extra.end()
    result.append(body[cursor:])
    if len(matches) > 1:
        _logger.warning(
            "reader_format.meaning_duplicate_dropped",
            extra={"segment": segment, "count": len(matches) - 1},
        )
    return "".join(result)
