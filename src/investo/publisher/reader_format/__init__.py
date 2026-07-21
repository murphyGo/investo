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

This package owns the post-format pass that *fixes 2 through 6* on top of
already-generated Stage-2 markdown (1 is a Stage 2 prompt rule + a fallback
heuristic here for the rare miss). All helpers are pure ``str -> str``.

u81 (2026-05-28) split the original 1208-line module into one submodule per
transformation pass (``tldr`` / ``headings`` / ``emphasis`` /
``watchpoint_audit`` / ``glossary`` / ``meaning`` / ``disclaimer`` /
``sentence_audit`` / ``reflow``), with shared markers in ``_constants`` and
the pass-ordering chain (:func:`apply_reader_format`,
:func:`reflow_first_viewport`) living here. The public import path
``from investo.publisher.reader_format import …`` is unchanged: every public
name is re-exported below, and the pass order is byte-for-byte identical.

Module boundary
~~~~~~~~~~~~~~~
* Imports stdlib only (``re``, ``logging``) plus ``briefing.segments`` for
  the ``MarketSegment`` type.
* Does NOT import from ``briefing/`` (beyond the segment type) / ``sources/``
  / ``notifier/`` / ``orchestrator/`` (project rule 2: ``orchestrator`` is
  the only caller permitted to import publisher helpers).

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

import re
from typing import Final

from investo._internal.public_quality_language import (
    first_forbidden_public_evidence,
    project_public_quality_language,
)

# Private regexes consumed by ``investo.publisher.watchpoint_matrix`` via the
# historical ``from investo.publisher.reader_format import _BULLET_RE`` path.
# Aliased (``X as X``) so mypy --strict treats them as explicit re-exports
# (PEP 484 no-implicit-reexport) — preserving that caller's import unchanged.
from investo.publisher.reader_format._constants import _BULLET_RE as _BULLET_RE
from investo.publisher.reader_format._constants import _SECTION_HEADER_RE as _SECTION_HEADER_RE
from investo.publisher.reader_format._constants import (
    MEANING_FALLBACK,
    MEANING_MARKER,
    MEANING_MAX_CHARS,
    TLDR_HEADER,
)
from investo.publisher.reader_format.disclaimer import (
    SHORT_DISCLAIMER_CRYPTO,
    SHORT_DISCLAIMER_EQUITY,
    emit_first_viewport_disclaimer,
)
from investo.publisher.reader_format.emphasis import wrap_numbers_bold
from investo.publisher.reader_format.glossary import dedupe_glossings
from investo.publisher.reader_format.headings import enforce_h3_subheadings
from investo.publisher.reader_format.meaning import normalize_meaning_lines
from investo.publisher.reader_format.public_projection import project_public_markdown
from investo.publisher.reader_format.reflow import (
    DIAGNOSTICS_SUMMARY_LABEL,
    SNIPPET_MAX_CHARS,
    bound_summary_snippet,
    reflow_first_viewport,
)
from investo.publisher.reader_format.sentence_audit import (
    FILLER_DENSITY_PER_1000_THRESHOLD,
    SENTENCE_ENDING_DOMINANCE_THRESHOLD,
    FillerDensityReport,
    SentenceEndingReport,
    check_filler_phrase_density,
    check_sentence_ending_diversity,
)
from investo.publisher.reader_format.tldr import ensure_tldr_block

# Private watch-point regexes consumed by ``watchpoint_matrix`` (see above).
from investo.publisher.reader_format.watchpoint_audit import (
    _WATCHPOINT_IMPLICATION_RE as _WATCHPOINT_IMPLICATION_RE,
)
from investo.publisher.reader_format.watchpoint_audit import (
    _WATCHPOINT_SOURCE_RE as _WATCHPOINT_SOURCE_RE,
)
from investo.publisher.reader_format.watchpoint_audit import (
    _WATCHPOINT_TRIGGER_RE as _WATCHPOINT_TRIGGER_RE,
)
from investo.publisher.reader_format.watchpoint_audit import (
    ACTION_RATIO_THRESHOLD,
    check_action_bullet_ratio,
    check_watchpoint_actionability,
)

