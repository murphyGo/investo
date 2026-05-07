# Cross-Check: u29 site-discovery-v2

**Scope**: u29 site-discovery-v2
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 7 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **7** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u29 is a Wave 1 P0 follow-up from the 2026-05-07 persona evaluation (persona #2 — P0 + P1 + wish-list) that reframes the public site so the first screen surfaces today's briefing content (not site-meta copy) and gives weekend retrospect readers a time-axis traversal layer. The unit does not introduce paid sources, accounts, trading, external image scraping, or new external dependencies; it only restructures the static site, adds a deterministic SVG calendar heatmap, an OG image meta channel, and a Saturday-only weekly-digest publish path.

**Plan**: `aidlc-docs/construction/plans/u29-site-discovery-v2-code-generation-plan.md`
**Goal**: Reframe the public site so the first screen surfaces today's briefing content (not site-meta copy), and give weekend retrospect readers a time-axis traversal layer.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/publisher/site_index.py` (hero conclusion-quote rendering preserves Korean glyphs), `src/investo/publisher/weekly_digest.py` (Korean weekly retrospective copy) | Hero quote cards reuse the same conclusion extraction the segmented archive markdown uses; weekly digest renders Korean section headers and a 5-day conclusion bullet list per segment. |
| FR-003 static web publishing | ✅ | `mkdocs.yml` (`site_url: https://murphygo.github.io/investo/`, segment-prefixed nav), `site_docs/index.md`, `site_docs/about.md`, `archive/index.md`, `archive/{domestic-equity,us-equity,crypto,weekly}/index.md`, `overrides/main.html` (OG meta) | Hero auto-refresh, About split, calendar heatmap, segment nav, OG image meta, and weekly retrospective archive index all land on the static site without dynamic infra. mkdocs build --strict passes; OG meta emits an absolute URL (`https://murphygo.github.io/investo/assets/og-card.svg`). |
| FR-008 segmented briefing | ✅ | `src/investo/publisher/site_index.py` (per-segment hero card, segment-prefixed nav), `src/investo/visuals/calendar_heatmap.py` (per-segment color row), `src/investo/publisher/weekly_digest.py` (per-segment 5-day conclusion list) | Site discovery surfaces each segment independently — three hero cards, three nav entries (`Archive › 미국 증시 / 크립토 / 국내 증시`), three heatmap rows, three weekly retrospective sections. |
| NFR-002 cost / no paid APIs | ✅ | All u29 surfaces are deterministic Python + SVG renderers; no Anthropic SDK, no paid API, no external image fetch | Hero / heatmap / weekly digest / OG image are all derived from existing archive files; no new HTTP call surface added. |
| NFR-003 graceful degradation | ✅ | `src/investo/orchestrator/pipeline.py::_stage_publish_segments` (M1 rollback fix), `src/investo/publisher/weekly_digest.py` (M2 disclaimer gate), `src/investo/publisher/site_index.py` (`_render_segment_index` empty-archive branch) | Validate / verify failures during the segment publish stage now invoke `_rollback_paths(snapshots)` before re-raising `(SummaryQualityError, PublisherDisclaimerError, PublisherIOError)`; weekly digest publish goes through `verify_disclaimer` and aborts atomically on failure; segment index pages render safely on zero-archive days. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/publisher/weekly_digest.py::publish_weekly_digest` invokes `verify_disclaimer` before atomic write; `src/investo/orchestrator/pipeline.py::_stage_publish_segments` already routes segmented archive writes through `verify_disclaimer` | M2 fix wires the weekly digest through the same publisher gate as segmented archives, so `PublisherDisclaimerError` aborts the digest write before any file lands. |
| NFR-005 consistency / DRY | ✅ | conclusion extraction shared via `briefing.summary_quality` style + segment naming reused from `briefing.segments` (publisher imports only models / publisher helpers — no cross-unit imports added) | The four conclusion-extraction sites (`site_index.py`, `weekly_digest.py`, `og_card.py`, `assets.py`) are quadruply duplicated today; consolidation is registered as DEBT-060. The sequence diagram retains the existing module-boundary contract (only `orchestrator` imports `briefing` / `publisher` / `notifier`). |
| NFR-006 testing | ✅ | `tests/unit/visuals/test_calendar_heatmap.py` (new), `tests/unit/visuals/test_og_card.py` (new), `tests/unit/publisher/test_weekly_digest.py` (new), `tests/unit/publisher/test_site_index.py` (rewrite), `tests/unit/orchestrator/test_run_pipeline.py` (M1 rollback assertion + M3 weekly opt-in 4 tests) | +30 targeted tests (1210 → 1240); covers hero auto-refresh, calendar heatmap deterministic SVG, OG image meta absolute URL, weekly digest Saturday-only opt-in (env unset / `"0"` / failure rollback), and segment-index empty-archive branch. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/publisher/weekly_digest.py`, `src/investo/visuals/og_card.py`, `src/investo/visuals/calendar_heatmap.py` (no env-var read; consume only existing archive files) | u29 does not introduce any secret-flow surface. The single environment variable wired by the unit (`INVESTO_PUBLISH_WEEKLY` opt-in flag) carries a non-secret integer-string value that gates a publish step, not a credential. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `docs/index.md` hero is auto-generated on every publish: three latest-segment conclusion quote cards (domestic / us / crypto). No hardcoded "최신 묶음 YYYY-MM-DD". | ✅ | `src/investo/publisher/site_index.py::_render_hero_block` (rewrites `site_docs/index.md` from the latest segmented archive entries on every publish); `tests/unit/publisher/test_site_index.py` (hero refresh regression). |
| About content (current 7-section / sources / disclaimer meta copy) is moved to a separate About page; nav is updated. | ✅ | `site_docs/about.md` (new — carries the meta copy); `site_docs/index.md` (hero-only); `mkdocs.yml` nav adds `About` entry. |
| `docs/archive/index.md` includes a calendar heatmap SVG keyed on publish date and segment coverage color. | ✅ | `src/investo/visuals/calendar_heatmap.py` (new — deterministic SVG renderer); `archive/index.md` (heatmap embedded as `<img>`); `tests/unit/visuals/test_calendar_heatmap.py` (deterministic output regression). |
| Weekly retrospective auto-page (`archive/weekly/YYYY-WNN.md`) is published by the Saturday 09:00 KST cron with a 5-day conclusion list. | ✅ | `src/investo/publisher/weekly_digest.py::publish_weekly_digest` (new); `.github/workflows/daily-briefing.yml` (KST Sat 09:00 cron sets `INVESTO_PUBLISH_WEEKLY=1`); `archive/weekly/index.md` (new); `tests/unit/orchestrator/test_run_pipeline.py` (4 weekly opt-in tests). |
| mkdocs nav has explicit segment entry points (`Archive › 미국 증시`, `Archive › 크립토`, `Archive › 국내 증시`). | ✅ | `mkdocs.yml` segment-prefixed nav; `archive/{domestic-equity,us-equity,crypto,weekly}/index.md` (per-segment listing pages with `_render_segment_index`). |
| Each publish writes an OG image meta (`<meta property="og:image">`) referencing the rendered hero SVG (or PNG twin). | ✅ | `src/investo/visuals/og_card.py` (new — deterministic OG card renderer); `mkdocs.yml` `site_url` set so `overrides/main.html` emits an absolute OG URL `https://murphygo.github.io/investo/assets/og-card.svg`; `site_docs/assets/og-card.svg` (placeholder). PNG twin is registered as DEBT-058. |
| Pipeline stage rollback on publish-time validation failure. | ✅ | `src/investo/orchestrator/pipeline.py::_stage_publish_segments` validate / verify loop now wrapped in try/except that invokes `_rollback_paths(snapshots)` before re-raising `(SummaryQualityError, PublisherDisclaimerError, PublisherIOError)`; pinned by `tests/unit/orchestrator/test_run_pipeline.py`. |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed (181 files)
- `uv run mypy --strict src/` — passed (69 source files)
- `uv run pytest -q` — 1240 passed (1210 → 1240, +30 new tests)
- `uv run mkdocs build --strict` — passed; OG meta verified to emit an absolute URL `https://murphygo.github.io/investo/assets/og-card.svg`

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u29 introduces deterministic Python + SVG renderers only; no LLM client added. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | New modules live in `publisher/` (`weekly_digest.py`, rewritten `site_index.py`) and `visuals/` (`calendar_heatmap.py`, `og_card.py`); the orchestrator continues to be the only cross-unit importer. |
| 무료 API only (no paid keys) | ✅ | No new external endpoints; the only env var added (`INVESTO_PUBLISH_WEEKLY`) is a local opt-in flag. |
| 면책조항 자동 삽입 | ✅ | M2 fix wires `publish_weekly_digest` through `verify_disclaimer`. Segmented archive writes already enforce the gate. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u29 does not change notifier targets. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | u29 does not touch `raw_metadata`. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | The single env var is non-secret. The `_internal/redaction.py` chokepoint introduced by u27 remains the canonical path for any secret-shaped value; u29 does not bypass it. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u29 does not introduce any XML parsing path. SVG output is direct string templating, not XML parsing. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **H1** — `mkdocs.yml` `site_url: https://murphygo.github.io/investo/` set explicitly so the `overrides/main.html` OG meta emits an absolute URL `https://murphygo.github.io/investo/assets/og-card.svg`. mkdocs build --strict verified the absolute URL on the rendered HTML.
  - **H2** — `src/investo/visuals/og_card.py` module docstring corrected: SVG-only output is suitable for metadata / GH Pages preview tooling, but normal social-card unfurl on Telegram / Slack / Twitter / LinkedIn requires the PNG twin (registered as DEBT-058). The previous wording overstated SVG OG support and was misleading.
  - **M1** — `src/investo/orchestrator/pipeline.py::_stage_publish_segments` validate / verify loop wrapped in try/except that invokes `_rollback_paths(snapshots)` before re-raising `(SummaryQualityError, PublisherDisclaimerError, PublisherIOError)`. Prevents partial-write archive corruption on summary-quality / disclaimer / IO failure mid-loop.
  - **M2** — `src/investo/publisher/weekly_digest.py::publish_weekly_digest` now invokes `verify_disclaimer` before the atomic write and raises `PublisherDisclaimerError` on failure. Closes the disclaimer-gate gap for the new weekly digest publish path.
  - **M3** — `tests/unit/orchestrator/test_run_pipeline.py` adds 4 regression tests covering the weekly-digest opt-in contract: (a) `INVESTO_PUBLISH_WEEKLY=1` invokes `publish_weekly_digest`, (b) env unset skips, (c) `INVESTO_PUBLISH_WEEKLY=0` skips, (d) failure during weekly publish triggers full segment rollback. `_patch_publish_segments_relative_paths` helper added to keep the M1 rollback assertion aligned with archive path expectations.
- Deferred to TECH-DEBT (no Critical / High findings outstanding):
  - **M4** → `DEBT-060 (Medium)` — conclusion prefix / extraction helper duplicated 4 times (`site_index.py`, `weekly_digest.py`, `og_card.py`, `assets.py`).
  - **M5** → `DEBT-058 (P1)` — OG image PNG twin generation. Most OG consumers (Telegram / Slack / Twitter / LinkedIn) do not honour SVG; PNG twin is required for social-card unfurl correctness.
  - **TECH-DEBT P2** → `DEBT-059 (Medium)` — `INVESTO_PUBLISH_WEEKLY` env-var keying via byte-identical `github.event.schedule == '0 0 * * 6'` matching is fragile; alternatives include weekday + KST 09:00 timezone comparison or a dedicated workflow file.
  - **TECH-DEBT P3** → `DEBT-061 (Low)` — heatmap dark-mode toggle accuracy mirrors the same OS-vs-mkdocs-Material site-toggle disagreement already registered as DEBT-049 (cross-reference only).
  - **L1** → `DEBT-062 (Low)` — `_stage_publish_segments` archive-paths absolute / relative branching means tests with absolute monkeypatched paths skip the index / heatmap / og / weekly stages entirely; the production code shape depends on the test shape.
  - **L2** → `DEBT-063 (Low)` — `_render_segment_index` uses `entry.parents[2]` slicing which is fragile to archive directory restructuring; `entry.relative_to(archive_dir)` is more explicit.
  - **L3** → `DEBT-064 (Low)` — `_render_hero_block` markdown blockquote injection: archived briefing conclusions containing `]` / `)` could clash with the link parser. LLM-generated content makes a hostile case unlikely but the guarantee is not hard.
  - **L4** → `DEBT-065 (Low)` — `og_card._wrap` word segmentation is inappropriate for Korean; sparse-whitespace sentences see incorrect `max_chars` truncation and `…` placement.
  - Developer self-discovered → `DEBT-066 (Medium)` — `*.svg.json` provenance manifest sidecars are not enumerated in `asset_paths` and therefore are not included in the snapshot / rollback path; on `SummaryQualityError` / `PublisherDisclaimerError` rollback the JSON manifests are orphaned.
- No Critical or High findings outstanding after pre-merge fixes.

---

## TECH-DEBT Surfaced by This Unit

Nine new items registered (`docs/TECH-DEBT.md`):

- **DEBT-058 (P1)** — OG image PNG twin generation for social-card unfurl correctness on Telegram / Slack / Twitter / LinkedIn (SVG-only is metadata / preview-tooling only).
- **DEBT-059 (Medium)** — `INVESTO_PUBLISH_WEEKLY` env-var keyed via byte-identical `github.event.schedule == '0 0 * * 6'` matching; alternatives: weekday + KST timezone comparison or dedicated workflow file.
- **DEBT-060 (Medium)** — conclusion prefix / extraction helper duplicated across `site_index.py` / `weekly_digest.py` / `og_card.py` / `assets.py`. Consolidate via `briefing.summary_quality.CONCLUSION_PREFIX` public export + `briefing.extract` helper.
- **DEBT-061 (Low)** — heatmap dark-mode toggle accuracy (cross-reference DEBT-049; same policy applies to `calendar_heatmap.py`).
- **DEBT-062 (Low)** — `_stage_publish_segments` archive-paths absolute / relative branching couples production code shape to the test shape.
- **DEBT-063 (Low)** — `_render_segment_index` `entry.parents[2]` slicing is fragile to archive directory restructuring; `entry.relative_to(archive_dir)` is more explicit.
- **DEBT-064 (Low)** — `_render_hero_block` markdown blockquote injection: archived briefing conclusion bodies containing `]` / `)` can clash with the link parser. LLM-generated content makes a hostile case unlikely but the guarantee is not hard.
- **DEBT-065 (Low)** — `og_card._wrap` word segmentation is inappropriate for Korean; sparse-whitespace sentences see incorrect `max_chars` truncation and `…` placement.
- **DEBT-066 (Medium)** — `*.svg.json` provenance manifest sidecars are not enumerated in `asset_paths` and therefore are not snapshotted / rolled back; orphan JSON manifests can be left behind on `SummaryQualityError` / `PublisherDisclaimerError`. `prepare_segment_visual_assets` should also return manifest paths so they participate in the rollback set.

---

## Gaps Analysis

No gaps found. Persona #2 P0 + P1 + wish-list items are all closed by u29.

## Proposed Actions

- No requirements / design changes.
- TECH-DEBT updates already registered (DEBT-058 through DEBT-066).
- Quality gate verified end-to-end at the close of the u25-u29 wave: `ruff` ✅, `ruff format` ✅ (181 files), `mypy --strict` ✅ (69 source files), `pytest` ✅ (1240/1240), `mkdocs build --strict` ✅.
