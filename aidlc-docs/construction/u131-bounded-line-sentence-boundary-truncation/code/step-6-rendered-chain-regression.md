# u131 Code Generation Step 6 — Rendered-Chain Regression

## Scope Delivered

- Added a trimmed JSON fixture for the 2026-06-29/30 meaning, caution, and watchpoint-title residue family.
- Ran one real crypto `Briefing` through `apply_reader_format_to_segments`, including the u81 chain, watchpoint rendering, reflow, and surface repair.
- Required exact owned-line content, order, and count.
- Proved the three legacy residue strings are absent and the canonical scanner is clean.
- Proved a second complete chain run is byte-identical.

## Fixture Safety

The fixture is deterministic and redacted. It contains only the minimum public prose needed to reproduce the algorithms, the already-public archived residue strings, and no raw source payload, credential, URL, repository identity, notification destination, or operator metadata.

## Review

Fresh-eyes review found one Low assertion gap because prefix/presence checks could permit suffixes or duplicates. The test now compares the complete ordered owned-line list with the three exact expected outputs. Re-review approved with no remaining findings and independently passed the regression.

## Validation

- Rendered-chain regression — 1 passed.
- Cumulative u131 related tests — 133 passed.
- Scoped Ruff and format — passed.
- Fixture JSON parse and `git diff --check` — passed.

## Extensions

- Property-Based Testing: no new production function in Step 6; byte-idempotence is asserted over the complete chain.
- Security Baseline: declined; the fixture is redacted and introduces no runtime surface.

## TECH-DEBT

None added.

## Next Step

Step 7 runs the final cumulative static, type, publisher, and internal quality gates.
