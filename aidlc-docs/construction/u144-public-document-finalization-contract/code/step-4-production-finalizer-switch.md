# Step 4.8 Production Finalizer Switch

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The default segmented pipeline now crosses the public-document lifecycle once.
`GenerateStage` freezes the complete E1 context after generation and supplement
preparation; it no longer calls the reader-format chain, catches
`SurfaceQualityError`, retries a reduced mapping, or creates finalization
outcomes. `PublishStage` calls `finalize_public_bundle()` exactly once and uses
the returned E6 documents and typed `trust_blocked` outcomes for writing,
navigation, notification missing-segment input, and final partial status.

The pure finalizer owns the bounded active-survivor fixed point. Every pass
starts from the generated inputs, recomputes the active context, performs
assembly/projection/repair/read-only validation, and either seals survivors or
records a typed block. A presentation defect that deterministic repair can
contain remains published; a genuine summary, disclaimer, numeric, entity,
compliance, or structure defect withholds only its segment. Zero survivors
raise `PublicDocumentFinalizationError` before publish I/O.

## Integration corrections

- The finalizer now deterministically owns the exact public H1 title. This
  accommodates the real generation path, whose body may start with no H1,
  while keeping the E3 layout contract exact and idempotent.
- Navigation, disclaimers, first-viewport repair, body-evidence accounting, and
  terminal notification-summary extraction run before sealing. Notification
  cleanup delegates to the neutral `_internal.public_summary_extract` owner.
- A compatibility branch remains in `_stage_publish_segments` for direct
  legacy callers. The production segmented call sets `phase_one_complete=True`
  and performs no reader-facing mutation after E6.
- Execution-level regression proves E8 from the real `PublishStage` catch path
  becomes a failed publish result and skips notification.

## Validation

- focused pipeline/finalizer/integration scope: 119 passed;
- full publisher/orchestrator unit scope: 1,063 passed;
- Ruff check/format and strict mypy over all 243 source files: passed;
- architecture regressions prove no GenerateStage surface retry, no legacy
  reader-format call there, and exactly one production finalizer call.
- Fresh-eyes review approved with no Critical/High finding. Its one Medium test
  gap was closed by a direct sealed-path regression that makes both phase-one
  helpers fail fast and proves the exact same Markdown reaches `write_briefing`.

Run-owned staging and later-I/O rollback are intentionally the remaining Step
4.9 checklist item.
