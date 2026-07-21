# Step 4.2 Required and Optional Region Containment

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The concrete `projected -> repaired` phase handler now runs the bounded FD
containment sequence. It first applies the existing deterministic surface
repair, scans reader-visible E3 bodies through the canonical scanner, groups
findings by owned region, executes exactly one fixed disposition per group,
records one redacted outcome, reprojects replacements, and performs the final
deterministic repair. Any actionable residual is resolved through the same
closed policy and terminates the segment with `document.fallback_exhausted`.

A malformed required `watchpoints:section` body is replaced with
`PUBLIC_WATCHPOINT_LIMITED_TEXT` through `replace_region_body()`. The indexed
body offsets preserve the canonical `## ⑥ 오늘의 관전 포인트` wrapper and all
other regions. Malformed `visual` and `chart` supplements use the fixed
`omit_optional_block` disposition: their public body becomes empty, their
canonical marker shell remains indexed, and the segment advances to
`repaired` instead of being dropped.

All replacement wording stays in `_internal.public_quality_language`. The
remaining FD augmentation fallback constants were added there so the closed
replace policy has one shared owner. The existing timestamp watermark owner
was moved without behavior change to neutral `_internal.public_watermark`,
allowing both briefing assembly and publisher repair to reuse it without an
adapter-to-adapter import. Watermark replacement changes exactly one line;
grouped first-viewport repair can therefore apply the canonical summary
fallback in the same single attempt without deleting unrelated copy.

## Validation

- direct containment regressions: 13 passed;
- publisher, module-boundary, and summary-fidelity regression set: 720 passed;
- strict mypy for the changed test and all 241 source files: passed;
- Ruff check and format check: passed;
- scoped diff check: passed;
- fresh-eyes review: approved after correcting exhaustive first-viewport
  dispatch, residual re-resolution, and smallest-safe-boundary preservation.
