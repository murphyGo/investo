# Code Generation Plan: `u35 event-lookahead`

**Date**: 2026-05-08
**Unit**: u35 event-lookahead
**Stage**: Code Generation
**Status**: ✅ Closed 2026-05-08 — Phase 0 (DEBT-060 통합) fully landed; Phase 1 partial (4 lookahead-specific adapters + orchestrator wire-through + `LOOKAHEAD_DATA_MISSING` reason code deferred to **DEBT-067** under R10 fabricated-fixture 금지). Cross-check: `docs/cross-checks/2026-05-08-u35-event-lookahead.md`. Summary: `aidlc-docs/construction/u35-event-lookahead/code/summary.md`.

---

## Goal

Lift each daily briefing from a backward-looking recap into forward-looking context by surfacing the upcoming week's and month's high-impact scheduled events (FOMC / FRB calendar, US macro releases, Big Tech earnings, KRX option-expiry, crypto token unlocks / major upgrades) inside the segment narrative — vertical slice from source adapter to LLM prompt to segment markdown to Telegram summary, all on free public data and within existing budgets, gates, and module boundaries.

---

## Definition of Done

- [~] Forward-looking event coverage extends across 3 segments via free public sources only — partial: nasdaq-earnings-calendar lookahead opt-in landed (Step 1 below); new FOMC / FRED / CoinGecko events / KRX adapters registered as follow-up TECH-DEBT (require live-API fixture recording outside this offline coding session). The existing `fomc-rss` adapter continues to surface scheduled meeting press releases.
- [x] Model layer expresses scheduled time distinct from publish time: `NormalizedItem.scheduled_at: datetime | None` added (default `None`, backward-compat); ``ensure_tz_aware`` validator extended.
- [x] `FetchWindow.lookahead(days)` builder added; aggregator stays single-pass for now (each adapter manages its own forward query loop — opt-in via env var) so existing R14 fair-access UA + `retry_get` identity-encoding contract stays intact unchanged.
- [x] Stage 2 system prompt adds a "주요 일정" section + the three usage rules (input-only citation / no arbitrary forecast / 이번 주·이번 달 framing). Stage 1 classification untouched (lookahead routing happens deterministically by `scheduled_at` rather than via classifier — keeps Stage 1 prompt body stable).
- [x] Briefing pipeline applies lookahead sub-cap (`_MAX_LLM_LOOKAHEAD_ITEMS = 12`) inside the existing 96 total / 24 per-source cap.
- [x] Segment markdown receives the lookahead bucket via the `{lookahead_context}` Stage 2 placeholder + ``_render_lookahead_context_block`` renderer; LLM weaves the rows into ⑥ 관전 포인트 per the system rule. Empty-bucket branch emits the explicit "no lookahead" note.
- [x] Telegram summary one-line summary prepends a deterministic imminent-event tag (`📊 NVDA 실적 D-2`, `📅 FOMC D-2`) when ``scheduled_at`` falls inside the 72h horizon. Tag computed from `NormalizedItem.scheduled_at` and `now_utc` only — no LLM surface.
- [ ] `SegmentCoverage.reason_codes` lookahead-data-missing wiring deferred — covered by registering as TECH-DEBT alongside the new adapter work (the reason code is most informative when paired with a real adapter's failure-to-collect signal; landing the wiring without the adapters would always show LOOKAHEAD_DATA_MISSING and degrade the coverage contract's reader trust).
- [x] Token / character budget guard: lookahead block uses ~300 chars per segment via the per-row 80-char title trim + 12-row sub-cap; lives separately from the u34 recent-context budget.
- [x] R8 (defusedxml only — no new adapter needed it; existing fomc_rss continues to use `defusedxml.ElementTree`) and R13 (secret hygiene — no new env var carries credentials, only adapter-tuning integers) preserved.

---

## Steps

### Step 1 — Source Layer (Forward-Looking Adapters)

- [x] Extend `nasdaq-earnings-calendar` to opt-in lookahead (next N days, env `INVESTO_EARNINGS_LOOKAHEAD_DAYS`, clamped to `[0, 14]`) while preserving its existing backward window contract; lookahead failures isolated per day so the target-date pass never breaks.
- [ ] Add `fomc-calendar` adapter (Federal Reserve public RSS / ICS) under the existing `@register` plugin pattern, `retry_get` + `strip_html` + `defusedxml` per R8. — **Deferred to TECH-DEBT-067.**
- [ ] Add `fred-economic-calendar` adapter (FRED / Treasury / BLS release-schedule public feed) for US macro. — **Deferred to TECH-DEBT-067.**
- [ ] Add `coingecko-events` adapter (or equivalent free crypto event endpoint) for token unlocks / major upgrades. — **Deferred to TECH-DEBT-067.**
- [ ] Investigate KRX option-expiry / 공시 lookahead; ship if a free feed exists, otherwise log as TECH-DEBT and proceed. — **Deferred to TECH-DEBT-067.**
- [x] Existing adapter (nasdaq-earnings-calendar) keeps its R14 fair-access UA policy and `retry_get` identity-encoding (u11).

