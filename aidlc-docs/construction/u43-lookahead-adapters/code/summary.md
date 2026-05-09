# u43 lookahead-adapters — Code stage summary

**Closed**: 2026-05-10 (partial — 1 adapter of 4 landed; 3 deferred under DEBT-067 sub-bullets)
**Status**: ✅ Complete (partial — 3 adapters DEBT-067 deferred)
**Persona**: #4 미국 (P1) + #8 운영자 (P1)
**Resolves**: DEBT-067 partial — orchestrator wire-through + reason code complete; 3 adapter sub-bullets retained

## What landed

### Adapter — `fomc-calendar` ✅

- New module `src/investo/sources/fomc_calendar.py` (~330 lines).
- Endpoint: Federal Reserve `https://www.federalreserve.gov/json/calendar.json` (forward-looking schedule).
- Tier `S` (regulator), segment `us-equity`.
- env override: `INVESTO_FOMC_LOOKAHEAD_DAYS` (default 30, clamp `[1,180]`).
- Plan called for `press_monetary` RSS but that's backward-looking; the forward surface is `calendar.json`. Existing `fomc-rss` (consuming `press_all.xml`) is also backward-looking — the two are now genuinely complementary.

### Orchestrator wire-through (M1 + M3 contracts) ✅

- **M1 (clock-explicit)**: `notifier/summary.py::build_segmented_summary` raises `ValueError("now_utc required when lookahead_items_by_segment is supplied")` before any rendering. `orchestrator/pipeline.py::_stage_notify_segmented_briefing` computes `notify_now_utc = datetime.now(UTC)` at the call site and passes it explicitly.
- **M3 (single-filter chokepoint)**: new public helper `briefing.segments.filter_lookahead_items(items)` returns `tuple(item for item in items if item.scheduled_at is not None)`. Both consumers — `briefing/pipeline.py::_render_lookahead_context_block` (Stage 2 prompt narrative) and `orchestrator/pipeline.py::_stage_notify_segmented_briefing` (Telegram tag selector) — route through this single helper. Anti-regression test asserts the orchestrator module contains zero inline duplicates of the predicate.

### `LOOKAHEAD_DATA_MISSING` reason code ✅

- New entry in `CoverageReasonCode` Literal at `briefing/segments.py`. Korean label "예정 일정 데이터 미확보".
- New `LOOKAHEAD_AWARE_SOURCES` registry — at u43 landing: `frozenset({"fomc-calendar", "nasdaq-earnings-calendar"})`.
- Emit logic in `_lookahead_data_missing` helper: requires (a) any `source_outcome.source_name in LOOKAHEAD_AWARE_SOURCES` AND (b) zero items in segment with `scheduled_at is not None`. Anti-regression: domestic-equity / crypto cannot trip the reason code at u43 landing because both lookahead-aware sources are us-equity-only.

## What was deferred (DEBT-067 sub-bullets)

| Adapter | Status | Retry condition |
|---------|--------|-----------------|
| `fred-economic-calendar` | DEFERRED | `api.stlouisfed.org` TLS handshake timeout from implementation network during session — transient FRED-side / network outage, not credentials. Verified post-session that FRED is reachable from main shell (status 400 with test key = TLS OK). Re-record fixture in a follow-up dev session. |
| `coingecko-events` | DEFERRED | `https://api.coingecko.com/api/v3/events` returns 404 `{"error":"Incorrect path"}` (verified live). Endpoint deprecated upstream. CoinMarketCal fallback needs a free-tier key the user has not registered yet — user decision needed. |
| `krx-option-expiry` | DEFERRED | No public KRX path exposes option-expiry calendar without OTP / scraping (consistent with u36 out-of-scope). Sub-bullet retained until KRX exposes a public feed. |

## R10 fixture recording session

| fixture | bytes | sha256 prefix | api_key plaintext hits |
|---------|-------|---------------|------------------------|
| `tests/unit/sources/fixtures/api/fomc-calendar/upcoming.json` | 528,613 | `8d7995f3…` | 0 |
| `tests/unit/sources/fixtures/api/fomc-calendar/meta.json` | (small) | n/a | 0 |

R13 verification: `grep -ic "api_key\|API_KEY"` → 0 across both files. Endpoint is unauthenticated.

Other adapters: deferred → no fixtures recorded (per R10 — fabricated payloads forbidden).

## Files changed

