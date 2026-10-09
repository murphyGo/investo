# Code Generation Plan: u163 terminal-numeric-emphasis-containment

Date:2026-10-09. Status:PLANNED, design draft not approved. Priority:P0-1.
Estimate:4–8h plus scheduled acceptance. [Functional Design](../u163-terminal-numeric-emphasis-containment/design-brief.md).
Coverage:US-002/003/004/005/007; FR-002/003/004/008/010; NFR-003/005/006/R13.

## Scope and deduplication

Extend existing u112 repair in `src/investo/_internal/surface_quality.py`, u144 final scan in `publisher/public_document.py` and its policy. Preserve u149 content trust and u150 protected-link boundaries. No archive rewrite, source change, new model retry or layout/event activation.

## Steps

- [ ] 1. Characterize scanner versus repair for reproduced patterns, valid/ambiguous/protected forms; record unavailable original production text.
- [ ] 2. Implement bounded split-sign repair, preserve all numeric tokens and existing valid repairs; no generic whole-sentence rewriting.
- [ ] 3. Verify fully composed finalizer scan and protection policy; change integration only where needed, preserve stronger content blockers.
- [ ] 4. Add `tests/unit/publisher/test_numeric_emphasis_containment_u163.py` with real full/mixed bundles, summaries, supplements, repeated processing and sibling preservation. Extend `tests/unit/internal/test_surface_quality.py`.
- [ ] 5. Run focused/full validation; update implementation summary and AIDLC surfaces. Code completion is distinct from production recovery.
- [ ] 6. After authorized integration/pin update, observe10 distinct scheduled runs; record runtime SHA, terminal states, publication SHA, notification and Pages.

## Checks and registration

Focused tests include `test_surface_quality.py`, new u163 suite, `tests/unit/publisher/test_public_document_policy_u144.py`, `test_public_document_assembly_u144.py`, `test_public_document_containment_u144.py`. Use offline pytest; then full pytest, Ruff/format, mypy, no-paid/other existing policy guards and `git diff --check`. The new test is created in Step4, not claimed run by this planning task.

Registry/tier/window/core/env/plugin changes:none. Acceptance is the four design ACs, unchanged numeric tokens/content gates and separate10-run operational closeout.
