# u134 Step 1 — Driver composition

## Outcome

- Added heading-aware composition at the canonical `SummaryHeader.driver` assembly point.
- A Markdown heading and its first prose sentence now render as
  `{heading} — {first sentence}`.
- When that pair exceeds the existing 280-character budget, the heading alone is
  retained deterministically.
- Non-heading inputs continue through the pre-existing summary-sentence path.

## Contract Evidence

- The verbatim 2026-06-30 heading and first sentence pair has a regression assertion for
  the spaced em-dash separator and absence of the legacy bare-space splice.
- A 280-character boundary regression proves the heading-only fallback.
- A conjunction-tail heading regression proves that heading validation happens
  on the completed composition and cannot re-enter the legacy splice path.
- The rendering layer and shared unsafe-summary predicate were not changed.

## Validation

- Focused briefing suite: 52 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved after the unsafe-heading fallback and verbatim-fixture
  findings were closed; no remaining findings.
