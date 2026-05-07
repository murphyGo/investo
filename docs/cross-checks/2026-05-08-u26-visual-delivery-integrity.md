# Cross-Check: u26 visual-delivery-integrity

**Scope**: u26 visual-delivery-integrity
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 6 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u26 is a Wave 1 P0 follow-up from the 2026-05-07 persona evaluation (persona #2 — P0 + P1). It diagnoses why the five public segmented archive entries from 2026-05-06 were missing embedded SVG cards on the public site, backfills the affected day with curated visual assets, and standardises the trust signals that ride along with every generated card (font, version fallback, dark-mode legibility). The unit does not introduce paid sources, accounts, trading, external image scraping, or new external dependencies.

**Plan**: `aidlc-docs/construction/plans/u26-visual-delivery-integrity-code-generation-plan.md`
**Goal**: Diagnose and fix the post-u24 regression where archive pages no longer render embedded SVG cards, then standardise visual trust signals (font, version fallback, dark-mode legibility).

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/visuals/render.py` (Noto Sans KR + Arial fallback in the SVG `font-family` stack) | Korean glyphs render correctly on GitHub Pages where Noto Sans KR is available; the Arial fallback prevents `.notdef` boxes when Noto is unavailable. |
| FR-003 static web publishing | ✅ | `tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs`, `scripts/backfill_2026_05_06_visuals.py` | New regression pin asserts the segmented publish path runs `assets.insert_visual_links` and stages SVG assets next to each segment archive markdown; 2026-05-06 segment archives were backfilled with 9 SVG + 9 manifest assets across the three segments. |
| FR-008 segmented briefing | ✅ | `tests/unit/orchestrator/test_run_pipeline.py` (segment-aware insertion), `scripts/backfill_2026_05_06_visuals.py` (per-segment backfill) | Each domestic-equity / us-equity / crypto segment runs visual link insertion and asset staging independently; the backfill produced one `2026-05-06.assets/` directory per segment with three SVGs (data-confidence / market-snapshot / watchlist-relevance) plus their JSON manifests. |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/visuals/render.py` (deterministic SVG only), `src/investo/visuals/provenance.py::_investo_version` | u26 only changes existing visual-rendering surfaces; no Anthropic SDK introduced, no paid call surface added, no external image fetch enabled (`EXTERNAL_IMAGE_SCRAPING_ENABLED` remains `False`). |
| NFR-003 graceful degradation | ✅ | `src/investo/visuals/provenance.py::_investo_version` (3-tier fallback chain) | Version fallback walks `investo.__version__` → `git rev-parse --short=7 HEAD` → `"dev"`. The 7-hex-char regex match (`^[0-9a-f]{7,40}$`) ensures `git` output that is not a clean SHA falls through to `"dev"` rather than leaking a non-version string. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/orchestrator/pipeline.py` (publish ordering unchanged), publisher's `verify_disclaimer` | u26 only modifies pre-publish visual rendering; `verify_disclaimer` remains the publish-time gate. The backfill script invokes the production `insert_visual_links` and the same downstream gates (`disclaimer`, `summary_quality`, `leak_guard`, `dimension validation`) on the rebuilt markdown. |
| NFR-005 consistency / DRY | ✅ | `src/investo/visuals/render.py` (single SVG style block applies to every card type), `src/investo/visuals/provenance.py::_investo_version` | The dark-mode style hooks (class selectors driven by `@media (prefers-color-scheme: dark)`) live in one render path; both `DataConfidenceCard` and `WatchlistCard` inherit identical light/dark behaviour. The version fallback is a single helper used by every provenance builder. |
| NFR-006 testing | ✅ | `tests/unit/visuals/test_render.py` (font-family + dark-mode), `tests/unit/visuals/test_provenance.py` (version fallback chain — 5 + auto-extended SHA test), `tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs` | +10 targeted tests (1172 → 1182): font-family stack, dark-mode `<style>` block, 3-tier version fallback, segmented publish visual-link insertion, asset staging path layout. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/_internal/redaction.py` (u27 chokepoint, unchanged) | u26 does not introduce new redaction surfaces; the `_investo_version` helper emits at most a 7-hex-char SHA or `"dev"`, neither of which match any secret-shape pattern. The 7-hex regex is a plain string literal to avoid the chokepoint guard's secret-pattern false positive. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| A test guarantees that on the segmented publish path `assets.insert_visual_links` runs and the produced markdown contains `![](...)` references for staged SVG assets. | ✅ | `tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs` |
| Staged assets are verified to land beside the archive markdown after a dry-run publish (path layout regression pin). | ✅ | Same regression pin asserts each segment's staged SVGs land in `<segment>/<YYYY>/<MM>/<YYYY-MM-DD>.assets/` next to the archive markdown. |
| 2026-05-06 segment archives (us / crypto / domestic) are backfilled with visual links (re-publish or curated patch). | ✅ | `scripts/backfill_2026_05_06_visuals.py`; produced 3 archive markdown rewrites + 9 SVG + 9 manifest assets across `domestic-equity / us-equity / crypto` 2026-05-06 directories; all gates passed (disclaimer / summary_quality / leak_guard / dimension validation). |
| Generated SVG cards declare `font-family` including `Noto Sans KR` with Arial fallback so Korean glyphs render on GitHub Pages. | ✅ | `src/investo/visuals/render.py` (font-family stack `Noto Sans KR, Arial, sans-serif`); `tests/unit/visuals/test_render.py` (font-family assertion). |
| `_investo_version()` fallback returns `"dev"` (or git short SHA when available) instead of `"0"`. | ✅ | `src/investo/visuals/provenance.py::_investo_version` (3-tier chain `investo.__version__` → `git rev-parse --short=7 HEAD` → `"dev"`, with `^[0-9a-f]{7,40}$` regex on the SHA path); `tests/unit/visuals/test_provenance.py` (5 fallback-chain tests + 1 auto-extended SHA test). |
| `DataConfidenceCard` and `WatchlistCard` provide a dark-mode-readable variant (CSS `prefers-color-scheme` rule or dark variant asset) so the cards are legible on the mkdocs dark theme. | ✅ | `src/investo/visuals/render.py` (option (a): single SVG with embedded `<style>` + `@media (prefers-color-scheme: dark)` rules driving classed `<rect>` / `<text>` elements); `tests/unit/visuals/test_render.py` (dark-mode style block assertion). |

---

## Regression Diagnosis

The five missing-SVG public archive entries from 2026-05-06 are **not** a code regression. The visuals module integration commit `e695bfb` (2026-05-08) landed *after* the four 2026-05-06 segmented briefings were published (commits `605744a`, `879cddf`, `9215b97`, `e3cc413`, all 2026-05-06). At publication time the orchestrator's segmented publish path simply did not include an `assets.insert_visual_links` step yet, so the archive markdown was written without `![](...)` references and no SVGs were staged.

Republishing the 2026-05-06 segmented briefings now would rebuild visual delivery, but the narrative content is already public and we wanted to avoid disturbing reader-visible Stage 2 output. We therefore handled 2026-05-06 with a one-shot curated backfill (`scripts/backfill_2026_05_06_visuals.py`) that repairs the truncated quote-block lines, renders the three SVG cards per segment with their JSON manifests, and inserts the markdown image links via the production `insert_visual_links`. A new regression pin (`test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs`) guarantees that any future segmented run always emits `![](...)` references and stages SVGs beside the markdown.

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed (174 files)
- `uv run mypy --strict src/` — passed (66 source files)
- `uv run pytest -q` — 1182 passed (1172 → 1182, +10 new tests)
- `uv run mkdocs build --strict` — passed (no new mkdocs nav/content changes in u26)

---

## Backfill Artifacts

The 2026-05-06 backfill produced (commit-pending) the following artifacts under `archive/`:

- `archive/domestic-equity/2026/05/2026-05-06.md` (markdown rewrite)
- `archive/domestic-equity/2026/05/2026-05-06.assets/` — 3 SVG + 3 manifest
- `archive/us-equity/2026/05/2026-05-06.md` (markdown rewrite)
- `archive/us-equity/2026/05/2026-05-06.assets/` — 3 SVG + 3 manifest
- `archive/crypto/2026/05/2026-05-06.md` (markdown rewrite)
- `archive/crypto/2026/05/2026-05-06.assets/` — 3 SVG + 3 manifest

Total: 3 archive markdown rewrites + 9 SVGs + 9 manifests. Every SVG passes `validate_visual_asset` (dimensions in `[100, 2000]`); every manifest passes `VisualProvenanceManifest` schema validation; every rewritten markdown passes `verify_disclaimer`, `summary_quality`, and `briefing.leak_guard.scan`.

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u26 does not introduce any LLM client; the backfill script is purely deterministic SVG / manifest rendering and reuses the production `insert_visual_links`. No `claude -p` invocation is required for the backfill. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | All u26 source changes are inside `visuals/` (`render.py`, `provenance.py`); the regression pin lives under `tests/unit/orchestrator/` but only exercises orchestrator → visuals via the existing public surface. No new cross-unit import added. |
| 무료 API only (no paid keys) | ✅ | No new external endpoints. `EXTERNAL_IMAGE_SCRAPING_ENABLED` remains `False`. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; the backfill script invokes the same downstream gate chain on the rebuilt markdown. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u26 does not change notifier targets. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | u26 does not touch `raw_metadata`. The new `_investo_version` helper feeds `VisualProvenanceManifest.version`, which is already routed through u24's `sanitize_provenance_text` chokepoint (now u27's `redact_text` chokepoint). |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | The `_investo_version` output is deterministically constrained to a 7-hex SHA, `"dev"`, or `investo.__version__` — none of which match any secret-shape pattern. The 7-hex regex is held as a plain string literal so the chokepoint guard does not classify it as a secret pattern. |
| `defusedxml` only (no raw stdlib XML) | ✅ | `src/investo/visuals/render.py` continues to emit SVG via string templates only; no XML parser is involved on the render path. SVG dimension validation in `visuals/assets.py` continues to use `defusedxml`. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M2** — `_investo_version` SHA branch tightened with a `^[0-9a-f]{7,40}$` regex so `git rev-parse` output that is not a clean SHA (e.g., a partial line, an error string, a tag-decorated ref) falls through to `"dev"` instead of leaking a non-version string into provenance metadata.
  - **M3** — `_investo_version` docstring corrected so the example fallback chain matches the actual implementation order (`investo.__version__` → 7-hex SHA → `"dev"`); prior wording could be misread as `"dev"` preceding the SHA branch.
