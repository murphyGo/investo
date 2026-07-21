# Step 4.7 Finalization Error Routing

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`PublicDocumentFinalizationError` is now a first-class publish-stage failure at
the orchestrator composition root. It is registered exactly once in both
`_PUBLISH_FAILURES` and `EXCEPTION_ROUTING` with `alert=True` and
`PipelineStatus.FAILED`.

The existing `PublishStage` catch boundary therefore converts a finalization
failure into a failed `StageResult`; the run loop routes it under the `publish`
label and suppresses downstream notification. No finalizer-specific catch,
fallback, or alternate status rule was added.

## Validation

- focused stage-protocol and u144 lifecycle tests: 51 passed;
- full publisher/orchestrator unit scope: 1,061 passed;
- Ruff check/format, strict mypy, and scoped diff check: passed;
- fresh-eyes review verified the catch path, exact single registration, publish
  alert/status semantics, and absence of inheritance or import-cycle side
  effects with no blocker.

The reviewer recommended an execution-level `PublishStage` propagation test
when the production finalizer call is connected in Step 4.8; that behavior
belongs to the next checklist item rather than this routing-only slice.
