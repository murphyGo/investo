# u133 Step 2 — Registry match diagnostics routing

## Outcome

- `build_impact_center` consults the canonical source spec before normal u73 grouping.
- An accepted registry match becomes an immutable diagnostics-only copy with
  `reason="reference-registry"` and enters the existing redacted uncertain bucket.
- Registry matches are absent from `public_impact`; non-registry matches retain
  their established Direct/Related/Uncertain classification.

## Compatibility

- u64 matching output is consumed as-is and never mutated.
- Unknown source names and every source whose flag is false follow the old path.
- The existing daily diagnostics renderer exposes only term, source name, and
  reason; source title, summary, URL, and matcher alias stay hidden.

## Validation

- Impact, daily-page, and source-spec suites: 46 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; independent 74-test/Ruff/mypy run passed.
