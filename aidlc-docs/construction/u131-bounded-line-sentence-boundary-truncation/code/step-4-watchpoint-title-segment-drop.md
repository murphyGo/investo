# u131 Code Generation Step 4 — Watchpoint Title Segment Drop

## Scope Delivered

- Preserved the watchpoint title threshold at 30 characters.
- Replaced hard character slicing with right-to-left removal of exact ` · ` segments.
- Retained the largest whole segment prefix that fits the threshold.
- Kept an overlong first segment whole rather than cutting it.
- Removed the title ellipsis construction path.

## Compatibility

Directional-particle derivation still runs before title bounding, Markdown links still reduce to visible text, trailing bare Korean particles remain stripped, and rendering a completed watchpoint matrix again remains byte-stable.

## Review

Fresh-eyes review found one Medium ordering regression in the first implementation: segment handling ran before the established directional derivation. The original derivation order was restored and a centered-dot directional regression was added. Re-review approved with no remaining findings and independently passed 45 tests.

## Validation

- Watchpoint matrix tests — 45 passed.
- Scoped Ruff and format — passed.
- Scoped mypy — passed.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: no new standalone pure helper; the existing pure `_short_signal` contract gained deterministic boundary cases and idempotence coverage.
- Security Baseline: declined; no dependency, secret, external input, network, or cost surface changed.

## TECH-DEBT

None added.

## Next Step

Step 5 expands the publish-blocking truncation detector to all three u131 reader surfaces.
