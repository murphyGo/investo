# Step 2.3 Pre-finalization Supplements

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

Visual, chart, and carryover Markdown now enters production through
`publisher.public_document._apply_pre_finalization_supplements`. Producers
construct typed `PublicDocumentSupplement` values; the adapter wraps each body
in its canonical `investo:block {kind}:{supplement_id}` marker pair and owns the
single `Briefing.rendered_markdown` replacement.

Existing placement algorithms remain authoritative. Visuals render explicit
`VisualMarkdownBlock(placement_key, markdown)` values so the publisher does not
open an asset or infer placement from Markdown. Chart and carryover continue to
use their existing injectors. Current public-destination asset and sidecar I/O
is intentionally unchanged for the Step 2.4 staging migration.

The adapter validates every owned marker region before an idempotent return.
An existing region must have no markers or exactly one balanced pair. Changed
content and empty carryover remove the complete pair before the kind-specific
injector runs; duplicate pairs and extra opening/closing markers fail closed.
This preserves same-day idempotence without leaving nested or orphan markers.

Validation: scoped Ruff/format and strict source mypy passed; 7 focused
transition/malformed regressions and 1,224 publisher, visual, orchestrator, and
integration tests passed. Fresh-eyes final review independently reproduced all
changed/empty/orphan/duplicate cases and approved the snapshot.
