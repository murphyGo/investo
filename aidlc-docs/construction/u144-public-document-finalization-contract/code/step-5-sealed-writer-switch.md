# Step 5.1 Sealed Writer Switch

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

Default segmented publication now writes each E5 `FinalizedPublicDocument`
through `write_finalized_document()`. `_stage_publish_segments()` derives a
canonical segment-to-document map from E6, rejects any mismatch with the
published survivor tuple, and dispatches the sealed document through the
cancellation-draining worker boundary.

The writer rechecks the sealed identity, target date, segment, SHA-256 digest,
and disclaimer contracts before touching the archive destination, then writes
the exact sealed Markdown bytes atomically. The legacy direct-call path remains
available only when no finalized bundle is supplied.

## Regression evidence

- An E6-backed segmented call invokes the sealed writer once and makes the
  legacy `write_briefing()` path unreachable.
- Production publish-I/O failure and image-ledger rollback tests now inject at
  the sealed-writer boundary and retain their prior transaction assertions.
- The architecture guard records exactly one production sealed-writer dispatch
  at `_stage_publish_segments()`.
- Existing compatibility coverage proves a direct phase-one-complete call
  without E6 still preserves exact Markdown through `write_briefing()`.

## Validation

- writer, public-document architecture, and orchestrator regressions: 128 passed;
- Ruff check/format and strict mypy: passed;
- no dependency, schema, source, secret, network, or workflow change.
