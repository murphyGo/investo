# Business Rules — `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Source**: u86-curated-asset-library-code-generation-plan.md + 2026-05-28 user-confirmed policy (deferred-asset allowance, seed-minimum-real-binaries).

Rules are listed in order of precedence. `R1`-`R9`. Entity ids (`E1`-`E5`)
and invariants (`I1`-`I16`) reference `domain-entities.md`. NFR ACs
(`AC-1.1`-`AC-1.6`) reference `nfr-requirements/nfr-requirements.md`.

---

## R1. Every library asset requires a manifest (AC-1.2, I1)

- A binary under the library root with no sibling manifest is rejected at
  load time and by the CI gate. A manifest with no binary is allowed **only**
  under the explicit `deferred` declaration (R8); otherwise rejected.
- The curated manifest is the existing `ExternalAssetManifest`
  (E2) with `kind="curated-licensed"`. No parallel manifest type is
  introduced.

## R2. Republishability is the clearance criterion (AC-1.3, I3)

- An asset clears only if its `license` + `allowed_use` permit republication
  to a **public GitHub Pages site + public Telegram rebroadcast**.
- Accepted bases: US federal-government public-domain official portraits
  (17 U.S.C. §105 — e.g. Powell / President official photos); file-specific
  PD/CC0 declarations (e.g. the public-domain Bitcoin logo); commercially-
  reusable stock under the Unsplash / Pexels licenses (and equivalents).
- The license string must be a recognized clean token; an unrecognized or
  ambiguous license fails the gate (fail-closed).

## R3. Excluded categories are hard-rejected (AC-1.3, AC-1.5)

- News-article photos, community memes, corporate trademark logos (beyond
  cleared PD marks), and unofficial photos of real people are rejected by
  the clearance gate regardless of any manifest claim.
- A federal-PD portrait is clean **only** for the official-government file;
  a news-agency reshoot of the same person is rejected. Crypto logos are
  clean only with a file-specific PD/CC0 declaration; a trademark brand-
  guideline logo is excluded.

## R4. Curated assets pass the existing binary gate, with scraping disabled (AC-1.1, AC-1.5, I4)

- A `curated-licensed` asset is validated by the **existing**
  `visuals/assets.py` PNG/JPEG/SVG signature + dimension gate (100-2000 px)
  and the byte/dimension budget (AC-1.1). No new image parser; pillow is
  NOT introduced (TS-1).
- Clearance for `curated-licensed` is granted **without** requiring
  `scraping_enabled` (a dedicated `assert_curated_asset_allowed` branch or
  kind-aware path), while the `explicit-license` runtime-scraping path stays
  gated exactly as today — `EXTERNAL_IMAGE_SCRAPING_ENABLED` remains `False`
  and is never read for the curated path.

## R5. Selection is deterministic (AC-1.3, I9, I12)

- Given the same `(segment, items, library, registry)`, selection yields a
  byte-equal `CuratedSelection` (E4). No wall-clock, no RNG, no hash-order.
- Tie-break order, fixed: segment-affinity match (R6) → registry key
  priority order → `asset_ids` index → `asset_id` lexical.

## R6. Segment-aware extraction reuses the u64 matcher (AC-1.3, I8, I13)

- Entity/topic extraction maps the day's `NormalizedItem`s + segment to
  registry keys using the **existing** `briefing/watchlist.py` matcher
  primitives (`_match_term_with_aliases`, boundary matching,
  `_matches_short_ticker`). No new fuzzy matcher (reuse u64).
- Segment affinity gates candidacy: crypto segment prefers
  `asset:`/crypto topics, us-equity prefers US topics/persons, domestic
  prefers KR topics, macro-driven days prefer `topic:federal-reserve` /
  `topic:inflation`. A key whose `segment_affinity` excludes the current
  segment is not a candidate.
- An empty / ambiguous segment selects nothing (`asset is None`).

## R7. No secret in any manifest or provenance artifact (AC-1.6, I5, R13)

- No `CuratedAsset` / `AssetRegistry` / provenance value may contain a
  secret. Manifest text routes through the project-wide u27 redaction
  chokepoint (`investo._internal.redaction.redact_text`) exactly as
  `visuals/provenance.py` already does. The CI gate rejects any manifest
  matching the redaction patterns.

## R8. Deferred-asset state is explicit; silent empties are rejected (AC-1.2, I7, I10, I14, I15)

- A registered key may lack a committed binary **only** when it is
  explicitly declared `deferred` (E5) via the machine-checkable deferral
  marker (I16). A deferred entry **passes** the strict CI gate.
- A deferred key is **never selectable** (I10/I11): selection skips it and
  the hero falls through. Deferred assets never render and never emit a
  provenance caption.
- A binary-absent key with **no** deferral marker is `(invalid)` and the CI
  gate **fails** with a clear message. This is the binding "no silent
  empties" rule.
- Auto-verification on fill (I15): when the binary is later committed and
  the deferral marker removed, the gate re-classifies the key as `filed` and
  applies R2/R3/R4 + budget automatically — no spec edit required.

## R9. Pipeline injection: curated hero with provenance, no-match fallback (AC-1.4, AC-1.5, I13)

- A selected `filed` asset is injected into `prepare_segment_visual_assets`
  as a new `curated-context-image` card kind, ranked in `_HERO_PRIORITY`
  **just below `external-context-image` and above `ai-market-hero`**
  (curated is the preferred *real-photo* hero now that runtime scraping is
  off). Confirmed priority:
  `external-context-image > curated-context-image > ai-market-hero > data-confidence`.
- The injected asset must pass the existing validation gate and write a
  provenance manifest via `write_manifest`, with the caption produced by
  `provenance_caption` (source / license / author). Reuse
  `build_external_provenance`, or add a thin `build_curated_provenance`
  only if the existing builder cannot represent `curated-licensed`.
- The disclaimer remains present and unchanged. When no curated asset
  matches, the hero falls back to the existing AI / data-confidence chain
  with no regression.

---

**Violation examples (reject in review)**: a library binary with no
manifest or a silent binary-absent key (R1/R8); a news-photo / meme /
trademark / unofficial-portrait asset passing clearance (R3); reading
`EXTERNAL_IMAGE_SCRAPING_ENABLED` or fetching at run time on the curated
path (R4); selection that varies across identical runs (R5); a new fuzzy
matcher instead of u64 reuse (R6); a secret leaking into a manifest (R7);
a deferred key rendering as a hero (R8); the disclaimer dropped on a curated
hero (R9).