### Source
- `src/investo/sources/fomc_calendar.py` (new, ~330 lines)
- `src/investo/sources/__init__.py` (+1 import row)
- `src/investo/sources/tiers.py` (+`"fomc-calendar": "S"` row)
- `src/investo/sources/aggregator.py` (`_US_MARKET_SOURCES` adds `"fomc-calendar"`)
- `src/investo/briefing/segments.py` (`CoverageReasonCode` Literal + `COVERAGE_REASON_LABELS` + `LOOKAHEAD_AWARE_SOURCES` registry + `filter_lookahead_items` helper + `_lookahead_data_missing` helper + `_US_ONLY_SOURCES` enrolment + `__all__`)
- `src/investo/briefing/pipeline.py` (one-line switch to `filter_lookahead_items`; import update)
- `src/investo/notifier/summary.py` (M1 ValueError invariant before rendering)
- `src/investo/orchestrator/pipeline.py` (`_stage_notify_segmented_briefing` accepts `lookahead_items_by_segment` + `now_utc`; call site computes `notify_now_utc = datetime.now(UTC)` and builds per-segment lookahead bucket via `filter_lookahead_items(routed_items_for_alert.for_segment(segment))`; `filter_lookahead_items` import added)

### Tests
- `tests/unit/sources/test_fomc_calendar.py` (new, 16 cases)
- `tests/unit/sources/test_plugin_contract.py` (count 20 → 21, name set, import row, leak set)
- `tests/unit/notifier/test_summary.py` (+2 cases — M1 contract + symmetric direction)
- `tests/unit/briefing/test_lookahead_data_missing_reason.py` (new, 7 cases)
- `tests/unit/orchestrator/test_stage_notify_segmented_lookahead.py` (new, 5 cases — including grep test pinning zero inline `scheduled_at is not None` predicates in orchestrator module)

### Docs
- `docs/TECH-DEBT.md` (DEBT-067 retained in High Priority with new "Partial resolution (2026-05-10, u43)" block + 3 deferred sub-bullets + planner-action note recommending P1 → P2 demotion)
- `aidlc-docs/construction/plans/u43-lookahead-adapters-code-generation-plan.md` (Status changed to "🟨 Partial"; DoD checkboxes + per-step landing notes)

## Project rule compliance

- Module boundary: orchestrator wire-through is the only cross-module touchpoint (notifier ← orchestrator). All other changes within `sources/` and `briefing/`.
- R10: 1 live recording for `fomc-calendar`. 3 deferred adapters → no fixtures, no fabrications. Sub-bullets in DEBT-067 retain explicit retry conditions.
- R13: `FRED_API_KEY` was already enrolled in `SECRET_ENV_VARS` from u35; no new secret added (FRED-economic-calendar deferred). `fomc-calendar` endpoint is unauthenticated.
- u35 infrastructure reuse: `format_lookahead_section`, `extract.CONCLUSION_PREFIX`, `_synthesize` lookahead signature, `FetchWindow.lookahead`, `NormalizedItem.scheduled_at`, `_MAX_LLM_LOOKAHEAD_ITEMS` cap — all reused without modification.
- u45 segment routing preserved: `fomc-calendar` registered in `_US_ONLY_SOURCES`. Anti-regression test confirms no leak to crypto / domestic-equity.

## Quality gate

| Gate | Result |
|------|--------|
| `ruff check` | passed |
| `ruff format --check` | 259 files unchanged |
| `mypy --strict src/` | 103 source files, no issues |
| `pytest -q` | **1763 passed** (1723 → 1763, +40 tests) in ~87s |
| `mkdocs build --strict` | built in 0.36s |

## DEBT-067 status

Retained in High Priority with a "Partial resolution (2026-05-10, u43)" block summarising:
- `fomc-calendar` adapter landed
- Orchestrator wire-through M1/M3 complete
- `LOOKAHEAD_DATA_MISSING` reason code complete
- 3 sub-bullets recording each deferred adapter's exact retry condition

Planner-action note inline recommending **P1 → P2 demotion** since the user-visible payoff (Telegram imminent tag + "주요 일정" block) now fires from `fomc-calendar` data, partially resolving the dormancy that drove the original P1.

## Out of scope (per plan)

Stage 2 prompt 본문 변경 (u35 가 이미 처리), 새 lookahead 카테고리 추가, 다른 어댑터 변경, KRX OTP scraping (R10 violation).
