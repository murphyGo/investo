# Business Logic Model — `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Source**: u86-curated-asset-library-code-generation-plan.md

Algorithms + sequence for the curated context-asset library. Reuses the
existing `visuals/` validation + provenance + hero-priority machinery and
the u64 `briefing/watchlist.py` matcher. Rule ids (`R1`-`R9`) and entity ids
(`E1`-`E5`, `I1`-`I16`) reference the sibling FD files.

---

## 1. Library load + clearance (build time / CI)

```
load_library(root):
  for each candidate under root/{category}/:
    classify(candidate):
      manifest present + binary present       -> filed     (E5)
      manifest present + deferral marker (I16) -> deferred  (E5)
      else                                     -> (invalid) -> RAISE / gate RED  (R1, R8)
    if filed:
      assert_curated_asset_allowed(manifest)        # R2, R3, R4 — no scraping_enabled (R4)
      assert_binary_signature_and_dims(binary)      # reuse visuals/assets.py gate (R4, AC-1.1)
      assert_byte_and_dim_budget(binary)            # AC-1.1
      assert_no_secret(manifest)                    # R7, AC-1.6
    if deferred:
      assert_no_secret(manifest)                    # R7 still applies
      # no binary checks; non-selectable (I10)
  assert_registry_referential_integrity()           # I8 — every registry id resolves; orphans warn (R8)
  return {asset_id -> CuratedAsset}
```

The CI gate (`scripts/check_curated_assets.py`, parallel to
`check_no_paid_apis.py`) runs the same `load_library` + reports the first
failure with a clear message and a non-zero exit. **Deferred entries pass.**
A binary-absent-without-marker entry fails (R8 / I14).

## 2. Entity extraction + deterministic selection (generation time)

```
select_curated_asset(segment, items, library, registry):
  text = concat(normalized titles/snippets for `items` in this segment)
  candidate_keys = []
  for key in registry:
    if segment not in key.segment_affinity: continue        # R6 segment gate
    match = match_registry_key(key, text)                   # reuse u64 primitives, no new matcher (R6)
    if match.confidence accepted:
      candidate_keys.append((key, match))
  if not candidate_keys:
    return CuratedSelection(asset=None, ...)                # R6/R9 fall-through

  # deterministic ordering (R5 / I12)
  candidate_keys.sort by (segment_affinity_match, registry_priority, key)
  for (key, match) in candidate_keys:
    for asset_id in key.asset_ids:                          # registry-ordered (I9)
      asset = library[asset_id]
      if asset.state == filed:                              # deferred skipped (I10/I11)
        return CuratedSelection(asset=asset, matched_key=key, match_reason=match.reason)
  return CuratedSelection(asset=None, ...)                  # all candidates deferred -> fall-through
```

No wall-clock / RNG anywhere; identical inputs → byte-equal output (R5).

## 3. Pipeline hero injection (generation time)

```
prepare_segment_visual_assets(..., curated_selection):
  if curated_selection.asset is not None:                   # filed only (I11)
    card = build curated-context-image card from asset
    validate card via existing assets.py gate               # R4
    provenance = build_curated_provenance(asset.manifest)   # reuse provenance.py (R9)
    write_manifest(provenance)                              # R9
    caption = provenance_caption(provenance)                # source/license/author (R9, AC-1.4)
    place into _HERO_PRIORITY:
      external-context-image > curated-context-image > ai-market-hero > data-confidence   # R9
  # disclaimer unchanged; no-match -> existing AI/data-confidence chain (R9 fallback)
```

## 4. Sequence (one segment, happy path with a matched curated asset)

```
orchestrator
  -> select_curated_asset(segment, items, library, registry)     # §2
       -> u64 matcher primitives (briefing/watchlist.py)         # R6
  -> prepare_segment_visual_assets(..., selection)               # §3
       -> assert_curated_asset_allowed (no scraping)             # R2/R3/R4
       -> visuals/assets.py signature+dim gate                   # R4/AC-1.1
       -> build_curated_provenance + write_manifest              # R9
       -> provenance_caption  -> curated-context-image hero      # R9/AC-1.4
  -> publisher renders hero + caption + disclaimer (unchanged)   # R9
```

No-match path: §2 returns `asset=None` → §3 skips injection → existing
hero chain runs unchanged (R9/I13). Zero external fetch on every path
(R4/AC-1.5).

## 5. Determinism + degradation summary

- Byte-stable selection (R5/I12); deferred keys never render (R8/I10).
- Missing/ambiguous segment → graceful `None` → existing fallback (R9/I13).
- Library load failures (invalid entry, disallowed license, budget breach,
  secret) fail **closed** at build/CI time, never silently at run time
  (R1/R2/R7/R8, AC-1.1/AC-1.2/AC-1.6).
