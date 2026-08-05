# Session Log: 2026-08-05 - u143 - Code Generation Step 0

## Overview

- **Unit**: u143 visual-theme-parity-dual-variant
- **Stage**: Code Generation
- **Iteration**: Step 0 of 7
- **Result**: Baseline measured; Material fragment contract confirmed

## Work Summary

Started from isolated `codex/u143` at `origin/main@850d9cc`, preserving the
user's dirty primary worktree. The previously ratified dual-variant design is
still compatible with the current archive and Material build.

The latest complete four-card sample (`2026-08-04` US equity) contains 13,003
bytes of primary SVG and
1,686 bytes of manifests. Because dark companions intentionally receive no
second sidecar, the projected three-segment increment is 39,009 bytes per run,
about 0.97 MiB per average month and 11.61 MiB per scheduled year.

The strict site build confirmed all four `#only-*` and
`#gh-*-mode-only` selectors in Material 9.7.6. The exact pre-u143 card style is
now a fixture, so Step 1 cannot accidentally alter the `auto` surface while
extracting the palette factory. `mkdocs.yml` was not changed.

## Next Boundary

Implement `build_card_style()` and the light/dark/auto/site-scoped renderer
variants, then run the registry-driven card matrix before committing Step 1.
