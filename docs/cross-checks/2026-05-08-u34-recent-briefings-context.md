# Cross-Check: u34 recent-briefings-context

**Scope**: u34 recent-briefings-context
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

u34 is a Wave 4 (사용자 직접 요청 — 2026-05-08 session) follow-up that lifts each daily briefing from a single-shot report into a "today inside the weekly arc" narrative. Stage 2 now receives a frozen `RecentBriefingsContext` carrying the most recent N publish days (default 5 = 1 trading week) of segment archive entries — per-segment per-day publish date, conclusion line, key driver line, watermark, and coverage status — so the LLM can naturally surface continuity, divergence, and "큰 변화 없음" signals without inventing facts beyond the input data candidates and without disturbing existing budgets, gates, or UI surfaces. Stage 1 classification, Telegram summary, hero callout, and visual cards are all unchanged.

**Plan**: `aidlc-docs/construction/plans/u34-recent-briefings-context-code-generation-plan.md`
**Goal**: Lift each daily briefing from a single-shot report into a "today inside the weekly arc" narrative by feeding Stage 2 the conclusions and key drivers of the most recent N publish days per segment.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/briefing/context.py` (`_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX` Korean anchor extraction, 50-char per-field truncate), `src/investo/briefing/prompts.py` (`STAGE2_SYSTEM` "Recent-briefings continuity rules" + `format_recent_context_section` helper) | Recent-context block renders Korean conclusion / driver / watermark lines verbatim from gated archive markdown; Stage 2 system prompt carries the four usage rules in Korean (continuity / divergence / "큰 변화 없음" / no extrapolation). |
| FR-003 static web publishing | ✅ | No site-content surface change — segment markdown / hero / archive / visual cards untouched | u34 is Stage 2 prompt-side only; the site-rendered briefing still flows through the existing publisher path. mkdocs build is unaffected. |
| FR-008 segmented briefing | ✅ | `RecentBriefingsContext.for_segment(...)` per-segment view; archive walk-back per segment under `archive/{domestic-equity,us-equity,crypto}/YYYY/MM/YYYY-MM-DD.md`; `briefing/pipeline.py::_render_recent_context_block` iterates per-segment | The recent context is segment-scoped end-to-end; no cross-segment bleed. Empty / first-publish path returns `RecentBriefingsContext.is_empty() == True` and the pipeline proceeds without raising. |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/briefing/context.py` reads only local `archive/**/*.md`; no HTTP, no LLM, no Anthropic SDK | u34 does not introduce any external call surface. The recent-context block is computed deterministically from already-published archive files. |
| NFR-003 graceful degradation | ✅ | `RecentBriefingsContext.is_empty()`, business-day walk-back with 21-day cap, `INVESTO_RECENT_CONTEXT_DAYS` `[0, 10]` clamp, M3-fix invalid-value warning log | First publish, gap days, partial coverage, and `INVESTO_RECENT_CONTEXT_DAYS=0` all return an empty context object; the pipeline proceeds without raising. Sat / Sun are skipped during walk-back; the 21-day cap prevents an unbounded scan on long gap windows. |
| NFR-004 compliance / disclaimer boundary | ✅ | Loader reads only archive markdown already gated through `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality` | u34 does not add a new publish-time gate and does not bypass any existing one. By consuming only post-publish archive files, the disclaimer / leak-guard / summary-quality gates already enforced at publish time carry through. Defensive `redact_text(STRICT)` is applied to extracted lines as a belt-and-suspenders measure. |
| NFR-005 consistency / DRY | ✅ | `briefing/context.py` reuses the u29 `_CONCLUSION_PREFIX` shape — registered as the 5th consumer cross-referenced under DEBT-060 (escalated Medium → High by this unit) | The conclusion / driver / watermark prefix matching logic is duplicated across `publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, and now `briefing/context.py`. DEBT-060 priority bumped Medium → High because the duplication threshold (fifth consumer) registered as the explicit promotion trigger has now landed. |
| NFR-006 testing | ✅ | `tests/unit/briefing/test_recent_context.py` (17 + caplog-strengthened, new file), `tests/unit/briefing/test_pipeline_recent_render.py` (6 new — 4 branch + 2 shape pins), `tests/unit/briefing/test_prompts.py` (+3 sentinels), `tests/unit/orchestrator/test_run_pipeline.py` (+2 integration) | +28 targeted tests (1240 → 1268). Covers archive-absent / N=0 / full-5-day / partial-coverage / leak-guard regression / business-day walk-back / 21-day cap / 50-char truncate / `INVESTO_RECENT_CONTEXT_DAYS` valid + invalid values / Stage 2 prompt sentinel / orchestrator threading. M2-fix: 4 branch + 2 shape unit tests in `test_pipeline_recent_render.py` pin `_render_recent_context_block` / `_render_recent_entry` against future prompt-format drift. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/briefing/context.py` invokes `redact_text(STRICT)` defensively on every extracted conclusion / driver / watermark line; loader does not touch raw source data | The single env var added (`INVESTO_RECENT_CONTEXT_DAYS`) is a non-secret integer-string opt-in. M3 fix logs warnings on non-numeric / negative / out-of-range values; missing/blank stays silent. The `_internal/redaction.py` chokepoint introduced by u27 is preserved end-to-end. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `briefing.context.recent_briefings` (or equivalent) module loads the last N publish days (default 5) of segment archive entries and returns a frozen `RecentBriefingsContext` carrying per-segment per-day conclusion, key drivers, publish-date watermark, and coverage status. | ✅ | `src/investo/briefing/context.py` (~290 LOC) — `RecentBriefingsContext` (frozen pydantic v2 + slots, `extra="forbid"`), per-segment per-day entries with publish date, conclusion, drivers, watermark, coverage status; `is_empty()` + `for_segment(...)` resolvers; pinned by `tests/unit/briefing/test_recent_context.py`. |
| Stage 2 system prompt receives a "최근 N일 컨텍스트" section with usage rules: (a) continuity, (b) avoid verbatim repetition, (c) "큰 변화 없음" explicit, (d) no extrapolation (extension of u25 numeric integrity rule); Stage 1 classification unchanged. | ✅ | `src/investo/briefing/prompts.py::STAGE2_SYSTEM` adds "Recent-briefings continuity rules"; `STAGE2_USER_TEMPLATE` carries the `{recent_context}` placeholder; `format_recent_context_section` helper. Stage 1 prompt untouched. Pinned by `tests/unit/briefing/test_prompts.py` (+3 sentinels). |
| Orchestrator threads the loaded `RecentBriefingsContext` into the Stage 2 call site immediately before `generate_briefing`; archive absence (first publish, gap days) returns an empty context and the pipeline proceeds without failure. | ✅ | `src/investo/orchestrator/pipeline.py::_load_recent_context_for_run` + Protocol extension; `briefing/pipeline.py::generate_briefing` signature extended; pinned by `tests/unit/orchestrator/test_run_pipeline.py` (+2 integration). |
| Token / character budget guard caps the recent-context block at ~500 chars per segment per day so it occupies a separate budget from the u13 LLM input candidate cap (96 total / 24 per source) and cannot starve fresh evidence. | ✅ | `src/investo/briefing/context.py` 50-char-per-field truncate (publish date + conclusion + drivers + watermark) keeps each per-day entry well under 500 chars; `briefing/pipeline.py::_render_recent_entry` produces a stable single-line shape. Independent of the u13 candidate cap. |
| Recent-context extraction reads only archive markdown files already gated through `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality` — no re-scan of raw sources, no fixture/secret exposure (R8 / R13 preserved). | ✅ | Loader walks `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` only; no `sources/` import; defensive `redact_text(STRICT)` applied per extracted field. Pinned by `tests/unit/briefing/test_recent_context.py` leak-guard regression. |
| Telegram summary, hero callout, and visual cards are not modified — continuity / divergence is expressed inside the segment narrative only (no new UI widget, no new manifest field). | ✅ | No change to `notifier/summary.py`, `notifier/_telegram.py`, `publisher/site_index.py`, `visuals/cards.py`, `visuals/provenance.py`, `visuals/render.py`. Diff confined to `briefing/context.py` (new), `briefing/prompts.py`, `briefing/pipeline.py`, `orchestrator/pipeline.py`. |
| N is configurable via `INVESTO_RECENT_CONTEXT_DAYS` (default 5, valid range `[0, 10]`, `0` disables the feature for a clean A/B); invalid values fall back to default with a log warning. | ✅ | `src/investo/briefing/context.py` reads `INVESTO_RECENT_CONTEXT_DAYS`, default 5, clamps to `[0, 10]`. M3 fix emits a warning log on non-numeric / negative / out-of-range values; missing/blank values stay silent (normal scenario). Pinned by `tests/unit/briefing/test_recent_context.py` caplog assertions. |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed
- `uv run mypy --strict src/` — passed (70 source files)
- `uv run pytest -q` — 1268 passed (1240 → 1268, +28 new tests)
- `uv run mkdocs build --strict` — passed (no site content change in u34)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u34 is a Stage 2 prompt-context loader; no LLM client introduced. The recent-context block flows into the existing Claude Code CLI subprocess as plain text. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | New `briefing/context.py` module sits inside `briefing/`; the orchestrator continues to be the only cross-unit importer. No `briefing → sources` / `briefing → publisher` / `briefing → notifier` import added. |
| 무료 API only (no paid keys) | ✅ | No new external endpoints. The single env var added (`INVESTO_RECENT_CONTEXT_DAYS`) is a non-secret integer-string opt-in. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u34 reads only post-publish archive files, so the disclaimer is already enforced upstream. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u34 does not change notifier targets. Telegram summary, hero callout, and visual cards are untouched. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | u34 does not touch `raw_metadata`. The recent-context loader consumes only archive markdown text, not normalized items. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | Defensive `redact_text(STRICT)` applied to every extracted conclusion / driver / watermark line. The `_internal/redaction.py` chokepoint introduced by u27 is preserved. M3 fix logs invalid `INVESTO_RECENT_CONTEXT_DAYS` values without echoing the value verbatim. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u34 does not introduce any XML parsing path. Archive markdown is consumed as plain text via prefix anchors. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M2** — `tests/unit/briefing/test_pipeline_recent_render.py` adds 6 unit tests (4 branch + 2 shape pins) that pin `_render_recent_context_block` / `_render_recent_entry` against future prompt-format drift. Closes the regression-pin gap on the recent-context render path.
  - **M3** — `src/investo/briefing/context.py` `INVESTO_RECENT_CONTEXT_DAYS` parser emits a warning log when the value is non-numeric, negative, or above the `[0, 10]` upper bound. Missing / blank values remain silent (normal scenario). Pinned by `tests/unit/briefing/test_recent_context.py` caplog assertions.
