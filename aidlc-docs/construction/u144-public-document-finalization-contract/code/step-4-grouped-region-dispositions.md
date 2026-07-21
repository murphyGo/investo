# Step 4.1 Grouped Region Dispositions

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The containment boundary now represents each canonical surface finding as one
typed `(region_id, block, SurfaceQualityIssue)` value. Resolution verifies the
finding against the active E3 layout index, groups every finding by region,
orders groups by layout source order, and reduces unique sorted issue codes to
one action through the fixed R10 precedence:

`block_segment > omit_optional_block > replace_block > repair > record_warning`.

The existing exhaustive `SURFACE_ISSUE_DISPOSITION_TABLE` remains the sole
issue-code and block policy owner. No scanner regular expression or detection
algorithm moved into the finalizer.

Completed actions record one redacted `PublicBlockOutcome` per region. E7
actions map exhaustively to E3 as `kept`, `repaired`, `replaced`, or `omitted`;
`block_segment` raises the typed segment trust-block signal. Outcomes contain
only region identity, block kind, disposition, and canonical issue codes. Raw
evidence and Markdown never cross into E3.

A repeated region attempt terminates with `document.fallback_repeat`, while
multiple simultaneous cosmetic findings in one region produce one grouped
decision and one outcome. Actual replacement, omission, repair execution, and
residual validation remain the following Step 4 slices.

## Validation

- policy, containment, and lifecycle focused set: 51 passed;
- publisher and orchestrator regression set: 1,041 passed;
- module-boundary, u144 architecture, and publish-validator set: 30 passed;
- Ruff check and format check: passed;
- strict mypy for both changed production modules: passed;
- scoped diff check: passed;
- fresh-eyes review: approved with no remaining finding.
