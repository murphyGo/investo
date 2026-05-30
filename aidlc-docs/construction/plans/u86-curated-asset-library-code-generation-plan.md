# Code Generation Plan: `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Unit**: u86 curated-context-asset-library
**Stage**: Code Generation
**Status**: Implemented (6/6)
**Source**: 2026-05-28 user feature request — pre-curated, pre-verified local context-image library mapped by entity/topic, drawn from at briefing-generation time.
**Estimated Effort**: ~8-12 h
**Dependencies**:
- u19 briefing-visual-assets (visual pipeline + external-asset policy foundation)
- u24 visual-provenance-and-layout (provenance manifest + caption + hero/anchor layout)
- u26 visual-delivery-integrity (asset validation gate)
- u64 watchlist-entity-matching-and-actionability (entity matcher reused for entity extraction)

**No conflict with Wave 14 (u77–u85)**: Wave 14 is a behavior-preserving internal refactor of existing modules; u86 is an additive product unit. u86 should consume whatever `_internal/` / `visuals/` shapes exist at implementation time but introduces no Wave-14 dependency.

---

## Problem Statement

Segmented briefings currently get their above-the-fold hero image from one of three kinds (`_HERO_PRIORITY`: `external-context-image` > `ai-market-hero` > `data-confidence`). The `external-context-image` path (`visuals/external_image.py`) is a **runtime scraper that is disabled by policy** (`EXTERNAL_IMAGE_SCRAPING_ENABLED=False`), so in practice the hero is almost always an AI-generated card or a data-confidence card. There is no way to attach a real, contextually-appropriate photo (e.g. a Powell portrait when the day is FOMC-driven, a Wall Street image for a US-equity rally, a Bitcoin logo for a crypto-dominant day) without violating the no-runtime-scraping policy and without a license/republish-clearance story.

The user wants a **pre-curated, pre-verified, committed local asset library**: clean-license images sourced ahead of time, each carrying a license manifest, mapped to entity/topic keys, and selected deterministically at generation time — no per-run external fetch.

---

## Goal

Add a static, license-clean **curated context-asset library** that:
1. Lives as committed files under a single asset root with a per-asset license manifest.
2. Is keyed by entity/topic identifiers (e.g. `person:jerome-powell`, `topic:wall-street`, `asset:bitcoin`).
3. Is gated at load time by a **license-clearance check** that rejects any asset lacking a manifest or carrying a non-republishable license — runnable in CI.
4. Feeds the existing visual pipeline as a **new asset kind** so a matched clean image can become the segment hero with a provenance caption, **without** re-enabling runtime scraping.

---

## Confirmed Policy Decisions (binding)

1. **Sourcing scope: license-clean only.** Public-domain (US federal-government official portraits e.g. Powell/President official photos; PD crypto logos e.g. the Bitcoin logo) **plus** commercially-reusable stock (Unsplash / Pexels and equivalents). The clearance test is **republishability** to a public GitHub Pages site + public Telegram rebroadcast.
2. **Excluded**: news-article photos, community memes, corporate trademark logos (beyond cleared PD marks), and unofficial photos of real people.
3. **No runtime scraping.** `EXTERNAL_IMAGE_SCRAPING_ENABLED=False` stays. u86 never fetches at run time; it reads from the committed, pre-cleared local library only.
4. **Provenance/attribution mandatory.** Every used asset emits a provenance caption (source / license / author), reusing the existing `provenance.py` caption system. The disclaimer rules are unchanged.

