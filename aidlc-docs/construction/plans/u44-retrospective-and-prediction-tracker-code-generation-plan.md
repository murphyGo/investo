# Code Generation Plan: `u44 retrospective-and-prediction-tracker`

**Date**: 2026-05-09
**Unit**: u44 retrospective-and-prediction-tracker
**Stage**: Code Generation
**Status**: ✅ Complete
**Source**: 10-persona evaluation 2026-05-09 — persona #10 (장기 사용자) + persona #9 (회의주의자)
**Estimated Effort**: ~8-12 h
**Dependencies**:
- Builds on `u29 site-discovery-v2` (weekly digest pattern + `archive/` segment layout).
- Builds on `u30 telegram-first-impression` (closed-set action-tag enum: `[관망]` / `[변동성↑]` / `[강세]` / `[약세]` / `[혼조]` / `[데이터부족]`).
- Builds on `u31 operations-resilience` (`archive/_meta/` time-series logging convention).
- Builds on `u32 trust-traceability-deep-dive` (`briefing/quality_eval.py` 7-day KPIs).
- Builds on `u35 event-lookahead` (`scheduled_at` plumbing).
- Coexists with `u42 quality-kpi-history` (parallel `archive/_meta/*.jsonl` time-series; same atomic-write convention).

---

## Goal

Two long-horizon trust surfaces sharing the `archive/_meta/` time-series infrastructure:

1. **Monthly retrospective** (`archive/monthly/YYYY-MM.md`) — auto-generated month-boundary summary. Lists each day's 한 줄 결론, distribution of action tags (강세 / 약세 / 혼조 / 관망 / 변동성↑ / 데이터부족 ratios), Top 5 most-cited tickers / themes, and links to that month's weekly digests.
2. **Forecast accuracy tracker** — every publish appends action_tag + segment to `archive/_meta/forecast_log.jsonl`. A scheduled rolling job (7-day and 30-day) reads price data already collected by u1 sources to compute hit-rate per segment / per tag / per ticker, writes the result to `site_docs/accuracy.md`.

These two surfaces are bundled because they share the `archive/_meta/` time-series logging infrastructure and both target the long-horizon-reader trust surface. The plan deliberately separates them into distinct Steps so they can land independently if scope pressure forces a partial close.

---

## Persona evidence

> Persona #10 (장기 사용자, P2): "1년 넘게 매일 보는 사용자 입장에서는 한 달 모아본 회고 한 페이지가 있어야 한다. 매일 시황만 보면 패턴이 안 보임. 결론 톤 분포 / 자주 나온 종목 Top 5 같은 게 한 달 단위로 나와야 '이 한 달은 어떤 분위기였지' 가 회상된다."

> Persona #9 (회의주의자, P2): "예측 정확도 페이지 — 강세 / 약세 액션 태그가 7일 / 30일 후 실제 가격과 어떻게 매핑되는지. 이게 없으면 시황의 '예측 가치' 자체가 검증 불가능. 적어도 hit-rate 한 줄이라도 site_docs/accuracy.md 에 박혀 있어야 trust-but-verify 가 성립한다."

The two personas converge on the same infrastructure pattern: **append-only `archive/_meta/*.jsonl` time series + scheduled rolling-window aggregation + auto-generated public page.** They differ in surface (monthly retrospective vs. accuracy tracker) but share the time-series mechanics.

---

## Definition of Done

### Monthly Retrospective (Steps 1-3)

- [x] `archive/monthly/YYYY-MM.md` auto-generated for the closed month. Trigger options: (a) cron-based (1st-of-month KST 09:00); (b) publish-time month-boundary detection (when today's publish target_date crosses a month boundary, generate last month's retrospective). Default: **(b)** — keeps generation tied to the existing daily cron, no new scheduled job needed.
- [x] Retrospective markdown contains: H1 `YYYY년 MM월 회고`, per-day list of 한 줄 결론 (extracted via the existing `briefing/extract.extract_conclusion` chokepoint from u35 Phase 0), tag distribution table (% per tag), Top 5 tickers / themes by frequency, links to weekly digests within the month.
- [x] Retrospective is idempotent: re-running against the same archive directory produces a byte-identical file.
- [x] Mkdocs nav adds `Archive › 월간` entry; per-month pages discoverable via `archive/monthly/index.md` (list of all monthly retrospectives).

