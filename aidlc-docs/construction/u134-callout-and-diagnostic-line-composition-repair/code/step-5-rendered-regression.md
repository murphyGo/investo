# u134 Step 5 — Rendered production-shape regression

## Outcome

- Added one redacted JSON fixture for the four 2026-06-29/30 composition
  defects.
- Exercised the real driver producer, conclusion public renderer,
  reader-format/reflow chain, and both funding table renderers.
- Pinned exact repaired values and absence of the legacy splice, repeated
  pointer, and noisy Decimal strings.
- Proved byte-stable reruns over each repaired surface.
- Proved the canonical numeric count occurs only inside diagnostics while the
  public prefix retains the exact compact chip.

## Fixture Safety

- Contains only public archived prose, deterministic counter values, and one
  numeric funding string.
- Contains no raw source payload, secret, credential, private destination, or
  live endpoint response.

## Validation

- Cumulative focused regression: 108 passed.
- Scoped Ruff and format: passed.
- Fixture JSON: valid.
- `git diff --check`: passed.
- Fresh-eyes review: approved after funding rerun and public-prefix containment
  assertions were strengthened; no remaining findings.
