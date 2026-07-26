# u130 Code Generation Step 1 — Domestic Level-Claim Detection

## Scope Delivered

- Added domestic-only bare level-claim detection beside the existing u70 move-claim path.
- Reused `_SEGMENT_CORE_SYMBOLS`, canonical `anchor_label` aliases, existing sentence units, `_gate_line`, and deterministic replacement text.
- Pinned the exact planned 2026-06-30 shapes:
  - `코스피는 150.00, 코스닥은 344.00을 나타냈다`
  - `SK하이닉스[000660]는 2,628,000원으로 동반 하락했다`
- Added coverage for the actual parenthetical index-label form and independent KOSDAQ detection.

## Boundary Decisions

- Existing move claims are evaluated first and retain their behavior.
- Bare level detection is limited to `domestic-equity`; US and crypto remain move-only.
- Numeric ticker aliases, ISO/basic-ISO dates, percentages, count/duration units, and the named KOSPI 200/KOSDAQ 150 indices are not treated as levels.
- Structural-line fail-closed behavior, protected anchor blockquotes, source trace rows, and prose-prefix preservation are unchanged.

## Review

A separate fresh-eyes reviewer found no Critical, High, or Medium issue. One Low observation noted that the compatibility wrapper's generalized error wording would alter US/crypto text; the final implementation preserves their existing `precise move claim` wording and uses `precise anchor claim` only for domestic errors.

The reviewer also identified `코스피는 150.00으로 하락했다` as a broader-goal edge. It remains outside Fixed Contract 1 because the sentence contains `_MOVE_VERBS` but does not satisfy u70's existing magnitude pattern. No unapproved contract expansion was made in this step.

## Validation

- `uv run pytest tests/unit/publisher/test_anchor_assertion_gate.py -q` — 41 passed.
- `uv run pytest tests/unit/publisher -q` — 972 passed.
- `uv run ruff check ...` — passed.
- `uv run ruff format --check ...` — passed.
- `uv run mypy src` — passed, 248 source files.
- `git diff --check` — passed.

## Next Step

Step 2 adds the Fixed Contract 4 same-run same-symbol consistency sweep and double-application idempotency test.
