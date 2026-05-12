"""Reader-facing post-format helpers for u51 (TL;DR / H3 / bold-number / dedupe).

The Stage 2 LLM emits Korean prose that — in practice (10-subagent review
of ``archive/us-equity/2026/05/2026-05-11.md`` on 2026-05-13) — falls short
on six reader-facing dimensions:

1. No self-contained TL;DR (the conclusion line lacks magnitude / direction
   / action).
2. The ``> **시장 anchor**: ...`` line is a 250-char prose wall.
3. Sub-headings within §②/③/④/⑥ use a ``**Title** — body`` bold-prefix
   pattern instead of true ``### Title`` H3 — no nav, hurts scannability.
4. Bold inversion: section titles are bold but *numbers* (``+11.51%``,
   ``$81,154.06``, ``4.42%``) are plain — readers' eyes skip past the
   load-bearing facts.
5. §⑥ watch-points end overwhelmingly with ``~여부 / ~필요가 있다`` —
   describing observation rather than action.
6. Glossings (``S&P 500(스탠더드앤드푸어스 500 지수)``) repeat 3x in the
   same page.

This module owns the post-format pass that *fixes 2 through 6* on top of
already-generated Stage-2 markdown (1 is a Stage 2 prompt rule + a fallback
heuristic here for the rare miss). All helpers are pure ``str -> str``:

* :func:`ensure_tldr_block` — inserts a ``## 한눈에 보기`` H2 block when
  the LLM omitted it. Heuristic: extract three salient facts from the
  existing header callouts (오늘의 결론 / 핵심 동인 / 주의할 점).
* :func:`enforce_h3_subheadings` — rewrites ``**Title** — body`` patterns
  to true ``### Title\\n\\nbody`` inside §②/③/④/⑥ (§① stays prose; §⑤
  has its own grouping logic).
* :func:`wrap_numbers_bold` — adds ``**...**`` around plain numeric tokens
  (``[+-]?\\d+(?:\\.\\d+)?%``, ``\\$[\\d,]+(?:\\.\\d+)?``). Skips code
  blocks, table rows, already-bold tokens, and links (the latter so URL
  query strings like ``s=%5Espx`` don't get accidentally wrapped).
* :func:`check_action_bullet_ratio` — non-blocking diagnostic. Counts
  the share of §⑥ bullets ending in observation suffixes; returns the
  ratio + the offending bullets so the caller can WARN log.
* :func:`dedupe_glossings` — keeps the first ``base(풀어쓰기)`` occurrence
  and strips the gloss from subsequent occurrences of the same base term.

Module boundary
~~~~~~~~~~~~~~~
* Imports stdlib only (``re``, ``logging``).
* Does NOT import from ``briefing/`` / ``sources/`` / ``notifier/`` /
  ``orchestrator/`` (project rule 2: ``orchestrator`` is the only caller
  permitted to import publisher helpers).

R13 hygiene
~~~~~~~~~~~
* Logs at WARNING level use *structured extras* (``segment``, ``ratio``,
  ``count``) — the input strings are LLM output text already stripped of
  raw_metadata by upstream redaction. The helpers themselves never log
  the bullet bodies verbatim.

Disclaimer enforcement
~~~~~~~~~~~~~~~~~~~~~~
Every helper is a *string transform*; none of them removes the disclaimer
(it lives at the tail of the document, untouched by every regex here).
The orchestrator pipeline still calls ``verify_disclaimer`` after this
chain — the pin is a unit test (``test_reader_format_preserves_disclaimer``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from investo.briefing.segments import MarketSegment

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TL;DR block
# ---------------------------------------------------------------------------

TLDR_HEADER: Final[str] = "## 한눈에 보기"

# Markers used by ``ensure_tldr_block`` to:
#   1. detect whether the LLM already emitted a TL;DR block (idempotent),
#   2. locate the right insertion site (after the header callouts, before
#      ``## ①``).
_FIRST_SECTION_MARKER: Final[str] = "## ①"
_CONCLUSION_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*오늘의 결론\*\*\s*:\s*(.+?)$", re.MULTILINE
)
_DRIVER_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*핵심 동인\*\*\s*:\s*(.+?)$", re.MULTILINE
)
_CAUTION_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*주의할 점\*\*\s*:\s*(.+?)$", re.MULTILINE
)


def ensure_tldr_block(text: str, *, segment: str | None = None) -> str:
    """Insert a ``## 한눈에 보기`` H2 + 3-bullet block if absent.

    Idempotent: when the block already exists (Stage 2 prompt compliance
    is the *common* case), the text is returned unchanged. When missing,
    we fall back to a heuristic that re-uses the three header callouts
    (``오늘의 결론`` / ``핵심 동인`` / ``주의할 점``) as bullet bodies —
    they already carry magnitude + direction + caution, so the placeholder
    is informative rather than generic.

    When *neither* the block nor the callouts exist (a malformed input
    that the LLM never recovered), the text is returned unchanged and a
    WARNING is logged — the caller's downstream gates (``verify_disclaimer``,
    summary-fidelity) will surface the underlying problem; we do not
    silently insert empty bullets.
    """
    if TLDR_HEADER in text:
        return text

    conclusion = _capture_first(text, _CONCLUSION_CALLOUT_RE)
    driver = _capture_first(text, _DRIVER_CALLOUT_RE)
    caution = _capture_first(text, _CAUTION_CALLOUT_RE)

    if conclusion is None and driver is None and caution is None:
        _logger.warning(
            "reader_format.tldr_missing",
            extra={"segment": segment, "fallback": "none"},
        )
        return text

    bullets = [
        f"- {conclusion}" if conclusion else "- (요약 데이터 부족)",
        f"- {driver}" if driver else "- (핵심 동인 데이터 부족)",
        f"- {caution}" if caution else "- (주의 데이터 부족)",
    ]
    block = f"{TLDR_HEADER}\n\n" + "\n".join(bullets) + "\n\n"

    insertion = text.find(_FIRST_SECTION_MARKER)
    if insertion == -1:
        # No body sections — append to end (still better than dropping).
        _logger.warning(
            "reader_format.tldr_missing",
            extra={"segment": segment, "fallback": "appended"},
        )
        return f"{text.rstrip()}\n\n{block}"

    _logger.info(
        "reader_format.tldr_inserted",
        extra={"segment": segment, "source": "callout_fallback"},
    )
    return text[:insertion] + block + text[insertion:]


def _capture_first(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# H3 sub-headings
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Number bold wrap
# ---------------------------------------------------------------------------

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
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|.*\|\s*$")
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


# ---------------------------------------------------------------------------
# §⑥ action-bullet ratio diagnostic
# ---------------------------------------------------------------------------

# Korean "observation" sentence endings — the LLM's default mode that
# u51 wants to *flag* (not block). All five are present in the 2026-05-11
# audit ("여부", "할 필요가 있다", "관건이다", "주목할 필요"...).
_ACTION_SUFFIX_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p)
    for p in (
        r"여부[\.\s]*$",
        r"필요가 있다[\.\s]*$",
        r"관건이다[\.\s]*$",
        r"주목할 필요[가\s]*있다[\.\s]*$",
        r"확인할 필요[가\s]*있다[\.\s]*$",
    )
)

ACTION_RATIO_THRESHOLD: Final[float] = 0.40

_SECTION_HEADER_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(?P<header>.+?)$", re.MULTILINE)
_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^\s*[-*]\s+(.+?)$", re.MULTILINE)


def check_action_bullet_ratio(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
) -> tuple[float, tuple[str, ...]]:
    """Compute the fraction of §⑥ bullets ending in observation suffixes.

    Returns ``(ratio, violating_bullets)``. ``ratio`` is in ``[0.0, 1.0]``
    — when no §⑥ bullets exist the ratio is ``0.0`` (vacuously clean).
    When ``ratio`` exceeds :data:`ACTION_RATIO_THRESHOLD` we WARN-log,
    but the function is *non-blocking* — generation variance makes a
    hard reject inappropriate (some days the watch-list is genuinely
    observation-shaped).
    """
    section_body = _extract_section_body(text, section_marker)
    if section_body is None:
        return 0.0, ()
    bullets = [match.group(1).strip() for match in _BULLET_RE.finditer(section_body)]
    if not bullets:
        return 0.0, ()
    violations = tuple(b for b in bullets if _ends_with_observation(b))
    ratio = len(violations) / len(bullets)
    if ratio > ACTION_RATIO_THRESHOLD:
        _logger.warning(
            "reader_format.action_ratio_high",
            extra={
                "segment": segment,
                "ratio": round(ratio, 3),
                "count": len(violations),
                "total": len(bullets),
            },
        )
    return ratio, violations


def _extract_section_body(text: str, marker: str) -> str | None:
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if marker in match.group("header"):
            start = match.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
            return text[start:end]
    return None


def _ends_with_observation(bullet: str) -> bool:
    # Strip trailing whitespace + a single trailing punctuation char.
    stripped = bullet.rstrip()
    return any(p.search(stripped) for p in _ACTION_SUFFIX_PATTERNS)


# ---------------------------------------------------------------------------
# Glossing dedupe
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# u56 — first-viewport short disclaimer (segment-aware)
# ---------------------------------------------------------------------------

# Short disclaimer text per segment. The canonical footer
# (``DISCLAIMER`` / ``DISCLAIMER_CRYPTO`` in ``briefing.disclaimer``)
# remains untouched as the publish gate; this short blockquote is an
# *additive* surface that lands above-the-fold for reader UX. u56
# evaluation Finding #5 (crypto needs its own §10 reference) is what
# motivates the segment-aware variant.
SHORT_DISCLAIMER_EQUITY: Final[str] = "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다."
SHORT_DISCLAIMER_CRYPTO: Final[str] = (
    "> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. "
    "가상자산은 가격 변동성이 매우 큽니다."
)

# Idempotence detectors. The blockquote-prefix substring is unique to
# the short disclaimer — the canonical footer does not start with ``>``.
_SHORT_DISCLAIMER_DETECT_EQUITY: Final[str] = "매매 권유가 아닙니다"
_SHORT_DISCLAIMER_DETECT_CRYPTO: Final[str] = "가상자산 매매 권유가 아닙니다"


def _short_disclaimer_for(segment: MarketSegment) -> str:
    if segment == "crypto":
        return SHORT_DISCLAIMER_CRYPTO
    return SHORT_DISCLAIMER_EQUITY


def emit_first_viewport_disclaimer(text: str, segment: MarketSegment) -> str:
    """Insert a one-line short disclaimer blockquote in the first viewport.

    Placement order (first match wins):
      1. Immediately before ``## 한눈에 보기`` (TLDR header) when present.
      2. Immediately before ``## ①`` (first section) when (1) is absent.
      3. Prepended to the document when neither anchor exists.

    Idempotent: when the segment-appropriate short disclaimer is already
    present in the first ~30 rendered lines, returns the input unchanged.
    """
    detect = (
        _SHORT_DISCLAIMER_DETECT_CRYPTO if segment == "crypto" else _SHORT_DISCLAIMER_DETECT_EQUITY
    )
    if detect in text:
        return text

    short = _short_disclaimer_for(segment)
    block = f"{short}\n\n"

    insertion = text.find(TLDR_HEADER)
    if insertion == -1:
        insertion = text.find(_FIRST_SECTION_MARKER)
    if insertion == -1:
        return f"{block}{text}"
    return text[:insertion] + block + text[insertion:]


# ---------------------------------------------------------------------------
# u56 — retail tone caps (Finding #12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SentenceEndingReport:
    """Distribution of dominant sentence-ending patterns in the body."""

    counts: dict[str, int]
    total: int
    dominant: str | None
    dominant_ratio: float


@dataclass(frozen=True, slots=True)
class FillerDensityReport:
    """Filler-phrase density per 1000 chars of cleaned body text."""

    counts: dict[str, int]
    total_chars: int
    density_per_1000: float


# Korean closing patterns categorised. Matched right-of-sentence, after
# stripping a final trailing period / space. The category list is small
# on purpose — over-matching produces noisy ratios; we want a clean
# "dominant ending" signal.
_SENTENCE_ENDING_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("했다", re.compile(r"했다\.?\s*$")),
    ("된다", re.compile(r"된다\.?\s*$")),
    ("이다", re.compile(r"이다\.?\s*$")),
    ("전망이다", re.compile(r"전망이다\.?\s*$")),
    ("보인다", re.compile(r"보인다\.?\s*$")),
    ("가능성", re.compile(r"가능성[이가]?\s*\S*\.?\s*$")),
)

_FILLER_TERMS: Final[tuple[str, ...]] = (
    "여부",
    "전망",
    "우려",
    "가능성",
    "작용",
)

SENTENCE_ENDING_DOMINANCE_THRESHOLD: Final[float] = 0.60
FILLER_DENSITY_PER_1000_THRESHOLD: Final[float] = 8.0

_YAML_FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_SENTENCE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"[.!?]\s+|\n+")


def _strip_non_body_regions(text: str) -> str:
    """Strip yaml frontmatter / code fences / table rows for tone metrics.

    The tone caps operate on prose only: structural / data surfaces are
    not part of the reader-perceived rhythm. Disclaimer footer is also
    stripped so the canonical text does not weight the ratio.
    """
    out = _YAML_FRONTMATTER_RE.sub("", text)
    # Strip disclaimer footer.
    anchor = "## ⑦ 면책조항"
    anchor_idx = out.find(anchor)
    if anchor_idx >= 0:
        out = out[:anchor_idx]
    # Strip code fences.
    out = re.sub(r"```.*?```", "", out, flags=re.DOTALL)
    out = re.sub(r"`[^`\n]+`", "", out)
    # Strip table rows.
    out = "\n".join(line for line in out.splitlines() if not _TABLE_ROW_RE.match(line))
    return out


def check_sentence_ending_diversity(
    text: str, *, segment: MarketSegment | None = None
) -> SentenceEndingReport:
    """Return the dominant Korean sentence-ending ratio in the body.

    WARN-only — emits ``tone.sentence_ending_dominance`` when the
    dominant ending exceeds :data:`SENTENCE_ENDING_DOMINANCE_THRESHOLD`.
    """
    body = _strip_non_body_regions(text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(body) if s.strip()]
    counts: dict[str, int] = {}
    classified_total = 0
    for sentence in sentences:
        for label, pattern in _SENTENCE_ENDING_PATTERNS:
            if pattern.search(sentence):
                counts[label] = counts.get(label, 0) + 1
                classified_total += 1
                break

    if classified_total == 0:
        return SentenceEndingReport(counts=counts, total=0, dominant=None, dominant_ratio=0.0)

    dominant = max(counts.items(), key=lambda kv: kv[1])
    dominant_label = dominant[0]
    dominant_ratio = dominant[1] / classified_total

    if dominant_ratio > SENTENCE_ENDING_DOMINANCE_THRESHOLD:
        _logger.warning(
            "tone.sentence_ending_dominance",
            extra={
                "segment": segment,
                "dominant": dominant_label,
                "ratio": round(dominant_ratio, 3),
                "total": classified_total,
            },
        )
    return SentenceEndingReport(
        counts=counts,
        total=classified_total,
        dominant=dominant_label,
        dominant_ratio=dominant_ratio,
    )


def check_filler_phrase_density(
    text: str, *, segment: MarketSegment | None = None
) -> FillerDensityReport:
    """Return the filler-family per-1000-chars density.

    WARN-only — emits ``tone.filler_density`` when the density exceeds
    :data:`FILLER_DENSITY_PER_1000_THRESHOLD`.
    """
    body = _strip_non_body_regions(text)
    total_chars = len(body)
    counts: dict[str, int] = {}
    occurrences = 0
    for term in _FILLER_TERMS:
        count = body.count(term)
        if count:
            counts[term] = count
            occurrences += count
    density = (occurrences / total_chars * 1000.0) if total_chars else 0.0
    if density > FILLER_DENSITY_PER_1000_THRESHOLD:
        _logger.warning(
            "tone.filler_density",
            extra={
                "segment": segment,
                "density_per_1000": round(density, 2),
                "total_chars": total_chars,
                "occurrences": occurrences,
            },
        )
    return FillerDensityReport(counts=counts, total_chars=total_chars, density_per_1000=density)


# ---------------------------------------------------------------------------
# Composite pipeline
# ---------------------------------------------------------------------------


def apply_reader_format(
    text: str,
    *,
    segment: str | None = None,
) -> str:
    """Run the full reader-format chain in canonical order.

    Order matters:
      1. ``ensure_tldr_block`` — *before* H3 promotion so the heuristic's
         callout regex still sees the ``> **오늘의 결론**: ...`` prefix.
      2. ``enforce_h3_subheadings`` — *before* number wrapping so a freshly-
         promoted H3 isn't bolded again by the wrapper.
      3. ``wrap_numbers_bold`` — number wrapping after structural changes.
      4. ``dedupe_glossings`` — after wrapping so glossings inside bolded
         spans (rare) are still detected.
      5. ``check_action_bullet_ratio`` — pure diagnostic; runs last so it
         observes the final shape.
    """
    out = ensure_tldr_block(text, segment=segment)
    out = enforce_h3_subheadings(out)
    out = wrap_numbers_bold(out)
    out = dedupe_glossings(out)
    check_action_bullet_ratio(out, segment=segment)
    return out


__all__ = [
    "ACTION_RATIO_THRESHOLD",
    "FILLER_DENSITY_PER_1000_THRESHOLD",
    "SENTENCE_ENDING_DOMINANCE_THRESHOLD",
    "SHORT_DISCLAIMER_CRYPTO",
    "SHORT_DISCLAIMER_EQUITY",
    "TLDR_HEADER",
    "FillerDensityReport",
    "SentenceEndingReport",
    "apply_reader_format",
    "check_action_bullet_ratio",
    "check_filler_phrase_density",
    "check_sentence_ending_diversity",
    "dedupe_glossings",
    "emit_first_viewport_disclaimer",
    "enforce_h3_subheadings",
    "ensure_tldr_block",
    "wrap_numbers_bold",
]
