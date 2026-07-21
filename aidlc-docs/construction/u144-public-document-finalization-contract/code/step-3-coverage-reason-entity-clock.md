# Step 3.6 Coverage Reasons and Entity Observation Clock

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The projection handler now derives E4 public limitation reasons directly from
the generated segment's typed `SegmentCoverage` and the run's E1 source
outcomes. A closed `CoverageReasonCode` mapping classifies all 21 current
values, including the intentional no-op for `DOMESTIC_DISCLOSURE_QUIET`.
Non-normal coverage, core-price conditions, and unavailable source accounting
produce stable canonical reasons before typed producer reasons such as
`watchpoint_unavailable`.

The exhaustive regression compares the mapping keys with
`typing.get_args(CoverageReasonCode)`, so adding a future code without an E4
classification fails the test. Projection-level coverage also proves that,
with `source_count > 0`, empty E1 source outcomes produce
`source_count_unavailable` while a non-empty outcome tuple does not.

`_scan_terminal_entity_fact_claims()` is the finalizer-owned adapter for the
existing entity guard. It passes the immutable E1 `fact_bundle`, target date,
segment, Markdown, and exact timezone-aware `entity_observed_at_utc` to
`scan_entity_fact_claims()`. It performs no wall-clock read. The two legacy
orchestrator entity-drop paths remain unchanged for the Step 4 production gate
consolidation.

## Validation

- focused public projection tests: 37 passed;
- publisher and orchestrator regression set: 1,028 passed;
- module-boundary, u144 architecture, and publish-validator set: 30 passed;
- Ruff check and format check: passed;
- strict mypy for the changed production module: passed;
- scoped diff check: passed;
- fresh-eyes review: one missing source-outcome connection test corrected,
  re-review approved with no remaining finding.
