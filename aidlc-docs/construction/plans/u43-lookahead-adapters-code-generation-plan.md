# Code Generation Plan: `u43 lookahead-adapters`

**Date**: 2026-05-09
**Unit**: u43 lookahead-adapters
**Stage**: Code Generation
**Status**: 📋 Planned (blocked on live API sessions for R10 fixtures across 4 endpoints; FRED key registration also required)
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

- [ ] Four new source adapters registered via the existing `@register` plugin pattern, each with R10-compliant fixtures recorded against live API responses:
  - **(a) `fomc-calendar`** — Federal Reserve `press_monetary` RSS / ICS feed; segment routing: `us-equity` + `crypto`; tier `S` (regulator-of-record).
  - **(b) `fred-economic-calendar`** — FRED public release-schedule endpoint (or the equivalent BEA / BLS release-schedule public feed if FRED's calendar surface is insufficient); segment routing: `us-equity` + `crypto`; tier `A` (authoritative but not regulator-of-record).
  - **(c) `coingecko-events`** — CoinGecko events public endpoint (gauge availability — endpoint deprecated upstream is possible; if so, fall back to a free crypto event aggregator like CoinMarketCal); segment routing: `crypto`; tier `B`.
  - **(d) `krx-option-expiry`** — KRX public option-expiry / 공시 lookahead feed; segment routing: `domestic-equity`; tier `S`.
- [ ] All four adapters stamp `NormalizedItem.scheduled_at` (UTC) so the u35 deterministic 72h Telegram imminent-tag selector and the `_render_lookahead_context_block` Stage 2 renderer route them automatically.
- [ ] Orchestrator wire-through: `_stage_notify_segmented_briefing` populates `lookahead_items_by_segment` from the new adapters' output filtered through `_render_lookahead_context_block`'s **single** filter call, and passes both that mapping and `now_utc` **explicitly** to `build_segmented_summary`. The notifier raises `ValueError` if `lookahead_items_by_segment` is supplied while `now_utc=None`. (Per DEBT-067 M1 + M3 sub-bullets.)
- [ ] `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` added to the u22 reason-code enum and emitted from the aggregator only when (a) the lookahead pass for a given segment returns zero items **and** (b) at least one lookahead-aware adapter was attempted for that segment. Pin: the reason code never fires on a segment that has no lookahead-aware adapter registered.
- [ ] `FRED_API_KEY` enrolled in `_internal/redaction.py::SECRET_ENV_VARS`. (`fomc-calendar`, `coingecko-events`, `krx-option-expiry` use no API key; only `fred-economic-calendar` does.)
- [ ] All four adapters apply the source-level graceful degradation contract: missing key (where applicable) / HTTP 401 / 403 / 5xx → empty list + INFO log + source health records `failed`. Pinned by per-adapter regression test.
- [ ] Stage 2 prompt + segment markdown + Telegram tag verified end-to-end by an integration test that wires through one or more of the new adapters (not all four required for the integration test — one suffices to prove the wire-through).
- [ ] DEBT-067 marked **Resolved** in `docs/TECH-DEBT.md` with the resolution date and a one-line note pointing at this unit.
- [ ] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Live API Sessions + Fixture Recording (Per-Adapter)

- [ ] **Operator action (one-time, off-line from coding session)**: complete the four prerequisites:
  - Register a free `FRED_API_KEY` at https://fred.stlouisfed.org/docs/api/api_key.html.
  - Confirm CoinGecko events endpoint is still live (curl https://api.coingecko.com/api/v3/events; if 404 / deprecated, choose the fallback aggregator).
  - Confirm KRX option-expiry feed URL — the feed lives at the KRX public market-data surface; verify the public path that does not require OTP / scraping.
  - Verify Federal Reserve `press_monetary` RSS reachable (https://www.federalreserve.gov/feeds/press_monetary.xml).
- [ ] Record one happy-path fixture per adapter against the real endpoint. Each fixture pair: response body file + `.meta.json` sidecar with `recorded_at`, redacted URL, sha256 of body.
- [ ] Record one empty-window fixture per adapter (a window with no scheduled events).
- [ ] Save under `tests/fixtures/sources/{adapter_slug}/{scenario}/sample.{ext}` per the existing fixture convention.
- [ ] **R10 invariant**: fixtures must be byte-equal to live API responses (modulo redacted secrets). No fabricated payloads.

### Step 2 — `fomc-calendar` Adapter

- [ ] Create `src/investo/sources/fomc_calendar.py` registered via `@register("fomc-calendar", segments=("us-equity","crypto"))`.
- [ ] Parse via `defusedxml.ElementTree` per R8 (RSS/ICS path). Apply R14 SEC-style fair-access UA (Federal Reserve does not have a strict UA policy, but a clear `Investo/1.0 (https://murphygo.github.io/investo)` UA matches the project's R14 conventions).
- [ ] Stamp `NormalizedItem.scheduled_at` from the RSS `<pubDate>` or ICS `DTSTART` (whichever the chosen endpoint provides). `category="calendar"`.
- [ ] Files affected:
  - `src/investo/sources/fomc_calendar.py` (new)
- [ ] Unit tests at `tests/unit/sources/test_fomc_calendar.py`:
  - happy-path fixture replay → 1+ items with `scheduled_at` populated.
  - empty-window fixture replay → empty list.
  - HTTP 5xx → empty list + source health failed.
  - malformed XML → empty list + source health failed.

### Step 3 — `fred-economic-calendar` Adapter

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

### Step 4 — `coingecko-events` Adapter

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

### Step 5 — `krx-option-expiry` Adapter

- [ ] Create `src/investo/sources/krx_option_expiry.py` registered via `@register("krx-option-expiry", segments=("domestic-equity",))`.
- [ ] Use the public KRX market-data path that does **not** require OTP / scraping (consistent with u36's "no Naver / KRX scraping" out-of-scope rule). If no such path exists, defer this specific adapter to a TECH-DEBT and ship the other three (re-evaluate at unit closeout).
- [ ] Stamp `NormalizedItem.scheduled_at` from the option-expiry date.
- [ ] Files affected:
  - `src/investo/sources/krx_option_expiry.py` (new — conditional on confirmed public feed)
- [ ] Unit tests at `tests/unit/sources/test_krx_option_expiry.py`:
  - happy-path fixture → 1+ items.
  - empty-window fixture → empty list.
  - HTTP 5xx → empty list + source health failed.

### Step 6 — Tier Registry Enrollment

- [ ] In `sources/tiers.py`, add: `"fomc-calendar": "S"`, `"fred-economic-calendar": "A"`, `"coingecko-events": "B"`, `"krx-option-expiry": "S"`.
- [ ] Files affected:
  - `src/investo/sources/tiers.py`
- [ ] Anti-regression test: each new adapter's fixture replay produces a `SourceOutcome` with the expected tier.

### Step 7 — R13 Secret Enrollment

- [ ] Add `"FRED_API_KEY"` to `_internal/redaction.py::SECRET_ENV_VARS`.
- [ ] Files affected:
  - `src/investo/_internal/redaction.py`
- [ ] Anti-regression test: simulated log line containing `FRED_API_KEY` value → STRICT redaction strips it.

### Step 8 — Orchestrator Wire-Through (DEBT-067 M1 + M3)

- [ ] `orchestrator/pipeline.py::_stage_notify_segmented_briefing`:
  - Compute `now_utc = datetime.now(UTC)` at orchestrator entry.
  - Populate `lookahead_items_by_segment` from the new adapters' output, filtered through `_render_lookahead_context_block`'s **single** filter call (M3: single-filter reuse).
  - Pass both `lookahead_items_by_segment` and `now_utc` **explicitly** to `build_segmented_summary`.
- [ ] `notifier/summary.py::build_segmented_summary`: raise `ValueError("now_utc required when lookahead_items_by_segment is supplied")` when the kwarg is supplied while `now_utc=None`. (M1: clock-explicit contract.)
- [ ] Files affected:
  - `src/investo/orchestrator/pipeline.py`
  - `src/investo/notifier/summary.py`
- [ ] Unit tests:
  - integration-style test: orchestrator with one fixture-driven lookahead adapter → Telegram summary contains the imminent-event tag.
  - clock-explicit contract: `build_segmented_summary(lookahead_items_by_segment={...}, now_utc=None)` raises `ValueError`.
  - single-filter reuse: a single filter call's result feeds both the markdown context block and the imminent-tag selector (regression: assert the two surfaces see byte-identical filtered lists).

### Step 9 — `LOOKAHEAD_DATA_MISSING` Reason Code

- [ ] Add `LOOKAHEAD_DATA_MISSING` to `models/coverage.py::SegmentCoverage.reason_codes` enum.
- [ ] Aggregator emit logic: emit only when (a) lookahead pass for the segment returns zero items **and** (b) at least one lookahead-aware adapter was attempted. Never emit on a segment with no lookahead-aware adapter registered (anti-regression).
- [ ] Files affected:
  - `src/investo/models/coverage.py`
  - `src/investo/sources/aggregator.py`
- [ ] Unit tests:
  - segment with zero lookahead items + ≥ 1 attempted adapter → `LOOKAHEAD_DATA_MISSING` reason emitted.
  - segment with zero lookahead items + zero attempted adapters → reason **not** emitted (anti-regression).
  - segment with ≥ 1 lookahead item → reason not emitted.

### Step 10 — DEBT-067 Resolution

- [ ] Move DEBT-067 from `## High Priority` to `## Resolved Items` in `docs/TECH-DEBT.md` with `**Resolved**: YYYY-MM-DD — u43 landed all 4 lookahead adapters + orchestrator wire-through + LOOKAHEAD_DATA_MISSING reason code.`
- [ ] If `krx-option-expiry` was deferred (no public non-scraping feed), keep DEBT-067 open with a scoped sub-bullet noting only that adapter is pending; mark the other three resolutions inline.
- [ ] Files affected:
  - `docs/TECH-DEBT.md`

### Step 11 — Verification

- [ ] Run targeted lookahead tests + the full quality gate.
- [ ] Manual: with `FRED_API_KEY` set + a date close to a known FOMC meeting, run a dry-run publish (`INVESTO_DRY_RUN=1`) and confirm the segment markdown carries the "주요 일정" block populated with FOMC + FRED entries; confirm the Telegram preview (rendered via the dry-run summary path) carries the `📅 FOMC D-N` tag.

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
