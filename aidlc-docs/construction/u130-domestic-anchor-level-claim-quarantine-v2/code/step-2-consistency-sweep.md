# u130 Code Generation Step 2 — Same-Run Consistency Sweep

## Scope Delivered

- Split the public gate into a deterministic first pass plus a bounded consistency post-pass.
- Kept the first pass over the full canonical missing-symbol basket.
- Collected only symbols whose unsupported claim was actually rewritten (`finding.isolated`).
- Re-ran the gate for those symbols in canonical `_SEGMENT_CORE_SYMBOLS` order across the first-pass Markdown.
- Merged findings in first-seen order while removing identical structural findings emitted by both passes.

## Contract Decisions

- A structural-only finding does not qualify a symbol for the second pass because no rewrite occurred.
- Canonical symbol order is preserved by filtering the existing gate basket rather than iterating a set.
- The second pass reuses `_gate_line`; it adds no new claim semantics and does not change US/crypto detection.
- The pass is intentionally defensive: the current first pass already scans the whole document, but the explicit post-pass prevents a future line-gating change from reintroducing cross-section inconsistency.

## Review

The fresh-eyes reviewer found the implementation correct but initially raised a Medium test gap: the result-oriented tests would still pass if the second pass were removed. The final regression test stages a first-pass result with residual claims and directly proves:

1. the first call receives the full canonical missing-symbol basket;
2. the second call receives only isolated-rewrite symbols;
3. reverse finding order is normalized to canonical symbol order;
4. a structural-only symbol is excluded;
5. the second pass removes the staged residual claims while preserving the structural row.

Re-review confirmed the Medium finding was resolved and approved Step 2 with no remaining issues.

## Validation

- `uv run pytest tests/unit/publisher/test_anchor_assertion_gate.py -q` — 45 passed.
- `uv run pytest tests/unit/publisher -q` — 976 passed.
- `uv run ruff check ...` — passed.
- `uv run ruff format --check ...` — passed.
- `uv run mypy src` — passed, 248 source files.
- `git diff --check` — passed.

## TECH-DEBT

None added.

## Next Step

Step 3 adds the `discontinuous` quarantine reason by reusing the existing previous-published-anchor lookup path and pins the 477→344, 477→460, and no-history cases.