- Deferred to TECH-DEBT (no Critical / High findings outstanding from u34 itself):
  - **M1** → cross-references `DEBT-060` (Medium → **High** escalation by this unit). u34 is the fifth consumer of the conclusion / driver / watermark prefix matching logic (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, and now `briefing/context.py::_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX`). The DEBT-060 priority reasoning explicitly identified "fifth consumer lands" as the promotion trigger; that condition is now met, so DEBT-060 is escalated to High in this cross-check.
- No Critical or High findings introduced by u34.

---

## TECH-DEBT Surfaced by This Unit

No new TECH-DEBT items registered by u34 itself. One existing item promoted:

- **DEBT-060** — promoted **Medium → High** by this unit. The duplication count goes from 4 → 5 sites (`briefing/context.py` is the fifth consumer of the `_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX` shape). The DEBT-060 priority reasoning explicitly named "fifth consumer" as the promotion trigger; the suggested fix shifts from "4-site import switch" to "5-site import switch" and the description is updated to "duplicated 5x".

---

## Gaps Analysis

No gaps found. All 7 Definition-of-Done items are complete with evidence.

## Proposed Actions

- No requirements / design changes.
- TECH-DEBT updates: DEBT-060 priority promoted Medium → High (description + suggested fix + summary count adjusted).
- Quality gate verified end-to-end at the close of u34: `ruff` ✅, `ruff format` ✅, `mypy --strict` ✅ (70 source files), `pytest` ✅ (1268/1268), `mkdocs build --strict` ✅.
