"""Watchlist Carryover renderer + idempotent injector for u52.

Pure str → str transforms — no I/O, no clock, no env reads — so the
same (segment, date) re-publish (FR-006) yields byte-equal output.
The orchestrator post-processes Stage 2's markdown by:

1. Calling :func:`render_carryover_block` to render the deterministic
   table from a :class:`BriefingCarryover`;
2. Calling :func:`inject_carryover_block` to splice the block into
   the Stage 2 markdown at the §② → §③ boundary (or replace an
   existing "## Watchlist Carryover" block on idempotent re-runs).

The renderer is the *single source of truth* for the published table:
even if the LLM emits its own ``## Watchlist Carryover`` block from
the prompt input, the post-process pass overrides it with this
deterministic rendering. This matches the u49 anchor-table pattern
(deterministic table > LLM-invented table).

Disclaimer enforcement: the renderer never touches the disclaimer
string; the boundary regexes anchor on §② / §③ / "## Watchlist
Carryover" headings only. The publisher's ``verify_disclaimer`` gate
runs *after* injection (in ``write_briefing``) so a regression cannot
slip past.

Module boundary: ``publisher.carryover`` imports from
``investo.models`` (foundation) only. No cross-unit imports.
"""

from __future__ import annotations

import re
from typing import Final

from investo.models import BriefingCarryover, CarryoverItem, status_label_kr

# Block header — the renderer's idempotency contract pins this string.
# Changing the header text requires a coordinated test update.
CARRYOVER_BLOCK_HEADING: Final[str] = "## Watchlist Carryover"

# Boundary regex: locate the §② → §③ transition so the block lands
# *between* §② (전일 핵심 이슈) and §③ (섹터/수급 동향). Anchors on the
# H2 line literal — segmented briefings emit these headers verbatim
# (see :data:`investo.briefing.prompts.STAGE2_SECTION_HEADERS`).
_SECTION_THREE_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+③\s+섹터/수급 동향\s*$",
    re.MULTILINE,
)

# Existing-block detector for idempotent re-run replacement. Matches
# the "## Watchlist Carryover" heading through the next H2 boundary.
# Non-greedy so multiple H2 sections in the body do not get swallowed.
_EXISTING_BLOCK_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Watchlist\s+Carryover\s*$.*?(?=^##\s+)",
    re.MULTILINE | re.DOTALL,
)


def render_carryover_block(carryover: BriefingCarryover) -> str:
    """Return the deterministic markdown table for a carryover bundle.

    Returns the empty string when ``carryover.is_empty`` — callers
    use the empty-string sentinel to skip injection entirely (the
    "no carryover" case must not litter the published markdown with
    an empty table).

    Otherwise emits a 4-column table (이벤트 / 발원일 / 기대일 / 상태)
    plus a trailing blank line so the next H2 heading stays visually
    separated. Order: ``prior_resolved`` first, then
    ``prior_unresolved`` (with ``carried_over`` rows interleaved by
    the parser's split). The order matches the prompt-side rendering
    so LLM citations align row-by-row.
    """
    if carryover.is_empty:
        return ""
    rows = [
        "| 이벤트 | 발원일 | 기대일 | 상태 |",
        "|--------|--------|--------|------|",
    ]
    for item in carryover.prior_resolved:
        rows.append(_render_row(item))
    for item in carryover.prior_unresolved:
        rows.append(_render_row(item))
    body = "\n".join(rows)
    return f"{CARRYOVER_BLOCK_HEADING}\n\n{body}\n"


def inject_carryover_block(markdown: str, block: str) -> str:
    """Inject (or replace) the carryover block in the Stage 2 markdown.

    Idempotency contract:

    * Calling :func:`inject_carryover_block` twice with the same
      ``(markdown, block)`` returns the same output as a single call.
    * Empty ``block`` → ``markdown`` returned unchanged (no insertion,
      no replacement). This is how the orchestrator skips injection
      for an empty :class:`BriefingCarryover`.
    * If ``markdown`` already contains a "## Watchlist Carryover"
      heading (e.g. the LLM emitted one from the prompt input, or this
      is a same-day re-run), the existing block is *replaced* — the
      deterministic renderer is the single source of truth.
    * If ``markdown`` does not yet carry a block, the new block is
      inserted *before* the §③ heading. This satisfies AC#4 ("§② 뒤,
      §⑥ 앞") with the further refinement of "right after §② body".
    * If ``markdown`` lacks a §③ heading (data-limited body shape, no
      §③ line), the block is appended at the end of the markdown to
      preserve the trust contract that an injected block is always
      present when the renderer emitted content.
    """
    if not block:
        # Empty render — but the markdown may still carry a stale
        # block from a prior same-day run. Strip it so idempotency
        # holds for the "empty input but stale output" combination.
        return _strip_existing_block(markdown)

    # Replace existing block in place (idempotent re-run). The lambda
    # neutralises ``re.sub`` backreference parsing — a Korean topic
    # with a stray ``\1`` substring cannot break the substitution.
    # ``block`` ends with a single ``\n``; the regex stops at the next
    # H2 heading, so we append a second ``\n`` to mirror the fresh-
    # insert path's blank-line separator (keeps idempotency byte-equal).
    if _EXISTING_BLOCK_RE.search(markdown):
        return _EXISTING_BLOCK_RE.sub(lambda _m: block + "\n", markdown, count=1)

    # Fresh insertion before §③. The block already ends with ``\n``;
    # we add a second newline so the §③ heading stays visually
    # separated by a blank line (matches the rest of the segmented
    # output's H2 spacing).
    section_three = _SECTION_THREE_HEADING_RE.search(markdown)
    if section_three is not None:
        idx = section_three.start()
        return markdown[:idx] + block + "\n" + markdown[idx:]
    # No §③ heading — fall through to the defensive end-append below.

    # Defensive fallback: no §③ header found — append at the end
    # (data-limited body or non-standard shape).
    sep = "" if markdown.endswith("\n") else "\n"
    return markdown + sep + block


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_TABLE_BREAKING_CHARS: Final[re.Pattern[str]] = re.compile(r"([|\\])")


def _escape_table_cell(text: str) -> str:
    """Escape ``|`` and ``\\`` so a topic does not break the markdown table.

    Bracket / paren / underscore are deliberately *not* escaped — they
    render fine inside table cells and the parser preserves them in
    ``ticker_or_topic``.
    """
    return _TABLE_BREAKING_CHARS.sub(r"\\\1", text)


def _render_row(item: CarryoverItem) -> str:
    """Render one :class:`CarryoverItem` as a markdown table row."""
    topic = _escape_table_cell(item.ticker_or_topic)
    originated = item.originated_date.isoformat()
    expected = item.expected_date.isoformat() if item.expected_date is not None else "미정"
    status = status_label_kr(item.status)
    return f"| {topic} | {originated} | {expected} | {status} |"


def _strip_existing_block(markdown: str) -> str:
    """Remove an existing Watchlist Carryover block from ``markdown``.

    Used when the renderer returns an empty string but a prior
    same-day publish left a stale block in the archive. Idempotent —
    calling on already-clean markdown returns it unchanged.
    """
    return _EXISTING_BLOCK_RE.sub("", markdown, count=1)


__all__ = [
    "CARRYOVER_BLOCK_HEADING",
    "inject_carryover_block",
    "render_carryover_block",
]
