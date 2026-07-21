# Step 5.2 Sealed Consumer View

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

When E6 is supplied, `_stage_publish_segments()` validates that the caller's
segment keys match the canonical finalized-document tuple and then discards
the caller's compatibility values. It derives one briefing mapping directly
from E5 and uses that mapping for every downstream publish consumer.

This makes the sealed bytes the shared input to archive writing, index and OG
rendering, evidence accounting, quality snapshot/consistency checks, forecast
replay, watchlist surfaces, and the PublishStage notifier handoff. No consumer
can observe a differing generated `Briefing` after finalization.

## Regression evidence

- A direct E6 publish supplies deliberately different compatibility Markdown;
  the sealed writer receives the E5 document and index/OG receive only its
  exact briefing.
- PublishStage returns the same E5-derived mapping stored in the finalized
  bundle for the next-stage notifier handoff.
- The production construction guard continues to allow no post-seal Markdown
  mutation site.

## Validation

- sealed consumer and PublishStage handoff regressions: 4 passed;
- Ruff check/format and strict mypy over 243 source files: passed;
- no dependency, schema, source, secret, network, or workflow change.
