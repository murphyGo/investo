# u133 Step 1 — SourceSpec registry classification

## Outcome

- Added `SourceSpec.reference_registry` with a backward-compatible `False` default.
- Marked exactly `nasdaq-symbol-directory` and `sec-company-facts` as reference registries.
- Kept market-window, item-routing, outcome-routing, tier, and adapter discovery behavior unchanged.

## Contract Evidence

- The fixed set is expressed only in `SOURCE_SPECS`; downstream code does not compare source names.
- A registry-wide test asserts the exact two-member set and a representative non-registry default.
- The shared-leaf module still imports no source or briefing work unit.

## Validation

- `pytest -q tests/unit/sources/test_source_specs.py`: 10 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; independent 10-test/Ruff/mypy run passed.
