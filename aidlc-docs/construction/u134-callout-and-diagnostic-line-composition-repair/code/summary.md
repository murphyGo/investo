# u134 Code Generation Summary — Callout and Diagnostic Composition Repair

## Outcome

u134 is complete. The four production composition defects from 2026-06-29/30
now have producer-level repairs and exact rendered regressions.

## Delivered Contracts

1. Driver headings and first sentences compose with a spaced em dash, or use
   the heading alone past the existing budget.
2. A terminal data-limited conclusion tag renders the canonical full reader
   sentence after a valid terminator.
3. Collapsed diagnostics retain the canonical five-slot source-count line;
   reader-visible/no-anchor paths keep the existing public projection.
4. Both crypto funding tables share a bounded exact fixed-point Decimal
   formatter with no rounding, exponent notation, or trailing fractional zeroes.

## Regression Evidence

A redacted fixture reproduces the archived US driver/conclusion, the repeated
source-pointer line, and the crypto funding noise. It pins exact repaired
values, public/diagnostic containment, ⓪-A/⓪-B equality, and repaired-input
idempotence.

## Validation

- Ruff/format: 13 changed Python files passed.
- mypy: 249 source files passed.
- Planned unit scope: 1,947 passed.
- Lock, fixture JSON, and diff integrity: passed.
- Cumulative fresh-eyes review: AC-134.1-6 and Fixed Contracts 1-4 approved
  with no findings; independent 420-test target passed.

## TECH-DEBT

None added.
