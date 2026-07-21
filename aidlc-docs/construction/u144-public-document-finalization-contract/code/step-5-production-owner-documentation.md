# Step 5.8 Production Owner Documentation

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The production-facing documentation now matches the landed boundary:

- `daily-briefing.yml` documents rc 0/1/2, bounded controller outputs,
  commit-gated Pages dispatch, and delayed fail-closed rc re-emission;
- `component-methods.md` records the typed result fields,
  `finalize_public_bundle`, `write_finalized_document`, terminal
  `build_segmented_summary` DTO input, and content-aware CLI contract;
- `docs/DESIGN.md` describes generated drafts, the single pure finalizer and
  E5 seal, exact-byte consumers, typed partial containment, staged artifact
  transaction, terminal notification DTO, and Pages-before-exit sequencing.

These owners supersede the earlier status-only exit description and the
pre-u144 implication that segmented consumers could continue reading mutable
`Briefing.rendered_markdown` after publish validation.

## Validation

- CLI/workflow contract tests: 68 passed;
- workflow YAML parsed successfully;
- owner-term contract search and `git diff --check`: passed;
- shared-worktree `mkdocs build --strict` reached the build but was blocked by
  12 pre-existing/generated dangling links to absent 2026-04-27 archive files;
  no U-144 documentation is under the public `site_docs` tree. The Step 6
  full gate will rerun strict MkDocs from a clean committed-HEAD worktree.
- no source, dependency, secret, or runtime behavior change.
