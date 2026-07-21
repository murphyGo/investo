# Step 4.6 Compliance Repair and Terminal Scan Ownership

## Characterized assembly scans

`repair_compliance_language()` remains a text-producing assembly operation.
`segment_reader_format` retains exactly two load-bearing read-only scans:

1. after repair and before watchpoint rendering, while raw section-⑥ bullets
   are still prose and cannot be hidden by a renderer-owned shape; and
2. after watchpoint rendering, so any reader-visible producer output is checked
   before later first-viewport transforms.

The former third scan after surface repair was removed from the generic reader
transform. A regression observer proves exactly two calls and records the raw
bullet shape followed by the rendered `#### 관찰 신호:` shape.

## Public-document terminal ownership

The production compatibility boundary
`_assemble_phase_one_reader_briefings()` now scans every final reader output
immediately before returning it. This preserves the existing P0 fail-close
until the sealed lifecycle switch while moving the final scan owner out of the
interleaved reader transform.

`_scan_terminal_compliance(draft, context)` is the typed final-layout adapter.
It validates draft/context identity and delegates only to the existing
read-only `scan_compliance()` over `draft.layout.markdown`. It never invokes
repair, changes layout bytes, or swallows `ComplianceLanguageError`.

## Regression evidence

- A fail-fast injected unsafe reader output proves the production
  public-document boundary actually runs the final scan and propagates P0.
- A typed-draft test proves terminal P0 detection leaves exact final Markdown
  unchanged and retains the forbidden phrase as evidence rather than repairing
  it.
- Focused compliance/assembly/projection/integration scope passed 107 tests;
  the full publisher/orchestrator unit scope passed 1,060. Strict mypy passed
  all 242 source files; Ruff check/format and scoped diff checks passed.
- Fresh-eyes review first found the unconnected-helper regression, then
  approved the production-boundary connection and read-only terminal contract
  after correction with no remaining blocker.
