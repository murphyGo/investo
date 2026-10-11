"""Number bold-wrap pass.

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

from investo._internal.surface_quality import find_surface_quality_issues
from investo.publisher.reader_format._constants import _TABLE_ROW_RE

# Numeric token shapes we wrap:
#   - signed compound moves: ``+0.74달러(+0.97%)``.
#   - signed percentage-point deltas: ``-0.04%p``, ``+0.29pp``.
#   - signed dollar amounts: ``-$0.23``.
#   - dollar amounts with scale suffixes: ``$2.30T``.
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
    r"[+\-]\d+(?:\.\d+)?달러\([+\-]\d+(?:\.\d+)?%\)"  # signed KRW/USD prose move
    r"|[+\-]\d+(?:\.\d+)?(?:%p|pp)"  # signed percentage-point tokens
    r"|[+\-]\$\d{1,3}(?:,\d{3})*(?:\.\d+)?"  # signed dollar with thousands
    r"|[+\-]\$\d+(?:\.\d+)?"  # signed plain dollar
    r"|\$\d{1,3}(?:,\d{3})*(?:\.\d+)?[TMB]?"  # dollar with optional scale suffix
    r"|\$\d+(?:\.\d+)?[TMB]?"  # plain dollar with optional scale suffix
    r"|[+\-]\d+(?:\.\d+)?%"  # signed percentage
    r"|\b\d+\.\d+%"  # bare decimal percent
    r")"
    # Do not backtrack to a numeric prefix inside an already-bold token.
    r"(?![\d,*]|\.\d)"
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
_BOLD_SPAN_RE: Final[re.Pattern[str]] = re.compile(r"\*\*[^*\n]+\*\*")
_DATA_CARD_RE: Final[re.Pattern[str]] = re.compile(
    r'^<(section|details)\b[^>]*\bclass="investo-data-card"(?:\s|>)'
)


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
    card_tag: str | None = None
    for line in text.splitlines(keepends=False):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        # These producer-owned structured cards use raw HTML. Markdown emphasis
        # would become visible punctuation inside their table/text fields. This
        # only skips cosmetic wrapping; all reader-visible trust gates still run.
        card_open = _DATA_CARD_RE.match(line)
        if card_open is not None:
            card_tag = card_open.group(1)
        if card_tag is not None:
            out_lines.append(line)
            if line == f"</{card_tag}>":
                card_tag = None
            continue
        if _TABLE_ROW_RE.match(line):
            out_lines.append(line)
            continue
        out_lines.append(_wrap_line(line))
    # Preserve trailing newline if the original had one.
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(out_lines) + trailing


def _wrap_line(line: str) -> str:
    if any(issue.link_shape is not None for issue in find_surface_quality_issues(line)):
        return line
    # Mask URL and valid emphasis spans without moving token boundaries;
    # numeric matches are applied to the original prose in reverse order.
    protected = [match.span(2) for match in _LINK_URL_RE.finditer(line)] + [
        match.span() for match in _BOLD_SPAN_RE.finditer(line)
    ]
    masked = line
    for start, end in protected:
        # Keep star boundaries so a neighboring malformed token cannot appear
        # eligible merely because a protected span was split off.
        masked = masked[:start] + "*" * (end - start) + masked[end:]
    for match in reversed(tuple(_NUMBER_RE.finditer(masked))):
        line = line[: match.start()] + _bold_repl(match) + line[match.end() :]
    return line


def _bold_repl(match: re.Match[str]) -> str:
    return f"**{match.group('token')}**"
