# Cross-Check: u134 callout-and-diagnostic-line-composition-repair

**Scope**: u134 callout-and-diagnostic-line-composition-repair
**Date**: 2026-08-03
**Checked by**: Codex
**Baseline**: `beb0f4b`
**Implementation head**: `b2d6023`

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

The unit definition maps u134 to FR-002, FR-008, FR-009, NFR-003, and NFR-006
(`aidlc-docs/inception/application-design/unit-of-work.md:1932`). This report
checks the bounded u134 contribution to those project requirements.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 AI briefing | Complete | `src/investo/briefing/_assembly/summary_extraction.py:87`, `src/investo/briefing/_reader_enhance/enhancement.py:99` | Driver and low-coverage conclusion values are composed at their deterministic producer/public-render seams. |
| FR-008 segmented briefing | Complete | `src/investo/publisher/reader_format/reflow.py:142`, `src/investo/publisher/channel_anchor_block.py:198` | Per-segment diagnostics and crypto channel baselines use canonical bounded formats. |
| FR-009 reader-facing format | Complete | `tests/unit/publisher/test_u134_rendered_regression.py:51`, `tests/unit/publisher/test_reader_format_reflow_u71.py:101` | The four production defects are absent; public prefix and protected diagnostics retain their intended boundary. |
| NFR-003 reliability | Complete | `src/investo/publisher/reader_format/reflow.py:402`, `src/investo/_internal/decimal_format.py:12` | No-anchor paths reproduce existing public projection, and hostile/oversized Decimal strings fail closed before expansion. |
| NFR-006 testing | Complete | `aidlc-docs/construction/u134-callout-and-diagnostic-line-composition-repair/code/step-6-quality-gate.md:5`, `tests/unit/publisher/test_u134_rendered_regression.py:86` | Planned suites, exact production fixture, parser agreement, resource boundaries, and repaired-input idempotence pass. |

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-134.1: Driver renders `{heading} — {sentence}` or heading-only past the existing budget. | Complete | `_driver_summary` at `src/investo/briefing/_assembly/summary_extraction.py:87`; exact 2026-06-30 and budget regressions in `tests/unit/briefing/test_summary_fidelity.py`. |
| AC-134.2: Low-coverage note is its own terminated sentence. | Complete | `_render_public_conclusion` at `src/investo/briefing/_reader_enhance/enhancement.py:99`; missing/present/quote/bracket terminators and the exact archived two-sentence shape pass. |
| AC-134.3: Diagnostics show five canonical slots and no pointer sentence; downstream parsers agree. | Complete | Composer at `src/investo/publisher/reader_format/reflow.py:142`; full-chain/parser regression at `tests/unit/publisher/test_reader_format_reflow_u71.py:101`. |
| AC-134.4: Funding rows use identical shortest-exact plain values. | Complete | Shared formatter at `src/investo/_internal/decimal_format.py:12`; both renderers and equality regression at `tests/unit/publisher/test_channel_anchor_block.py:191`. |
| AC-134.5: Public source-count projection remains unchanged. | Complete | No-anchor restoration at `src/investo/publisher/reader_format/reflow.py:402`; exact public projection regression at `tests/unit/publisher/test_reader_format_reflow_u71.py:121` and exact compact chip in the rendered fixture. |
| AC-134.6: Repaired reruns are byte-stable. | Complete | Driver, conclusion, reader chain, and noisy-versus-repaired funding blocks are byte-equal in `tests/unit/publisher/test_u134_rendered_regression.py:86`. |

## Fixed Contracts

| Contract | Status | Evidence |
|----------|--------|----------|
| 1. Driver uses spaced em dash and heading-only budget fallback. | Complete | Producer implementation and exact archived/budget/conjunction-tail regressions. |
| 2. Conclusion uses `PUBLIC_LOW_COVERAGE_TEXT` as a full sentence; inline uses remain. | Complete | Conclusion-only renderer plus audit of generic projection/watchpoint inline call sites. |
| 3. Protected diagnostics retain numeric slots; reader-visible projections do not expose them. | Complete | Full-chain canonical composer, exact public prefix assertions, no-anchor fallback, and quality/evidence parser agreement. |
| 4. Funding Decimal uses shortest exact fixed-point form with no rounding or exponent. | Complete | Bounded tuple formatter, renderer equality, huge exponent/zero/boundary tests, and 10,000 seeded reference comparisons. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| Driver splice eliminated. | Complete | Exact archived heading/body renders a visible em dash and contains no `마감 나스닥 기사` shape. |
| Low-coverage suffix is a complete sentence. | Complete | Exact archived conclusion ends with the canonical full sentence and contains no legacy splice. |
| Collapsed source counts are numeric/미집계 and pointer-free. | Complete | Five-slot line appears only inside `<details>`; exact compact chip remains outside. |
| Funding rate has no trailing-zero noise. | Complete | Both ⓪-A and ⓪-B render `0.0001`; noisy source text is absent. |

## Verification

- Ruff and format passed all 13 changed Python files.
- `mypy src` passed 249 source files.
- Publisher, briefing, and internal suites passed 1,947 tests.
- `uv lock --check`, u134 fixture JSON parse, and `git diff --check` passed.
- Cumulative fresh-eyes review approved AC-134.1-6 and Fixed Contracts 1-4
  with no Critical, High, Medium, or Low findings; 420 independent targeted
  tests and 10,000 seeded Decimal/reference comparisons passed.
- Property-Based Testing remains Partial. Security Baseline remains declined;
  no dependency, source, credential, network, external-I/O, or cost surface was
  introduced, while the external-exponent memory boundary is explicitly capped.

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Existing ownership | Complete | Driver assembly, conclusion rendering, reader reflow, and existing funding rows own their respective changes; no new gate family. |
| u131/u127 compatibility | Complete | Shared truncation caps/algorithm and reject predicate are unchanged. |
| u108/u144 boundary | Complete | Numeric counts survive only into protected diagnostics; fail paths restore existing public projection; no post-seal mutation. |
| Graceful degradation | Complete | Invalid/non-finite/oversized rates use existing missing behavior; malformed count lines use existing public projection. |
| Zero-cost / free API | Complete | No dependency, source, HTTP call, credential, or paid service was added. |
| R13 / archive safety | Complete | Fixture contains only public archived prose and deterministic numbers; no archive backfill or raw/private metadata. |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low finding remains. The implementation matches
the unit definition, Fixed Contracts 1-4, Definition of Done, six acceptance
criteria, and all bounded project requirement mappings.

## Gaps Analysis

No u134 gap found.

## Proposed Actions

- No development-plan additions.
- No TECH-DEBT items.
- u134 has no remaining construction work.
