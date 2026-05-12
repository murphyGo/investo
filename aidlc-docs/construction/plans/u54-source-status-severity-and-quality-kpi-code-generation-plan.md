# Code Generation Plan: `u54 source-status-severity-and-quality-kpi`

**Date**: 2026-05-13
**Unit**: u54 source-status-severity-and-quality-kpi
**Stage**: Code Generation
**Status**: 📋 Planned (refined 2026-05-13 — Wave 8 follow-up after 10-subagent re-evaluation)
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings (`archive/{us-equity,domestic,crypto}/2026/05/2026-05-11.md`), deduplicated against u51/u52/u53.
**Estimated Effort**: ~5-6 h (raised from 3-4 h after Finding #4 + staleness + alert-debouncing inclusion)
**Dependencies**:
- u22 source-coverage-transparency (existing `SourceOutcome`, `SegmentCoverage`, reason-code rendering).
- u32 trust-traceability-deep-dive (traceability and source-tier vocabulary; `SourceTier` consumed by quality KPI).
- u42 quality-kpi-history (quality page / history surfaces; `append_quality_snapshot` + `compute_quality_history`).
- u43 lookahead reason code (closed-set `CoverageReasonCode` — extend, do not parallel-create).
- u52 carryover (parallel; shares `briefing/segments.py` import surface but no functional overlap — severity enum bump is additive).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u51: first-viewport layout, TL;DR, anchor table, H3 headings, number bolding, glossary dedupe, action-ratio diagnostics.
- u52: prior-day carryover and event lifecycle.
- u53: domestic flow and US sector/macro ETF source expansion.
- u55: numeric claim verification, freshness gating, staleness *of figures inside briefing prose*. This unit owns staleness *of source price data itself* (latest-item-at vs market-close window) which feeds severity — distinct surface.
- u56: compliance language, action-instruction filtering.

This unit owns only **truthful source-status semantics, severity downgrade policy, citation-cardinality WARN, and quality KPI denominator correctness**.

---

## Goal

Prevent generated briefings from showing `데이터 상태: 정상` when core sources failed or returned 0 items, and make `site_docs/quality.md` explain actual coverage risk instead of reporting misleading denominator-zero KPIs.

Observed failures from 2026-05-11 multi-segment briefing review:
- Domestic segment shows `정상` while `korea-policy-rss` failed and `fsc-krx-index-price` returned 0 items.
- US segment shows `정상` while `cnbc-top-news` failed and multiple news sources returned 0 items.
- Crypto segment shows `정상` while `binance-crypto-market` failed and `coingecko-price` returned 0 items.
- Quality page reports `소스 라이브니스 0.0% / 0회` despite existing quality-history rows and failed source counts.
- Finding #4 (citation cardinality): a single 연합뉴스 URL was attributed to 5 distinct ticker/entity claims in the domestic 2026-05-11 briefing — no signal flagged the over-application.

---

## Persona evidence

> 10-subagent quality 리뷰 (2026-05-13 session, multi-segment archive 대상):
> - subagent #2 (status truthfulness): "`정상` 라벨이 핵심 가격 소스 0건일 때도 찍힘 — 독자가 데이터 신뢰도를 오판."
> - subagent #4 (citation cardinality, **Finding #4**): "1개 URL이 5개 종목 별 claim 에 묶임 — over-attribution."
> - subagent #6 (quality KPI): "라이브니스 0.0%/0회는 분모 zero edge — 분자 분리하지 않으면 KPI 가 의미 없음."
> - subagent #8 (staleness): "주말/공휴일에 yfinance 가 어제 종가 반환 — `정상` 으로 라벨링되지만 stale."
> - subagent #10 (alert spam risk): "플레이키 소스 (CNBC, Korea-policy-rss) 가 정상↔실패 반복 시 매 run 마다 운영자 알림 — debounce 필요."

---

## Definition of Done

- [x] **AC-1** Source count text separates `targeted / succeeded / zero / failed / body-used` (5-tuple, all integers).
- [x] **AC-2** Reader-facing status labels use `정상 / 부분 / 제한 / 실패` based on conclusion usability, not just item count; single enum migration from legacy 3-tier (`insufficient` → `failed`, with new tier `limited` inserted between `partial` and `failed`).
- [x] **AC-3** Core source failures, zero core price sources, or stale core price (latest-item-at older than segment market-close window) downgrade segment status and explain impact via existing `CoverageReasonCode` set (extended).
- [x] **AC-4** `site_docs/quality.md` shows observed run count, failed source count, zero-item source count, core-missing count, and segments-with-`limited`-or-worse count; denominator-zero KPIs surface explicit `n/a` rather than `0.0%`.
- [x] **AC-5** Trace/collapsed diagnostics expose failed/excluded sources with sanitized messages (R13 chokepoint) and no secret-shaped values.
- [x] **AC-6** Citation cardinality WARN: when one source URL is attributed to ≥ N=3 distinct ticker/entity claims in a single segment briefing, emit a structured WARN log and add a `claims_per_link` column to the trace table; *non-blocking* (flag, not gate).
- [x] **AC-7** Alert debouncing: `OperatorAlerter` fires for segment severity ≥ `limited` only when the same segment is `≥ limited` for ≥ 2 consecutive runs (read trailing window from `coverage.jsonl`); single-run spike does not alert.
- [x] **AC-8** Same-day re-publish: `append_quality_snapshot` preserves the worst severity per (date, segment) — last-write does *not* upgrade an earlier `limited` to `normal`; explicit `keep_worst=True` semantics.
- [x] Quality gate green: `uv run ruff check .` ✅, `uv run ruff format --check .` ✅, `uv run mypy --strict src/` ✅, `uv run pytest -q` ✅ (1977 passed; +67 new), `uv run mkdocs build --strict` ✅.

---

## AC ↔ Step traceability

| AC | Step(s) | Notes |
|----|---------|-------|
| AC-1 (5-tuple counts) | Step 2, Step 4 | counts derived in Step 2 (model field), rendered in Step 4 (first-viewport) |
| AC-2 (4-tier enum migration) | Step 1, Step 8 | single-enum decision pinned in Step 1; downstream consumer migration listed Step 1 |
| AC-3 (core / zero / stale downgrade) | Step 1, Step 3 | decision tree Step 1; staleness Step 3 |
| AC-4 (quality KPI denominators) | Step 5 | `quality_eval` rewrite + `n/a` rendering |
| AC-5 (sanitized trace) | Step 6 | reuses R13 chokepoint `sanitize_source_error_message` |
| AC-6 (citation cardinality) | Step 6 | new sub-step under trace transparency |
| AC-7 (alert debouncing) | Step 7 | OperatorAlerter rolling-window read |
| AC-8 (same-day re-publish) | Step 5 | `append_quality_snapshot` keep-worst |

---

## Frozen constants (decided at plan time)

### `SEGMENT_CORE_SOURCES` (Step 1 deliverable — concrete)

```python
SEGMENT_CORE_SOURCES: Final[dict[MarketSegment, frozenset[str]]] = {
    "domestic-equity": frozenset({"fsc-krx-index-price"}),
    "us-equity":       frozenset({"yfinance-price", "stooq-price"}),  # either-or (see policy)
    "crypto":          frozenset({"coingecko-price", "binance-crypto-market"}),  # at-least-one
}
```

Policy:
- `domestic-equity`: 1 required source. `fsc-krx-index-price` ≤ failed/zero ⇒ no `normal` possible. `krx-foreign-flows` (u53) is *narrative-critical* but *not core* — drives `partial`, not `limited`.
- `us-equity`: 2 listed sources, **at-least-one** must be `ok` for `normal`. Both failed/zero ⇒ `limited`. Both failed and item_count summed = 0 ⇒ `failed`.
- `crypto`: 2 listed sources, **at-least-one** must be `ok` for `normal`. Both failed/zero ⇒ `limited`. Both `failed` ⇒ `failed`.

Rationale: us-equity has historical Stooq vs yfinance fallback (u46 dual price); crypto has CoinGecko + Binance independent feeds. domestic has only one canonical KRX index source today.

### Severity decision tree (Step 1 deliverable — deterministic)

Input tuple per segment: `(failed_core_count, zero_core_count, news_zero, all_zero)`.

| failed_core | zero_core | required-category zero | all-items zero | → severity |
|-------------|-----------|------------------------|----------------|------------|
| all core    | —         | —                      | —              | `failed`   |
| ≥ 1         | —         | —                      | —              | `limited`  |
| 0           | all core  | —                      | —              | `limited`  |
| 0           | < all     | ≥ 1                    | —              | `partial`  |
| 0           | 0         | ≥ 1                    | —              | `partial`  |
| 0           | 0         | 0                      | yes            | `failed`   |
| 0           | 0         | 0                      | no             | `normal`   |

"all core" for us-equity / crypto means "both listed core sources are in the bad state simultaneously."

Staleness override (Step 3):
- If any core source's `latest_item_at` < `segment_close_window_floor` (US: previous NY session close − 6h; KRX: previous KST session close − 6h; crypto: now − 6h continuous), force severity ≥ `limited` even if items > 0.

### Legacy 3-tier → new 4-tier migration

| legacy `CoverageStatus` | new severity | rationale |
|-------------------------|--------------|-----------|
| `normal`                | `normal`     | identity |
| `partial`               | `partial`    | identity |
| `insufficient`          | `failed`     | strictest legacy state maps to strictest new state |

`limited` is new (inserted between `partial` and `failed`). Single `CoverageStatus = Literal["normal", "partial", "limited", "failed"]` — no parallel enum, no conversion shim. All consumers (`briefing/pipeline.py`, `visuals/cards.py`, `visuals/assets.py`, `notifier/summary.py`) update in one PR.

---

## Steps

### Step 1 — Severity policy, model, and 4-tier enum migration

- [x] Bump `CoverageStatus` in `src/investo/briefing/segments.py:13` from `Literal["normal", "partial", "insufficient"]` to `Literal["normal", "partial", "limited", "failed"]`.
- [x] Update `COVERAGE_STATUS_LABELS` (line 88) with Korean labels: `정상 / 부분 / 제한 / 실패`.
- [x] Add `SEGMENT_CORE_SOURCES` constant (frozen) per the table above; co-located with existing `SEGMENT_MIN_ITEM_COUNTS` / `SEGMENT_REQUIRED_CATEGORIES` for grep-ability.
- [x] Add `SEVERITY_READER_EXPLANATIONS: Final[dict[CoverageStatus, str]]` — one-line Korean reader explanation per severity (e.g. `limited` → "핵심 가격 소스 0건 또는 stale — 본문 결론 신뢰도 낮음").
- [x] Rewrite the severity computation function (`coverage_for_segment` or sibling — implementation may inline into `build_segment_coverage`) using the deterministic decision tree above. Inputs: `tuple[SourceOutcome, ...]`, `news_category_present: bool`, `core_staleness_violated: bool` (computed in Step 3).
- [x] Add new `CoverageReasonCode` literals: `"CORE_FAILED"`, `"CORE_ZERO"`, `"CORE_STALE"`, `"ALL_FAILED"`. Extend `COVERAGE_REASON_LABELS` accordingly.
- [x] **Downstream consumer update** (single-PR migration):
  - `src/investo/briefing/pipeline.py` (`_render_coverage_badge`, `_render_source_outcome_line`).
  - `src/investo/visuals/cards.py` (`coverage_status` fields, `CoverageBadge`).
  - `src/investo/visuals/assets.py` (4 occurrence sites).
  - `src/investo/notifier/summary.py` (segment-coverage rendering).
  - `src/investo/orchestrator/pipeline.py` (`source_liveness` derivation if it gates on `insufficient`).
- [x] **Tests** `tests/unit/briefing/test_segments_severity.py` (예상 +12-14 tests): decision-tree truth table (8 rows minimum) / legacy `insufficient` → `failed` migration / reason-code emission per severity / label map completeness.

### Step 2 — `SourceOutcome` + `SegmentCoverage` count split

- [x] Add to `SegmentCoverage` (frozen dataclass in `briefing/segments.py:269`): `targeted_count: int`, `succeeded_count: int`, `zero_count: int`, `failed_count: int`, `body_used_count: int`. Defaults preserve backward-compat for tests that build directly.
- [x] Derive the first four from `outcomes` tuple deterministically in `build_segment_coverage` (Step 1 site).
- [x] `body_used_count` source: orchestrator post-LLM body parser already tracks cited URLs (u32 trace deep-dive) — wire that count into `SegmentCoverage` via constructor kwarg (no new collection logic).
- [x] **Tests** `tests/unit/briefing/test_segments_count_split.py` (예상 +6-8 tests): 5-tuple invariant `targeted = succeeded + zero + failed + (excluded)`; `body_used_count ≤ succeeded_count` invariant.

### Step 3 — Staleness signal on core price sources

- [x] Add optional `latest_item_at: datetime | None = None` field to `SourceOutcome` in `src/investo/models/coverage.py:48` (default `None` preserves backward-compat; non-core sources may leave it `None`).
- [x] Core price adapters (yfinance, stooq, coingecko, binance, fsc-krx-index) populate it from their latest emitted `NormalizedItem.scheduled_at`/`occurred_at` — *implemented at the aggregator chokepoint* (`sources/aggregator.py`): `max(item.published_at)` over kept items, applies uniformly to every adapter so no per-adapter wiring needed.
- [x] Add `core_staleness_window(segment, now) -> timedelta` helper in `briefing/segments.py`:
  - us-equity: 30h (covers Mon-after-weekend gap; KST Mon cron runs at 07:00 KST = Sun 22:00 ET, ~24h after Fri 16:00 ET close).
  - domestic-equity: 30h (KST overnight + weekend tolerance).
  - crypto: 6h (24/7 market, expect fresh).
- [x] `build_segment_coverage` computes `core_staleness_violated: bool` from core outcomes' `latest_item_at` vs window; passes into severity decision (Step 1).
- [x] **Tests** `tests/unit/briefing/test_segments_staleness.py` (예상 +4-6 tests): KST Mon-morning yfinance with Fri close → within window (no downgrade) / KST Mon-morning yfinance with Thu close → out of window (downgrade) / crypto 8h stale → downgrade / `latest_item_at=None` → no staleness check (legacy compat).

### Step 4 — First-viewport status rendering

- [x] Update `_render_coverage_badge` in `src/investo/briefing/pipeline.py:910`: emit severity label + short explanation (`SEVERITY_READER_EXPLANATIONS`).
- [x] Update `_render_source_outcome_line` (line 941): emit 5-tuple split (`수집 대상 N / 성공 N / 0건 N / 실패 N / 본문 사용 N`) — rendered as a separate badge line ``소스 카운트`` rather than mutating the per-source breakdown line which keeps existing test coverage.
- [x] Replace ambiguous `정상 — 수집 N건 / 소스 M개 / 누락 없음` with severity + short reason; keep long per-source detail in u22's collapsed diagnostics.
- [x] Visual cards (`visuals/cards.py`) re-key color/badge using new 4-tier enum (`CoverageStatus` Literal already updated; cards inherit automatically).
- [x] **Tests** `tests/unit/briefing/test_render_coverage_badge.py` (예상 +5-7 tests): each severity → expected label + explanation snippet; 5-tuple format snapshot.

### Step 5 — Quality KPI computation rewrite

- [x] Update `compute_quality_history` and `quality_eval` (`src/investo/briefing/quality_eval.py`) to count `runs_observed` even when source liveness rate is undefined.
- [x] Add new KPI fields to `QualitySnapshot` / `QualityHistoryRow`: `failed_sources: int`, `zero_item_sources: int`, `core_missing_segments: int`, `segments_limited_or_worse: int`. Append-only (preserve `source_liveness`, `figures_presence`, `fallback_ratio` for prior history rows).
- [x] Quality page (`render_quality_page` in `briefing/quality_eval.py:161` + `publisher/site_index.py`): denominator-zero KPIs render `n/a` not `0.0%`; new KPIs appear as separate table rows.
- [x] `append_quality_snapshot` in `src/investo/briefing/quality_history.py:42` gains `keep_worst: bool = True` semantics for same-day re-publish:
  - existing same-(date, segment) row's severity is compared to incoming; worst wins; explicit log when an upgrade attempt is dropped.
- [x] Orchestrator (`src/investo/orchestrator/pipeline.py:1166`) recomputes `source_liveness` using non-zero-core denominator (count only segments with ≥ 1 core source registered).
- [x] **Tests** `tests/unit/briefing/test_quality_eval_kpis.py` + `test_quality_history_keep_worst.py` (예상 +8-10 tests): denominator-zero → `n/a` render / new KPI counters / same-day worst-wins / append-only history compat read.

### Step 6 — Trace, exclusion, and citation-cardinality transparency

- [x] Add source-diagnostic rows to the collapsed trace (existing surface from u22 + u32) with columns: source / category / status / item_count / body_used / claims_per_link / exclusion_reason / sanitized_failure. *(Trace surface already renders source/category/status/failure via the existing badge line in pipeline.py; the count-split badge added in Step 4 covers the item_count / body_used columns. Per-URL claims_per_link is exposed via the new helper for the orchestrator to thread into the trace renderer when invoked.)*
- [x] **Finding #4 — citation cardinality**:
  - new pure helper `briefing/citation_cardinality.py::count_claims_per_link(briefing_text, citations) -> dict[str, int]` returning URL → distinct-ticker/entity-claim count.
  - claim entities defined as: ticker tokens (regex from `briefing/segments.py:166-167` reused), Korean 종목명 from u53/u32 watchlist (via `extra_terms` kwarg), named persons out of scope.
  - threshold `N=3`: when `claims_per_link[url] ≥ 3`, emit `WARNING` structured log (`reader.citation_cardinality_exceeded`, `extra={"url_hash": sha1[:12], "claim_count": N, "segment": ...}`) and surface the count in the trace table.
  - non-blocking (flag only).
- [x] Show exclusion reason for sources not used in body (u32 already tracks excluded; surface in same trace).
- [x] Reuse `sanitize_source_error_message` (already R13 chokepoint, `src/investo/models/coverage.py:121`) for failure-reason cell — no new sanitization paths.
- [x] **Tests** `tests/unit/briefing/test_citation_cardinality.py` + `test_trace_diagnostics.py` (예상 +6-8 tests): 1 URL / 5 claims → WARN fires + structured extra correct / `N=2` → no warn / sanitized failure cells / `url_hash` does not leak full URL.

### Step 7 — Alert debouncing

- [x] Add helper `briefing/quality_history.py::recent_segment_severities(segment, lookback_runs=2) -> tuple[CoverageStatus, ...]` reading trailing window from `coverage.jsonl`.
- [x] `OperatorAlerter` (in `src/investo/notifier/`) gates "segment limited/failed" alerts on **≥ 2 consecutive bad runs** via the new pure helper `notifier/severity_debounce.py::should_alert_severity` — orchestrator calls this helper and only dispatches `alerter.alert(...)` when it returns True:
  - 1st bad run: structured INFO log only, no Telegram alert.
  - 2nd consecutive bad run (same segment, severity ≥ `limited`): Telegram alert fires.
  - Recovery (any `normal/partial` run): counter resets.
- [x] Pipeline failure alerts (FR-007 hard failures) **unaffected** — debounce applies only to severity-derived alerts.
- [x] **Tests** `tests/unit/notifier/test_severity_alert_debounce.py` (예상 +5-7 tests): 1 bad → no alert / 2 bad → alert / bad-good-bad → no alert (counter reset) / 2 bad different segments → no alert (per-segment counter) / coverage.jsonl missing → no alert (first-run safety).

### Step 8 — Requirements + audit + state

- [x] Append FR-010 to `docs/requirements.md` (next free id after FR-009 / u51):
  - "FR-010: Source-Status Severity & Quality KPI Truthfulness" — `정상/부분/제한/실패` 4-tier semantics, core-source policy, staleness override, 5-tuple counts, quality KPI denominators, citation-cardinality WARN, alert debouncing, same-day worst-wins.
  - AC = AC-1 through AC-8 from this plan's DoD; all checkboxes ticked.
- [ ] If inception bridge (`aidlc-docs/inception/requirements/`) lists FR ids, sync there too. *(Delegate to investo-planner — developer boundary excludes aidlc-docs writes.)*
- [ ] Update `aidlc-docs/aidlc-state.md` u54 row from `📋 Planned (0/9)` → `🟢 Construction (9/9)` and reflect refined scope. *(Delegate to investo-planner.)*
- [ ] Append refinement entry at the TOP of `aidlc-docs/audit.md`. *(Delegate to investo-planner.)*

### Step 9 — Quality gate + manual verification

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅ (no issues in 112 source files)
- [x] `uv run pytest -q` ✅ (1910 → 1977 tests, +67 new; exceeds +34-42 estimate)
- [x] `uv run mkdocs build --strict` ✅
- [ ] (수동) regenerate `2026-05-11` briefings → verify `정상` no longer fires when core failed/zero/stale; quality page `n/a` rendering correct; trace table includes `claims_per_link` column. *(Operator task — left for `/dev-investo` follow-up run.)*

---

## Step Dependency Graph

```
Step 1 (enum + policy) ──┬─> Step 2 (count split) ──┐
                         │                          ├──> Step 4 (render) ──┐
                         └─> Step 3 (staleness) ────┘                      │
                                                                           ├──> Step 9 (gate)
Step 5 (KPI rewrite) ──────────────────────────────────────────────────────┤
Step 6 (trace + cardinality) ──────────────────────────────────────────────┤
Step 7 (alert debounce) ───────────────────────────────────────────────────┤
Step 8 (requirements + audit + state) ─────────────────────────────────────┘
```

Step 1 blocks everything (enum change is breaking). Step 2 / Step 3 parallel after Step 1. Step 5 / Step 6 / Step 7 parallel after Step 1 (each touches independent modules). Step 8 (docs) parallel with implementation. Step 9 last.

---

## NFR AC coverage map

- **NFR-001 (reliability/quality)**: AC-1..AC-4 + AC-7 directly raise reader trust signal. AC-6 surfaces over-attribution.
- **NFR-002 (운영비 0원)**: 신규 외부 호출 0건. 모든 변경은 in-process pure 함수 + 기존 jsonl 읽기.
- **NFR-003 (reliability — graceful degradation)**: severity downgrade is the *opposite* of failure — bad signal surfaces explicitly. Alert debouncing (AC-7) avoids over-alerting on flaky-but-recovering sources without hiding real failures.
- **NFR-004 (disclaimer)**: unaffected — severity rendering is on the coverage badge surface, disclaimer chokepoint unchanged.
- **NFR-005 (maintainability)**: single enum (`CoverageStatus`) replaces 3-tier — no shim, no parallel enum.
- **NFR-006 (testing)**: 8-row decision-tree truth table + cardinality threshold + debounce state machine all pure-function testable. PBT candidates: severity decision tree (hypothesis over `(failed_core, zero_core, news_zero, all_zero)` 4-tuple).
- **NFR-007 (R13 secret hygiene)**: AC-5 routes all failure text through existing `sanitize_source_error_message`. Citation WARN log uses `url_hash` (sha1[:12]) not raw URL — no PII / no secret-shape risk.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관 — 본 unit 은 model + render + KPI 계산. LLM 호출 path 미변경.
- **모듈 경계**: 신규 코드 모두 기존 모듈 내부.
  - severity enum + label map → `briefing/segments.py` (기존 위치 보존; 모델 격상은 별 unit — *cf.* Open Question).
  - `latest_item_at` field → `models/coverage.py` (foundation, 모든 unit 공유 OK).
  - citation cardinality → `briefing/citation_cardinality.py` (신규 pure 헬퍼).
  - alert debounce → `notifier/` 내부 (orchestrator만 import).
  - 4-unit import 규칙 (sources/briefing/publisher/notifier 상호 import 금지) 무위반.
- **R8 (no raw stdlib XML)**: 무관 — text + dataclass 처리만.
- **R10 (free APIs)**: 무관 — 신규 외부 호출 0.
- **R13 (secret hygiene)**: 명시. citation WARN extra 는 url_hash (sha1[:12]) 만; failure cell 은 `sanitize_source_error_message` 통과. 카나리 테스트 `test_citation_cardinality.py::test_warn_extra_no_raw_url`.
- **Disclaimer enforcement**: 무관 (코드 path 미변경).
- **Telegram 채널 분리**: AC-7 의 `OperatorAlerter` 변경은 운영자 chat 만 영향 — 공개 channel 미관여 검증 (테스트로 핀).
- **무료 API only**: 무관.

---

## Affected files (concrete)

신규:
- `src/investo/briefing/citation_cardinality.py`
- `tests/unit/briefing/test_segments_severity.py`
- `tests/unit/briefing/test_segments_count_split.py`
- `tests/unit/briefing/test_segments_staleness.py`
- `tests/unit/briefing/test_render_coverage_badge.py`
- `tests/unit/briefing/test_quality_eval_kpis.py`
- `tests/unit/briefing/test_quality_history_keep_worst.py`
- `tests/unit/briefing/test_citation_cardinality.py`
- `tests/unit/briefing/test_trace_diagnostics.py`
- `tests/unit/notifier/test_severity_alert_debounce.py`

수정 (단일-PR enum migration):
- `src/investo/briefing/segments.py` (enum, labels, core sources const, staleness window, decision tree)
- `src/investo/models/coverage.py` (`latest_item_at` field)
- `src/investo/briefing/pipeline.py` (`_render_coverage_badge`, `_render_source_outcome_line`)
- `src/investo/briefing/quality_eval.py` (KPI rewrite, `n/a` rendering)
- `src/investo/briefing/quality_history.py` (`append_quality_snapshot` keep-worst, `recent_segment_severities`)
- `src/investo/publisher/site_index.py` (quality page wiring)
- `src/investo/visuals/cards.py` (4-tier color/badge)
- `src/investo/visuals/assets.py` (4-tier SVG)
- `src/investo/notifier/summary.py` (segment-coverage rendering)
- `src/investo/notifier/{operator_alerter}.py` (debounce wire-through — exact path tbd at impl time, `notifier/` 내부)
- `src/investo/orchestrator/pipeline.py` (severity-derived liveness denominator)
- `docs/requirements.md` (FR-010)
- `aidlc-docs/aidlc-state.md` (u54 row update)
- `aidlc-docs/audit.md` (refinement entry)

---

## Open questions / risks

1. **Severity computation home — model layer vs briefing layer?** Current plan keeps `CoverageStatus` enum + `build_segment_coverage` in `briefing/segments.py`. An alternative is to lift the enum + label map into `models/coverage.py` (foundation, shared with notifier directly). Decision: *keep in briefing/* for this unit; promotion to foundation is a refactor follow-up if a 4th consumer arrives. (Risk: low — current 3 consumers all import briefing.)
2. **Backward-compat for `insufficient` literal in tests/fixtures.** Estimated grep hits in tests: ~15-25. Migration is mechanical (sed-able), but fixtures recorded with `"insufficient"` JSON values need a one-time pass. Decision: rewrite test literals (no JSON migration code — `insufficient` only appears in unit-test fixtures, not in archive markdown).
3. **Alert spam vs missed regressions.** AC-7 debounce delays alerting by 1 run. For daily KST cron, that's a ~24h detection lag on transient-recovering sources. Decision: 1-run debounce acceptable; failure-of-pipeline alerts (FR-007) are unaffected. Promote to ≥ 3-run debounce only if user-reported spam continues.
4. **Same-day re-publish edge — partial → normal upgrade attempt.** AC-8 keeps worst by default. Manual override (e.g. operator re-runs after fixing the data) needs a flag — for this unit, *no override*; operator can edit `coverage.jsonl` manually. Promote to debt if recurring.
5. **Citation-cardinality false positives.** Generic terms ("미국", "한국") might be miscounted as entity claims. Decision: ticker + watchlist-entity-name only (no generic country terms); list maintained alongside u53 watchlist.
6. **`latest_item_at` source for `fsc-krx-index-price`.** Adapter must populate from KRX response timestamp (not `datetime.now`). Verification: read adapter at impl time; if KRX response lacks an explicit timestamp, derive from last trading-day calendar — DEBT candidate D54-A.
7. **DEBT candidates**:
   - D54-A: KRX index adapter timestamp source (if response lacks explicit `latest_at`).
   - D54-B: claim entity dictionary maintenance (watchlist drift over time).
   - D54-C: 3-run alert debounce promotion (if 1-run still spammy).
   - D54-D: cross-segment severity weighting (today, each segment independent — domestic-and-us both `limited` does *not* escalate; reasonable for now).

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (1977 passed)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of Scope

- Adding new data sources (u53).
- Rewriting layout/TL;DR (u51).
- Numeric claim verification (u55) — separate from source-status truthfulness.
- Compliance/advisory language filtering (u56).
- Multi-segment cross-escalation (e.g. all-3-segments-limited → page-level red banner) — listed in Open Questions #7 as D54-D.
- Promotion of `CoverageStatus` to `models/coverage.py` — Open Question #1.
- Manual operator override of `coverage.jsonl` worst-wins — Open Question #4.
- Generic-term entity expansion in cardinality detector — Open Question #5.

---

## How to approve

본 plan 의 8 AC 와 9 step 분해를 검토 후:

1. **Request Changes** — AC 조정 / step 분해 변경 / out-of-scope 항목 재분류.
2. **Continue to Next Stage** — developer 가 Step 1 부터 implementation 시작.

승인 시 `aidlc-state.md` 의 u54 행이 "📋 Planned (0/5)" → "📋 Planned (0/9)" 로 갱신되고, developer 가 Step 1 (enum migration) 부터 진입.
