# u131 Code Generation Summary — Bounded-Line Sentence Boundary Truncation

## Outcome

u131 is complete. Reader-visible meaning lines and caution callouts no longer end at word-cut clause fragments, and watchpoint titles no longer use hard-cut ellipsis. The terminal scanner blocks recurrence on all three owned surfaces.

## Delivered Contracts

1. `bound_at_sentence` uses the exact decimal-safe terminator contract and returns `None` when no complete sentence fits.
2. Meaning lines preserve the 80-character cap and use exact `MEANING_FALLBACK` on `None`.
3. Caution callouts preserve the 90-character cap, use exact `본문 §②·§④ 참조` on failure, and append `본문 참고.` only after a complete retained sentence when content was omitted.
4. Watchpoint titles preserve the 30-character threshold and remove trailing exact ` · ` segments without ellipsis; an overlong first segment remains whole.
5. `summary.truncated_mid_token` now blocks owned meaning, caution, and watchpoint-title residue while u144 region-local scans still exclude arbitrary section bodies.

## Regression Evidence

Verbatim 2026-06-29/30 residue lines are blocking cases. A trimmed real-chain fixture produces exactly the caution fallback, meaning fallback, and bounded CoinGecko heading; legacy residue is absent and a second full-chain run is byte-identical.

## Validation

- Ruff/format: 13 changed Python files passed.
- mypy: 248 source files passed.
- Unit scope: 1,142 passed.
- Lock, fixture JSON, and diff integrity: passed.
- Cumulative fresh-eyes review: AC-131.1-6 and Fixed Contracts 1-5 approved with no findings.

## TECH-DEBT

None added.
