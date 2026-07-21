# Step 4.4 Active Daily-Thesis Fixed Point

## Landed boundary

The pure survivor decision now lives in
`investo._internal.daily_thesis_decision`. Initial bundle-context computation,
the temporary orchestrator compatibility path, and the public-document
finalizer all call that neutral owner. `publisher.public_document` has no
orchestrator import.

The bundle finalization skeleton is now a bounded active-survivor fixed point.
Every pass derives its active tuple in canonical order from the original
generated `Briefing` mapping. A trust block discards that pass's transformed
documents, records the typed issue codes, and restarts from the original input.
The pass budget is `len(expected_segments)`.

## Active thesis contract

- `PublicDocumentContext.bundle_context is None` returns the exact same
  context and never calls the redecision helper.
- Otherwise, every pass filters daily-thesis signals to active segments and
  recomputes decision support, per-segment wording, and mode from the immutable
  base context.
- Before the first segment is assembled, the finalizer validates target date,
  active signal/support membership, exact active wording keys, and the existing
  cross-segment distinctness rule.
- The defensive snapshot copies mutable mappings without deep-copying an
  already frozen `MappingProxyType`, so survivor-pass context replacement is
  repeatable while caller-owned dictionaries remain isolated.
- Generation absence and trust blocks remain distinct typed outcomes. A final
  zero-survivor result includes the known generation/trust reason codes and
  fails before any public I/O.

## Regression evidence

- Neutral-owner tests prove orchestrator compatibility is an alias to the
  neutral function and statically reject publisher-to-orchestrator imports.
- Fixed-point tests prove a removed crypto segment disappears from the next
  pass's signals, support tuple, and per-segment wording while the immutable
  base context remains unchanged.
- The explicit `None` test replaces the helper with a fail-fast sentinel and
  proves it is never called.
- Focused U-144/orchestrator tests passed 172. The full publisher and
  orchestrator unit scope passed 1,053. Strict mypy passed all 242 source files;
  Ruff check/format and scoped diff checks passed.
- Fresh-eyes review approved the neutral ownership, bounded restart, exact
  `None` branch, active-state removal, zero-survivor behavior, import boundary,
  and shallow snapshot safety with no blocker.
