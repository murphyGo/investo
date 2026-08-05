# u143 Step 5 — Inline SVG site-scoped themes

## Outcome

- Replaced the calendar heatmap's literal OS-media style with one
  `_HEATMAP_PALETTE` and the same four-variant factory shape as cards.
- Made both populated and empty heatmaps emit `site-scoped` styles.
- Switched populated and empty quality sparklines from `_CARD_STYLE` auto to
  `build_card_style("site-scoped")`.
- Removed all production consumers of the `_CARD_STYLE` compatibility alias;
  the alias remains only to preserve the approved pre-u143 import/byte contract.

## Cascade contract

Both surfaces are raw inline SVG, so their internal `<style>` participates in
the page document cascade. Light declarations are the base. Dark declarations
are qualified by `[data-md-color-scheme="slate"]`, whose specificity exceeds
the base class and follows the same Material toolbar state as the page.

The old `@media (prefers-color-scheme: dark)` is absent from production
heatmap and sparkline output. The auto factory branch remains tested as a
non-production compatibility variant. No asset file or manifest is added.

## Validation

- Heatmap + sparkline + renderer scope: 35 passed.
- Complete visual unit suite: 302 passed.
- Ruff/format and scoped source mypy: passed.
- `git diff --check`: passed.

## Fresh-eyes review

Approved with zero Critical/High/Medium/Low findings. The reviewer confirmed
Fixed Contract #6 / AC-143.6, including the preserved heatmap palette and font
semantics, populated and empty path coverage, stronger ancestor specificity,
zero production `_CARD_STYLE` consumers, unchanged OG auto behavior, and zero
asset/manifest file-count delta. Independent validation repeated the focused 35
tests, the complete 302-test visual suite, Ruff, format, scoped mypy, and diff
check successfully.

## Next boundary

Step 6 will run cumulative gates, verify built HTML/CSS, document the theme
contract and raw-GitHub result, resolve DEBT-049/061, and close the unit.
