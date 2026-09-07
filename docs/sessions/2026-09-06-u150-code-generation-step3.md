# Session Log: 2026-09-06 - u150 - Code Generation Step 3

## Overview

- **Date**: 2026-09-06
- **Unit**: `u150 terminal-markdown-link-containment`
- **Stage**: Code Generation
- **Step**: 3 of 6 implementation steps — shape-aware policy matrix and single-action finalizer

## Work Summary

Implemented the approved shape-aware disposition matrix for both link issue
codes across all 16 public block kinds. The finalizer now evaluates complete
findings, selects the strongest action before redacting shape and evidence, and
applies exactly one owned-region action to original bytes. Removed remaining
document-wide cosmetic mutations before and after selected actions, including
the u149 numeric-containment post-action path.

## Files Changed

- Modified: `src/investo/publisher/_public_document_policy.py`
- Modified: `src/investo/publisher/public_document.py`
- Modified: `src/investo/_internal/surface_quality.py`
- Modified: policy, containment, incident-characterization, scanner, and numeric regression tests
- Updated: u150 Code Generation plan, AIDLC state, and audit records
- Created: this session log

## Key Decisions

| Decision | Rationale |
| --- | --- |
| Resolve `(code, block, shape)` before redaction | Reference/residual and recoverable shapes sharing one code must not collapse to the same action. |
| Evaluate every finding, then select the strongest disposition | A recoverable finding cannot hide a simultaneous replacement or hard-block finding in the same region. |
| Bypass first-viewport partial repair when a link code is present | A selected full fallback remains the region's only action and cannot return early after watermark/summary repair. |
| Remove global post-action cosmetic repair from numeric containment | u149 output must proceed directly to reindex and read-only terminal checks without changing unrecorded document bytes. |
| Keep Step 4 residual diagnostics out of this slice | Step 3 closes action selection; bounded residual-code propagation remains its own reviewed plan step. |

## Code Review Results

| Category | Status |
| --- | --- |
| Correctness | Pass |
| Safety / evidence boundary | Pass |
| Reliability / one-action behavior | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

The required separate fresh-eyes review initially found two contract defects:
first-viewport specialized repair could weaken a stronger link replacement,
and numeric containment still ran a document-wide cosmetic transform after its
owned actions. Both were removed and regression-tested. Two ambiguous test
fixtures were also narrowed so their scanner findings match their intended
contract. Final re-review reported no remaining Step 3 findings.

## Validation

- Focused scanner, policy, containment, characterization, and numeric suite: 140 passed
- Broad internal, publisher, and public-notification regression suite: 1,172 passed
- Independent reviewer related suite: 156 passed
- Scoped Ruff check and format: passed
- Full strict mypy: 254 source files passed
- `git diff --check`: passed

## Potential Risks

- Step 4 has not yet added bounded residual surface codes beside
  `document.fallback_exhausted`; residual actionable findings still use the
  pre-Step-4 diagnostic outcome.
- Orchestrator composition and exact-date production qualification remain
  Steps 5-6. No production replay occurred in this step.

## TECH-DEBT Items

- None. Existing dashboard remains Critical 0, High 0, Medium 0, Low 34.

## Delivery

- No commit or push was created. The dirty root worktree remained untouched;
  work continues in the isolated u150 worktree.
