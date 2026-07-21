# Step 2.1 Phase-One Publish Mutations

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The former `_stage_publish_segments` Markdown rewrites now execute through two
pure collaborators owned by `publisher.public_document`:

- presentation assembly validates the active-segment/date/key identity, then
  applies navigation, first-viewport short disclaimer, canonical disclaimer,
  and summary repair in the historical byte order;
- body-evidence assembly delegates to the existing u123 evidence counter and
  body-used renderer after core-fact verification.

Partial navigation retains canonical segment order and marks absent segments
as `(미발행)`. Both collaborators are idempotent and leave the input model
unchanged when the resulting bytes are already canonical.

The publish boundary still runs the existing read-only validator registry
after assembly. Every ordinary pre-write assembly or gate failure now restores
the complete snapshot set, including staged visual assets, before preserving
the original exception.

Validation: scoped Ruff/format passed, strict mypy passed for 59 source files,
6 focused tests passed, publisher 594 passed, orchestrator 374 passed, and the
fresh-eyes re-review approved the final implementation.
