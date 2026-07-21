# Step 1.5 Sealed Writer

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`publisher.writer.write_finalized_document()` is now the only writer API that
accepts E5 `FinalizedPublicDocument`. Before any directory or temporary file
can be created it verifies:

1. the exact E5 runtime type and canonical closed segment;
2. embedded briefing date and sealed notification date/segment identity;
3. SHA-256 of the exact UTF-8 compatibility Markdown;
4. the canonical segment/date archive path;
5. canonical footer and segment-aware short first-viewport disclaimer.

Identity/digest failures use the existing `PublisherIOError` with bounded
`seal.*` cause codes. An invalid segment is never passed into path arithmetic;
its error context uses the safe canonical unsegmented path. Disclaimer failure
continues to use `PublisherDisclaimerError`. Atomic-write cleanup and error
wrapping remain identical to the legacy writer after the seal passes.

The API is exported from `investo.publisher`, but the production segmented
caller is intentionally unchanged until Step 5. Legacy `write_briefing()`
remains available for the documented compatibility path.
