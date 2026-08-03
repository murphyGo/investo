# u134 Step 2 — Low-coverage conclusion sentence

## Outcome

- Replaced only the terminal conclusion `[데이터부족]` tag with the full
  reader-facing `PUBLIC_LOW_COVERAGE_TEXT` sentence.
- Preserved an existing terminator on the preceding conclusion.
- Added `.` when the preceding conclusion lacks a terminator.
- Left genuine mid-sentence `PUBLIC_LOW_COVERAGE_INLINE_TEXT` projections and
  watchpoint uses unchanged.

## Contract Evidence

- Terminator-present and terminator-absent unit cases produce the same two
  complete sentences.
- Terminators before closing quotes or parentheses are recognized without
  inserting duplicate punctuation.
- An enhanced-header integration test proves the final first-viewport callout
  contains no raw `[데이터부족]` tag or legacy punctuation-less splice.
- The conversion happens before generic reader projection and is idempotent for
  already public conclusions.

## Validation

- Focused briefing and publisher suites: 404 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved after the closing-punctuation finding was fixed;
  no remaining findings.
