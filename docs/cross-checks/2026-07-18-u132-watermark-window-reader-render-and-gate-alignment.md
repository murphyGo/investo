# Cross-Check: u132 watermark-window-reader-render-and-gate-alignment

**Scope**: u132 watermark-window-reader-render-and-gate-alignment
**Date**: 2026-07-18
**Checked by**: Codex
**Baseline**: `0af9c7a`
**Implementation head**: `8682b94`

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 5 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **5** | **100%** |

**Overall Compliance**: 100%

## Scope Mapping

The unit definition maps u132 to FR-002, FR-003, FR-008, FR-009, and
NFR-006 (`aidlc-docs/inception/application-design/unit-of-work.md:1880`).
Its bounded purpose is to replace the malformed half-open watermark with a
reader-readable collection window, align the existing surface gate with the
real producer, preserve the line through the full reader chain, and avoid any
archive backfill.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | Complete | `src/investo/briefing/_reader_enhance/enhancement.py:91`, `tests/unit/briefing/test_summary_fidelity.py:250` | The producer uses the Korean `수집창 ... (종료 미포함)` explanation instead of mathematical half-open notation. |
| FR-003 static web publishing | Complete | `src/investo/_internal/surface_quality.py:300`, `tests/unit/publisher/test_segment_reader_surface_quality.py:148` | The actual segment publish gate accepts the fixed line and blocks malformed watermark lines before publication. |
| FR-008 segmented briefing | Complete | `tests/unit/briefing/test_summary_fidelity.py:250`, `tests/unit/models/test_segment_market_clock.py:23` | Domestic, US, and crypto watermarks retain their KST, NY, and UTC market-window semantics and match aggregator windows. |
| FR-009 reader-facing format | Complete | `tests/integration/test_briefing_reader_format.py:193` | The producer line remains byte-identical through summary repair, surface repair, and the complete segment reader-format chain; placement and disclaimer metadata remain intact. |
| NFR-006 testing | Complete | `tests/unit/internal/test_surface_quality.py:213`, `tests/unit/publisher/test_segment_reader_surface_quality.py:104` | Success, legacy, missing-token, unbalanced-parenthesis, repair-path, and full-chain cases are covered. Current cross-check run: 100 passed. |

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-132.1: Newly rendered markdown contains the balanced, bracket-free `수집창 ... ~ ... (종료 미포함)` watermark. | Complete | Producer implementation at `src/investo/briefing/_reader_enhance/enhancement.py:91`; exact KST/NY/UTC assertions at `tests/unit/briefing/test_summary_fidelity.py:250`. |
| AC-132.2: The verbatim 2026-06-30 legacy dangling watermark blocks publication. | Complete | Gate predicate at `src/investo/_internal/surface_quality.py:300`; verbatim public-line regression at `tests/unit/publisher/test_segment_reader_surface_quality.py:166`. |
| AC-132.3: The watermark is byte-stable through the full repair and reader-format chain. | Complete | Producer-to-chain assertion at `tests/integration/test_briefing_reader_format.py:193`, including uniqueness, target date, and disclaimer preservation. |
| AC-132.4: Valid shapes pass; legacy, missing `수집창`, and unbalanced parentheses fail. | Complete | Direct KST/NY/UTC and invalid-shape matrix at `tests/unit/internal/test_surface_quality.py:213`; public gate evidence assertion at `tests/unit/publisher/test_segment_reader_surface_quality.py:177`. |
| AC-132.5: No committed archive file is modified. | Complete | `git diff --name-only 0af9c7a..8682b94 -- archive site_docs` returned no paths. The cumulative implementation diff contains only source, tests, and development records. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| Published watermark is balanced and bracket-free. | Complete | `enhancement.py:114`, three segment renderer tests. |
| Legacy `..., ...Z)` shape is a blocking surface issue on new writes. | Complete | `_bad_watermark_window`, full segment-gate regression. |
| Watermark survives the complete reader-format chain unchanged. | Complete | Integration byte-stability test. |
| Legacy committed archives are not rewritten. | Complete | No `archive/` or `site_docs/` path in the committed u132 diff. |

## Verification

- Cross-check focused suite: 100 passed.
- Scoped Ruff and format checks: passed for all 13 changed Python files.
- `mypy src`: passed for 226 source files.
- Planned Step 7 scope: 1,440 passed plus 2 baseline-identical DEBT-081 failures.
- Same Step 7 scope with only the two DEBT-081 tests deselected: 1,440 passed.
- Both DEBT-081 failures reproduce unchanged at pre-u132 baseline `0af9c7a`.
- Cumulative fresh-eyes review: no findings; AC-132.1 through AC-132.5 confirmed.

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| No Anthropic SDK | Complete | No LLM client or dependency change. |
| Module boundary | Complete | Application changes stay inside `_internal` and `briefing`; no new cross-unit import. |
| Zero-cost / free API | Complete | Pure rendering and validation logic; no network, key, or source change. |
| Disclaimer enforcement | Complete | Full-chain regression preserves the disclaimer field; existing publish verification remains unchanged. |
| Telegram channel separation | Complete | Notifier code and channel IDs are untouched. |
| Secret hygiene | Complete | No raw metadata, secret, environment, or fixture-recording surface is added. |
| No archive backfill | Complete | Committed u132 diff contains no archive or generated-site files. |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low u132 findings remain. The implementation
matches its unit definition, plan contracts, five acceptance criteria, and
project rules.

## Gaps Analysis

No u132 gaps found. DEBT-081 remains an existing repository-wide test debt;
it is baseline-identical and outside this unit's changed surfaces.

## Proposed Actions

- No development-plan additions.
- No new TECH-DEBT items.
- Mark the u132 cross-check complete in `aidlc-docs/aidlc-state.md`.
