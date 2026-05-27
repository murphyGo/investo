"""Number bold-wrap pass.

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

from investo.publisher.reader_format._constants import _TABLE_ROW_RE

# Numeric token shapes we wrap:
#   - signed percentages: ``+11.51%``, ``-0.96%`` (decimal required so the
#     pure-integer-percent case is captured by the next pattern).
#   - bare-percent decimals: ``4.42%``, ``0.47pp`` is NOT included — pp /
#     bps remain plain (they're already conventionally small and reading
#     them as bold creates visual noise).
#   - dollar amounts with optional decimals: ``$81,154.06``, ``$1,234``.
# Negative lookarounds:
#   - ``(?<!\*)`` / ``(?!\*)`` — already-wrapped tokens stay untouched
#     (idempotent).
#   - ``(?<![\w.])`` / ``(?![\w.])`` for the percent forms — avoids matching
#     the percent at the tail of a URL slug or a sub-token of a larger word.
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\*)"
    r"(?P<token>"
    r"[+\-]\d+(?:\.\d+)?%"  # signed percentage
    r"|\$\d{1,3}(?:,\d{3})*(?:\.\d+)?"  # dollar with thousands
    r"|\$\d+(?:\.\d+)?"  # plain dollar (no thousands)
    r"|\b\d+\.\d+%"  # bare decimal percent
    r")"
    r"(?!\*)"
)

# Lines that must NOT be touched:
#   - ``|...|`` markdown table rows (we don't want to bold inside cells —
#     the table itself is the bolding mechanism).
#   - lines inside triple-backtick fences (state machine in ``wrap_numbers_bold``).
_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*```")
# A markdown link's URL (``[text](https://...)``) must also be exempt —
# pre-strip the URL by replacing it with a placeholder of equal length so
# token offsets are preserved during the regex pass.
_LINK_URL_RE: Final[re.Pattern[str]] = re.compile(r"(\]\()([^)]+)(\))")


def wrap_numbers_bold(text: str) -> str:
    """Add ``**...**`` around plain numeric tokens in body prose.

    Skipped contexts:
      * fenced code blocks (``\\`\\`\\`...\\`\\`\\```` runs),
      * markdown table rows (``|...|``),
      * already-bold tokens (the regex's negative lookarounds),
      * the URL part of markdown links (pre-redacted so the regex never
        sees those characters).
    """
    out_lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=False):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        if _TABLE_ROW_RE.match(line):
            out_lines.append(line)
            continue
        out_lines.append(_wrap_line(line))
    # Preserve trailing newline if the original had one.
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(out_lines) + trailing


def _wrap_line(line: str) -> str:
    # Pre-split on link URL spans so the number regex never sees the
    # href contents. Each odd-indexed piece is an URL — we re-insert it
    # verbatim and only run the wrap on prose (even indices).
    pieces: list[str] = []
    cursor = 0
    for match in _LINK_URL_RE.finditer(line):
        url_start = match.start(2)
        url_end = match.end(2)
        pieces.append(line[cursor:url_start])  # prose before URL
        pieces.append(line[url_start:url_end])  # URL itself
        cursor = url_end
    pieces.append(line[cursor:])
    # Even indices: prose (wrap); odd indices: URLs (preserve).
    return "".join(_NUMBER_RE.sub(_bold_repl, p) if i % 2 == 0 else p for i, p in enumerate(pieces))


def _bold_repl(match: re.Match[str]) -> str:
    return f"**{match.group('token')}**"
