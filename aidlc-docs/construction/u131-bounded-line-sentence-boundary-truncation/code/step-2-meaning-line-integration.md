# u131 Code Generation Step 2 — Meaning-Line Integration

## Scope Delivered

- Routed meaning-line overflow through the shared `bound_at_sentence` helper.
- Preserved `MEANING_MAX_CHARS = 80`.
- Kept the last complete sentence without an ellipsis when it fits.
- Used the exact existing `MEANING_FALLBACK` when no complete sentence fits.
- Removed the obsolete word-boundary character table and `...` suffix path.

## Compatibility

The deterministic pass still leaves under-cap meaning lines unchanged, preserves advice text for downstream compliance rejection, drops duplicate meaning lines, scopes processing to §②-§⑤, and leaves glossary/carryover blocks intact. Applying the reader-format chain again remains byte-stable.

## Review

Fresh-eyes review approved with no findings. It independently confirmed the unchanged 80-character cap, exact fallback reuse, absence of ellipsis construction, complete-sentence retention, and unchanged surrounding u76 behavior. Its independent helper-plus-meaning run passed 38 tests.

## Validation

- Meaning and general reader-format tests — 51 passed.
- Scoped Ruff and format — passed.
- Scoped mypy — passed.
- `git diff --check` — passed.

## Extensions

- Property-Based Testing: no new pure function in Step 2; the delegated helper's property coverage landed in Step 1.
- Security Baseline: declined; no new input, secret, dependency, or external I/O surface.

## TECH-DEBT

None added.

## Next Step

Step 3 applies sentence-boundary bounding and the separate continuation sentence to 주의할 점 snippets.
