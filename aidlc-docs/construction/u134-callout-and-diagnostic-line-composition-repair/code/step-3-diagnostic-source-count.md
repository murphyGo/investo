# u134 Step 3 — Diagnostic source-count composition

## Outcome

- Preserved a fully canonical source-count record through the pre-collapse
  reader-language pass.
- Captured and re-composed all five slots inside the collapsed diagnostics:
  `수집 대상 N / 성공 N / 0건 N / 실패 N / 본문 사용 N|미집계`.
- Kept the public compact status chip byte-unchanged.
- Left malformed or partial count lines on the existing fail-safe public
  projection path.

## Contract Evidence

- A full-chain regression reproduces the former three-pointer defect and now
  asserts the exact numeric line inside `<details>` with zero pointer sentence.
- `quality_consistency` reads the restored failed count.
- `evidence_accounting` rewrites the restored body-used slot at the same line.
- The existing public-chip assertion remains exact.
- No-status/no-anchor paths reproduce the prior line-level public projection
  exactly, including LF/CRLF endings.

## Validation

- Focused reader-format, public-projection, quality, and evidence suites:
  389 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved after no-anchor leakage and EOF-newline findings
  were fixed; no remaining findings.
