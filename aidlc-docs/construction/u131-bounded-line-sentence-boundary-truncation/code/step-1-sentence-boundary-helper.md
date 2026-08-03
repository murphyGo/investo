# u131 Code Generation Step 1 — Sentence Boundary Helper

## Scope Delivered

- Added `bound_at_sentence(text, max_chars)` to `investo._internal.text`.
- Preserved under-cap and exact-cap text byte-for-byte.
- On overflow, returns the last complete pinned sentence within the cap without appending an ellipsis.
- Returns `None` when no complete sentence fits so each caller can apply its existing deterministic fallback.

## Fixed Contract

The helper uses `(?<=[^\d\s])[.!?。](?=\s|$)`. A match must end at or before `max_chars`. This preserves decimal values such as `7,499.36` and rejects a period immediately preceded by a digit even when whitespace follows it.

## Tests

The focused module covers:

- under-cap and exact-cap passthrough;
- last-complete-sentence selection;
- `.`, `!`, `?`, and `。` terminators;
- decimal and explicit digit-preceded-period guards;
- no-terminator `None` behavior;
- property-based byte idempotency.

## Review

Fresh-eyes review found one Low test-adequacy issue in the original decimal example. The added `7,499.36. ` case now directly distinguishes the negative digit lookbehind. Re-review approved Step 1 with no remaining Critical, High, Medium, or Low findings.

## Validation

- `tests/unit/_internal/test_text.py` — 25 passed.
- Scoped Ruff and format — passed.
- Scoped mypy — passed.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: Partial, applied to the new pure helper's idempotency contract.
- Security Baseline: declined; no input boundary, secret, dependency, or external I/O added.

## TECH-DEBT

None added.

## Next Step

Step 2 replaces meaning-line word-boundary truncation with this helper and uses `MEANING_FALLBACK` when it returns `None`.
