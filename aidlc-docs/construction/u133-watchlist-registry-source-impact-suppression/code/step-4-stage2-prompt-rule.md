# u133 Step 4 — Stage-2 §⑤ registry narration rule

## Outcome

- The Stage-2 system prompt identifies `nasdaq-symbol-directory` and
  `sec-company-facts` rows as entity-identification evidence only.
- A registry row may be cited in §⑤ only when a same-run, non-registry item
  covers the same ticker.
- A registry-only ticker set is explicitly forbidden from creating a §⑤
  subsection.

## Boundary

This rule shapes model input use; it is not the security or publication
backstop. The deterministic impact-center routing from Step 2 remains the
enforcement point, and no post-render scanner was added.

The prompt already sat close to its u101 byte ceiling. Adjacent instructions
were wording-compressed without changing their tested contracts, leaving the
updated Stage-2 prompt at 20,271 bytes under the existing 20,300-byte limit.

## Validation

- Prompt suite: 39 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; independent 57-test prompt /
  anchor / hierarchy scope, Ruff, format, mypy, size, and diff checks passed.
