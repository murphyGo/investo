# Code Generation Plan: u154 canonical-preamble-block-assembly

**Updated**: 2026-10-10. **Status**: Complete6/6. User explicitly requested numeric-table reduction following event activation; existing commit/push instructions apply. Parent owns implementation; independent read-only review uses dev-investo/code-review.

## Problem and scope

2026-10-08 US archive has duplicate H1, five-row market table before news, hero before TLDR, then repeated index rows in ⓪-B. Domestic/crypto have equivalent duplicated numeric preambles. Extend existing u154, not a new unit. Preserve source data while reducing visible tables to zero before§1 and placing summary first. Existing numeric surfaces move into one CLOSED accessible details panel. Body tables explaining an actual event remain visible.

## Stage Decision

Functional Design: REQUIRED and completed under user's implementation instruction; see functional-design/business-logic-model.md, business-rules.md, domain-entities.md. NFR Requirements/Design: reuse existing NFR-003/004/005/006/R13; no extra I/O/LLM/dependency. The earlier proposed FR-009 anchor-before-TLDR order is superseded. Three-item summaries preserve u158 values. Invalid arbitrary summary content remains visible to hard gates and fails shape validation, rather than silently discarded.

## Fixed implementation

Pure publisher/reader_format/preamble.py extracts only preamble known spans outside fences/supplements. Stable order: title/disclaimer/watermark/nav/TLDR/callouts/owned preamble supplements/other context/closed numeric details/unchanged body. Exact repeated canonical titles dedupe; other H1s fail. Shells have explicit empty-content header regions. Numeric regions remain reader_visible and exclude closing shell from their replaceable contents. Assembly unwraps owned shell before producers, composes after all producers, before E2 reindex. Terminal shape/order validation is required for assembled documents. md_in_html renders native details, without JS dependency. Existing archives are not backfilled.

## Steps

- [x] Step1: Inspect three-market archived layouts, existing u154 and u144/event contracts; complete functional design and independent hazard review.
- [x] Step2: Implement bounded canonical composer and exact summary normalization.
- [x] Step3: Integrate final assembly, shell ownership and terminal shape/order checks while preserving trust gates.
- [x] Step4: Add actual-config HTML, finalizer, partial-sibling, unsafe-hidden-evidence, fallback-shell and idempotence regressions.
- [x] Step5: Independent code review, full/static/policy/docs gates and cross-check; fix findings. Final independent178 PASS, review CLOSED; full integration6382/339.01s and all guards PASS.
- [x] Step6: Commit/push on current main; verify exact remote/CI and record operational applicability separately. Main99519774 preserves concurrent u16521c979e4; scoped runtime4e0dc424 exact CI6236/275.10s PASS. Session record owns activation/readback and pending real observations.

## Acceptance criteria

AC-154.1 One canonical article H1, one TLDR and three list items; exact duplicate title normalization only, unsafe extra content not hidden.
AC-154.2 Summary precedes hero and one closed numeric panel; all preamble tables inside it; body event tables unaffected.
AC-154.3 Values, timestamps, URLs, missing-data labels, complete supplement markers/IDs, body and diagnostics/disclaimer preserved.
AC-154.4 Numeric details remain reader_visible; original numeric/entity/compliance/link gates and region fallback still apply; no shell loss.
AC-154.5 Finalization/reassembly stable, event reconciliation/DTO/receipts and partial navigation unchanged.
AC-154.6 Actual Markdown configuration builds tables/links inside CLOSED details, three summary list items outside; strict MkDocs/Material passes. Browser visual QA only if actually inspected.

## Validation

New tests/unit/publisher/test_canonical_preamble_u154.py and tests/integration/test_canonical_preamble_html_u154.py; existing u144 types/assembly/fallback/incident, u150 links, u153 snippets, u158/event publication and mixed rollout. Full pytest, Ruff/check+format, mypy, four policy guards, strict MkDocs/Material, git diff check. No additional model calls or synthetic production sends.
