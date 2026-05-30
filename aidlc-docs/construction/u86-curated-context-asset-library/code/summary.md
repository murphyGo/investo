# u86 — Curated Context Asset Library (Code Generation Summary)

**Status**: ✅ Complete (6/6 steps) — 2026-05-30
**Plan**: `aidlc-docs/construction/plans/u86-curated-asset-library-code-generation-plan.md`
**Stage Decision**: Functional Design **Required** (new product capability, new asset kind + clearance contract + state machine) · NFR Requirements **Required** (new storage budget, license-compliance CI gate, R13 manifest hygiene). FD authored under `functional-design/`, NFR under `nfr-requirements/`.

## What shipped

A pre-curated, license-clean, **committed** local context-image library mapped by entity/topic, drawn at briefing time via deterministic entity match. **No runtime scraping** — `EXTERNAL_IMAGE_SCRAPING_ENABLED` stays `False`; the curated path never performs a network fetch.

### Step 1 — Layout + manifest kind
- Library root `assets/library/{category}/{asset-id}.{ext}` with sibling `{asset-id}.manifest.json` (run-time/committed domain, parallel to `archive/`).
- `visuals/policy.py`: added `curated-licensed` to `AllowedExternalAssetKind`; reuses the existing `ExternalAssetManifest` (no second manifest class).
- New `assert_curated_asset_allowed(manifest)` allows `curated-licensed` **without** requiring scraping while still enforcing manifest presence + public-URL provenance + allowed `license`/`allowed_use`. `explicit-license` runtime scraping stays gated exactly as before.

### Step 2 — License-clearance gate (load-time + CI)
- `visuals/curated.py::load_library` walks `assets/library/`, requires a sibling manifest per asset, validates schema + allowed-license/`allowed_use`, and validates committed binaries via the existing `assets.py` PNG/JPEG/SVG signature + dimension checks (reused, not duplicated).
- `scripts/check_curated_assets.py` (mirrors `check_no_paid_apis.py`) is the CI gate: fails on any asset without a clean manifest, disallowed license, byte/dimension budget violation, or orphan manifest/binary. R13 enforced — manifests rejected if any redaction pattern matches.
- **Deferred-asset state machine (I14/I15/I16, AC-1.2)**: a manifest-only key with no committed binary is an **explicit-deferred** asset (green); a registered key that silently produces no usable asset is **red**. Selection skips deferred keys.

### Step 3 — Registry + extraction
- Static committed registry (`default_registry()`) maps `person:` / `topic:` / `asset:` keys → asset ids.
- Deterministic extraction reuses u64 watchlist matcher primitives (`_match_term_with_aliases`, boundary/short-ticker matching) — no new fuzzy matcher.
- Selection deterministic given identical inputs: registry priority then key lexical, then registry-ordered asset ids; segment-affinity gated (crypto prefers `asset:`/crypto topics, US-equity prefers US topics/persons).

### Step 4 — Pipeline injection
- New `curated-context-image` card kind in `_HERO_PRIORITY`, ranked just below `external-context-image` (preferred real-photo hero now that scraping is off): **external-context-image > curated-context-image > ai-market-hero > data-confidence**.
- Injected asset passes the existing validation gate and writes a provenance manifest via `write_manifest`; caption via `provenance_caption` (source/license/author). `build_curated_provenance` added in `provenance.py` for the `curated-licensed` representation.
- Korean `_CARD_LABELS` entry + section anchor consistent with `external-context-image`.

### Step 5 — Seed library + registry seed
- 13 seed keys filed as **manifest-only / deferred** (no binaries committed this unit): `person:` jerome-powell, us-president; `asset:` bitcoin, ethereum; `topic:` federal-reserve, cryptocurrency, us-equity-market, korea-market, kospi, stock-market-chart, macro, wall-street, inflation.
- License basis recorded per manifest (US-federal PD portraits, PD crypto logos, PD/CC0 stock). `check_curated_assets.py` reports `0 filed, 13 deferred` (explicit-deferred green) — operator commits cleared binaries later without code changes.

### Step 6 — Tests, docs, gate
- New tests: `test_curated.py` (loader/clearance/registry/selection determinism/segment-awareness/deferred skip), `test_check_curated_assets.py` (CI gate: orphan/missing/disallowed/budget), `test_curated_injection.py` (hero injection + provenance caption + disclaimer retention + no-match fallback); `test_assets.py` updated for the new card kind.
- Negative policy pins: news-photo/meme/trademark/unofficial-portrait fixtures rejected by clearance; `EXTERNAL_IMAGE_SCRAPING_ENABLED` asserted `False` and no runtime fetch on the curated path.
- `docs/DESIGN.md` visuals section documents the library + no-scraping guarantee.

## Gate (full, 2026-05-30)
- `ruff check` + `ruff format --check` (changed scope) — clean
- `mypy --strict` (15 changed source files) — clean
- `python scripts/check_curated_assets.py` — exit 0 (`0 filed, 13 deferred`)
- `pytest` full suite — **2845 passed** (+1 net; visuals 151)
- `mkdocs build --strict` — pass

## Requirements traceability
- R1–R9, E1–E5, I1–I16 (FD); AC-1.1..AC-1.6, TS-1..TS-3 (NFR) — all MET.
- TS-1 no pillow (reuse signature parsing); TS-3 CI gate mirrors `check_no_paid_apis.py`.

## TECH-DEBT
None new. Seed binaries deliberately deferred (operator clearance) — tracked by the explicit-deferred state, not as debt.
