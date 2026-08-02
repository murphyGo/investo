# u130 Domestic Anchor Level Claim Quarantine v2

## Status

Code Generation complete, 7/7, on 2026-08-03.

## Delivered Contract

- Domestic-only bare level detection covers `^KOSPI`, `^KOSDAQ`, `KRW=X`, `005930.KS`, and `000660.KS` while retaining the existing move-claim path.
- Unsupported sentences are rewritten with the existing deterministic data-limited callout; supported neighboring prose is preserved.
- A second canonical-order pass gates every remaining precise claim for any symbol rewritten in the first pass and is byte-idempotent.
- Domestic anchor candidates are compared with the newest published value from the prior seven calendar days. Changes strictly above 15% for index/FX or 30% for the two large-cap symbols are withheld as `discontinuous`.
- One previous-close mapping is loaded per segmented run and shared across anchor preparation, quality-history metadata, and notification filtering.
- `discontinuous` contributes to the existing withheld count and deterministic reason tuple.

## Incident Regression

A redacted trimmed 2026-06-30 Stage-2 fixture carries the four affected KOSPI 150.00 surfaces. The production reader-format and gate chain removes all four, preserves adjacent supported statements, and returns an empty terminal anchor scan.

## Compatibility

Four representative US/crypto cases were run against pre-u130 commit `08b241f`. Rendered Markdown bytes, ordered findings, and SHA-256 digests matched exactly. Existing US/crypto fixtures required no edit.

## Validation

- Scoped Ruff and format: passed.
- `mypy src`: 248 source files, passed.
- Focused regression scope: 69 passed.
- Publisher and orchestrator unit suites: 1,410 passed.
- Lock and diff checks: passed.
- Cumulative fresh-eyes review: AC-130.1-6 and Fixed Contracts 1-5 approved with no findings.

No archive/generated-site output changed and no TECH-DEBT item was added.
