# u131 Code Generation Step 5 — Owned-Surface Detector

## Scope Delivered

- Reused the existing blocking `summary.truncated_mid_token` issue code.
- Added body ownership for exact meaning-marker lines and `#### 관찰 신호:` headings.
- Blocked incomplete caution clauses followed by `본문 참고.`.
- Blocked both `...` and `…` on all three owned line shapes, including non-Hangul endings.
- Kept arbitrary body text outside the body-owned truncation route.

## Production Evidence

Tests pin verbatim lines from the 2026-06-29 crypto and 2026-06-30 US archives: one truncated meaning line, one malformed caution continuation, and one ellipsized watchpoint title. Each emits one blocking issue with the exact source line as evidence.

## u144 Compatibility

The finalizer's region-local scan now retains `segment_body` truncation findings only when the canonical scanner assigned body ownership. The existing first-viewport-only false-positive guard remains effective for arbitrary isolated section text. Since the issue code is unchanged, the closed disposition policy and exhaustiveness registry require no new entry.

## Review

Fresh-eyes review found one Medium coverage gap for non-Hangul caution endings. Explicit ASCII/Unicode ellipsis checks were added under the caution marker, preserving its actual viewport region. Re-review approved with no remaining findings and independently passed 69 focused tests.

## Validation

- Detector, reader-format, watchpoint, and u144 ownership/policy tests — 132 passed.
- Scoped Ruff and format — passed.
- Scoped mypy — passed.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: no new bounding transformation; the narrow caution predicate is covered by positive and negative contract examples.
- Security Baseline: declined; no dependency, secret, external input, network, or cost surface changed.

## TECH-DEBT

None added.

## Next Step

Step 6 runs trimmed reproductions through the real reader-format chain and proves byte-stable reruns.
