# Step 7 exact replay — structure routing repair

## First replay

- Workflow: `daily-briefing.yml`
- Run: `29882588545`
- Job: `88806417178`
- Head: `516e582`
- Input: `target_date=2026-07-17`
- Result: workflow failure after 12m22s; no public commit and Pages correctly
  skipped.

The run collected 119 items and generated all three drafts
(`ok=3 failed=0`). The first domestic assembly completed reader-format repair,
then publication failed as:

```text
PublicDocumentFinalizationError
segment=domestic-equity phase=bundle codes=invariant.phase_handler
```

## Root cause

`PublicDocumentLayout.reindex()` represented every required-structure problem
as a plain `ValueError`. `_finalize_bundle_skeleton()` therefore caught the
error as an invariant/handler bug and aborted E8 for the whole bundle. That
contradicted AC-144.7: required structure is a segment trust failure and must
participate in the bounded survivor fixed point.

The first-run log intentionally contained no generated Markdown or exception
payload, so it could not expose the concrete structure subcode. The code path
after the logged phase-one surface repair and the generic exception mapping
identified the lost typed boundary; the replay after this patch is the live
confirmation.

## Repair

- Added `_PublicDocumentLayoutError(issue_code)` at the canonical layout-error
  factory without changing the existing `ValueError` compatibility surface.
- `_finalize_segment_skeleton()` converts that typed error at any phase into
  `_SegmentTrustBlockedError(expected_phase, issue_code)`.
- The fixed point can now keep valid siblings, preserve the concrete
  `structure.*` issue code, and produce the documented partial outcome instead
  of whole-bundle `invariant.phase_handler`.

## Validation

- Public-document lifecycle, containment, pipeline, and CLI scope: 232 passed.
- Ruff and format: passed.
- mypy: no issues in 246 source files.
- Added a two-segment regression proving `structure.empty` blocks only the
  domestic segment while the US document seals and the ordered outcomes remain
  `trust_blocked`, `finalized`.

Production confirmation remains pending the exact-date replay retry.
