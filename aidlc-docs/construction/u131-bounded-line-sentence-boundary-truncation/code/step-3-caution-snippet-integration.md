# u131 Code Generation Step 3 — Caution-Snippet Integration

## Scope Delivered

- Routed only `주의할 점` callouts through the shared `bound_at_sentence` helper.
- Preserved `SNIPPET_MAX_CHARS = 90` and the existing non-caution u71 paths.
- Reserved space for `본문 참고.` before choosing a complete retained sentence.
- Appended that continuation only when source content was actually omitted.
- Used exact `본문 §②·§④ 참조` when no complete sentence fits.

## Compatibility

TL;DR bullets, 오늘의 결론, 핵심 동인, residual-summary repair, diagnostics movement, and badge rendering retain their prior word-boundary behavior. Short valid caution lines remain byte-identical, and a second reflow pass is byte-stable.

## Review

Fresh-eyes review found one Low documentation-contract mismatch in the public non-caution helper description. The helper and reflow docstrings were aligned with the caution-only branch; re-review approved with no remaining findings and independently passed 25 focused tests.

## Validation

- Helper, meaning, and reflow tests — 63 passed.
- Scoped Ruff and format — passed.
- Scoped mypy — passed.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: no new public pure contract; Step 1 already covers the shared helper property.
- Security Baseline: declined; no dependency, secret, external input, network, or cost surface changed.

## TECH-DEBT

None added.

## Next Step

Step 4 replaces watchpoint title hard cuts with deterministic right-to-left ` · ` segment removal.
