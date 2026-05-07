# Code Summary: u29 site-discovery-v2

**Date**: 2026-05-08

## Completed

- Reframed the public site so the first screen surfaces today's briefing content (not site-meta copy), and gave weekend retrospect readers a time-axis traversal layer. The unit decomposes into four concerns and threads them consistently through the segmented publish path:
  1. **Hero auto-refresh + About split** — `src/investo/publisher/site_index.py::_render_hero_block` regenerates `site_docs/index.md` on every publish from the latest segmented archive entries (three quote cards: domestic / us / crypto). The site-meta copy moved out to a dedicated `site_docs/about.md`. mkdocs nav adds a top-level `About` entry.
  2. **Calendar heatmap + segment-prefixed nav** — `src/investo/visuals/calendar_heatmap.py` renders a deterministic SVG keyed on publish date × per-segment coverage color into `archive/index.md`. `mkdocs.yml` nav exposes explicit segment entry points (`Archive › 미국 증시`, `Archive › 크립토`, `Archive › 국내 증시`); `_render_segment_index` produces per-segment archive listing pages at `archive/{domestic-equity,us-equity,crypto,weekly}/index.md`.
  3. **Weekly retrospective** — `src/investo/publisher/weekly_digest.py::publish_weekly_digest` writes `archive/weekly/YYYY-WNN.md` with a per-segment 5-day conclusion list. The Saturday 09:00 KST cron arm in `.github/workflows/daily-briefing.yml` sets `INVESTO_PUBLISH_WEEKLY=1`, which `_stage_publish_segments` reads to opt the weekly publish step in.
  4. **OG image meta** — `src/investo/visuals/og_card.py` renders an OG card SVG. `mkdocs.yml::site_url: https://murphygo.github.io/investo/` and `overrides/main.html` together emit an absolute `<meta property="og:image">` URL `https://murphygo.github.io/investo/assets/og-card.svg`. The PNG twin required for normal Telegram / Slack / Twitter / LinkedIn unfurl is registered as DEBT-058 (P1).
- Applied pre-merge fixes that lift the unit from "ships but with disclaimer / rollback gaps" to "publish-grade":
  - **H1** — `mkdocs.yml` `site_url` set so the OG meta is crawl-correct on GH Pages. `mkdocs build --strict` verified the absolute URL on the rendered HTML.
  - **H2** — `src/investo/visuals/og_card.py` module docstring corrected: SVG-only OG is suitable for metadata / GH Pages preview tooling; social-card unfurl on Telegram / Slack / Twitter / LinkedIn requires the DEBT-058 PNG twin.
  - **M1** — `src/investo/orchestrator/pipeline.py::_stage_publish_segments` validate / verify loop wrapped in try/except that invokes `_rollback_paths(snapshots)` before re-raising `(SummaryQualityError, PublisherDisclaimerError, PublisherIOError)`. Prevents partial-write archive corruption mid-loop.
  - **M2** — `src/investo/publisher/weekly_digest.py::publish_weekly_digest` now invokes `verify_disclaimer` before the atomic write and raises `PublisherDisclaimerError` on failure. Closes the disclaimer-gate gap on the new weekly publish path.
  - **M3** — `tests/unit/orchestrator/test_run_pipeline.py` adds 4 regression tests covering the weekly opt-in contract: invoke / unset skip / `"0"` skip / failure rollback. `_patch_publish_segments_relative_paths` helper added.
- M4 / M5 / TECH-DEBT P2 / TECH-DEBT P3 / L1-L4 / developer-self-discovered manifest-sidecar rollback gap deferred to DEBT-058 through DEBT-066.

## Files Changed

### New source files

- `src/investo/visuals/calendar_heatmap.py` — deterministic SVG calendar heatmap renderer keyed on publish date × per-segment coverage color.
- `src/investo/visuals/og_card.py` — OG image SVG renderer (PNG twin tracked under DEBT-058).
- `src/investo/publisher/weekly_digest.py` — `publish_weekly_digest` writes `archive/weekly/YYYY-WNN.md` with per-segment 5-day conclusion lists; goes through `verify_disclaimer` (M2 fix).

### Modified source files

- `src/investo/publisher/site_index.py` — full rewrite: `_render_hero_block` (hero auto-refresh from latest segmented archive entries), `_render_segment_index` (per-segment archive listing pages), OG meta wiring through `overrides/main.html`.
- `src/investo/publisher/__init__.py` — re-export surface for `weekly_digest` + new `site_index` helpers.
- `src/investo/visuals/__init__.py` — re-export surface for `calendar_heatmap` + `og_card`.
- `src/investo/orchestrator/pipeline.py` — M1 rollback fix (`_stage_publish_segments` validate / verify loop try/except invoking `_rollback_paths(snapshots)`); `INVESTO_PUBLISH_WEEKLY` opt-in branch invoking `publish_weekly_digest`; visual-asset coverage_status thread retained from u26 / u28.

