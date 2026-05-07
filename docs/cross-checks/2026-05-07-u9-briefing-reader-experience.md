# Cross-Check Report: u9 briefing reader experience

**Date**: 2026-05-07
**Scope**: Unit `u9 briefing reader experience` / FR-002 + FR-003 + FR-008 quality correction
**Checked by**: Codex

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 1 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| **Total** | **1** | **100%** |

**Verdict**: ✅ Complete for this slice. The briefing generator now has reader-facing first-screen structure, concise zero-item segment output, source URL propagation, and stronger narrative/citation prompt rules.

## Review Inputs

Five reader-perspective reviews converged on the same issues:

- Domestic briefing had useful material but read like dense bullet clipping.
- US and crypto pages became repetitive data-limited fallback pages.
- Pages lacked H1/date/segment context, segment navigation, source links, and visual/story structure.
- Major claims needed safer wording and provenance.

## Compliance Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Segment first-screen UX | ✅ | `_enhance_reader_experience()` prepends H1, segment nav, and 3-line brief. |
| Data-limited UX | ✅ | `_build_data_limited_body()` emits a concise status document and `generate_briefing()` bypasses Claude for zero-item data-limited segments. |
| Source provenance for writing | ✅ | `_render_grouped_sections()` and `_render_unassigned()` now include item URLs when present. |
| Narrative and safety prompt rules | ✅ | `STAGE2_SYSTEM` asks for newsletter narrative, source links, conservative wording, and grouped notable tickers/assets. |

## Verification

- `uv run pytest tests/unit/briefing/test_budget_happy_path.py tests/unit/briefing/test_prompts.py tests/unit/briefing/test_pipeline_unit.py tests/unit/briefing/test_pipeline_pbt.py -q` ✅ 65 passed
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 140 files already formatted
- `uv run mypy --strict src/` ✅ 52 source files
- `uv run pytest -q` ✅ 971 passed
- `uv run mkdocs build --strict` ✅

## Deferred Follow-Ups

- Actual generated image/chart insertion is not implemented in this slice. The safer next step is data-backed chart/card generation from source items rather than decorative images.
- US/crypto source coverage still depends on the preceding u8/Yahoo fixes being confirmed in a fresh GitHub Actions run.
