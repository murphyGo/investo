# Domain Entities — `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Source**: u86-curated-asset-library-code-generation-plan.md

This unit introduces a new **persisted artifact** (a committed, license-clean
local context-image library + an entity/topic registry) that feeds the
existing visual pipeline. It reuses, and does not duplicate, the
`visuals/policy.py` manifest type and the `visuals/provenance.py` caption
system. Entities below describe the *new* persisted shapes and their
invariants. `E1`-`E5`.

---

## E1. CuratedAsset (the committed library entry)

A single license-clean image filed under the library root, addressed by a
stable `asset-id`.

| Attribute | Type | Notes |
|-----------|------|-------|
| `asset_id` | str | Stable slug, `^[a-z0-9][a-z0-9-]*$`. Filename stem. |
| `category` | str | Library subfolder (`person` / `topic` / `asset`). |
| `path` | path | `assets/library/{category}/{asset_id}.{ext}`, `ext ∈ {png,jpg,jpeg,svg}`. |
| `manifest` | `ExternalAssetManifest` | The **existing** u19 type with `kind="curated-licensed"` (new literal). Sibling `{asset_id}.manifest.json`. |
| `state` | `CuratedAssetState` | `filed` (binary committed + manifest) or `deferred` (manifest present, binary `not-yet-available`). See E5. |

**Invariants**

- I1 (manifest required). A `CuratedAsset` is never constructed without a
  sibling manifest. A binary with no manifest, or a manifest with no
  binary *and no explicit `deferred` declaration*, is rejected (R1, R8).
- I2 (kind pinned). `manifest.kind == "curated-licensed"`. The
  `project-owned` / `explicit-license` kinds never appear in the library.
- I3 (republishable license). `manifest.license` / `manifest.allowed_use`
  must clear the republishability test (R2). Excluded categories are
  rejected (R3).
- I4 (binary integrity). When `state == filed`, the binary passes the
  existing `visuals/assets.py` PNG/JPEG/SVG signature + dimension gate
  (R4) and the byte/dimension budget (NFR AC-1.1).
- I5 (no secret). No attribute value matches the u27 redaction patterns
  (R7).

---

## E2. CuratedAssetManifest (alias — not a new type)

Not a new class. It is `ExternalAssetManifest` (frozen, `extra="forbid"`,
pydantic v2) with the literal `AllowedExternalAssetKind` widened to include
`"curated-licensed"`. Reused fields: `kind`, `source_url` (`HttpUrl`,
public), `license`, `attribution`, `author`, `fetched_on`, `allowed_use`.

**Invariants**

- I6. `source_url` is a public http(s) URL (existing `_assert_public_http_url`),
  pointing at the *original* license-clean source (e.g. the
  federalreserve.gov / Wikimedia / Unsplash page), even when the binary is
  served locally. Provenance traceability.
- I7. For `state == deferred`, the manifest carries the deferral marker
  (E5) and the binary file is absent by contract — this is the *only*
  sanctioned way a registered key may lack a binary (R8).

---

## E3. AssetRegistry (entity/topic → asset mapping)

Committed static data mapping a namespaced key to one or more `asset_id`s
with a deterministic priority.

| Attribute | Type | Notes |
|-----------|------|-------|
| `key` | str | `^(person|topic|asset):[a-z0-9][a-z0-9-]*$`. Namespaces extensible. |
| `asset_ids` | list[str] | Ordered by registry priority (index 0 = preferred). |
| `segment_affinity` | set[str] | Subset of `{us-equity, domestic-equity, crypto, macro}`. Drives segment-aware selection (R6). |

**Invariants**

- I8 (referential integrity). Every `asset_id` in the registry resolves to
  a `CuratedAsset` in the library (filed OR deferred). A dangling id is a
  gate failure (R8). An orphan asset (filed but unregistered) is allowed
  but never selectable; the CI gate warns, not fails.
- I9 (deterministic order). `asset_ids` is an explicit ordered list; ties
  are never broken by hash/RNG/wall-clock (R5).
- I10 (deferred selectability). A key whose only resolvable asset is
  `deferred` contributes **no** selectable candidate — selection skips it
  silently and falls through (R5, R6). Deferred never renders.

---

## E4. CuratedSelection (the per-segment selection result)

The deterministic output of entity-extraction + selection for one segment.

| Attribute | Type | Notes |
|-----------|------|-------|
| `asset` | `CuratedAsset \| None` | The chosen filed asset, or `None` (no match → fall through). |
| `matched_key` | str \| None | The registry key that won (for audit/caption). |
| `match_reason` | str | Reused `WatchlistMatch.reason` shape (u64). |

**Invariants**

- I11 (filed-only). `asset`, when non-`None`, has `state == filed`. A
  `deferred` key never produces a non-`None` selection (I10).
- I12 (determinism). Same `(segment, items, library, registry)` → byte-equal
  selection. Tie-break order: segment affinity match → registry key priority
  order → `asset_ids` index → `asset_id` lexical (R5).
- I13 (graceful empty). No match / ambiguous / empty segment →
  `asset is None`; the hero falls through to the existing AI /
  data-confidence chain with no crash (R6, R9).

---

## E5. CuratedAssetState (the deferred-asset state machine)

The lifecycle of a registered key's binary. The library root + registry
together encode the state; the CI gate is the transition validator.

| State | Meaning | Binary | Manifest | Selectable | CI gate |
|-------|---------|--------|----------|------------|---------|
| `deferred` | Key registered, binary not yet filed; explicitly marked `not-yet-available`. | absent | present, `allowed_use` includes the deferral marker, OR a sibling `.deferred` marker file | **no** (I10) | **passes** (explicit) |
| `filed` | Cleared binary committed alongside its manifest. | present | present, republishable, no deferral marker | **yes** | **passes** iff binary clears R2/R3/R4 + budget |
| `(invalid)` | Binary missing with **no** deferral marker, OR binary present with no manifest, OR disallowed license. | — | — | n/a | **fails** (R8) |

**Transitions**

```
(register key) ──> deferred ──(operator files cleared binary + drops marker)──> filed
                      │                                                            │
                      └── stays non-selectable; gate green ───────────────────────┘
filed ──(binary fails R2/R3/R4/budget OR loses manifest)──> (invalid) ── gate RED
deferred ──(marker removed but no binary)──> (invalid) ── gate RED
```

**Invariants**

- I14 (explicit only). The *only* way a registered key may lack a binary
  and stay green is an **explicit** `deferred` declaration. A silent empty
  entry is `(invalid)` and fails the gate (R8). This is the binding
  realization of the user's "no silent empties" policy.
- I15 (auto-promotion verification). When a `deferred` key's binary is
  later filed, no spec change is needed: the gate re-classifies it as
  `filed` and applies R2/R3/R4 + budget automatically. The marker's removal
  is the transition signal.
- I16 (deferral marker hygiene). The deferral marker is a literal, machine-
  checkable token (recommended: a sibling `{asset_id}.deferred` empty
  marker file under the category folder, OR `allowed_use` containing the
  exact substring `not-yet-available`). Pin the exact mechanism in
  implementation; the FD requires only that it be explicit and grep-stable.
