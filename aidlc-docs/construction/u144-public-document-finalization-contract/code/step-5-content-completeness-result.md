# Step 5.4 Content Completeness Result

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

`PipelineResult` now carries a backward-compatible typed
`content_completeness` value (`complete`, `partial`, or `none`) and canonical
per-segment `SegmentFinalizationOutcome` values. The shared outcome model owns
the closed terminal states (`finalized`, `generation_absent`, and
`trust_blocked`) plus bounded, sorted issue codes.

The orchestrator derives completeness only from the sealed bundle's terminal
outcomes. A delivery-only or optional-visual failure can therefore retain
`PipelineStatus.PARTIAL` while public content remains `complete`; one or two
sealed survivors are `partial`; zero survivors are `none`. Legacy unsegmented
callers retain an empty outcome tuple and their existing result construction.

## Regression evidence

- Three sealed segments produce `complete` with three `finalized` outcomes.
- Generation absence and terminal trust blocking produce `partial` with the
  failed segment's distinct typed disposition.
- Visual-only failure remains content-complete despite the legacy overloaded
  pipeline status.
- Result validation rejects duplicate segments and completeness/outcome
  mismatches while preserving backward-compatible defaults.
- Existing u63 partial publication continues to emit only survivor archive
  paths and absence navigation.

## Validation

- focused result and five orchestration scenarios: 51 passed;
- result, finalizer, staged-artifact, and full orchestrator regressions:
  189 passed;
- Ruff check/format and strict mypy over 244 source files: passed;
- no dependency, source, secret, network, or workflow change.