- Deferred to TECH-DEBT (no Critical / High findings outstanding):
  - **M1** → `DEBT-049 (Medium)` — SVG dark-mode CSS uses OS-level `prefers-color-scheme` only, which can disagree with mkdocs Material's `data-md-color-scheme="slate"` site toggle.
  - **M4** → `DEBT-050 (Low)` — `scripts/backfill_2026_05_06_visuals.py` is single-use; retire or generalise around 2026-08.

---

## TECH-DEBT Surfaced by This Unit

Two new items registered (`docs/TECH-DEBT.md`):

- **DEBT-049 (Medium)** — SVG dark-mode CSS uses `@media (prefers-color-scheme: dark)` evaluated at the `<img>` document level, which only sees the OS-level scheme. mkdocs Material's site toggle (`data-md-color-scheme="slate"`) is invisible to the embedded SVG, so an OS-light + site-dark (or OS-dark + site-light) reader sees a mismatched card. Fix options: (b) inline `<svg>` embed + parent class selector that picks up the site attribute, or (c) light/dark variant pair plus a `<picture>` element on the markdown side.
- **DEBT-050 (Low)** — `scripts/backfill_2026_05_06_visuals.py` is a one-shot curated backfill specific to 2026-05-06 quote-block lines and the three card types active at that date. Reuse for any other date would require code changes. Plan to either delete the script around 2026-08 (after the 2026-05-06 archive has aged out of the "latest" view) or generalise into a reusable `backfill_visuals(target_date, segments)` helper if a second backfill request appears.

---

## Gaps Analysis

No gaps found.

## Proposed Actions

- No requirements/design changes.
- TECH-DEBT updates already registered (DEBT-049, DEBT-050).
- `mkdocs build --strict` re-verified at u26 close (passed); will be re-verified once again at the close of the broader u25-u33 follow-up wave.
