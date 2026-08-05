# u143 Step 3 — Fragment-paired Markdown

## Outcome

- Single-homed the Material/GitHub fragment spellings in `visuals/paths.py`.
- Production card Markdown now emits one forced-light link, one forced-dark
  link, and one primary-manifest caption.
- Kept fragments entirely out of `Path`, primary/companion tuples, manifests,
  validation inputs, and staged artifact paths.
- Preserved the exact legacy single-link output when no companion mapping is
  supplied, including PNG/JPEG heroes.

## Presentation boundary

`prepare_segment_visual_assets` builds a primary-to-dark `Path` mapping while
writing pairs. It passes that mapping only to `build_visual_markdown_blocks`.
`_visual_block` first converts both real paths to relative URL strings and only
then appends `#gh-light-mode-only` / `#gh-dark-mode-only`.

The public helper uses `None` as the empty-mapping sentinel rather than a
mutable `{}` default. Its externally observable empty behavior is identical to
the fixed contract: pre-u143 single-link bytes are unchanged.

## Regression contract

- Exact two-line pair and one caption.
- Second insertion is byte-idempotent.
- Production preparation supplies a pair for every SVG card.
- Empty/default mapping remains one fragment-free link.
- PNG/JPEG hero assertions retain one fragment-free link.
- Primary, companion, relative-path, and manifest `asset_path` values contain
  no `#`.

## Validation

- Paths/assets/render/provenance scope: 66 passed.
- Complete visual unit suite: 300 passed.
- Ruff/format and scoped source mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; it confirmed that the `None`
  sentinel is behaviorally identical to an empty mapping and that legacy
  assertions were retained while production assertions were strengthened.

## Next boundary

Step 4 will add each companion to staged artifact and git-add accounting and
will update integration file-count assertions from measured pipeline output.
