# u51 TL;DR Block + Number Bold Inversion — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u51 tldr-block-and-number-bold-inversion
**Status**: Complete (7/7 steps)
**FR**: FR-009
**Commit**: `224a422` (`Land u51 + u52 + u53 — reader-format, prior-briefing carryover, KRX flows + sector ETFs`)

## Goal

Close the reader-facing format defects found in the 2026-05-11 US-equity briefing: missing self-contained TL;DR, prose-wall market anchors, bold-prefix pseudo-headings, plain critical numbers, repetitive `여부` endings, and repeated glossary expansions.

## Key Deliverables

- `publisher/reader_format.py`: deterministic post-format chain for TL;DR insertion, H3 conversion, numeric bolding, action-ratio WARNs, glossing dedupe, first-viewport disclaimer preservation, and idempotence.
- `publisher/anchor_table.py`: market-anchor table renderer replacing the single prose anchor line.
- Orchestrator wire-through in `_apply_reader_format_to_segments`, with reader-format applied after enhancement and before disclaimer verification.
- Stage-2 prompt rules for TL;DR, H3 sub-headings, bold numeric facts, and actionability language.
- Regression coverage in `tests/unit/publisher/test_reader_format.py`, `tests/unit/publisher/test_anchor_table.py`, and `tests/integration/test_briefing_reader_format.py`.

## Quality Gate

This unit landed as part of the combined Wave 7 commit with u52/u53. Combined gate at closeout:

| Gate | Result |
|------|--------|
| `ruff check .` | clean |
| `ruff format --check` | clean |
| `mypy --strict src/` | clean |
| `pytest -q` | 1910 passed after the combined u51/u52/u53 wave |
| `mkdocs build --strict` | clean |

## Notes

- The action-ratio check is WARN-only by design; regeneration/blocking is reserved for a later unit if field evidence requires it.
- u40 glossary callouts remain unchanged. u51 only dedupes repeated inline parenthetical glossing inside the rendered briefing body.
