# u143 Step 1 — Card style factory

## Outcome

- Replaced the duplicated literal style block with one ordered
  `_CARD_PALETTE` and a typed `build_card_style()` factory.
- Added `light`, `dark`, `auto`, and `site-scoped` variants without changing
  any pre-u143 color value.
- Preserved `_CARD_STYLE = build_card_style("auto")` for the quality
  sparkline until Step 5 moves that inline surface deliberately.
- Routed every `_RenderableCard` member through the single `_svg_document`
  variant boundary; `render_card_svg()` now defaults to forced light.

## Compatibility contract

The `auto` result is byte-identical to the 512-byte Step 0 fixture. Light and
dark contain no media query. Site-scoped contains the Material body ancestor
selector and no media query. Each palette declaration appears exactly once in
the variant branch where it belongs.

The registry-driven test derives its parameter set from
`typing.get_args(_RenderableCard)`. Adding a card input to the union without a
render sample or two-variant support therefore fails the test instead of
silently emitting only one theme.

## Validation

- `tests/unit/visuals/test_render.py`: 22 passed.
- Complete visual unit suite: 297 passed.
- Ruff check and format: passed on both changed Python files.
- Mypy: passed on the renderer and its test module.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; the reviewer additionally
  confirmed all five quality-sparkline compatibility tests.

## Next boundary

Step 2 will write one forced-light primary and one forced-dark companion for
every rendered card, while keeping `asset_paths` membership and order intact.
