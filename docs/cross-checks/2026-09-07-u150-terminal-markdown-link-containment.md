# Cross-check — u150 terminal-markdown-link-containment

**Scope**: component `u150 terminal-markdown-link-containment`
**Date**: 2026-09-07
**Checked by**: Codex
**Implementation**: `e867b0f0f21a3e048d5b5a345c7e07a3e04bf1d0`; production commits `b949c54a711eed0ad54ae6af13dded69cbb4a814` and `02607d3874b075bdf23382b26187eacf1f2d6bbc`

## Summary

| Status | Count | Percentage |
| --- | ---: | ---: |
| ✅ Complete | 14 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total ACs** | **14** | **100%** |

**Verdict**: APPROVE — COMPLETE. AC-150.1 through AC-150.14 are implemented,
tested, documented, delivered, and production-qualified with no development or
operational gap.

## Requirement traceability

| Requirement | Status | u150 evidence | Notes |
| --- | --- | --- | --- |
| FR-003 — static web publication | ✅ | `src/investo/publisher/public_document.py:1928-2139`; pipeline integration tests | Link-only presentation defects retain a sealed archive document; genuine blocks retain valid-sibling publication. |
| FR-004 — Telegram briefing notification | ✅ | `src/investo/orchestrator/pipeline.py:3350-3378`; `test_run_pipeline_link_only_defect_keeps_three_sealed_segments_and_telegram`; integration test at `tests/integration/test_pipeline.py:324` | Telegram consumes terminal `PublicNotificationSummary` values and never the blocked target. |
| FR-006 — permanent history | ✅ | sealed exact-byte writer remains unchanged; `tests/integration/test_pipeline.py:324` | Repaired bytes are sealed before archive write and invalid targets are absent. |
| FR-011 — numeric/freshness gate | ✅ | terminal hard-gate collection at `public_document.py:2743-2804`; `test_non_domestic_numeric_claims_remain_fail_closed` | u149 remains the only domestic numeric-degradation owner; US/crypto behavior is unchanged. |
| FR-012 / NFR-004 — compliance and disclaimer | ✅ | exhaustive terminal collection and `test_link_action_does_not_mask_hard_gate_and_partial_commit_exits_two` | Link containment cannot hide canonical disclaimer or other compliance failure. |
| NFR-003 — graceful degradation | ✅ | shape/block policy and survivor pipeline tests | Eligible presentation defects stay local; protected or simultaneous hard defects remain typed partial failures. |
| NFR-005 — maintainability | ✅ | one scanner owner, one exhaustive table, one finalizer path; DESIGN TD-014 | No parallel parser, state, retry loop, or fallback-copy family was added. |
| NFR-006 — testing | ✅ | example tests, Hypothesis properties, policy totality tests, finalizer/orchestrator/integration tests; full suite 4,516 passed | The project's partial PBT opt-in is satisfied for the pure transform. |
| NFR-007 / R13 — bounded disclosure | ✅ | residual snapshot at `public_document.py:2699-2723`; negative tests starting at `test_public_document_containment_u144.py:612` and `test_main.py:621` | Failure outputs exclude evidence, targets, URLs, Markdown, shapes, region IDs, payloads, and secrets. |

## Acceptance criteria detail

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC-150.1 — one canonical detector | ✅ | `SurfaceLinkShape`, transform, and link scanner live in `src/investo/_internal/surface_quality.py:19-26,229-273,439-482`; policy consumes shape only at `_public_document_policy.py:232-252`. |
| AC-150.2 — exact recoverable outputs | ✅ | example cases in `tests/unit/internal/test_surface_quality.py`; balanced/escaped targets and optional-title ownership are pinned; reference definitions remain unchanged and select replacement later. |
| AC-150.3 — valid/protected byte stability | ✅ | `test_valid_links_remain_byte_identical` and `test_protected_regions_remain_byte_identical` in `test_surface_quality_properties.py:86-156`. |
| AC-150.4 — deterministic idempotence | ✅ | `test_recoverable_transform_is_exact_idempotent_and_closes_scanner` plus stable-order property at `test_surface_quality_properties.py:57-125`. |
| AC-150.5 — recoverable seal/replacement | ✅ | finalizer repair/replacement tests in `test_public_document_containment_u144.py`; link-only pipeline test at `test_run_pipeline.py:1679`; u71/u76 post-link invariants at `test_numeric_degradation_containment_u149.py:391-451`. |
| AC-150.6 — residual owned-region replacement | ✅ | `test_unrecoverable_first_viewport_link_uses_the_stronger_whole_region_replacement` and required-heading/sibling assertions in the same containment suite. |
| AC-150.7 — optional artifact behavior | ✅ | `test_invalid_link_chart_and_visual_are_omitted_without_dropping_segment` and staged-artifact assertions at `test_public_document_containment_u144.py:493-551`. |
| AC-150.8 — protected region fail-close | ✅ | exhaustive 16-block matrix tests at `tests/unit/publisher/test_public_document_policy_u144.py:140-199` and protected-terminal snapshot tests at `test_public_document_containment_u144.py:749-804`. |
| AC-150.9 — eligibility and hard precedence | ✅ | one-action resolver at `public_document.py:1952-1993`; stronger-action and simultaneous-hard-gate tests at `test_public_document_containment_u144.py:552-706`. |
| AC-150.10 — bounded residual diagnostics | ✅ | `_TerminalHardGateSnapshot` and `_terminal_failure_issue_codes` at `public_document.py:2736-2761`; bounds tests in `test_public_document_containment_u144.py`. |
| AC-150.11 — numeric non-regression | ✅ | u149 global-post-action guard at `test_numeric_degradation_containment_u149.py:320`; US/crypto pipeline fail-close at `test_run_pipeline.py:2206`. |
| AC-150.12 — delivery and exit semantics | ✅ | 3/3 success at `test_run_pipeline.py:1679`; genuine 2/3 commit/exit 2 at `test_run_pipeline.py:2122`; Pages contract at `test_daily_workflow_contract_u144.py:36-45`; degraded 3/3 output counts at `test_main.py:506`. |
| AC-150.13 — example and partial PBT | ✅ | `tests/unit/internal/test_surface_quality.py` and `tests/unit/internal/test_surface_quality_properties.py`; both run in the normal 4,516-test suite. |
| AC-150.14 — exact-date production qualification | ✅ | Daily runs `34072608117`/`34074873175` succeeded with exit 0 and 3/3 `finalized`; bot commits `b949c54`/`02607d3`; Pages `34073340478`/`34075738426` succeeded; Telegram returned HTTP 200 twice per run; all six live archive URLs returned 200; canonical scans found zero surface/link issues. |

## Validation evidence

- `uv lock --check`: 65 packages resolved, no lock drift.
- Ruff check and format: 576 Python files passed.
- Strict mypy: 254 source files passed.
- Focused cumulative regression scope: **346 passed**.
- Final integrated-SHA pytest: **4,516 passed in 305.48 seconds**.
- Anthropic SDK, paid API, curated-assets, and image-store guards passed.
- Strict MkDocs passed on Material 9.7.6.
- Material CSS and rendered-pair contract guards passed.
- `git diff --check` passed; no tracked archive/site-doc test residue remained.
- Separate cumulative fresh-eyes code review: approved with no remaining
  Critical, High, or Medium finding; independent final scope 289 passed plus
  Ruff, mypy, and diff integrity.

## Gaps and proposed actions

No implementation or operational gap and no new TECH-DEBT candidate were
found. Development Plan additions: 0. TECH-DEBT additions: 0.
