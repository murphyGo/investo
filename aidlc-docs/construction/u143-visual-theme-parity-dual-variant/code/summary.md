# u143 visual-theme-parity-dual-variant — construction summary

## Status

Code Generation complete (7/7) on 2026-08-05. Main integration follows the
requirements cross-check.

## Delivered contract

- One typed eight-class palette factory renders forced light, forced dark,
  byte-compatible OS-auto, and Material site-scoped styles.
- Every registered card emits an ordered light/dark SVG pair. Primary path
  membership and order remain stable; dark companions travel separately.
- Markdown emits exact `#gh-light-mode-only` / `#gh-dark-mode-only` pairs with
  one primary caption. PNG/JPEG and legacy empty mappings stay single-link.
- Only the primary manifest exists; it records `theme_variant` and
  `dark_variant`. Dark binaries are independently validated and participate in
  the same u144 staged-artifact lifecycle as the primary and manifest.
- Inline heatmap and quality sparkline use parent-site selectors on populated
  and empty paths. OG auto behavior remains unchanged.
- Strict docs CI now guards both exact Material fragment rules and an actual
  MkDocs Material render preserving both built-HTML fragment sources.
- The rerunnable legacy 2026-05-06 backfill explicitly retains OS-auto SVGs.

## Storage and compatibility

The latest complete four-card sample measured 13,003 SVG bytes. The projected
dark increment is 39,009 bytes per three-segment run, about 0.97 MiB/month and
11.61 MiB/scheduled year. Dark manifests are not duplicated. Existing archives
are not backfilled. Raw GitHub may stack the pair; Pages is canonical.

## Validation

Full suite **4,319 passed**. Ruff/format, strict mypy (252 source files), all four
policy guards, strict MkDocs, the built-CSS contract, lock check, diff check, and
generated-file cleanliness passed. Fresh-eyes review's built-HTML persistence
and legacy-backfill neutrality findings were fixed and revalidated; no finding
remains.

## Debt closure

DEBT-049 and DEBT-061 moved to Resolved Items. Active debt is Medium 0 / Low 33.

## Evidence

- `code/step-0-measured-baseline.md`
- `code/step-1-style-factory.md`
- `code/step-2-dual-assets.md`
- `code/step-3-fragment-markdown.md`
- `code/step-4-staging.md`
- `code/step-5-inline-site-scope.md`
- `code/step-6-quality-gate.md`
- `docs/sessions/2026-08-05-u143-code-generation-step0.md` through Step 6
