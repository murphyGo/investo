# Step 2.2 Segment Reader Internal Collaborator

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`orchestrator.pipeline` now reaches the reader-format chain only through
`publisher.public_document._assemble_phase_one_reader_briefings`. The legacy
`segment_reader_format` module remains a compatibility surface for tests and
non-production callers, but production treats it as an internal phase-1 text
transform and surface-repair collaborator.

Surface scanner/error policy no longer lives in the transform module. Before
the Step 4 terminal validator lands, `public_document` supplies a policy-free
post-repair observer that preserves the current fail-close behavior and the
exact per-segment ordering: pre-repair scan, repair, post-repair scan, bounded
WARN logging, then block.

Fresh-eyes review found that a batch-level scan could let a later segment's
hard error outrank an earlier segment's surface blocker. The final observer is
called synchronously inside each segment iteration; a two-segment regression
proves the earlier `SurfaceQualityError` fires before the later segment begins.

Validation: scoped Ruff/format, strict mypy (59 source files), 19 focused,
597 publisher, 374 orchestrator, 14 integration, and 28 boundary tests passed.
Fresh-eyes re-review approved the corrected snapshot.
