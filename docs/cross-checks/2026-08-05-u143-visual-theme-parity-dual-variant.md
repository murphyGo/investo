# Cross-check — u143 visual-theme-parity-dual-variant

**Scope**: component `u143 visual-theme-parity-dual-variant`
**Date**: 2026-08-05
**Checked by**: Codex
**Implementation head**: `09be264`

## Summary

| Status | Count | Percentage |
|---|---:|---:|
| ✅ Complete | 7 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total ACs** | **7** | **100%** |

**Verdict**: APPROVE. All unit acceptance criteria and all six fixed contracts
are implemented, persistently tested where applicable, and documented. No new
development-plan item or technical-debt entry is required.

## Requirement traceability

| Requirement | Status | u143 evidence | Notes |
|---|---|---|---|
| FR-002 — consistent Korean briefing | ✅ | `src/investo/visuals/render.py:30-87`; `tests/unit/visuals/test_render.py` | Existing content contract is unchanged; visual cards now follow the reader-selected site theme. |
| FR-003 — static Pages publication and archive | ✅ | `src/investo/visuals/assets.py:169-407`; `.github/workflows/quality.yml:32-74` | Pure Markdown pairs remain archive-native; strict site build and theme contract now bind in Quality CI. |
| NFR-005 — maintainability | ✅ | `src/investo/visuals/render.py:40-81`; `src/investo/visuals/paths.py:15-16`; `docs/DESIGN.md` TD-011 | One palette factory, one fragment home, registry-driven card coverage, no duplicated dark manifest policy. |
| NFR-006 — testing | ✅ | `tests/unit/visuals/test_render.py`; `test_assets.py`; `test_check_material_theme_contract.py`; `tests/unit/orchestrator/test_run_pipeline.py`; `tests/integration/test_pipeline.py` | Unit, integration, structural, fail-closed built-output, and full-suite coverage all pass. |

## Fixed-contract matrix

| Contract | Status | Evidence |
|---|---|---|
| #1 Style chokepoint | ✅ | `_CARD_PALETTE`, `CardStyleVariant`, `build_card_style`, and byte-compatible `_CARD_STYLE` at `src/investo/visuals/render.py:30-87`; registry test at `tests/unit/visuals/test_render.py:111`. |
| #2 Dual output + Markdown pair | ✅ | Forced pair write at `src/investo/visuals/assets.py:276-287`; pair assembly at `assets.py:520`; exact output tests at `tests/unit/visuals/test_assets.py:203-217`. |
| #3 Stable primary membership + companions | ✅ | `PreparedVisualAssets.companion_paths` at `assets.py:169-174`; ordered assertions at `test_assets.py:293-310`; staged dark git-add at `test_run_pipeline.py:1130-1145`. |
| #4 GitHub fallback spelling | ✅ | Single-home constants at `src/investo/visuals/paths.py:15-16`; Pages CSS/HTML guard at `scripts/check_material_theme_contract.py:17-129`. Raw GitHub stacking remains the ratified non-canonical fallback. |
| #5 Storage/provenance | ✅ | One primary manifest metadata at `assets.py:854-865`; dark binary-only validation at `assets.py:276-286`; no-dark-manifest regression at `test_run_pipeline.py:1130-1134`; measured 39,009 B/run delta in the plan. |
| #6 Inline surfaces | ✅ | Site-scoped heatmap at `calendar_heatmap.py:179-216` and sparkline at `quality_sparkline.py:20`; populated/empty no-media tests in `test_calendar_heatmap.py` and `test_quality_sparkline.py`. |

## Acceptance criteria detail

| Criterion | Status | Evidence |
|---|---|---|
| AC-143.1 — light/dark site-toggle parity | ✅ | CI builds the repo site, checks both exact Material hiding rules, then builds an exact pair through installed MkDocs Material and requires both built-HTML fragment `src` values (`scripts/check_material_theme_contract.py:17-129`; workflow lines 69-74). |
| AC-143.2 — default/OS fallback | ✅ | Primary renderer default is forced light (`render.py:84-87`); Material default hides dark and slate hides light. No card-internal media query can contradict the parent state. The exact CSS pair is fail-closed in CI. |
| AC-143.3 — new-card chokepoint | ✅ | `_RenderableCard` is the single type registry and `test_every_renderable_card_type_inherits_light_and_dark_variants` enumerates every member. |
| AC-143.4 — non-invasive auto compatibility | ✅ | `build_card_style("auto")` is byte-compared with `tests/fixtures/u143_card_style_auto.txt`; OG remains independent auto. The rerunnable legacy backfill now explicitly requests `variant="auto"` (`scripts/backfill_2026_05_06_visuals.py:265`). |
| AC-143.5 — fragment isolation | ✅ | Fragments are constants used only by `_visual_block`; path/manifest/staging assertions in `test_assets.py:305-380` and git-add assertions prove no `#` enters filesystem arguments. |
| AC-143.6 — inline site-scoped surfaces | ✅ | Both populated and empty heatmap/sparkline paths contain slate ancestor rules and no production `@media`; no writer/manifest path changed, so file delta is zero. |
| AC-143.7 — tests strengthened | ✅ | Production assertions now require pairs and 27 files (`test_run_pipeline.py:1117-1145`; `tests/integration/test_pipeline.py:255-262`). Legacy empty mapping and fragment-free PNG/JPEG tests remain. |

## Validation evidence

- `uv lock --check`: 65 packages resolved, no lock drift.
- Ruff check/format: 569 Python files passed.
- Strict mypy: 252 source files passed.
- Full pytest: **4,319 passed in 267.90 seconds**.
- Anthropic SDK, paid API, curated-assets, and image-store policy guards passed.
- `mkdocs build --strict` passed on Material 9.7.6.
- Combined CSS + actual ephemeral built-HTML theme contract passed.
- `git diff --check` passed; no archive/site-doc generated residue remained.
- Cumulative fresh-eyes review approved with zero remaining
  Critical/High/Medium/Low findings.

## Deferred and non-goal audit

- Existing pre-u143 archives are intentionally not backfilled. Their old
  single-link behavior is preserved; the one-shot 2026-05-06 script remains
  explicitly OS-auto if rerun.
- Raw GitHub visual behavior awaits the first honest post-u143 production
  archive. Pair stacking is the ratified fallback, not a correctness gap;
  Pages is the canonical reader surface and is fully guarded.
- OG cards, photo heroes, palette contrast tuning, `<picture>`, per-dark
  sidecars, and double-fetch optimization remain correctly out of scope.

## Gaps and proposed actions

None. Development Plan additions: 0. TECH-DEBT additions: 0.
