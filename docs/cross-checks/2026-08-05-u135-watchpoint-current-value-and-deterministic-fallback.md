# Cross-Check: u135 watchpoint-current-value-and-deterministic-fallback

**Scope**: u135 watchpoint-current-value-and-deterministic-fallback
**Date**: 2026-08-05
**Checked by**: Codex
**Baseline**: `05c6915`
**Implementation head**: `6f9fc64`

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 8 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **8** | **100%** |

**Overall Compliance**: 100%

## Scope mapping

The unit definition maps u135 to FR-002, FR-004, FR-008, FR-009, FR-012,
NFR-003, NFR-006, and R13
(`aidlc-docs/inception/application-design/unit-of-work.md:1963`). This report
checks the bounded u135 contribution to those project requirements.

The UoW annotates FR-004 as “compliance-safe actionability,” while the
canonical requirement heading is Telegram notification. The canonical
requirement governs this cross-check: u135 makes no notifier-contract change,
and the private synthesized count remains separate from the unchanged terminal
public notification DTO.

| Requirement area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 AI briefing | Complete | `src/investo/publisher/watchpoint_matrix.py:716`, `src/investo/publisher/watchpoint_fallback.py:307` | Generated §⑥ rows receive reconciled current values or deterministic observational fallbacks without a new LLM call. |
| FR-004 Telegram notification | Complete | `src/investo/publisher/public_document.py:3114`, `tests/unit/publisher/test_public_document_types_u144.py:496` | The synthesized count is private and additive; the sealed terminal `PublicNotificationSummary` identity and Telegram-facing DTO remain unchanged. |
| FR-008 segmented briefing | Complete | `src/investo/publisher/segment_reader_format.py:305`, `tests/unit/publisher/test_watchpoint_incident_regression_u135.py:101` | Segment identity gates anchor/item ownership, and US, crypto, domestic, and empty paths retain distinct deterministic behavior. |
| FR-009 reader-facing format | Complete | `src/investo/publisher/watchpoint_matrix.py:1160`, `tests/unit/publisher/test_watchpoint_incident_regression_u135.py:67` | Existing u98 card shape is preserved while `현재:` becomes a real value and rich zero-survivor runs produce bounded cards. |
| FR-012 compliance language | Complete | `src/investo/publisher/segment_reader_format.py:329`, `tests/unit/publisher/test_watchpoint_fallback.py:252` | Synthesized rows reuse u64 structure owners and both row-local and final compliance scans; a rejected row is dropped without blocking publish. |
| NFR-003 reliability | Complete | `src/investo/publisher/watchpoint_fallback.py:231`, `tests/unit/publisher/test_watchpoint_fallback.py:165` | Empty/malformed/cross-segment inputs fail closed, close-only domestic anchors remain truthful, and all-row rejection degrades to the canonical note. |
| NFR-006 testing and observability | Complete | `src/investo/briefing/quality_history.py:63`, `aidlc-docs/construction/u135-watchpoint-current-value-and-deterministic-fallback/code/step-7-quality-gate.md:11` | Typed private fallback counts persist to quality history; full planned static/type/unit/integrity gates pass. |
| R13 public-surface safety | Complete | `src/investo/publisher/watchpoint_matrix.py:377`, `tests/unit/briefing/test_quality_history.py` | Existing flat scalar metadata is snapshotted immutably; resolution consumes explicit public candidate fields, adds no raw-metadata logging, and exposes no synthesized/LLM distinction. |

## Acceptance criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-135.1: no source label remains in `현재:`; a matching value resolves or the row is filtered. | Complete | `_anchor_candidate` and exact-token selection in `watchpoint_matrix.py`; 2026-06-29 CoinGecko regression plus unresolved/fuzzy/mixed-boundary tests. |
| AC-135.2: zero survivors plus resolvable data render at most two cards in fixed priority. | Complete | `synthesize_watchpoint_rows`; US RANGE→CFTC, crypto cap, and production close-only domestic reference regressions. |
| AC-135.3: no resolvable key preserves the bounded note byte-identically. | Complete | `test_empty_payload_preserves_existing_bounded_note_byte_identically`. |
| AC-135.4: synthesized cards pass structure/compliance; failures drop without blocking. | Complete | Five closed-template rendered cards pass shared u64 regexes and P0 scans; partial/all-row forced rejection tests preserve typed non-blocking results. |
| AC-135.5: private synthesized count reaches quality history without a public marker. | Complete | Typed count propagation through `PublicDocumentDraft`/`FinalizedPublicDocument`; `test_run_pipeline` and quality-history regressions. |
| AC-135.6: existing u110 LLM filtering stays unchanged. | Complete | No-payload compatibility, canonical rerun, partial subset, u110 fixtures, and the complete publisher suite pass. |