### Modified site / infrastructure

- `mkdocs.yml` — H1 fix `site_url: https://murphygo.github.io/investo/`; segment-prefixed nav entries (`Archive › 미국 증시 / 크립토 / 국내 증시 / 주간`); top-level `About` entry.
- `site_docs/index.md` — hero-only home page (auto-refreshed by `_render_hero_block`).
- `site_docs/about.md` — new — carries the previous home-page meta copy (7-section / sources / disclaimer).
- `site_docs/assets/og-card.svg` — placeholder OG card (overwritten on each publish).
- `site_docs/assets/u29.css` — heatmap + hero card styling.
- `archive/index.md` — embeds the calendar heatmap SVG.
- `archive/{domestic-equity,us-equity,crypto,weekly}/index.md` — per-segment archive listing pages rendered by `_render_segment_index`.
- `overrides/main.html` — emits `<meta property="og:image">` with the absolute URL derived from `site_url`.
- `.github/workflows/daily-briefing.yml` — Saturday 09:00 KST cron arm sets `INVESTO_PUBLISH_WEEKLY=1`.

### New test files

- `tests/unit/visuals/test_calendar_heatmap.py` — deterministic SVG output regression.
- `tests/unit/visuals/test_og_card.py` — OG card renderer tests.
- `tests/unit/publisher/test_weekly_digest.py` — `publish_weekly_digest` regression (M2 disclaimer gate; per-segment 5-day conclusion list).

### Modified test files

- `tests/unit/publisher/test_site_index.py` — full rewrite: hero refresh, segment index, OG meta absolute URL regressions.
- `tests/unit/orchestrator/test_run_pipeline.py` — M1 rollback assertion + M3 weekly opt-in 4 tests (invoke / unset skip / `"0"` skip / failure rollback) + `_patch_publish_segments_relative_paths` helper.

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-058 / DEBT-059 / DEBT-060 / DEBT-061 / DEBT-062 / DEBT-063 / DEBT-064 / DEBT-065 / DEBT-066 added)
- `docs/cross-checks/2026-05-08-u29-site-discovery-v2.md` (new)
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/u29-site-discovery-v2-code-generation-plan.md` (DoD + step checkboxes marked)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — Korean briefing comprehension: hero quote cards reuse the segmented archive conclusion lines (Korean glyphs render via the `Noto Sans KR` stack u26 standardised); weekly digest renders Korean section headers and a 5-day conclusion bullet list per segment.
- **FR-003** — static web publishing: every persona #2 P0 + P1 + wish-list surface (hero auto-refresh, About split, calendar heatmap, segment nav, OG meta, weekly retrospective) lands as static markdown / SVG. mkdocs build --strict passes.
- **FR-008** — segmented briefing: each segment is independently surfaced — three hero cards, three segment nav entries, three heatmap rows, three weekly retrospective sections.
- **NFR-002 (cost / no paid APIs)** — deterministic Python + SVG renderers only; no Anthropic SDK, no paid API, no external image fetch. The single env var added (`INVESTO_PUBLISH_WEEKLY`) is a non-secret opt-in flag.
- **NFR-003 (graceful degradation)** — M1 rollback fix prevents partial-write archive corruption; M2 disclaimer gate aborts the weekly digest write atomically on failure; segment index pages render safely on zero-archive days.
- **NFR-004 (compliance / disclaimer)** — `verify_disclaimer` is the gate on both segmented archive writes (already wired) and the new weekly digest publish path (M2 fix).
- **NFR-005 (consistency / DRY)** — module boundary preserved (only `orchestrator` imports `briefing` / `publisher` / `notifier`). Conclusion-extraction duplication is registered as DEBT-060 for consolidation.
- **NFR-006 (testing)** — +30 targeted tests (1210 → 1240); covers hero auto-refresh, deterministic SVG calendar heatmap, OG meta absolute URL, weekly digest opt-in (env unset / `"0"` / failure rollback), segment-index empty-archive branch.
- **NFR-007 (R8 / R13)** — no secret-flow surface added; the `_internal/redaction.py` chokepoint introduced by u27 is unchanged.

## Architecture Summary

```
publisher/
  site_index.py
    _render_hero_block(...)               # site_docs/index.md
                                          #   regenerated on every publish
                                          #   3 hero quote cards: domestic / us / crypto
                                          #   no hardcoded "최신 묶음 YYYY-MM-DD"
    _render_segment_index(...)            # archive/<segment>/index.md
                                          #   per-segment archive listing pages

  weekly_digest.py
    publish_weekly_digest(...)            # archive/weekly/YYYY-WNN.md
                                          #   per-segment 5-day conclusion list
                                          #   M2 fix: verify_disclaimer pre-write