---

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- **`visuals/policy.py`** — `ExternalAssetManifest` (kind/source_url/license/attribution/author/fetched_on/allowed_use) and `assert_external_asset_allowed`. **Extend** the `AllowedExternalAssetKind` literal with a new `curated-licensed` kind rather than inventing a parallel manifest type.
- **`visuals/provenance.py`** — `build_external_provenance`, `provenance_caption`, `VisualProvenanceManifest`, `write_manifest`/`read_manifest`. Reuse for the used-asset caption + provenance manifest write. Do not add a second caption system.
- **`visuals/assets.py`** — `prepare_segment_visual_assets`, `_HERO_PRIORITY`, `_SECTION_ANCHORS`, `insert_visual_links`, the PNG/JPEG/SVG dimension + manifest validation gate. The curated asset must flow through this validation gate and slot into the hero priority.
- **`visuals/external_image.py`** — the runtime scraper. u86 does **not** call it and does **not** re-enable it. The curated library is the no-fetch alternative source of an `external-context`-class hero.
- **`briefing/watchlist.py`** — `match_watchlist_items`, `_match_term_with_aliases`, `WatchlistMatch(confidence/reason/matched_alias)`, `_matches_short_ticker`. Reuse the boundary-aware matcher for entity extraction; do not write a new fuzzy matcher.

---

## Scope Boundary

In scope:
- A committed asset library root with per-asset license manifests.
- A static entity/topic → asset registry.
- A load-time + CI license-clearance gate.
- Deterministic entity extraction from a segment's items and deterministic asset selection.
- Injection of the selected asset into the existing visual pipeline as a new clean asset kind, with provenance caption.
- An initial seed candidate list (assets are added by the operator; this unit ships the structure + seed registry, not necessarily the binary files).

Out of scope:
- Any runtime/external image fetch (policy: scraping stays off).
- Re-enabling `EXTERNAL_IMAGE_SCRAPING_ENABLED`.
- An image-editing / cropping / generation pipeline (AI hero stays as-is in `openai_image.py`).
- A new fuzzy entity matcher (reuse u64).
- Auto-downloading seed assets in code (operator places cleared files; CI verifies them).

---

## Stage Decision

- **Functional Design — REQUIRED (lightweight).** This unit introduces a new persisted artifact (the asset library + registry) with its own invariants (license clearance, entity-key mapping, deterministic selection). Author the three per-unit FD files (`business-logic-model.md`, `business-rules.md`, `domain-entities.md`) covering: the asset-library entity, the registry mapping entity, the clearance rules (numbered R1..Rn), and the entity-extraction → selection algorithm. Keep it tight — it is a single bounded artifact, not a new module fan-out.
- **NFR Requirements — REQUIRED (focused).** Two new NFR surfaces justify it:
  - **Repository size / storage budget** — committed binary images grow the git repo and the Pages deploy. Author an AC capping per-asset and total library byte budget, image dimension bounds (reuse the existing 100–2000 px gate), and a guidance note on format/compression.
  - **License-compliance AC** — a blocking AC asserting every library asset carries a republishable manifest, runnable as a CI gate (mirrors `check_no_paid_apis` style). Also: no secret leakage in manifests (R13), provenance-caption presence on every used asset.
  - Author `nfr-requirements.md` (`AC-1.1`..) + `tech-stack-decisions.md` (only if a new lib is needed — likely none; pillow is NOT required since dimension parsing already exists in `assets.py`; record that decision as a `TS-` entry: "no new dependency, reuse existing binary-signature/dimension parsing").

> **FD + NFR authored 2026-05-28** (planner). R-numbers and AC-numbers are now pinned — the developer may start Step 1.
> - FD: `aidlc-docs/construction/u86-curated-context-asset-library/functional-design/{business-logic-model,business-rules,domain-entities}.md` — rules **R1-R9**, entities **E1-E5** (`CuratedAsset` / `CuratedAssetManifest` alias / `AssetRegistry` / `CuratedSelection` / `CuratedAssetState`), invariants **I1-I16** (incl. the **deferred-asset state machine** I14/I15/I16).
> - NFR: `aidlc-docs/construction/u86-curated-context-asset-library/nfr-requirements/{nfr-requirements,tech-stack-decisions}.md` — ACs **AC-1.1** (storage budget) / **AC-1.2** (license-compliance CI gate, explicit-deferred recognized green) / **AC-1.3** (republishability + excluded-category) / **AC-1.4** (provenance caption) / **AC-1.5** (no runtime fetch) / **AC-1.6** (R13 secret hygiene); decisions **TS-1** (no pillow / reuse signature parsing) / **TS-2** (reuse manifest+provenance) / **TS-3** (stdlib CI gate mirroring `check_no_paid_apis.py`).
> - **Confirmed policy folded in**: deferred-asset allowance is explicit-only (R8/I14, AC-1.2) — silent empties fail the gate; seed ships a minimum of real cleared binaries (Step 5) with the rest deferred.

