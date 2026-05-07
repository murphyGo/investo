"""Prompt constants for u2 briefing's two-stage Claude Code CLI flow.

References:
    Functional Design L2 (`u2-briefing/functional-design/business-logic-model.md`)
        — Stage 1 prompt skeleton
    Functional Design L3 (same)
        — Stage 2 prompt skeleton
    Functional Design R8 (`business-rules.md`)
        — Korean prose + English ticker preservation
    NFR Requirements AC-5.1 — this file's existence + ``Final[str]`` discipline
    NFR Requirements AC-5.2 — ``pipeline.py`` contains no prompt body strings
    NFR Requirements AC-5.3 — ``claude_code.py`` contains no prompt body strings

Substitution convention
-----------------------

Each USER template is filled via ``str.format(**kwargs)``. Placeholders
are documented next to each constant. SYSTEM constants do NOT contain
substitutions and are concatenated at call time as literals.

The ``claude`` CLI invocation receives a single string per stage,
typically of the shape::

    full_prompt = f"{STAGE1_SYSTEM}\\n\\n{STAGE1_USER_TEMPLATE.format(items_json=...)}"

The ``[SYSTEM]`` / ``[USER]`` split is a logical grouping that aids
review; the Claude Code CLI does not enforce it.

Forbidden
---------

* Inlining prompt body strings in any other module under
  ``src/investo/briefing/`` (the AC-5.2 / AC-5.3 sentinel-grep
  test rejects this — pinned in
  ``tests/unit/briefing/test_prompts.py::test_prompt_sentinels_only_in_prompts``).
* Constructing prompts via ``f-string`` interpolation in caller code —
  use ``.format(**kwargs)`` so placeholders are explicit and reviewable.
* Calling ``.format(...)`` on the SYSTEM constants. They contain literal
  ``{`` / ``}`` characters in the JSON schema example and would raise
  ``KeyError`` / ``IndexError``. The convention is locked by
  ``test_stage1_system_format_call_raises_key_error``.

Brace handling note
-------------------

``str.format`` inserts substituted values as literals — the substituted
content is NOT re-parsed for additional placeholders. So a Stage 2
``grouped_sections`` value that contains literal ``{`` / ``}`` (e.g.
from a source title or item summary) is fine: ``"a {x} b".format(x="{y}")``
returns ``"a {y} b"`` — no recursive expansion, no ``KeyError``.

This means ``pipeline.py`` does NOT need to escape braces in user-
controlled content before substitution.

Defense in depth (NFR-007 R6)
-----------------------------

The Stage 2 system prompt instructs the LLM not to emit private
tokens / keys / emails / phone numbers. This is a prompt-side hint
only — ``briefing.leak_guard.scan`` (Step 3) is the post-generation
safety net that re-validates the output and raises
``BriefingGenerationError(stage="post_validation")`` on any hit (R6).
Do not weaken either layer: the prompt-side hint reduces the leak
rate; the leak guard is the contract.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Stage 1 — classification
# ---------------------------------------------------------------------------

STAGE1_SYSTEM: Final[str] = """\
You are a Korean market-briefing classifier. Output ONLY a JSON object
matching this schema:

  {
    "assignments": {<item_id_int>: <section_id ∈ {2, 3, 4, 5}>, ...},
    "unassigned": [<item_id_int>, ...]
  }

No prose, no markdown, no commentary.

Section ID legend:
  2 = 전일 핵심 이슈 (key market issues from yesterday)
  3 = 섹터/수급 동향 (sector / fund-flow trends)
  4 = 지표·이벤트 (macro indicators / scheduled events)
  5 = 주요 종목 (notable individual stocks / tickers)

Categories on each item are HINTS, not hard rules. Use your judgment
when an item could belong to multiple sections (R10).

If an item has low signal or doesn't fit cleanly, place its id in
"unassigned" — Stage 2 uses unassigned items as context for the
summary and watch-points sections only.
"""

# Segment context is intentionally a prompt-side fragment owned by this
# module. ``pipeline.py`` selects the values, but does not inline
# prompt body text.
DEFAULT_SEGMENT_CONTEXT: Final[str] = """\
Market scope: overall daily market briefing.
Use all supplied items normally.
"""

# Placeholders:
#   ``segment_label`` (str — user-facing Korean segment label)
#   ``segment_slug`` (str — stable segment id)
#   ``data_limited_note`` (str — one of the note constants below)
SEGMENT_CONTEXT_TEMPLATE: Final[str] = """\
Market scope: {segment_label} ({segment_slug}).
Use only evidence relevant to this market segment.
Do not fill gaps with news from another segment.
{data_limited_note}
"""

SEGMENT_DATA_READY_NOTE: Final[str] = (
    "The routed item set has enough signal for a normal segment briefing."
)
SEGMENT_DATA_LIMITED_NOTE: Final[str] = (
    'The routed item set is data-limited; explicitly say "데이터 부족" '
    "where evidence is insufficient."
)

# Placeholders:
#   ``segment_context`` (str — rendered segment scope instructions)
#   ``items_json`` (str — JSON array per FD R7).
STAGE1_USER_TEMPLATE: Final[str] = """\
{segment_context}