### Step 2 — Model Layer

- [x] Add `NormalizedItem.scheduled_at: datetime | None` (None = backward-looking, default).
- [x] Existing `Category` literal kept unchanged — forward-looking items use `category="earnings"` / `"calendar"` / `"macro"` and are separated by the `scheduled_at` flag instead. Avoids growing the closed-set typing surface unnecessarily.

### Step 3 — Aggregator + FetchWindow Lookahead

- [x] `FetchWindow.lookahead(days)` added (raises on `days <= 0`, preserves `target_date` anchoring + half-open membership).
- [~] Aggregator unchanged — per-adapter env-var opt-in keeps backward pass untouched + each opted-in adapter does its own forward iteration. Two-pass aggregator behavior reconsidered as TECH-DEBT-067 follow-up once multiple lookahead-aware adapters land.

### Step 4 — LLM Prompt + Briefing Layer

- [~] Stage 1 classification prompt — left unchanged. Forward-vs-past separation runs deterministically off `scheduled_at` (cleaner than asking the classifier to re-derive it).
- [x] Stage 2 system prompt adds "주요 일정" rules block (input-only citation / no arbitrary forecast / 이번 주·이번 달 framing).
- [x] `_select_llm_candidate_items` lookahead sub-cap (`_MAX_LLM_LOOKAHEAD_ITEMS = 12`) inside the u13 96-total / 24-per-source cap.
- [x] `_render_lookahead_context_block` renderer + `{lookahead_context}` placeholder on `STAGE2_USER_TEMPLATE`; empty-bucket branch emits the "no lookahead" note.
- [ ] `SegmentCoverage.reason_codes` lookahead-data-missing wiring — deferred (see DoD note above).

### Step 5 — Notifier Surface (Imminent Tag)

- [x] `build_segmented_summary` accepts `lookahead_items_by_segment` + `now_utc` and prepends a deterministic `📊 NVDA 실적 D-2` / `📅 FOMC D-2` tag for events inside the 72h horizon, top-1 by ascending `scheduled_at` (tiebreaker: source then title). LLM never sees this tag.
- [x] Absence of imminent events keeps the line unchanged (backward-compat — the kwarg defaults to `None`).
- [ ] Orchestrator wire-through (`_stage_notify_segmented_briefing` passes the per-segment lookahead bucket) — registered as TECH-DEBT-067 alongside the source adapters that will populate the bucket. Today the kwarg defaults to `None` so the tag is always omitted in production until that wiring lands.

### Step 6 — Verification

- [~] Unit tests for the extended `nasdaq-earnings-calendar` lookahead path (6 new tests under `tests/unit/sources/test_nasdaq_earnings_calendar.py`); new-adapter record/replay fixtures deferred to TECH-DEBT-067.
- [x] `FetchWindow.lookahead` regression in `tests/unit/sources/test_window.py` (3 tests).
- [x] Stage 2 prompt regression — `test_stage2_system_carries_lookahead_no_forecast_rule` + format helpers.
- [x] Briefing markdown regression — `tests/unit/briefing/test_pipeline_lookahead_render.py` (5 tests).
- [x] Notifier imminent-tag regression — 5 tests in `tests/unit/notifier/test_summary.py`.
- [x] `leak_guard.scan` + `verify_disclaimer` + `summary_quality` no-regression (full suite green).
- [x] Full quality gate: `ruff check .`, `ruff format --check .`, `mypy --strict src` (71 files, 0 errors), `pytest -q` (1308 passed, 0 failed), `mkdocs build --strict` (0 errors).

---

## Source

User direct request 2026-05-08: "어제/오늘일은 아니지만 이번주나 이번달 중요한 이벤트가 있으면 미리 파악해서 주요 일정을 시황에 포함하면 좋을듯. 그러기 위해서는 데이터소스부터 프롬프트 생성까지 전부 건드려야 할 듯. 일단 계획후 유닛 만들고 진행." Wave 4 (사용자 직접 요청 — 페르소나 평가 wave 와 분리; u34 와 동일 wave). Aligned with persona #3 (analyst) and persona #4 (watchlist tracker) wish-list signals around "옵션·실적·배당락 캘린더 7-day 룩어헤드"; partial overlap with u33 watchlist depth (u33 = watchlist-specific lookahead, u35 = general segment lookahead — kept distinct so provenance stays clean). No new paid API, no module-boundary change (orchestrator → sources / briefing only); R8 / R13 / R14 preserved across new adapters.