---

## Implementation Steps

### Step 1 — Asset library layout + license manifest schema `[x]`
- [x] Choose and document the library root. Recommended: `assets/library/` at repo root (run-time/committed asset domain, parallel to `archive/`), NOT under `docs/` or `aidlc-docs/`. Each asset is `assets/library/{category}/{asset-id}.{ext}` with a sibling `{asset-id}.manifest.json`.
- [x] Extend `visuals/policy.py`: add `curated-licensed` to `AllowedExternalAssetKind`. A curated asset's manifest is the existing `ExternalAssetManifest` with `kind="curated-licensed"`. Do NOT introduce a second manifest class.
- [x] Define the curated-asset clearance contract: `assert_external_asset_allowed` currently hard-rejects when `scraping_enabled=False`. Add a separate `assert_curated_asset_allowed(manifest)` (or a `kind`-aware branch) that allows `curated-licensed` **without** requiring scraping, while still enforcing the manifest presence + public-URL provenance + allowed `license`/`allowed_use` constraints. Runtime scraping for the `explicit-license` kind stays gated exactly as today.
- **Acceptance**: a `curated-licensed` manifest loads and passes clearance with scraping disabled; a missing manifest or a disallowed-license manifest is rejected; the existing `explicit-license` scraping path is unchanged (its tests stay green).

### Step 2 — License-clearance gate (load-time + CI) `[x]`
- [x] Implement a library loader that walks `assets/library/`, requires a sibling manifest per asset, validates the manifest against the schema + allowed-license/`allowed_use` constraints, and validates the binary via the existing `assets.py` PNG/JPEG/SVG signature + dimension checks (reuse, do not duplicate).
- [x] Expose a CI-runnable check (script entry parallel to the no-paid-apis check) that fails on any asset without a clean manifest, any disallowed license, any byte/dimension budget violation, or any orphan manifest/asset.
- [x] Enforce R13: a manifest must contain no secret value; reject anything matching the redaction patterns.
- **Acceptance**: the CI gate passes on the seed library and fails (with a clear message) on an injected unmanifested or disallowed-license fixture asset.

### Step 3 — Entity/topic registry + extraction `[x]`
- [x] Define a static registry mapping entity/topic keys → one or more asset ids. Key namespaces: `person:`, `topic:`, `asset:` (extensible). The registry is committed data (JSON or a typed module), not derived at run time.
- [x] Implement deterministic entity extraction for a segment: reuse `briefing/watchlist.py` matcher primitives (`_match_term_with_aliases` / boundary matching / `_matches_short_ticker`) to map the day's `NormalizedItem`s + segment to registry keys. No new fuzzy matcher.
- [x] Selection must be deterministic given the same inputs (stable ordering by registry priority then asset id; no wall-clock / RNG). Segment-aware: crypto segment prefers `asset:`/crypto topics, US-equity prefers US topics/persons, etc.
- **Acceptance**: a fixture segment with FOMC/Powell evidence selects `person:jerome-powell`; a crypto-dominant segment selects `asset:bitcoin`; selection is byte-stable across repeated runs; an empty/ambiguous segment selects nothing (no crash, falls through to the existing AI/data-confidence hero).