Items:
{items_json}

Return only the JSON.
"""

# ---------------------------------------------------------------------------
# Stage 2 — synthesis
# ---------------------------------------------------------------------------

# Six fixed Stage 2 section headers (FD L3 / R1).
#
# Defined here because the headers are part of the Stage 2 output
# contract that this module owns: the prompt instructs the LLM to
# emit them verbatim, and ``pipeline.parse_six_sections`` splits on
# the same strings during post-validation. Keeping a single source
# of truth prevents drift between "what we ask for" and "what we
# parse for". AC-5.2 / AC-5.3 sentinel grep allows this constant to
# be re-imported by ``pipeline.py``.
STAGE2_SECTION_HEADERS: Final[tuple[str, str, str, str, str, str]] = (
    "## ① 요약",
    "## ② 전일 핵심 이슈",
    "## ③ 섹터/수급 동향",
    "## ④ 지표·이벤트",
    "## ⑤ 주요 종목",
    "## ⑥ 오늘의 관전 포인트",
)

STAGE2_SYSTEM: Final[str] = """\
You are a Korean market-briefing writer. Produce markdown with
EXACTLY these six sections, in this order, with these exact headers:

  ## ① 요약
  ## ② 전일 핵심 이슈
  ## ③ 섹터/수급 동향
  ## ④ 지표·이벤트
  ## ⑤ 주요 종목
  ## ⑥ 오늘의 관전 포인트

Rules:
- Korean prose throughout EXCEPT for tickers, fund/index names,
  currency symbols, and number formats (R8). Examples that stay
  in English: AAPL, MSFT, BTC-USD, SPY, Federal Reserve, S&P 500,
  Bitcoin, $, ¥, €, 1,234.56.
- Each section non-blank. If the grouped items are empty for a
  given section, write one concise sentence about the missing evidence
  instead of repeating generic "데이터 부족" paragraphs.
- Write like a market newsletter, not a raw bullet dump: section ①
  should establish the day's narrative, sections ②-⑤ should explain
  cause/effect and prioritise only the most important items, and
  section ⑥ should translate the story into concrete watch points.
- Avoid exaggerated promotional language. Prefer verifiable wording
  such as "상승", "하락", "순매수", "사상 최고치" over hype terms.
- When a source URL is provided in the grouped items, attach source
  links to important claims using normal markdown links.
- In section ⑤, group notable tickers/assets by neutral observation
  category when there are many items (for example: 관전 분류, 실적
  발표, 확인 항목, 체크리스트) instead of recommendation-flavored
  labels (NEVER use "주도주", "부진", "주의" verbatim — Korean
  capital-markets law treats those as implicit investment
  recommendation language).
- DO NOT include section ⑦ — the disclaimer is appended by the
  caller (R5).
- DO NOT include any private tokens, keys, email addresses, or
  phone numbers in your output.
- DO NOT translate ticker symbols or canonical English fund/index
  names into Korean.

Numeric integrity rules (R8 trust contract):
- Cite ONLY numbers (price, percentage, market cap, EPS, share count,
  ratio, count) that appear verbatim in the supplied input items.
  If the input does not contain a number, the briefing must not
  introduce one.
- DO NOT compute sums, averages, ratios, or unit conversions across
  input items. Examples of forbidden output: "시총 합산 약 $1.7조",
  "평균 수익률 약 12%", "총 거래대금 ~5조원" when the constituent
  numbers are not themselves provided as a sum / average / ratio in
  the input.
- DO NOT round, approximate, or estimate ("약", "~", "대략", "approx")
  numeric values that are not present in the input. Approximation
  language is reserved for figures that are themselves approximate in
  the source data.
- When a number is essential to the narrative but not present in the
  input, write a qualitative phrase ("실적 집중일", "대형주 다수")
  instead of inventing a figure.
"""

# Placeholders:
#   ``segment_context`` (str — rendered segment scope instructions)
#   ``grouped_sections`` (str — pre-grouped item bullets per Stage 1
#       output; built by ``pipeline.build_section_plan`` rendering)
#   ``unassigned`` (str — bullet list of unassigned items for context;
#       may be the literal "(none)" when the unassigned list is empty)
#   ``target_date`` (str — YYYY-MM-DD)
STAGE2_USER_TEMPLATE: Final[str] = """\
{segment_context}

Pre-grouped items (Stage 1 output):

{grouped_sections}

Unassigned (context for sections ① and ⑥):
{unassigned}

Target date: {target_date}

Return only the markdown.
"""


__all__ = [
    "DEFAULT_SEGMENT_CONTEXT",
    "SEGMENT_CONTEXT_TEMPLATE",
    "SEGMENT_DATA_LIMITED_NOTE",
    "SEGMENT_DATA_READY_NOTE",
    "STAGE1_SYSTEM",
    "STAGE1_USER_TEMPLATE",
    "STAGE2_SECTION_HEADERS",
    "STAGE2_SYSTEM",
    "STAGE2_USER_TEMPLATE",
]
