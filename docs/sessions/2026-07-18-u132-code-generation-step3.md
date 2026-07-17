# Session Log: 2026-07-18 - u132 - Code Generation Step 3

## Overview

- **Date**: 2026-07-18
- **Unit**: u132 watermark-window-reader-render-and-gate-alignment
- **Stage**: Code Generation
- **Step**: 3 of 7 - Align the watermark gate with the reader renderer
- **Worktree**: `/private/tmp/investo-u132`
- **Branch**: `codex/u132-watermark-window`

## Work Summary

Aligned `_WATERMARK_LINE_RE` and `_bad_watermark_window()` with the Step 2
reader contract. Valid KST, NY, and UTC lines pass. Missing `수집창`,
unbalanced parentheses, the production legacy `Z, Z)` tail, and all other
bold watermark variants fail closed under the existing
`watermark.window_bracket` issue code.

The Step 1 production spy now expects the repaired legacy line to be blocked
rather than returned from the segment chain.

## Files Changed

- Modified: `src/investo/_internal/surface_quality.py`
- Modified: `tests/unit/internal/test_surface_quality.py`
- Modified: `tests/unit/publisher/test_segment_reader_surface_quality.py`
- Modified: `aidlc-docs/construction/plans/u132-watermark-window-reader-render-and-gate-alignment-code-generation-plan.md`
- Modified: `aidlc-docs/aidlc-state.md`
- Modified: `aidlc-docs/audit.md`
- Modified: `aidlc-docs/construction/u132-watermark-window-reader-render-and-gate-alignment/code/summary.md`
- Created: `docs/sessions/2026-07-18-u132-code-generation-step3.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Reuse `watermark.window_bracket` | u112 already owns the public issue code; u132 aligns it with production instead of adding another gate family. |
| Fail closed for bold watermark variants | A bold `기준 시각` line is the canonical reader surface and must match the complete contract. |
| Keep plain lookalikes out of scope | Noncanonical text is not the production watermark and should not trigger this specialized issue code. |
| Test KST, NY, and UTC directly | This closes the review residual that only NY had direct gate-acceptance coverage. |

## Code Review Results

| Category | Status |
|----------|--------|
| Correctness | Pass |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

Fresh-eyes review found no issues. Its only residual risk, direct gate
acceptance being NY-only, was addressed with KST and UTC cases.

## Validation

- Focused surface, renderer, and segment-chain tests: 68 passed.
- Scoped Ruff check: passed.
- Scoped Ruff format check: passed.
- `git diff --check`: passed.

## Potential Risks

- Full-chain byte-stability for a newly rendered segment is intentionally the
  next plan item, Step 4.

## TECH-DEBT Items

- None.