### Step 4 — Pipeline injection as new clean asset kind `[x]`
- [x] Wire the selected curated asset into `prepare_segment_visual_assets` so it participates in `_HERO_PRIORITY`. Decision: introduce a `curated-context-image` card kind ranked alongside/just below `external-context-image` (curated is the preferred real-photo hero now that scraping is off). Confirm the exact priority position in FD.
- [x] The injected asset must pass the existing validation gate (dimensions + manifest) and must write a provenance manifest via `write_manifest`, with the caption produced by `provenance_caption` (source/license/author). Reuse `build_external_provenance` adapted for `curated-licensed`, or add a thin `build_curated_provenance` if the existing builder cannot represent it.
- [x] Add a `_CARD_LABELS` entry (Korean) and a `_SECTION_ANCHORS`/hero behavior consistent with how `external-context-image` is placed.
- **Acceptance**: a segment with a matched curated asset renders it as the hero with a provenance caption; the disclaimer is still present; when no curated asset matches, the hero falls back to the existing AI/data-confidence chain with no regression.

### Step 5 — Seed library + registry seed `[x]`
- [x] Add the seed entity/topic registry entries for the candidate list below.
- [x] Add seed manifests (and, where the operator can place cleared files, the binaries) for the seed candidates. If binaries are not committed in this unit, the registry entry + manifest stub + a clearance-test allowance for "registered-but-unfiled" must NOT pass the strict CI gate silently — either commit the cleared asset or mark the key as not-yet-available so selection skips it.
- [x] Document, in the unit summary, exactly which seed assets were filed vs deferred and the license basis of each.
- **Acceptance**: at least one fully-filed seed asset per segment family (US / crypto / domestic-or-macro) passes the CI clearance gate and is selectable.

### Step 6 — Tests, docs, gate `[x]`
- [x] Unit tests: manifest schema + clearance (allow/reject), library loader (orphan/missing/disallowed), CI gate, entity extraction → selection determinism, segment-awareness, pipeline hero injection + provenance caption presence + disclaimer retention + no-match fallback.
- [x] Negative tests pinning policy: a news-photo/meme/trademark/unofficial-portrait fixture is rejected by clearance; `EXTERNAL_IMAGE_SCRAPING_ENABLED` is asserted still `False` and no run-time fetch occurs on the curated path.
- [x] Update `docs/DESIGN.md` visuals section to describe the curated library and its no-scraping guarantee.
- [x] Minimum gate: targeted pytest (visuals/briefing) + full suite, `ruff check` + `ruff format` on changed scope, `mypy --strict` on changed source, the new license-clearance CI check exit 0, `mkdocs build --strict`.

---

## Acceptance Criteria

- **AC-86.1** — A committed curated asset library exists with a per-asset republishable license manifest (`kind="curated-licensed"`), validated at load time.
- **AC-86.2** — A CI-runnable license-clearance gate rejects any library asset lacking a clean manifest, carrying a disallowed license, violating the byte/dimension budget, or orphaned.
- **AC-86.3** — Entity/topic keys (`person:`/`topic:`/`asset:`) map deterministically to assets; segment-aware selection is reproducible across runs.
- **AC-86.4** — A matched curated asset renders as the segment hero with a provenance caption (source/license/author) and the disclaimer intact; no-match falls back to the existing hero chain.
- **AC-86.5** — Runtime scraping stays disabled (`EXTERNAL_IMAGE_SCRAPING_ENABLED=False`); the curated path performs zero external fetches; excluded categories (news photo / meme / trademark / unofficial portrait) are rejected by clearance.
- **AC-86.6** — No secret value appears in any manifest or provenance artifact (R13).

---

## Step Dependency Graph

```
Step 1 (layout + manifest kind)
   ├─> Step 2 (clearance gate + CI)
   └─> Step 3 (registry + extraction)
              └─> Step 4 (pipeline injection)
Step 2, Step 4 ──> Step 5 (seed library)
all ──> Step 6 (tests + docs + gate)
```
Steps 2 and 3 can proceed in parallel after Step 1. Step 4 needs Step 3 (selection) and the Step 1 manifest kind. Step 5 needs the gate (Step 2) and the injection path (Step 4).

---

## NFR AC Coverage Map

NFR `AC-1.x` numbers pinned 2026-05-28 in `u86 .../nfr-requirements/nfr-requirements.md`.

