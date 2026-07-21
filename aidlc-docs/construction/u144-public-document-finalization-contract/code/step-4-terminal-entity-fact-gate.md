# Step 4.3 Single Terminal Entity-Fact Gate

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

Both legacy entity-fact drop paths are gone. `GenerateStage` no longer scans
or removes segments after reader formatting, and `_stage_publish_segments()`
no longer rebuilds facts, rereads the clock, scans Markdown, or changes the
active segment set.

The generation fact-context owner now returns the exact timezone-aware
`fact_now_utc` captured when it builds `VerifiedFactBundle`. That immutable
observation clock travels through `GenerateStage` data to `PublishStage`.
Immediately before any segmented publish I/O, one compatibility terminal
bridge scans every active segment exactly once through the finalizer-owned
`_scan_terminal_entity_fact_markdown()` adapter. The adapter checks target-date
and timezone identity and passes the original clock unchanged to the existing
`scan_entity_fact_claims()` owner.

The bridge preserves current production fail-close behavior until the complete
pure finalizer replaces it later in Step 4. A violating segment is excluded
once, recorded in `entity_fact_blocked_segments`, added to missing-segment
notification input, and makes the final pipeline status partial. If every
segment is blocked, publication fails before `_stage_publish_segments()` and
therefore before public writes.

## Validation

- terminal entity bridge, projection, stage protocol, and pipeline focused set:
  142 passed;
- orchestrator, publisher, and bundle/pipeline integration regression set:
  1,063 passed;
- final focused rerun after status propagation: 105 passed;
- strict mypy for all 241 source files: passed;
- Ruff check and format check: passed;
- scoped diff check: passed;
- fresh-eyes review: approved with no remaining blocker.