## Fixed contracts

| Contract | Status | Evidence |
|----------|--------|----------|
| 1. Segment-owned reconciled value keys only. | Complete | Immutable payload, `_anchor_belongs_to_segment`, indicator/CFTC group gates, domestic quarantine production-chain test. |
| 2. `현재:` requires a value and exact semantic/token match. | Complete | Source promotion precedes resolution; longest-token/indicator/source/stable precedence and closed Korean-particle boundary tests. |
| 3. Zero survivors trigger at most two rows in fixed priority. | Complete | RANGE/domestic close-reference → CFTC → F&G candidates and cap 2. |
| 4. Closed Korean templates only. | Complete | RANGE, domestic close-reference, CFTC, FEAR, and GREED constants plus exact rendered assertions. |
| 5. Confidence derives from freshness. | Complete | Same-run deterministic rows use `높음`; weekly CFTC uses `보통`; synthesized rows never use the limited confidence. |
| 6. Compliance failure drops a synthesized row without blocking. | Complete | Row-local filter, retained final scan, forced partial/all rejection integration regressions. |
| 7. Private quality marker only. | Complete | Typed count crosses pre-seal assembly and seal; quality history stores the count; public rendering has no marker. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| No public source-shaped current slot. | Complete | Exact 2026-06-29 defect is repaired to `$60,284.00 (+2.23%)`; unresolved rows are omitted. |
| Rich zero-survivor payload renders 1-2 observations. | Complete | US renders RANGE+CFTC; domestic close-only production path renders one reference card. |
| Compliance and empty-data behavior remain safe. | Complete | All five templates pass shared contracts; empty payload remains byte-identical. |
| Card shape, confidence set, and u110 behavior remain compatible. | Complete | Existing renderer/parser/no-payload suites and complete publisher scope pass. |

## Verification

- Ruff and format passed all 17 changed Python files.
- `mypy src` passed 250 source files.
- Publisher and orchestrator suites passed 1,464 tests.
- `uv lock --check`, u135 fixture JSON parse, and `git diff --check` passed.
- No `site_docs` path changed; the plan's conditional strict MkDocs gate did not apply.
- Cumulative fresh-eyes review approved AC-135.1-6, Fixed Contracts 1-7,
  u110/u144 compatibility, R13, and security with no remaining finding.
- Property-Based Testing remains Partial. Security Baseline remains declined;
  no dependency, source, credential, network, external-I/O, or cost surface was
  added.

## Project rule compliance

| Rule | Status | Notes |
|------|--------|-------|
| Existing ownership | Complete | Matrix resolution and sibling fallback remain publisher-owned; orchestration only snapshots and passes plain data. |
| u64/u72/u98/u110 compatibility | Complete | Structure regexes, card renderer, confidence set, and legacy no-payload behavior are reused rather than replaced. |
| u130 domestic quarantine | Complete | Only trusted reconciled domestic anchors reach the close-reference path; no quarantined value is read. |
| u144 lifecycle | Complete | Conversion and count propagation occur before projection/seal; no post-seal Markdown mutation or parsing was added. |
| Graceful degradation | Complete | Malformed, unowned, empty, and compliance-rejected candidates reduce to surviving rows or the canonical limited note. |
| Zero-cost / free API | Complete | No dependency, source, HTTP request, credential, LLM call, or paid service was added. |
| R13 / archive safety | Complete | The existing adapter no-secret invariant is preserved; u135 adds no raw-metadata logging, consumes only explicit public candidate fields, and keeps the synthesized diagnostic private. |

## QA verdict

**APPROVE**

No Critical, High, Medium, or Low finding remains. The implementation matches
the unit definition, Fixed Contracts 1-7, Definition of Done, six acceptance
criteria, and all bounded project requirement mappings.

## Gaps analysis

No u135 gap found.

## Proposed actions

- No development-plan additions.
- No TECH-DEBT items.
- u135 has no remaining construction work.
