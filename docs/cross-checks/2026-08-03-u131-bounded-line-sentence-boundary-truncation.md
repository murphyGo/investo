# Cross-Check: u131 bounded-line-sentence-boundary-truncation

**Scope**: u131 bounded-line-sentence-boundary-truncation
**Date**: 2026-08-03
**Checked by**: Codex
**Baseline**: `b449591`
**Implementation head**: `c527d13`

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 6 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100%

## Scope Mapping

The unit definition maps u131 to FR-002, FR-008, FR-009, FR-012, NFR-003,
and NFR-006
(`aidlc-docs/inception/application-design/unit-of-work.md:1851`). This report
checks the bounded u131 contribution to those project requirements.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 AI briefing | Complete | `src/investo/_internal/text.py:22`, `tests/unit/publisher/test_bounded_line_rendered_regression_u131.py:58` | Generated bounded prose now retains only complete decimal-safe sentence boundaries or an established fallback. |
| FR-008 segment isolation | Complete | `src/investo/publisher/public_document.py:2015`, `tests/unit/publisher/test_public_document_containment_u144.py:275` | The scanner owns only meaning/watchpoint body markers and the actual first viewport; arbitrary isolated section text is not promoted to a truncation finding. |
| FR-009 reader-facing format | Complete | `src/investo/publisher/reader_format/meaning.py:58`, `src/investo/publisher/reader_format/reflow.py:166`, `src/investo/publisher/watchpoint_matrix.py:440` | Meaning, caution, and watchpoint title lines render complete shapes without ellipsis residue. |
| FR-012 plain-language reader aid | Complete | `tests/unit/publisher/test_reader_format_meaning_u76.py:96`, `tests/unit/publisher/test_reader_format_reflow_u71.py:140` | Over-cap text collapses at readable sentence boundaries or to existing deterministic reader guidance. |
| NFR-003 graceful degradation | Complete | `src/investo/_internal/text.py:38`, `tests/unit/_internal/test_text.py:62` | A missing in-cap sentence returns `None`; each surface uses its existing deterministic fallback instead of crashing or emitting a hard cut. |
| NFR-006 testing | Complete | `tests/unit/_internal/test_text.py:24`, `tests/unit/internal/test_surface_quality.py:303`, `aidlc-docs/construction/u131-bounded-line-sentence-boundary-truncation/code/step-7-quality-gate.md:13` | Deterministic, property-based, production-residue, containment, and real-chain regressions cover the shared contract and all owned surfaces. |

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-131.1: Shared bounding retains the last complete `.`, `!`, `?`, or `。` sentence within the cap and never treats a decimal period as a boundary. | Complete | Helper at `src/investo/_internal/text.py:16`; decimal and terminator tests at `tests/unit/_internal/test_text.py:31`. |
| AC-131.2: Meaning lines keep the 80-character cap and use exact `MEANING_FALLBACK` when no complete sentence fits. | Complete | Integration at `src/investo/publisher/reader_format/meaning.py:58`; fallback and complete-sentence tests at `tests/unit/publisher/test_reader_format_meaning_u76.py:96`. |
| AC-131.3: Caution snippets keep the 90-character cap; `본문 참고.` follows only a retained complete sentence, otherwise the exact existing fallback is used. | Complete | Caution-only path at `src/investo/publisher/reader_format/reflow.py:166`; regressions at `tests/unit/publisher/test_reader_format_reflow_u71.py:140`. |
| AC-131.4: Watchpoint titles keep the 30-character threshold, remove whole exact-` · ` trailing segments, preserve an overlong first segment, and append no ellipsis. | Complete | Renderer at `src/investo/publisher/watchpoint_matrix.py:440`; title regressions at `tests/unit/publisher/test_watchpoint_matrix.py:303`. |
| AC-131.5: Existing `summary.truncated_mid_token` blocks legacy meaning, caution, and watchpoint residue without broad body false positives. | Complete | Owned-shape routing at `src/investo/_internal/surface_quality.py:240`; production lines and allowed controls at `tests/unit/internal/test_surface_quality.py:303`; u144 containment at `tests/unit/publisher/test_public_document_containment_u144.py:275`. |
| AC-131.6: The production reader chain emits exact clean owned lines and a second full run is byte-identical. | Complete | Real-chain fixture regression at `tests/unit/publisher/test_bounded_line_rendered_regression_u131.py:58`. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| No public bounded line ends with `...`/`…` or a mid-clause continuation splice. | Complete | Exact producer outputs plus terminal residue scan in the rendered-chain regression. |
| An over-cap first sentence uses the surface's existing deterministic fallback. | Complete | Meaning and caution no-boundary regressions assert exact established fallbacks. |
| The u112 surface gate blocks all three legacy residue shapes on rendered segment markdown. | Complete | Exact 2026-06-29/30 residue strings are blocking with pinned evidence and severity. |
| Existing caps remain unchanged and reruns are idempotent. | Complete | 80/90/30 constants are pinned; helper and full-chain double-application tests are byte-stable. |

## Verification

- Ruff passed for all 13 changed Python files; format reported all 13 already formatted.
- `mypy src` passed for 248 source files.
- Publisher, internal, and `_internal` unit suites passed 1,142 tests.
- `uv lock --check`, all three changed fixture JSON parses, and `git diff --check` passed.
- Cumulative fresh-eyes review: no Critical, High, Medium, or Low findings; AC-131.1-6 and Fixed Contracts 1-5 approved.
- The implementation keeps the established 80/90/30 caps, u134 producer ownership, u135 fallback ownership, and u144 region-local policy.

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Existing ownership | Complete | One shared helper extends u71/u76/u98/u110 owners; no parallel bounding or issue-code family was introduced. |
| Segment isolation | Complete | Body scanning is marker-owned and u144 retains only actual viewport or scanner-owned body findings. |
| Graceful degradation | Complete | No fitting sentence returns the existing per-surface fallback deterministically. |
| Zero-cost / free API | Complete | No dependency, source, network request, credential, or runtime service was added. |
| Secret hygiene | Complete | The fixture is trimmed and redacted; it contains no raw payload, URL, credential, or private destination. |
| No archive backfill | Complete | Production residue is pinned in tests only; no archive or generated-site document was mutated. |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low finding remains. The implementation matches
the unit definition, Fixed Contracts 1-5, Definition of Done, six acceptance
criteria, and bounded project requirement mappings.

## Gaps Analysis

No u131 gap found.

## Proposed Actions

- No development-plan additions.
- No TECH-DEBT items.
- u131 has no remaining construction work.