| Concern | NFR AC | Covered by step |
|---------|--------|-----------------|
| Repository / Pages storage budget (per-asset + total bytes, dimension bounds) | AC-1.1 | Step 1, Step 2 |
| License-compliance blocking CI gate (explicit-deferred recognized green) | AC-1.2 | Step 2, Step 5 |
| Republishability clearance (excluded categories rejected) | AC-1.3 | Step 1, Step 2, Step 6 |
| Provenance-caption presence on every used asset | AC-1.4 | Step 4 |
| No runtime fetch / scraping stays disabled | AC-1.5 | Step 4, Step 6 |
| Secret hygiene in manifests (R13) | AC-1.6 | Step 2 |

---

## Seed Library Candidate List (license basis)

Operator-fileable, all republishable. License basis must be re-verified at filing time and recorded in each manifest's `license` / `allowed_use` / `source_url` / `author` / `fetched_on`.

| Registry key | Subject | Candidate source | License basis (republishable) |
|--------------|---------|------------------|-------------------------------|
| `person:jerome-powell` | Fed Chair official portrait | Federal Reserve official portrait (federalreserve.gov) / Wikimedia Commons mirror | US federal-government work → public domain (17 U.S.C. §105). Verify the specific file's PD tag. |
| `person:us-president` | US President official portrait | White House official portrait via Wikimedia Commons | US federal-government work → public domain. |
| `topic:federal-reserve` | Eccles / Fed building | Wikimedia Commons (federal-gov photo) or Unsplash | PD (federal photo) or Unsplash License (free commercial reuse, no attribution required but recorded). |
| `topic:wall-street` | NYSE facade / Wall Street street scene | Unsplash / Pexels | Unsplash License / Pexels License — free commercial reuse incl. republish. |
| `topic:us-equity-market` | Generic trading floor / ticker board | Unsplash / Pexels | Unsplash / Pexels License. |
| `topic:stock-market-chart` | Abstract candlestick / market chart photo | Unsplash / Pexels | Unsplash / Pexels License. |
| `asset:bitcoin` | Bitcoin logo (₿) | Wikimedia Commons "Bitcoin logo" | Public domain (the Bitcoin logo is released to the public domain). Verify the specific SVG/PNG file's PD declaration. |
| `asset:ethereum` | Ethereum diamond logo | Wikimedia Commons / ethereum.org brand assets | ethereum.org brand assets are CC0/PD-equivalent — verify the specific file; treat as cleared only if CC0/PD. |
| `topic:cryptocurrency` | Generic crypto / blockchain photo | Unsplash / Pexels | Unsplash / Pexels License. |
| `topic:kospi` / `topic:korea-market` | Seoul finance district / KRX building | Unsplash / Pexels (generic Seoul skyline) | Unsplash / Pexels License. Avoid trademarked KRX marks; use generic skyline. |
| `topic:inflation` / `topic:macro` | Generic economy / money photo | Unsplash / Pexels | Unsplash / Pexels License. |

Notes on clearance:
- **PD federal portraits**: only the official-government file is PD; a news-agency reshoot of the same person is NOT — reject those.
- **Crypto logos**: only file-specific PD/CC0 declarations are accepted; a brand-guideline trademark logo is excluded per policy.
- **Stock sites**: Unsplash/Pexels licenses permit republish without per-use attribution, but u86 records attribution in the manifest and emits a provenance caption anyway for trust.
- **Excluded by policy** (must be rejected by the Step 2 gate): news-article photos, community memes, corporate trademark logos, unofficial photos of real people.

---

## Non-Goals

- Runtime image fetching / scraping (stays disabled).
- AI image generation changes (`openai_image.py` unchanged).
- Image cropping/resizing/optimization pipeline.
- A new entity matcher (reuse u64).
- Auto-downloading seed binaries in code.

---

## How to Approve

Reply with one of:
1. **Request Changes** — name the step/AC/seed-row to revise.
2. **Continue to Next Stage** — planner authors the u86 FD (`business-logic-model.md` / `business-rules.md` / `domain-entities.md`) and NFR (`nfr-requirements.md` / `tech-stack-decisions.md`) with pinned R-numbers / AC-numbers, then a developer picks up Step 1.
