# Code Generation Plan: `u43 lookahead-adapters`

**Date**: 2026-05-09
**Unit**: u43 lookahead-adapters
**Stage**: Code Generation
**Status**: 🟨 Partial (2026-05-10 — `fomc-calendar` + orchestrator wire-through M1/M3 + `LOOKAHEAD_DATA_MISSING` reason code landed; `fred-economic-calendar` + `coingecko-events` + `krx-option-expiry` deferred under DEBT-067 sub-bullets per R10 — see TECH-DEBT.md DEBT-067 partial-resolution note)
**Source**: 10-persona evaluation 2026-05-09 — persona #4 (미국 적극) + persona #8 (운영자) + DEBT-067
**Estimated Effort**: ~6-10 h (after live API access secured for all 4 endpoints)
**Dependencies**:
- Builds on `u35 event-lookahead` (Phase 0 + Phase 1 partial already landed; this unit lands the four lookahead-specific source adapters that Phase 1 deferred to DEBT-067).
- Builds on `u1 sources` (`@register` plugin pattern), `u11 http-identity-encoding`, `u14 R14 fair-access UA`.
- Resolves DEBT-067 (`docs/TECH-DEBT.md` line 32) — u35 event-lookahead 이월: 4 lookahead 어댑터 + orchestrator wire-through + LOOKAHEAD_DATA_MISSING reason code.
- Coexists with `u22 source-coverage-transparency` (the new `LOOKAHEAD_DATA_MISSING` reason code is added to u22's enum).

---

## Goal

Land the four lookahead-specific source adapters that u35 deferred to DEBT-067, then wire the orchestrator's `_stage_notify_segmented_briefing` + the `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` reason code so u35's downstream pipe (Stage 2 prompt "주요 일정" block + Telegram imminent tag) actually fires in production. Each adapter must surface forward-looking events keyed by `NormalizedItem.scheduled_at` so the existing u35 Phase 1 plumbing routes them deterministically.

---

## Persona evidence

> Persona #4 (미국 적극, P1): "FOMC 가 이번 주에 있는지, 이번 주말에 NFP 가 나오는지 — 이게 시황 첫 줄에 보여야 한다. u35 가 이미 깔아놨는데 어댑터가 없어서 dormant 라는 게 가장 답답하다."

> Persona #8 (운영자, P1): "DEBT-067 가 P1 인 이유가 사용자 입장에서는 'u35 가 끝났는데 왜 시황에 일정이 안 나오나' 가 풀리지 않은 채로 남아 있기 때문이다. 어댑터 4개 + wire-through + reason code 가 한 묶음으로 가야 의미가 있다."

> DEBT-067 (line 32): "u35 Phase 1 lands the entire downstream pipe ... end-to-end except for the four lookahead-specific source adapters that populate it: `fomc-calendar`, `fred-economic-calendar`, `coingecko-events`, KRX option-expiry."

---

## Definition of Done

- [x] **(a) `fomc-calendar`** — Federal Reserve `calendar.json` forward-schedule endpoint (preferred over `press_monetary` RSS because the latter is backward-looking press-release announcements; `calendar.json` carries forward FOMC meetings + speeches + statistical releases); segment routing: `us-equity` (single-segment, per `_US_ONLY_SOURCES`); tier `S`. R10-compliant fixture: `tests/unit/sources/fixtures/api/fomc-calendar/upcoming.json` (528 KB live recording 2026-05-10, sha256 `8d7995f3417d839497a62c30b8da992f9e4498561d193c08a72ae9e63b51de1f`).
- [ ] **(b) `fred-economic-calendar`** — DEFERRED under DEBT-067 sub-bullet. FRED `api.stlouisfed.org` was unreachable from the u43 implementation network (TLS handshake timed out across IPv4/IPv6/HTTP1.1/HTTP2 + via curl + via httpx; verified the existing `fred-macro` `series/observations` path was equally unreachable, so this is a transient FRED-side or network-side outage rather than a credential issue). Per R10, the adapter cannot land without a live recording.
- [ ] **(c) `coingecko-events`** — DEFERRED under DEBT-067 sub-bullet. Endpoint deprecated upstream (`https://api.coingecko.com/api/v3/events` returns 404 with `{"error":"Incorrect path. Please check https://docs.coingecko.com/"}` — verified live 2026-05-10). Fallback aggregator (CoinMarketCal) requires a free-tier key the user has not yet registered.
- [ ] **(d) `krx-option-expiry`** — DEFERRED under DEBT-067 sub-bullet. No public KRX market-data path that exposes the option-expiry calendar without OTP / scraping is currently identified; consistent with u36's "no Naver / KRX scraping" out-of-scope rule.
- [x] `fomc-calendar` stamps `NormalizedItem.scheduled_at` (UTC midnight on the event's first day); `published_at` anchored to the publish-window target date midnight (mirrors the `nasdaq-earnings-calendar` lookahead pattern).
- [x] Orchestrator wire-through: `_stage_notify_segmented_briefing` accepts `lookahead_items_by_segment` + `now_utc` kwargs, computes `notify_now_utc = datetime.now(UTC)` at orchestrator entry, populates the per-segment lookahead bucket via `briefing.segments.filter_lookahead_items` (M3 single chokepoint, also reused by `briefing/pipeline.py::_render_lookahead_context_block`), and passes both kwargs explicitly to `build_segmented_summary`. The notifier raises `ValueError("now_utc required when lookahead_items_by_segment is supplied")` when the kwarg is supplied while `now_utc=None` (M1 clock-explicit contract).
- [x] `SegmentCoverage.reason_codes` carries the new `LOOKAHEAD_DATA_MISSING` value with Korean label "예정 일정 데이터 미확보". Emission path: `_lookahead_data_missing` in `briefing/segments.py`. Anti-regression: never fires on a segment with no lookahead-aware adapter (`LOOKAHEAD_AWARE_SOURCES` registry is the single decision point — at u43 landing the registry contains `fomc-calendar` + `nasdaq-earnings-calendar`; both anchor to `us-equity`, so `domestic-equity` / `crypto` cannot trip the reason code today).
- [x] `FRED_API_KEY` already enrolled in `_internal/redaction.py::SECRET_ENV_VARS` (verified — was already present from the u35 / fred-macro work). `fomc-calendar` uses no API key.
- [x] `fomc-calendar` graceful-degradation contract pinned by `test_terminal_4xx_raises_source_fetch_error`, `test_malformed_json_raises_terminal_source_fetch_error`, `test_non_object_response_raises_terminal_source_fetch_error`. Aggregator R6 isolation handles each via the existing `SourceFetchError` path.
- [x] Stage 2 / Telegram round-trip pinned by `tests/unit/orchestrator/test_stage_notify_segmented_lookahead.py::test_stage_passes_lookahead_and_now_utc_to_summary_builder` — a 2-day-out FOMC item from the lookahead bucket lands as `D-2 📅` in the request body the publisher dispatches.
- [ ] DEBT-067 partially resolved (see `docs/TECH-DEBT.md` — kept in High Priority section with a "Partial resolution" block noting `fomc-calendar` + wire-through + reason code landed; FRED + CoinGecko + KRX retained as sub-bullets pending future live-API access). Planner action required to formally demote P1 → P2 if appropriate.
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` (1763 passed, +40 vs pre-u43) ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Live API Sessions + Fixture Recording (Per-Adapter)

- [x] **Operator action (one-time, off-line from coding session)**: completed for `fomc-calendar`; partial for the rest (see DoD bullets above):
  - Register a free `FRED_API_KEY` at https://fred.stlouisfed.org/docs/api/api_key.html.
  - Confirm CoinGecko events endpoint is still live (curl https://api.coingecko.com/api/v3/events; if 404 / deprecated, choose the fallback aggregator).
  - Confirm KRX option-expiry feed URL — the feed lives at the KRX public market-data surface; verify the public path that does not require OTP / scraping.
  - Verify Federal Reserve `press_monetary` RSS reachable (https://www.federalreserve.gov/feeds/press_monetary.xml).
- [x] Recorded one happy-path fixture for `fomc-calendar` (`tests/unit/sources/fixtures/api/fomc-calendar/upcoming.json`, 528 KB). The empty-window scenario is exercised by replaying the same fixture against a far-future `target_date` (2027-08-01) since the captured calendar stops at 2026-12-30 — this is the byte-equal real shape, not fabricated.
- [x] Saved under `tests/unit/sources/fixtures/api/fomc-calendar/` per the convention used by every other adapter in this repo. `meta.json` carries `_recorded_at`, `_recorded_url`, `status`, `headers`, `sha256`, and `byte_size`.
- [x] **R10 invariant**: the fixture body is byte-equal to the live `calendar.json` body recorded 2026-05-10. No api_key / token strings appear in either the fixture body or `meta.json` (verified via grep: zero hits). The endpoint is unauthenticated so no redaction was required.

### Step 2 — `fomc-calendar` Adapter ✅

- [x] Created `src/investo/sources/fomc_calendar.py` registered via the existing `@register` class decorator (the registry's signature is class-decorator only, not the `@register("name", segments=…)` form the plan originally sketched — segments routing lives in `briefing/segments.py::_US_ONLY_SOURCES`).
- [x] Parses live `calendar.json` (JSON path — `defusedxml` not required, the body is JSON not XML). Applies R14-style identity UA `Investo/1.0 (+https://murphygo.github.io/investo)`.
- [x] Stamps `NormalizedItem.scheduled_at` from the event's `month` + `days` fields (UTC midnight on the first day of multi-day meetings); `category="calendar"`.
- [x] Files affected:
  - `src/investo/sources/fomc_calendar.py` (new)
  - `src/investo/sources/__init__.py` (import row added)
  - `src/investo/sources/tiers.py` (`"fomc-calendar": "S"`)
  - `src/investo/sources/aggregator.py` (`_US_MARKET_SOURCES` enrolment)
  - `src/investo/briefing/segments.py` (`_US_ONLY_SOURCES` enrolment)
  - `tests/unit/sources/test_plugin_contract.py` (count 20 → 21, name set + import)
- [x] Unit tests at `tests/unit/sources/test_fomc_calendar.py` (16 cases):
  - happy-path real-fixture replay → 1+ items with `scheduled_at` populated, `published_at = target_date midnight UTC`.
  - includes-known-event regression → asserts FOMC Minutes 2026-05-20 appears in the captured fixture's 30-day window.
  - excludes historical events; respects env-var override; far-future target → empty list.
  - HTTP 4xx terminal → `SourceFetchError(transient=False)`.
  - malformed JSON / non-object response → `SourceFetchError(transient=False)`.
  - UTF-8 BOM body accepted; type whitelist drops `Conferences` / `Board`; multi-day event uses first day; relative `link` resolved to absolute URL.
  - env-var typo / above-max clamps to default / max with WARNING.
  - R13: no api_key in endpoint URL; module does not import Anthropic SDK.

### Step 3 — `fred-economic-calendar` Adapter (DEFERRED — DEBT-067 sub-bullet)

- [ ] Create `src/investo/sources/fred_economic_calendar.py` registered via `@register("fred-economic-calendar", segments=("us-equity","crypto"))`.
- [ ] Use `retry_get` with `FRED_API_KEY` query parameter. JSON path; no `defusedxml` needed.
- [ ] Stamp `NormalizedItem.scheduled_at` from the FRED release date. `category="macro"`.
- [ ] Missing `FRED_API_KEY` → empty list + INFO log (graceful degradation).
- [ ] Files affected:
  - `src/investo/sources/fred_economic_calendar.py` (new)
- [ ] Unit tests at `tests/unit/sources/test_fred_economic_calendar.py`:
  - happy-path fixture → 1+ items with `scheduled_at`.
  - empty-window fixture → empty list.
  - missing key → empty list + INFO.
  - HTTP 401 → empty list + source health failed.
  - HTTP 5xx → empty list + source health failed.

### Step 4 — `coingecko-events` Adapter (DEFERRED — DEBT-067 sub-bullet)

- [ ] Create `src/investo/sources/coingecko_events.py` registered via `@register("coingecko-events", segments=("crypto",))`.
- [ ] Use `retry_get`; CoinGecko's free tier requires no key but rate-limits aggressively (~10-30 calls/min); the daily pipeline runs once so no rate-limit handling beyond the existing `retry_get` is needed.
- [ ] If the endpoint is deprecated upstream, the adapter logs a clear deprecation warning and returns empty; the unit landing decision then includes the fallback (e.g., CoinMarketCal). The adapter's tests are written against the chosen fixture set.
- [ ] Stamp `NormalizedItem.scheduled_at` from the event start_date.
- [ ] Files affected:
  - `src/investo/sources/coingecko_events.py` (new)
- [ ] Unit tests at `tests/unit/sources/test_coingecko_events.py`:
  - happy-path fixture → 1+ items.
  - empty-window fixture → empty list.
  - deprecated-endpoint fixture (404) → empty list + WARNING log + source health failed.
  - HTTP 429 (rate-limit) → empty list + source health failed (relies on `retry_get`'s existing 429 handling).

### Step 5 — `krx-option-expiry` Adapter (DEFERRED — DEBT-067 sub-bullet)

- [ ] Create `src/investo/sources/krx_option_expiry.py` registered via `@register("krx-option-expiry", segments=("domestic-equity",))`.
- [ ] Use the public KRX market-data path that does **not** require OTP / scraping (consistent with u36's "no Naver / KRX scraping" out-of-scope rule). If no such path exists, defer this specific adapter to a TECH-DEBT and ship the other three (re-evaluate at unit closeout).
- [ ] Stamp `NormalizedItem.scheduled_at` from the option-expiry date.
- [ ] Files affected:
  - `src/investo/sources/krx_option_expiry.py` (new — conditional on confirmed public feed)
- [ ] Unit tests at `tests/unit/sources/test_krx_option_expiry.py`:
  - happy-path fixture → 1+ items.
  - empty-window fixture → empty list.
  - HTTP 5xx → empty list + source health failed.

### Step 6 — Tier Registry Enrollment ✅ (partial)

- [x] In `sources/tiers.py`, added `"fomc-calendar": "S"`. (`coingecko-events: B` was already present from a previous unit and remains, since the deferred adapter inherits it whenever it lands. `fred-economic-calendar` + `krx-option-expiry` will be added when those adapters land.)
- [x] Files affected:
  - `src/investo/sources/tiers.py`
- [x] Anti-regression: covered indirectly via the existing `tests/unit/sources/test_plugin_contract.py` drift guard (expanded count + name set) — every registered adapter must round-trip through `adapter_tier` without falling back to the default `"B"`.

### Step 7 — R13 Secret Enrollment ✅ (already complete from u35)

- [x] `FRED_API_KEY` was already enrolled in `_internal/redaction.py::SECRET_ENV_VARS` from the u35 / fred-macro work; verified in place at line 96. No new secret was introduced by `fomc-calendar` (the Federal Reserve calendar endpoint is unauthenticated).
- [ ] Files affected: none.
- [x] Anti-regression: existing `tests/unit/_internal/test_redaction.py` covers the FRED key shape.

### Step 8 — Orchestrator Wire-Through (DEBT-067 M1 + M3) ✅

- [x] `orchestrator/pipeline.py::_stage_notify_segmented_briefing`:
  - Computes `notify_now_utc = datetime.now(UTC)` at the call site.
  - Populates `lookahead_items_by_segment` per segment via `briefing.segments.filter_lookahead_items` applied to `routed_items_for_alert.for_segment(segment)` — same chokepoint reused by `briefing/pipeline.py::_render_lookahead_context_block` (M3: single-filter reuse, anti-regression test pins zero inline `scheduled_at is not None` predicates in the orchestrator module).
  - Passes both `lookahead_items_by_segment` and `now_utc` explicitly to `build_segmented_summary`.
- [x] `notifier/summary.py::build_segmented_summary`: raises `ValueError("now_utc required when lookahead_items_by_segment is supplied")` when the kwarg is supplied while `now_utc=None`. The check fires before any rendering so tests see a clean `ValueError` rather than a partially-built summary.
- [x] `briefing/segments.py::filter_lookahead_items` — new public chokepoint; consumers: orchestrator + briefing pipeline.
- [x] Files affected:
  - `src/investo/orchestrator/pipeline.py`
  - `src/investo/notifier/summary.py`
  - `src/investo/briefing/pipeline.py` (one-line switch from inline `tuple(item for item …)` to `filter_lookahead_items`)
  - `src/investo/briefing/segments.py` (helper added)
- [x] Unit tests at `tests/unit/orchestrator/test_stage_notify_segmented_lookahead.py` (5 cases) + `tests/unit/notifier/test_summary.py` (2 new cases at the end of the file):
  - integration-style test: orchestrator stage helper with a fixture-driven `fomc-calendar` lookahead item → Telegram request body contains `D-2 📅`.
  - clock-explicit contract: `build_segmented_summary(lookahead_items_by_segment={...}, now_utc=None)` raises `ValueError`; the symmetric direction (`now_utc=set, lookahead=None`) does not raise.
  - single-filter chokepoint test: pins the helper's exact return shape; orchestrator-module grep test asserts no inline duplicate of the predicate.
  - backward-compat: omitting `lookahead_items_by_segment` leaves the legacy line shape (no `D-N` injection).

### Step 9 — `LOOKAHEAD_DATA_MISSING` Reason Code ✅

- [x] Added `LOOKAHEAD_DATA_MISSING` to `briefing/segments.py::CoverageReasonCode` Literal (the canonical home — `models/coverage.py` was the plan's expected location, but `CoverageReasonCode` lives on the briefing-side `SegmentCoverage` per the existing module split, so the addition landed there next to its sibling reason codes). Korean label `"예정 일정 데이터 미확보"` registered in `COVERAGE_REASON_LABELS`.
- [x] Emit logic in `_lookahead_data_missing` helper inside `briefing/segments.py`: fires only when (a) at least one outcome's `source_name` is in the new `LOOKAHEAD_AWARE_SOURCES` registry **and** (b) zero items in the segment carry `scheduled_at is not None`. Anti-regression: registry today contains `fomc-calendar` + `nasdaq-earnings-calendar`, both us-equity-only — `domestic-equity` and `crypto` cannot trip the reason code at u43 landing.
- [x] Files affected:
  - `src/investo/briefing/segments.py` (Literal, label, helper, registry, `__all__`)
- [x] Unit tests at `tests/unit/briefing/test_lookahead_data_missing_reason.py` (7 cases):
  - segment with zero lookahead items + ≥ 1 attempted adapter → reason emitted.
  - segment with zero lookahead items + zero attempted adapters → reason not emitted (anti-regression — `crypto` + `domestic-equity` paths covered).
  - segment with ≥ 1 lookahead item → reason not emitted.
  - failed-only lookahead adapter still counts as "attempted" → reason fires alongside `SOURCE_FAILED`.
  - registry pin: `LOOKAHEAD_AWARE_SOURCES` contains both `fomc-calendar` (new) and `nasdaq-earnings-calendar` (u35).
  - Korean label rendered correctly in `reason_labels`.

### Step 10 — DEBT-067 Resolution ✅ (partial — kept open with scoped sub-bullets)

- [x] DEBT-067 retained in `## High Priority` with a "Partial resolution (2026-05-10, u43)" block summarising the wire-through + reason code + `fomc-calendar` landing. Three remaining sub-bullets (FRED + CoinGecko + KRX) document the deferral cause for each: live FRED unreachable from the implementation network (transient), CoinGecko events deprecated upstream + CoinMarketCal needs a free-tier key, KRX has no public non-scraping path. Planner-action note added recommending P1 → P2 demotion.
- [x] Files affected:
  - `docs/TECH-DEBT.md`

### Step 11 — Verification ✅

- [x] Targeted lookahead tests pass (40 new cases, all green): `pytest tests/unit/sources/test_fomc_calendar.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_lookahead_data_missing_reason.py tests/unit/orchestrator/test_stage_notify_segmented_lookahead.py -v` → 40 passed.
- [x] Full quality gate green: `ruff check .` ✅, `ruff format --check .` ✅ (259 files unchanged), `mypy --strict src/` ✅ (103 files), `pytest -q` ✅ (1763 passed, +40 vs pre-u43), `mkdocs build --strict` ✅.
- [ ] Manual dry-run with a known FOMC date — deferred to operator validation (the operator runs production cron with `INVESTO_DRY_RUN=1` to confirm the imminent tag fires). The unit-level integration test (`tests/unit/orchestrator/test_stage_notify_segmented_lookahead.py::test_stage_passes_lookahead_and_now_utc_to_summary_builder`) already pins the same wire end-to-end against an in-memory `MockTransport` publisher, so the production behavior is mechanically reproducible.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable.
- **Module boundary**: adapters live in `sources/`; orchestrator wire-through respects the existing `orchestrator → notifier / briefing / sources` direction. No new cross-module import beyond the existing patterns.
- **R8 (no raw stdlib XML)**: `fomc-calendar` uses `defusedxml.ElementTree`. The other three are JSON. Pinned by import-only test.
- **R10 (record/replay fixtures, no fabrication)**: enforced. Fixtures must be byte-equal to live API responses. **This unit is blocked on live API sessions across 4 endpoints — implementation cannot land without real fixtures for each.**
- **R13 (secret hygiene)**: enforced. `FRED_API_KEY` enrolled in `SECRET_ENV_VARS`. URL-aware redaction strips the `api_key` query parameter from any FRED URL appearing in logs / errors / `raw_metadata`. The other three adapters use no secrets.
- **R14 (fair-access UA)**: applied to `fomc-calendar` (Federal Reserve UA convention). Other three adapters use the project's existing UA conventions.
- **No paid APIs**: all four adapters are free-tier reachable. Compliant.
- **Disclaimer enforcement**: untouched (publisher gate stays the chokepoint).

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (expect ~40-60 new tests across 4 adapters + tier + reason code + orchestrator wire-through)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **Earnings calendar lookahead** — already covered by u35 Phase 1's `nasdaq-earnings-calendar` opt-in. Not duplicated here.
- **VIX / sector ETF volatility** — separate unit if persona feedback escalates. The lookahead adapters here cover scheduled events; volatility metrics are a different surface.
- **Token unlock aggregators beyond CoinGecko** — if the CoinGecko events endpoint is deprecated and CoinMarketCal does not satisfy, deeper aggregation (e.g., Token Unlocks API, paid) is out of scope per NFR-002.
- **Two-pass aggregator** — u35 Phase 1's per-adapter env-var opt-in pattern is preserved. A two-pass aggregator (one backward pass + one forward pass) is reconsidered if multiple lookahead-aware adapters demand it; today, each adapter does its own forward iteration.
- **AI / ML event impact prediction** — lookahead items are surfaced verbatim with deterministic D-N tags; no ML scoring of "expected impact magnitude."

---

## Open questions

- **Live API session scheduling**: this unit is **blocked** on live API sessions for all 4 endpoints. The user needs to (1) register `FRED_API_KEY`, (2) confirm `coingecko-events` endpoint or commit to a fallback, (3) verify the KRX public option-expiry path or defer that specific adapter to a TECH-DEBT, (4) record fixtures for each. Implementation cannot land without real fixtures per R10.
- **CoinGecko events deprecation risk**: if the endpoint is deprecated mid-implementation, the unit closeout records the fallback chosen (CoinMarketCal or other free aggregator) and re-runs Step 1's fixture recording.
- **KRX option-expiry feed availability**: if no public non-scraping path exists, ship the other three adapters and keep `krx-option-expiry` as an open TECH-DEBT sub-bullet under DEBT-067 (rather than closing DEBT-067 fully). Domestic-equity readers still benefit from the `dart-disclosure` adapter (u41) for forward-looking corporate events.
- **Tier classification for `coingecko-events`**: classified `B` because CoinGecko is a community aggregator rather than a regulator-of-record or first-party exchange feed. Re-evaluate if the chosen fallback has a different provenance signal.
