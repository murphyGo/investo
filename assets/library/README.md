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
assets/library/_rights/
  legacy-v0.json                         # exact-byte seal for the original 15
  {asset-id}/source-snapshot.json        # immutable exact-file source response
  {asset-id}/rights-evidence.json        # reproducible READY_FOR_REVIEW evidence
  {asset-id}/operator-decision.json      # separately authored approval + hashes
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

## Filing a new asset (operator)

1. Save one exact Wikimedia Commons imageinfo + Structured Data response and
   the exact selected binary. Phase 1 accepts only file-specific PD/CC0 with
   matching structured license/copyright status and no restriction signals.
2. Run `scripts/prepare_curated_asset_review.py` offline. It writes a pending
   packet outside the repository and can never create an approval, manifest,
   registry row, U137 clearance, or library binary.
3. A reviewer inspects file identity, license scope, subject relevance,
   non-copyright restrictions, and endorsement risk. Filing requires the
   binary, seven-field manifest, source snapshot, reproducible evidence,
   separately authored approved decision, and one registry reference.
4. Run `python scripts/check_curated_assets.py`. It verifies exact stored-byte
   hashes across the complete graph and fails on missing, tampered, or orphaned
   nodes. A one-byte evidence/manifest/binary change invalidates approval.

## CI gate

`scripts/check_curated_assets.py` (stdlib-only, mirrors
`check_no_paid_apis.py`) blocks the build on any violation. Deferred keys
pass; silent empties fail.

## Seed status

The original 15 seed keys ship **filed** and are frozen in the exact-byte
`legacy-v0` seal. Four post-seal assets add complete Commons evidence and
operator-decision graphs, bringing the library to **19 filed assets** with
zero deferred or orphan entries. Per-file
license-verified binaries — US federal-government works (17 U.S.C.
§105 / PD-USGov) for the person and government slots, and explicit
CC0 / public-domain files (Wikimedia Commons file pages, Flickr CC0
markers) for the rest. Each sibling `*.manifest.json` records the
source page, license token, author, and how the license was verified.
No Unsplash/Pexels-site claims were used: both photo-page hosts block
programmatic license verification, so only sources whose license
wording could be machine-checked were accepted.

The added semantic coverage is data centers, gold, renewable energy, and
Bitcoin mining hardware. Narrow assets such as mining hardware are separate
topic keys rather than generic Bitcoin variants. Exact topic aliases are ranked
ahead of broad market wording, while explicit person names have no global
priority. Repeated contexts use a deterministic narrative/key digest across a
key's filed variants, so new assets are both reachable and reproducible.

Person assets are registered by explicit names only. Office titles such
as `Fed Chair` or `Treasury Secretary` never select a specific portrait;
this keeps office-holder changes from silently reusing a predecessor's
image.