_KR_CODE_LINK_RE = re.compile(r"(?<!\\)\[(\d{6})\](?=\()")
_DATA_LIMITED_STANDALONE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>[^\S\n]*(?:>[^\S\n]*)?)(?:데이터[^\S\n]*부족|자료[^\S\n]*부족)[.。]?[^\S\n]*$",
    re.MULTILINE,
)
_DATA_LIMITED_READER_COPY: Final[str] = "오늘 확인 가능한 새 신호는 제한적입니다."


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
      5. ``normalize_meaning_lines`` — u76: bound/dedupe the per-section
         ``그래서 의미는?`` lines after structural changes so placement and
         length are validated before the downstream compliance scan.
      6. ``check_action_bullet_ratio`` — pure diagnostic; runs last so it
         observes the final shape.
    """
    # Keep the canonical footer byte-identical for publish verification.
    body, footer = _split_disclaimer_footer(text)
    out = ensure_tldr_block(body, segment=segment)
    out = enforce_h3_subheadings(out)
    out = wrap_numbers_bold(out)
    out = dedupe_glossings(out)
    out = normalize_meaning_lines(out, segment=segment)
    out = escape_krx_stock_code_link_fragments(out)
    out = normalize_data_limited_reader_copy(out)
    combined = out + footer
    check_action_bullet_ratio(combined, segment=segment)
    check_watchpoint_actionability(combined, segment=segment)
    return combined


def escape_krx_stock_code_link_fragments(text: str) -> str:
    """Prevent ``종목[000000](가격...)`` from becoming a Markdown link."""
    return _KR_CODE_LINK_RE.sub(r"\\[\1\\]", text)


def normalize_data_limited_reader_copy(text: str) -> str:
    """Rewrite terse data-limited placeholders into reader prose."""

    def _repl(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{_DATA_LIMITED_READER_COPY}"

    lines: list[str] = []
    in_code = False
    in_details = False
    for raw_line in _DATA_LIMITED_STANDALONE_RE.sub(_repl, text).splitlines(keepends=True):
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        protected = (
            in_code or in_details or stripped.startswith("|") or "수집/품질 진단" in stripped
        )
        if stripped.startswith("```"):
            in_code = not in_code
        if "<details" in line:
            in_details = True
        if "</details>" in line:
            in_details = False
        if protected:
            lines.append(raw_line)
            continue
        if first_forbidden_public_evidence(line) is None:
            lines.append(raw_line)
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        projected = project_public_quality_language(line)
        lines.append(projected + newline)
    return "".join(lines)


def _split_disclaimer_footer(text: str) -> tuple[str, str]:
    anchor = "## ⑦ 면책조항"
    anchor_idx = text.find(anchor)
    if anchor_idx == -1:
        return text, ""
    return text[:anchor_idx], text[anchor_idx:]


__all__ = [
    "ACTION_RATIO_THRESHOLD",
    "DIAGNOSTICS_SUMMARY_LABEL",
    "FILLER_DENSITY_PER_1000_THRESHOLD",
    "MEANING_FALLBACK",
    "MEANING_MARKER",
    "MEANING_MAX_CHARS",
    "SENTENCE_ENDING_DOMINANCE_THRESHOLD",
    "SHORT_DISCLAIMER_CRYPTO",
    "SHORT_DISCLAIMER_EQUITY",
    "SNIPPET_MAX_CHARS",
    "TLDR_HEADER",
    "FillerDensityReport",
    "SentenceEndingReport",
    "apply_reader_format",
    "bound_summary_snippet",
    "check_action_bullet_ratio",
    "check_filler_phrase_density",
    "check_sentence_ending_diversity",
    "check_watchpoint_actionability",
    "dedupe_glossings",
    "emit_first_viewport_disclaimer",
    "enforce_h3_subheadings",
    "ensure_tldr_block",
    "escape_krx_stock_code_link_fragments",
    "normalize_data_limited_reader_copy",
    "normalize_meaning_lines",
    "project_public_markdown",
    "reflow_first_viewport",
    "wrap_numbers_bold",
]
