# u143 Step 2 — Dual card assets and provenance

## Outcome

- Every deterministic card now writes `{kind}.svg` as forced light and
  `{kind}-dark.svg` as forced dark.
- Primary assets retain their exact pre-u143 names, membership, and order.
  Dark files are exposed only through `PreparedVisualAssets.companion_paths`.
- Primary manifests record `theme_variant=light` and the exact dark companion
  filename. Dark companions intentionally receive no second JSON sidecar.
- Primary files use the existing full asset gate; companions use the existing
  binary-only SVG gate.

## Contract details

`assets.py` now imports the renderer's `_RenderableCard` union rather than
maintaining a second local union. The renderer registry and the preparation
loop therefore share one card-type boundary.

The four-card regression pins the unchanged primary order:

1. `data-confidence.svg`
2. `market-snapshot.svg`
3. `price-snapshot.svg`
4. `watchlist-relevance.svg`

It also pins the parallel `-dark.svg` order, sidecar absence, manifest metadata,
forced palette values, media-query absence, and binary validation. The light
and dark style blocks are both 245 bytes, and every generated pair has equal
UTF-8 byte length, confirming the Step 0 size-parity projection.

Step 4 deliberately remains the owner of adding companions to staged artifact
and git-add accounting. This step only establishes generated files and the
typed return channel.

## Validation

- Render/assets/provenance scope: 60 passed.
- Complete visual unit suite: 298 passed.
- Ruff/format and scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings, including data-integrity and
  resource-lifecycle checks around the existing atomic SVG writer.

## Next boundary

Step 3 will map each primary to its companion only at markdown rendering time,
append Material fragments to URL strings, and emit one shared caption.