### Forecast Accuracy Tracker (Steps 4-6)

- [x] `archive/_meta/forecast_log.jsonl` append-only — every publish appends one line per (segment, action_tag, primary_ticker) tuple with: `target_date`, `segment`, `action_tag`, `tickers` (list of primary tickers cited in the conclusion), `published_at` (UTC), `briefing_url`.
- [x] Append is atomic + idempotent on same-day re-publish (replace the day's lines).
- [x] New module `briefing/accuracy.py::compute_accuracy(window_days, *, log_path, price_lookup)` reads the log + cross-references already-collected price candidates to compute hit-rate per (segment, tag) over the trailing N days. Hit-rate definition for the closed-set tags:
  - `[강세]` hits if the segment's primary index closed +0.0% or higher over the N-day forward window.
  - `[약세]` hits if the segment's primary index closed -0.0% or lower.
  - `[혼조]` hits if the index move is within ±1.0%.
  - `[관망]` always counted as N/A (no directional claim; no hit-rate metric).
  - `[변동성↑]` hits if the segment's realized volatility over the N-day window is in the top-20% of the trailing-90-day distribution.
  - `[데이터부족]` always counted as N/A.
- [x] `briefing/accuracy.py::render_accuracy_page` produces `site_docs/accuracy.md` with two tables (7-day rolling and 30-day rolling), per-segment + per-tag breakdown, with explicit "표본 크기" column so persona #9 can judge statistical noise.
- [x] `publisher/site_index.py::update_accuracy_page` writes the page atomically; orchestrator threads the rewrite into the existing snapshot/rollback envelope.
- [x] Mkdocs nav adds `데이터 품질 › 예측 정확도` (sibling to the existing `데이터 품질` quality dashboard from u32). Or replaces the single `데이터 품질` entry with a parent that has two children.

### Shared

- [x] Both append paths atomic (`.tmp` + rename) and idempotent on same-day re-publish.
- [x] Both pages render gracefully on insufficient data: monthly retrospective with < 7 days of data emits a `데이터 부족 — 다음 달부터 회고 가능` placeholder; accuracy page with < N days of data emits a `표본 누적 중 — 첫 30일 후 산출` placeholder.
- [x] Anti-regression: a regression test pre-seeds the JSONL with 30 days of mixed action tags + price data, asserts the rendered accuracy page contains the expected hit-rate row.
- [x] Anti-regression: month-boundary detection — a publish on May 1 KST 07:00 triggers April retrospective generation; a publish on May 2 does not re-generate April.
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Monthly Retrospective Generator

- [ ] Create `briefing/monthly_retrospective.py::render_monthly_retrospective(year, month, *, archive_root) -> str`.
- [ ] Walk `archive/{segment}/{year}/{month:02d}/*.md`, extract conclusion + action_tag from each per the existing u35 Phase 0 extract chokepoints.
- [ ] Aggregate: per-day rows, tag distribution (% over the month), Top 5 tickers by frequency (extracted via simple regex over conclusion bodies — not LLM-driven, deterministic).
- [ ] Files affected:
  - `src/investo/briefing/monthly_retrospective.py` (new)
- [ ] Unit tests at `tests/unit/briefing/test_monthly_retrospective.py`:
  - 30-day archive seed → rendered markdown contains 30 conclusion rows + tag distribution table summing to 100% + Top 5 tickers section.
  - empty month → `데이터 부족` placeholder.
  - idempotence: same archive seed → byte-identical output.

### Step 2 — Month-Boundary Detection in Orchestrator

- [ ] In `orchestrator/pipeline.py::_stage_publish_segments` (or a sibling stage), detect when `target_date.day == 1` AND the previous month has at least one published archive day. On detection, render the previous month's retrospective and stage it for commit alongside the regular publish.
- [ ] Snapshot `archive/monthly/YYYY-MM.md` (and `archive/monthly/index.md`) before the write so the existing snapshot/rollback envelope covers it.
- [ ] Files affected:
  - `src/investo/orchestrator/pipeline.py`
  - `src/investo/publisher/monthly_index.py` (new — renders `archive/monthly/index.md` listing all monthly retrospectives)
- [ ] Unit tests:
  - target_date = May 1 + April archive present → April retrospective generated.
  - target_date = May 2 → no retrospective generation (anti-regression on idempotence).
  - target_date = May 1 + April archive empty → no retrospective (graceful empty branch).

### Step 3 — Mkdocs Nav + Bootstrap Stub

- [ ] `mkdocs.yml`: add `Archive › 월간` nav entry pointing at `archive/monthly/index.md`.
- [ ] Ship a bootstrap `archive/monthly/index.md` stub so the first `mkdocs build --strict` passes before any retrospective has been generated.
- [ ] Files affected:
  - `mkdocs.yml`
  - `archive/monthly/index.md` (new bootstrap stub)
- [ ] Verification: `mkdocs build --strict` passes from a clean checkout.

### Step 4 — Forecast Log Append Path

- [ ] Create `briefing/forecast_log.py::append_forecast_entries(target_date, *, segment_results, log_path)` that atomically appends one JSON line per (segment, action_tag, primary_tickers) tuple to `archive/_meta/forecast_log.jsonl`.
- [ ] Same-day re-publish: read existing lines, replace lines with `target_date == today`, atomic temp + rename. Idempotent.
- [ ] Files affected:
  - `src/investo/briefing/forecast_log.py` (new)
- [ ] Unit tests at `tests/unit/briefing/test_forecast_log.py`:
  - first publish creates new file with 3 lines (one per segment).
  - second-day publish appends → 6 lines.
  - same-day re-publish replaces → 6 lines (idempotence).
  - corrupt JSONL line → re-publish skips, warning logged, no crash.
  - atomic-write: simulated write failure does not corrupt the existing file.

### Step 5 — Accuracy Computation + Page Renderer

- [ ] Create `briefing/accuracy.py::compute_accuracy(window_days, *, log_path, price_lookup) -> AccuracyReport`.
- [ ] `price_lookup` is a callable `(segment, target_date, window_days) -> PriceMove` — implemented as a thin wrapper over the existing yfinance / Binance price candidates already in `archive/{segment}/.../*.assets/`. No new HTTP fetch.
- [ ] Hit-rate semantics per the closed-set tag table in the DoD section.
- [ ] `briefing/accuracy.py::render_accuracy_page(report) -> str` produces the `site_docs/accuracy.md` body.
- [ ] `publisher/site_index.py::update_accuracy_page` writes the page atomically.
- [ ] Files affected:
  - `src/investo/briefing/accuracy.py` (new)
  - `src/investo/publisher/site_index.py` (extend with `update_accuracy_page`)
- [ ] Unit tests at `tests/unit/briefing/test_accuracy.py`:
  - 30-day mixed-tag + mixed-direction seed → expected hit-rate per (segment, tag).
  - `[관망]` always N/A.
  - `[데이터부족]` always N/A.
  - sample size below threshold (< 7 in window) → row marked `표본 부족`.
  - idempotence: same seed → byte-identical page.

### Step 6 — Orchestrator Wire-Through + Verification

- [ ] In `orchestrator/pipeline.py::_stage_publish_segments`, append forecast log lines after the segment archive write (before the commit).
- [ ] Schedule the accuracy page rewrite on every publish (rolling 7-day + 30-day always reflects the latest data).
- [ ] Snapshot `forecast_log.jsonl` + `site_docs/accuracy.md` before writes; the existing snapshot/rollback envelope (u33) covers them.
- [ ] Files affected:
  - `src/investo/orchestrator/pipeline.py`
  - `mkdocs.yml` (nav entry for accuracy page)
  - `site_docs/accuracy.md` (bootstrap stub)
- [ ] Unit tests:
  - successful publish appends to `forecast_log.jsonl` + rewrites `accuracy.md`.
  - publish failure rolls back both.
  - dry-run mode skips both writes.
- [x] Run targeted retrospective + accuracy + orchestrator tests + the full quality gate.
- [ ] Manual: pre-seed 35 days of mixed archive entries, run a publish, confirm both `archive/monthly/2026-04.md` (if month boundary crossed) and `site_docs/accuracy.md` render correctly with realistic hit-rate numbers. (Not run in this non-browser commit loop; deterministic fixtures and mkdocs strict cover rendering.)

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable — retrospective + accuracy are deterministic aggregation; no LLM call.
- **Module boundary**: changes touch `briefing/`, `publisher/`, `orchestrator/` — all already shared via the orchestrator entry; no new cross-module import.
- **R10 (record/replay fixtures, no fabrication)**: not applicable — both surfaces aggregate already-collected in-repo data; no new external HTTP source.
- **R13 (secret hygiene)**: not applicable — no new env var, no secret. The JSONL contains only public-archived signals (action_tag, ticker, target_date).
- **u24 visual-provenance contract**: respected if any visual cards are added; current scope is markdown-only (no SVG cards in this unit).
- **u32 quality dashboard contract**: the new accuracy page is sibling to the existing `site_docs/quality.md`; nav structure may be flattened or grouped under a parent `데이터 품질` entry.
- **Disclaimer enforcement**: the monthly retrospective + accuracy page are meta surfaces; they do **not** carry per-day market opinion. The publisher's existing `verify_disclaimer` gate applies to per-day briefings only — these meta pages are exempt by convention. Anti-regression: the retrospective page must not contain the action-tag literal in a way that re-asserts a market opinion (it cites past tags as historical fact, not new claims).

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **LLM-driven retrospective writing** — the monthly page is deterministic aggregation. Any narrative summary (e.g., "이번 달은 미국 증시가 강세 우위였다") would require Stage 2 invocation and risks LLM drift; defer to a future enrichment unit if requested.
- **Per-ticker accuracy breakdown** — the accuracy tracker reports per (segment, tag); per-ticker is feasible but adds noise on small sample sizes. Persona #9 prioritized "전체 hit-rate 한 줄이라도" — per-ticker is a future extension.
- **Backtest beyond 30 days** — only 7-day and 30-day rolling windows are reported. Quarterly / yearly backtests are deferred.
- **Realized volatility computation** — `[변동성↑]` hit-rate uses the existing yfinance price candidates' close-to-close stdev. More sophisticated realized-vol (intraday OHLC) is not pursued.
- **Statistical significance testing** — the page reports raw hit-rate; chi-squared / binomial-test is out of scope. Persona #9 explicitly prefers transparent raw numbers + sample size over derived p-values.
- **Email / RSS distribution of monthly retrospective** — page is web-only. RSS feed for monthly retrospectives is a separate ops unit.
- **Cross-segment correlation analysis** — out of scope.

---

## Open questions

- **Month-boundary trigger choice (cron vs. publish-time detection)**: default to **publish-time detection** (no new scheduled job, retrospective generated on the first publish of the new month). If the user prefers a strict 1st-of-month KST 09:00 cron arm, it can be added without code changes by flipping a workflow YAML toggle — but this adds GHA minutes consumption.
- **Hit-rate baseline for `[혼조]`**: the ±1.0% threshold is a heuristic. Persona #9 may prefer ±0.5% or a per-segment volatility-scaled threshold. Default to ±1.0%; revisit at unit closeout.
- **Top 5 ticker frequency extraction**: regex-based extraction over conclusion bodies. If conclusions reference tickers via Korean names (`엔비디아` not `NVDA`), the alias bundle from u28 (`DEFAULT_CORE_ALIASES`) is reused for normalization. Pinned by anti-regression test.
- **Archive directory layout**: `archive/monthly/YYYY-MM.md` (year-month flat) vs. `archive/monthly/YYYY/MM.md` (year-nested). Default to flat (mkdocs nav simpler); revisit if the directory grows past 24 months.
- **6-step plan structure**: per the user's note "단, 6 step plan 으로 명시 분리 권장" — Steps 1-3 cover the monthly retrospective surface, Steps 4-6 cover the accuracy tracker surface. The two surfaces can land independently if scope pressure forces a partial close (e.g., land Steps 1-3 in one PR and Steps 4-6 in a follow-up).
