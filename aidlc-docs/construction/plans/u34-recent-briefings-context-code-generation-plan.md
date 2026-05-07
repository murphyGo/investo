# Code Generation Plan: `u34 recent-briefings-context`

**Date**: 2026-05-08
**Unit**: u34 recent-briefings-context
**Stage**: Code Generation

---

## Goal

Lift each daily briefing from a single-shot report into a "today inside the weekly arc" narrative by feeding Stage 2 the conclusions and key drivers of the most recent N publish days (default 5 = 1 trading week) per segment, so the LLM can naturally surface continuity, divergence, and "no material change" signals — without inventing facts beyond the input data and without disturbing existing budgets, gates, or UI surfaces.

---

## Definition of Done

- [x] `briefing.context.recent_briefings` (or equivalent) module loads the last N publish days (default 5) of segment archive entries and returns a frozen `RecentBriefingsContext` carrying per-segment per-day conclusion line, key drivers, publish-date watermark, and coverage status.
- [x] Stage 2 system prompt receives a "최근 N일 컨텍스트" section with usage rules: (a) reference yesterday's continuity / divergence, (b) avoid repeating prior-day conclusions verbatim, (c) explicitly say "큰 변화 없음" when no new signal, (d) **no extrapolation beyond the input data candidates** (extension of u25 numeric integrity rule); Stage 1 classification is unchanged.
- [x] Orchestrator threads the loaded `RecentBriefingsContext` into the Stage 2 call site immediately before `generate_briefing`; archive absence (first publish, gap days) returns an empty context and the pipeline proceeds without failure.
- [x] Token / character budget guard caps the recent-context block at ~500 chars per segment per day (1-line conclusion + 1-line drivers + date) so it occupies a separate budget from the u13 LLM input candidate cap (96 total / 24 per source) and cannot starve fresh evidence.
- [x] Recent-context extraction reads only archive markdown files already gated through `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality` — no re-scan of raw sources, no fixture/secret exposure (R8 / R13 preserved).
- [x] Telegram summary, hero callout, and visual cards are not modified — continuity / divergence is expressed inside the segment narrative only (no new UI widget, no new manifest field).
- [x] N is configurable via `INVESTO_RECENT_CONTEXT_DAYS` (default 5, valid range `[0, 10]`, `0` disables the feature for a clean A/B); invalid values fall back to default with a log warning.

---

## Steps

### Step 1 — RecentBriefingsContext Loader

- [x] Define `RecentBriefingsContext` (frozen pydantic, `extra="forbid"`) with per-segment per-day entries: publish date, conclusion line, key driver line, coverage status.
- [x] Implement archive scan that walks `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` for the most recent N publish days (skips gap days; tolerates partial coverage).

### Step 2 — Stage 2 Prompt Integration

- [x] Append a "최근 N일 컨텍스트" section to the Stage 2 system prompt with the four usage rules (continuity / divergence / no-change explicit / no extrapolation).
- [x] Leave Stage 1 classification prompt and the existing numeric integrity clause unchanged.

### Step 3 — Orchestrator Wiring

- [x] Load `RecentBriefingsContext` in the orchestrator before `generate_briefing` per segment and thread it as a Stage 2 prompt parameter.
- [x] Empty / first-publish path returns an empty context object; pipeline proceeds without raising.

### Step 4 — Budget Guard and Config Hook

- [x] Enforce a per-day char/line cap inside the loader so the recent-context block stays inside its own ~500-char-per-segment-per-day budget, fully separate from the u13 input cap.
- [x] Read `INVESTO_RECENT_CONTEXT_DAYS` (default 5, valid `[0, 10]`); log a warning and fall back to default on invalid values.

### Step 5 — Verification

- [x] Add loader / prompt / orchestrator unit tests covering archive-absent / N=0 / full-5-day / partial-coverage / leak-guard regression pin (no secret in archive bleeds into the recent-context block).
- [x] Run the full quality gate (`ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest -q`, `mkdocs build --strict`).

---

## Source

User direct request 2026-05-08: "시황 생성 시 어느 정도의 맥락을 위해 최근 N일의 시황을 컨텍스트에서 알고 있는 상태로 작성하면 좋을 듯". Wave 4 (사용자 직접 요청 — 페르소나 평가 wave 와 분리). Expected effect: brief narrative depth lifts from "one-shot daily report" to "today inside the weekly arc"; partially overlaps persona #2 (site explorer) and persona #3 (analyst) wish-list signals around continuity / consistency.
