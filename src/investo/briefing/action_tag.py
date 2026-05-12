"""u30 Step 3 — closed-set action tag for the first-viewport conclusion.

Each segment's "오늘의 결론" line carries one terminal tag from a closed
set. As of u56 (2026-05-13 compliance-language-and-observational-tags),
the canonical set is **observational** — bullish/bearish-stance tags are
deprecated because Korean retail readers parse ``[강세]`` / ``[약세]`` as
*buy/sell stance*, which is implicit investment advice under
자본시장법 §17:

    Current closed set (observation labels):
        [상승 관찰] [하락 관찰] [혼재] [변동성 확대] [데이터부족]

    Legacy set (kept as input-side aliases only — u56 migration):
        [강세] → [상승 관찰]
        [약세] → [하락 관찰]
        [혼조] → [혼재]
        [변동성↑] → [변동성 확대]
        [관망] → [데이터부족]   (관망 = neutral wait-and-see; absorbed
                                  into the data-limited tag since the
                                  reader signal is identical)

The Telegram first-impression preview surfaces this tag verbatim, so the
alert tells the reader *what the day's data shape is* without implying
an action.

Two layers cooperate:

1. **Stage 2 prompt contract** — the LLM is asked to end section ① with
   exactly one closed-set tag drawn from the *new* set. (See
   ``STAGE2_SYSTEM`` in ``investo.briefing.prompts``.)
2. **Producer-side enforcement** — :func:`apply_action_tag` is called by
   :func:`investo.briefing.pipeline._build_summary_header` after
   :func:`investo.briefing.pipeline._summary_sentence` has chosen a
   conclusion sentence. The function:

   - normalises a legacy tag (``[강세]`` etc.) to its observation
     equivalent via :data:`LEGACY_TAG_ALIASES` — handles the case where
     the LLM emits a legacy tag during the prompt-rollout cutover;
   - keeps the LLM-emitted tag when it is one of the closed values;
   - strips off-set tags (``[강력매수]``, ``[BUY]``, …) and replaces
     them with the deterministic default;
   - appends the deterministic default when no tag is present;
   - forces ``[데이터부족]`` when ``data_limited=True``, regardless of
     what (if anything) the LLM emitted.

The function is pure — no I/O, no clock — so its output is a function
of ``(conclusion, data_limited)`` only. Determinism keeps the publish
path replayable from fixtures.

The tag is intentionally bracketed so the existing notifier conclusion
extractor (``_clean_summary_text``) preserves it through markdown
stripping (``[...]`` brackets are tolerated as plain text after
markdown-link reduction; the closed-set tags contain no link
parentheses, so they survive intact).
"""

from __future__ import annotations

import re
from typing import Final, Literal

ActionTag = Literal[
    "[상승 관찰]",
    "[하락 관찰]",
    "[혼재]",
    "[변동성 확대]",
    "[데이터부족]",
]

ACTION_TAGS: Final[frozenset[ActionTag]] = frozenset(
    {"[상승 관찰]", "[하락 관찰]", "[혼재]", "[변동성 확대]", "[데이터부족]"}
)
DEFAULT_ACTION_TAG: Final[ActionTag] = "[데이터부족]"
DATA_LIMITED_ACTION_TAG: Final[ActionTag] = "[데이터부족]"

# u56 — legacy → observation tag rewrite map. Legacy tags emitted by the
# LLM during the prompt-rollout cutover (or referenced in pre-2026-05-13
# archive prose that the producer re-reads) are normalised here so the
# rest of the pipeline only deals with the new set. Past archive
# markdown files are NOT re-rendered (the legal cutover is not
# retroactive); only fresh producer output passes through this map.
LEGACY_TAG_ALIASES: Final[dict[str, ActionTag]] = {
    "[강세]": "[상승 관찰]",
    "[약세]": "[하락 관찰]",
    "[혼조]": "[혼재]",
    "[변동성↑]": "[변동성 확대]",
    "[관망]": "[데이터부족]",
}

# Match a trailing bracket-token at the end of the conclusion. Anchored
# to the right so we only inspect the *last* bracketed token; bracket
# tokens elsewhere in the sentence (e.g. ``[NVDA]`` ticker callouts) are
# preserved untouched.
_TRAILING_BRACKET_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\s*\[([^\[\]]+)\]\s*$")
# Match every bracketed token in a string. Used to scavenge a closed-set
# tag from the raw section ① body when ``_summary_sentence`` clipped at
# a Korean sentence terminator and dropped the tag.
_ANY_BRACKET_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\[\]]+\]")


