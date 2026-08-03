# u134 Step 4 — Funding Decimal normalization

## Outcome

- Added one shared shortest-exact fixed-point Decimal formatter under
  `_internal`.
- Routed both the ⓪-A crypto indicator funding row and ⓪-B channel baseline
  funding row through the shared formatter.
- Removed trailing fractional zeroes, trailing dots, and exponent notation
  without quantization or rounding.
- Preserved existing missing-value behavior for invalid or non-finite metadata.
- Bounded input and predicted fixed-point output before allocation; oversized
  coefficient/exponent values use the same missing-value path.

## Contract Evidence

- `0.0001000000000000 → 0.0001`, `0.0100 → 0.01`, and `1.000 → 1` are
  pinned at the helper and both renderer surfaces.
- `1E-7` and `1E+3` render in plain fixed-point notation.
- A cross-surface assertion proves ⓪-A and ⓪-B output the same funding value.
- The formatter operates on `Decimal` and never calls `quantize` or float.
- Huge positive/negative exponents and exponent-zero inputs are pinned; a
  10,000-sample bounded reference comparison matched fixed-point Decimal output.

## Validation

- Focused internal, indicator, channel, and grounding suites: 53 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved after the unbounded exponent-allocation finding
  was fixed; no remaining findings.
