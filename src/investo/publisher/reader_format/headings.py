"""H3 sub-heading normalization pass.

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

# Rewrite the bold-prefix sub-heading pattern that the LLM emits when not
# explicitly told to use H3:
#
#   **3대 지수 상승 마감 — 전주 반등 흐름 연장**\n\nbody...
#
# becomes:
#
#   ### 3대 지수 상승 마감 — 전주 반등 흐름 연장\n\nbody...
#
# Constraints (false-positive guards):
# * Must start at line beginning (``^``).
# * Title must NOT contain a newline (inline bold runs are out of scope).
# * The line must consist ENTIRELY of ``**...**`` — paragraphs that just
#   *open* with a bold span (e.g. ``**S&P 500**은 ...``) are body prose
#   and must be left alone.
# * Title must NOT contain a colon followed by space (that pattern is
#   reserved for the header callouts ``**오늘의 결론**: ...``) and the
#   callouts live inside ``> ...`` blockquotes anyway, so we additionally
#   anchor on a non-blockquote line.
_H3_BOLD_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\*\*([^\n*][^\n]*?)\*\*\s*$",
    re.MULTILINE,
)


def enforce_h3_subheadings(text: str) -> str:
    """Promote ``**Title**`` sub-heading lines to ``### Title``.

    Only acts on *whole-line* bold patterns (the LLM's customary sub-
    heading form) — body prose that merely *contains* bold spans is left
    alone. Idempotent: a second pass over already-promoted ``### Title``
    text is a no-op.

    Blockquote lines (``> **...**: ...``) — the header callouts — are
    skipped because the regex requires the line to consist entirely of
    ``**...**`` with no trailing colon prose.
    """
    return _H3_BOLD_PREFIX_RE.sub(lambda m: f"### {m.group(1).strip()}", text)