def _normalize_tag(tag: str) -> str | None:
    """Return the observation-set equivalent of ``tag`` if known.

    ``tag`` may already be in the observation set (returned as-is), be
    a legacy stance tag (rewritten via :data:`LEGACY_TAG_ALIASES`), or
    be off-set (``None`` so the caller falls through to the default).
    """
    if tag in ACTION_TAGS:
        return tag
    return LEGACY_TAG_ALIASES.get(tag)


def apply_action_tag(
    conclusion: str,
    *,
    data_limited: bool,
    section_text: str | None = None,
) -> str:
    """Return ``conclusion`` with exactly one terminal closed-set tag.

    Pure function. ``conclusion`` is the cleaned summary sentence the
    pipeline already settled on; ``section_text`` is the raw ``① 요약``
    body the LLM produced. The pipeline's ``_summary_sentence`` may
    clip the conclusion at a Korean sentence terminator (``다.``) and
    drop a trailing closed-set tag the LLM emitted; when ``conclusion``
    has no trailing bracket but ``section_text`` does carry a closed-set
    tag, this function rescues that tag rather than overwriting it
    with the deterministic default.

    Resolution order:

    1. ``data_limited=True`` → force ``[데이터부족]``.
    2. Trailing in-set or legacy-aliased tag on ``conclusion`` →
       normalise + preserve.
    3. Trailing off-set tag on ``conclusion`` → strip + default.
    4. Closed-set (or legacy-aliased) tag anywhere in ``section_text`` →
       use that tag (normalised).
    5. Otherwise → append the deterministic default ``[데이터부족]``.
    """
    if data_limited:
        return _force_tag(conclusion, DATA_LIMITED_ACTION_TAG)

    stripped = conclusion.rstrip()
    match = _TRAILING_BRACKET_TOKEN_RE.search(stripped)
    if match is not None:
        existing = f"[{match.group(1)}]"
        normalised = _normalize_tag(existing)
        if normalised is not None:
            # Already (or legacy-aliased to) closed-set conformant;
            # normalise whitespace so the tag is separated from the
            # sentence by exactly one space.
            head = stripped[: match.start()].rstrip()
            return f"{head} {normalised}" if head else normalised
        # Off-set bracket token at the tail: strip and replace with the
        # default. We do not preserve unknown tags because doing so
        # would let the LLM expand the contract by emission alone.
        head = stripped[: match.start()].rstrip()
        return f"{head} {DEFAULT_ACTION_TAG}" if head else DEFAULT_ACTION_TAG

    # Conclusion has no trailing tag — try to rescue one from the raw
    # section text (LLM may have written it after the sentence
    # terminator that the producer's sentence picker discarded).
    if section_text is not None:
        rescued = _scavenge_in_set_tag(section_text)
        if rescued is not None:
            return f"{stripped} {rescued}" if stripped else rescued

    # No trailing bracket token, no rescue — append the default.
    return f"{stripped} {DEFAULT_ACTION_TAG}" if stripped else DEFAULT_ACTION_TAG


def _scavenge_in_set_tag(section_text: str) -> str | None:
    """Return the last in-set (or legacy-aliased) tag in ``section_text``.

    Off-set tokens are ignored. ``[데이터부족]`` is also ignored — the
    publisher forces that tag separately when the segment is data
    limited; LLM-emitted ``[데이터부족]`` would falsely override the
    deterministic default for healthy segments.
    """
    last: str | None = None
    for match in _ANY_BRACKET_TOKEN_RE.finditer(section_text):
        token = match.group(0)
        normalised = _normalize_tag(token)
        if normalised is not None and normalised != DATA_LIMITED_ACTION_TAG:
            last = normalised
    return last


def _force_tag(conclusion: str, tag: ActionTag) -> str:
    """Replace any trailing closed-set or off-set tag with ``tag``."""
    stripped = conclusion.rstrip()
    match = _TRAILING_BRACKET_TOKEN_RE.search(stripped)
    if match is not None:
        head = stripped[: match.start()].rstrip()
        return f"{head} {tag}" if head else tag
    return f"{stripped} {tag}" if stripped else tag


__all__ = [
    "ACTION_TAGS",
    "DATA_LIMITED_ACTION_TAG",
    "DEFAULT_ACTION_TAG",
    "LEGACY_TAG_ALIASES",
    "ActionTag",
    "apply_action_tag",
]