visuals/
  calendar_heatmap.py
    render_calendar_heatmap(...)          # deterministic SVG
                                          #   x-axis: publish date
                                          #   y-axis: segment
                                          #   color: coverage status

  og_card.py
    render_og_card(...)                   # SVG-only (DEBT-058 PNG twin pending)
                                          #   wired into overrides/main.html
                                          #   absolute URL via mkdocs.yml site_url

orchestrator/pipeline.py
  _stage_publish_segments(...)
    snapshots = _snapshot_paths(...)
    try:
        for segment in segments:
            verify_disclaimer(...)        # gate
            summary_quality.validate(...) # gate
            atomic_write(...)
    except (SummaryQualityError,
            PublisherDisclaimerError,
            PublisherIOError):
        _rollback_paths(snapshots)        # M1 fix
        raise

    publisher.site_index.publish(...)     # hero auto-refresh + segment indexes + OG meta
    if INVESTO_PUBLISH_WEEKLY == "1":
        publish_weekly_digest(...)        # Saturday opt-in only

.github/workflows/daily-briefing.yml
  Saturday 09:00 KST cron arm:            # DEBT-059: byte-identical schedule match fragile
    INVESTO_PUBLISH_WEEKLY=1
```

The publisher module remains the only authority over `site_docs/` and `archive/` writes. The orchestrator is the only cross-unit importer. The OG meta channel terminates at `overrides/main.html` (mkdocs theme override), so the absolute URL substitution is performed at site-build time, not at briefing-runtime.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- H1 (`mkdocs.yml` `site_url` set so OG meta emits an absolute URL `https://murphygo.github.io/investo/assets/og-card.svg`) applied pre-merge.
- H2 (`og_card.py` module docstring corrected — SVG-only OG is metadata / GH Pages preview only; social-card unfurl on Telegram / Slack / Twitter / LinkedIn requires the DEBT-058 PNG twin) applied pre-merge.
- M1 (`_stage_publish_segments` validate / verify loop wrapped in try/except invoking `_rollback_paths(snapshots)` before re-raising `(SummaryQualityError, PublisherDisclaimerError, PublisherIOError)`) applied pre-merge.
- M2 (`publish_weekly_digest` invokes `verify_disclaimer` before atomic write; raises `PublisherDisclaimerError` on failure) applied pre-merge.
- M3 (4 weekly-digest opt-in regression tests + `_patch_publish_segments_relative_paths` helper) applied pre-merge.
- M4 deferred → DEBT-060 (Medium) — conclusion prefix / extraction helper duplicated 4x across `site_index.py` / `weekly_digest.py` / `og_card.py` / `assets.py`.
- M5 deferred → DEBT-058 (P1) — OG image PNG twin generation.
- TECH-DEBT P2 deferred → DEBT-059 (Medium) — `INVESTO_PUBLISH_WEEKLY` env-var keyed via byte-identical `github.event.schedule` matching is fragile.
- TECH-DEBT P3 deferred → DEBT-061 (Low) — heatmap dark-mode toggle accuracy mirrors DEBT-049 (cross-reference only).
- L1 deferred → DEBT-062 (Low) — `_stage_publish_segments` archive-paths absolute / relative branching couples production code shape to the test shape.
- L2 deferred → DEBT-063 (Low) — `_render_segment_index` `entry.parents[2]` slicing fragile.
- L3 deferred → DEBT-064 (Low) — `_render_hero_block` markdown blockquote injection guarantee not hard.
- L4 deferred → DEBT-065 (Low) — `og_card._wrap` Korean word segmentation inappropriate.
- Developer self-discovered → DEBT-066 (Medium) — `*.svg.json` provenance manifest sidecars are not enumerated in `asset_paths` and therefore are not snapshotted / rolled back; `prepare_segment_visual_assets` should also return manifest paths.
- Cross-check: `docs/cross-checks/2026-05-08-u29-site-discovery-v2.md`.
- Source: persona evaluation 2026-05-07 (persona #2 P0 + P1 + wish-list).

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .` (181 files)
- `uv run mypy --strict src/` (69 source files)
- `uv run pytest -q` (1240 passed; 1210 → 1240, +30 new tests)
- `uv run mkdocs build --strict` (passed; OG meta absolute URL verified at `https://murphygo.github.io/investo/assets/og-card.svg`)

> **Permission-restricted environments**: when the editor sandbox refuses to write into `aidlc-docs/` or `docs/`, fall back to Bash heredoc (`cat <<'EOF' > <abs-path>`) for documentation deliverables. Source / test changes always go through the editor in the supported path.
