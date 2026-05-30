# Curated context-asset library (u86)

Pre-curated, pre-verified, **committed** license-clean context images,
mapped by entity / topic key and drawn from at briefing-generation time.
There is **no runtime scraping** — assets are read from these local
files only (`EXTERNAL_IMAGE_SCRAPING_ENABLED` stays `False`).

## Layout

```
assets/library/{person,topic,asset}/
  {asset-id}.{png|jpg|jpeg|svg}          # the cleared binary (filed)
  {asset-id}.manifest.json               # the license manifest (always required)
  {asset-id}.deferred                    # optional explicit deferral marker file
```

The manifest is the existing `visuals/policy.py` `ExternalAssetManifest`
with `kind="curated-licensed"`.

## States (E5 / R8)

| State | Binary | Marker | CI gate |
|-------|--------|--------|---------|
| `filed` | present, cleared | none | green (must clear R2/R3/R4 + budget) |
| `deferred` | absent | `allowed_use` contains `not-yet-available`, **or** a `{asset-id}.deferred` file | green |
| `(invalid)` | absent, **no marker**, or present with no manifest, or disallowed license | — | **red** |

A silent empty (binary absent, no marker) fails the gate. A deferred key
is never selectable and never renders.

## Filing a deferred asset (operator)

1. Download the cleared file from the manifest's `source_url` and verify
   the file-specific license (PD / CC0 / Unsplash / Pexels). Reject news
   photos, memes, trademark logos, and unofficial portraits (R3).
2. Drop the binary at `{asset-id}.{ext}` (≤ 500 KB raster / ≤ 64 KB SVG,
   100–2000 px).
3. Remove the deferral marker: delete the `{asset-id}.deferred` file (if
   present) and replace the `not-yet-available` `allowed_use` text with
   the real republish statement.
4. Run `python scripts/check_curated_assets.py` — it re-classifies the
   key as `filed` and applies the full clearance + budget gate.

## CI gate

`scripts/check_curated_assets.py` (stdlib-only, mirrors
`check_no_paid_apis.py`) blocks the build on any violation. Deferred keys
pass; silent empties fail.

## Seed status

All seed keys currently ship **deferred** — binaries are filed by the
operator after per-file license verification, never auto-downloaded.
