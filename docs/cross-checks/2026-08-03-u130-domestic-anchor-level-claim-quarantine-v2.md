# Cross-Check: u130 domestic-anchor-level-claim-quarantine-v2

**Scope**: u130 domestic-anchor-level-claim-quarantine-v2
**Date**: 2026-08-03
**Checked by**: Codex
**Baseline**: `08b241f`
**Implementation head**: `2ca93a7`

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

The unit definition maps u130 to FR-001, FR-002, FR-003, FR-008, FR-009,
NFR-003, NFR-006, and R13
(`aidlc-docs/inception/application-design/unit-of-work.md:1825`). This report
checks the bounded u130 contribution to those project requirements.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-001 data collection trust | Complete | `src/investo/orchestrator/domestic_anchor_quarantine.py:257`, `tests/unit/orchestrator/test_domestic_anchor_quarantine.py:306` | Reuses the existing published-archive walk and selects the newest domestic anchor in the exact prior seven-calendar-day window. No source adapter is added. |
| FR-002 briefing correctness | Complete | `src/investo/publisher/anchor_assertion_gate.py:181`, `tests/unit/publisher/test_u130_rendered_regression.py:35` | Unsupported precise domestic levels are removed from generated prose before publication. |
| FR-003 public publishing | Complete | `src/investo/publisher/anchor_assertion_gate.py:266`, `tests/unit/publisher/test_u130_rendered_regression.py:39` | The production reader-format/publisher gate removes the incident values and terminally scans for survivors. |
| FR-008 segment isolation | Complete | `src/investo/publisher/anchor_assertion_gate.py:250`, `aidlc-docs/construction/u130-domestic-anchor-level-claim-quarantine-v2/code/step-6-us-crypto-byte-stability.md:14` | Bare-level matching is domestic-only; four US/crypto baseline characterizations are byte-identical. |
| FR-009 reader-facing format | Complete | `tests/unit/publisher/test_anchor_assertion_gate.py:47`, `tests/unit/publisher/test_u130_rendered_regression.py:44` | TL;DR, list/body, and reader-callout shapes are gated while supported neighboring prose remains. |
| NFR-003 graceful degradation | Complete | `src/investo/orchestrator/domestic_anchor_quarantine.py:323`, `tests/unit/orchestrator/test_domestic_anchor_quarantine.py:195` | Missing or invalid history fails open without a crash; only evidence-backed discontinuity withholds a candidate. |
| NFR-006 testing | Complete | `tests/unit/publisher/test_anchor_assertion_gate.py:151`, `tests/unit/orchestrator/test_domestic_anchor_quarantine.py:245`, `aidlc-docs/construction/u130-domestic-anchor-level-claim-quarantine-v2/code/step-7-quality-gate.md:17` | Deterministic unit regressions plus Hypothesis cover idempotency and threshold boundaries; the planned suites are green. |
| R13 secret hygiene | Complete | `tests/fixtures/u130/README.md:3`, `aidlc-docs/construction/u130-domestic-anchor-level-claim-quarantine-v2/code/step-5-rendered-regression-fixture.md:11` | The incident fixture is trimmed and redacted; no source, secret, credential, raw payload, or network surface is introduced. |

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-130.1: An unsupported domestic core-symbol bare level is gated across body prose, lists, and reader callouts. | Complete | Domestic-only detector and dispatcher at `src/investo/publisher/anchor_assertion_gate.py:181`; prefix-shape regression at `tests/unit/publisher/test_anchor_assertion_gate.py:264`. |
| AC-130.2: All four 2026-06-30 KOSPI 150.00 surfaces are removed. | Complete | Real-chain fixture regression at `tests/unit/publisher/test_u130_rendered_regression.py:35`; all values removed and neighboring prose retained. |
| AC-130.3: Strict >15% index/FX and >30% large-cap discontinuities against the newest prior-seven-day value are withheld and recorded. | Complete | Classification/loader at `src/investo/orchestrator/domestic_anchor_quarantine.py:127`; boundaries, 477→344, newest/weekend selection, and metadata tests at `tests/unit/orchestrator/test_domestic_anchor_quarantine.py:171`. |
| AC-130.4: No precise claim for a rewritten symbol survives elsewhere in the same document. | Complete | Canonical second pass at `src/investo/publisher/anchor_assertion_gate.py:300`; cross-section residual regression at `tests/unit/publisher/test_anchor_assertion_gate.py:47`. |
| AC-130.5: Gate application is byte-idempotent. | Complete | Property-based double-application regression at `tests/unit/publisher/test_anchor_assertion_gate.py:151` plus deterministic replacement behavior. |
| AC-130.6: US and crypto behavior is byte-unchanged. | Complete | Four output/finding hashes match the pre-u130 baseline in `aidlc-docs/construction/u130-domestic-anchor-level-claim-quarantine-v2/code/step-6-us-crypto-byte-stability.md:14`; existing US/crypto tests pass at `tests/unit/publisher/test_anchor_assertion_gate.py:515`. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| Bare level claims without trusted anchors are gated like move claims. | Complete | Shared precise-claim dispatcher and rendered incident regression. |
| Discontinuous domestic anchors are quarantined at the fixed thresholds. | Complete | Strict-threshold property tests and exact KOSDAQ incident case. |
| Same-symbol decisions remain consistent throughout one document. | Complete | Canonical second pass, survivor scan, and byte-idempotency tests. |
| Quality metadata records `discontinuous`; US/crypto stays stable. | Complete | `_build_quality_snapshot` reason ordering at `pipeline.py:1990-2023`; byte comparison evidence. |

## Verification

- Scoped Ruff and format: passed for all 10 changed Python files.
- `mypy src`: passed for 248 source files.
- Focused u130 regressions: 69 passed.
- Full planned publisher and orchestrator suites: 1,410 passed.
- `uv lock --check` and `git diff --check`: passed.
- Cumulative fresh-eyes review: no Critical, High, Medium, or Low findings; all six ACs and all five Fixed Contracts approved.
- Cumulative implementation diff: no `archive/`, `site_docs/`, dependency, source-adapter, or generated-document change.

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Existing ownership | Complete | Extends u70/u109 owners and reuses the archive iterator; no parallel gate, scanner, or label registry. |
| Segment isolation | Complete | The new bare-level path is domestic-only and US/crypto byte behavior is pinned. |
| Graceful degradation | Complete | Missing/unreadable/non-finite history does not crash or suppress a candidate. |
| Zero-cost / free API | Complete | No network, dependency, source, key, or runtime service is added. |
| Secret hygiene | Complete | Only redacted deterministic fixture data is committed; no raw metadata or credential surface. |
| No archive backfill | Complete | No archive or generated-site path appears in the u130 diff. |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low finding remains. The implementation matches
the unit definition, Fixed Contracts 1-5, Definition of Done, six acceptance
criteria, and bounded project requirement mappings.

## Gaps Analysis

No u130 gap found.

## Proposed Actions

- No development-plan additions.
- No TECH-DEBT items.
- u130 has no remaining construction work.
