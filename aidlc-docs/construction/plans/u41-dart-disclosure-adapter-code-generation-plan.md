# Code Generation Plan: `u41 dart-disclosure-adapter`

**Date**: 2026-05-09
**Unit**: u41 dart-disclosure-adapter
**Stage**: Code Generation
**Status**: 📋 Planned (blocked on OPENDART_API_KEY live session for R10 fixtures)
**Source**: 10-persona evaluation 2026-05-09 — persona #5 (국내 페르소나)
**Estimated Effort**: ~4-6 h (after live API access secured)
**Dependencies**:
- Builds on `u1 sources` (plugin pattern, `@register`, `retry_get`, `strip_html`).
- Builds on `u36 source-expansion-bundles` (existing domestic-equity adapters: `fsc-krx-index-price`, `fsc-krx-stock-price`, `korea-policy-rss`).
- Builds on `u7 segmented briefing` (segment routing — DART output routes to domestic-equity only).
- Coexists with `u32 trust-traceability-deep-dive` (`SourceTier` registry — DART is `S` tier as the primary regulator-of-record source for KOSPI/KOSDAQ).

---

## Goal

Land a free public DART (전자공시시스템) adapter that surfaces four high-impact corporate disclosure categories — (a) 자사주 매입 / 소각, (b) 정기·수시 배당, (c) 증자·감자·CB (전환사채), (d) 최대주주 변동 — for KOSPI / KOSDAQ-listed companies. This is the #1 gap persona #5 cited: "국내 시황인데 DART 공시 정보가 없으면 핵심 정보가 빠진다." Output is segment-routed to domestic-equity exclusively.

---

## Persona evidence

> Persona #5 (국내, P0): "국내 시황인데 DART(전자공시) 공시 정보가 없으면 사실상 반쪽이다. 자사주 매입, 배당, 증자/감자, 최대주주 변동 — 이 4가지만 잡혀도 국내 페르소나의 갈증의 70% 가 해소된다."

> Persona #5 (continued): "OpenDART API 무료 등록 가능. 키 발급 후 fixtures 만들면 된다."

The persona's own diagnosis already maps the 4 categories that matter most. OpenDART REST API is free with a registered API key (https://opendart.fsc.go.kr/) — the blocker is a one-time live API session to record R10-compliant fixtures, not implementation difficulty.

---

## Definition of Done

- [x] New adapter `dart-disclosure` registered via the existing `@register` plugin pattern, segment-routed to **domestic-equity only** (never reaches the us-equity or crypto pipeline).
- [x] Four disclosure categories surface: (a) 자사주 매입 / 소각 (`자기주식취득결정`, `자기주식소각결정`), (b) 정기 / 수시 배당 (`현금ㆍ현물배당결정`, `주식배당결정`), (c) 증자 / 감자 / CB (`주요사항보고서(유상증자결정)`, `주요사항보고서(감자결정)`, `주요사항보고서(전환사채권발행결정)`), (d) 최대주주 변동 (`최대주주변경` family).
- [x] Output `NormalizedItem` carries: title (Korean disclosure title with corp name prefix), source url (OpenDART viewer link), category (`disclosure`), `published_at` (KST → UTC), `raw_metadata` (rcept_no / corp_code / corp_name / disclosure_type — all redacted of any secret-shaped substrings per R13).
- [x] R10 record/replay fixtures cover one happy-path sample per category (4 fixtures total) plus the empty-day branch (1 fixture). All fixtures recorded against a real OpenDART API call with a real API key; no fabricated payloads.
- [x] R13 secret hygiene: `OPENDART_API_KEY` enrolled in `_internal/redaction.py::SECRET_ENV_VARS` so the URL-aware redaction policy strips any inadvertent leak from logs / errors / coverage reports.
- [x] Adapter registered as `S` tier in `sources/tiers.py` (regulator-of-record source for KRX disclosures, on par with SEC EDGAR for US).
- [x] Source-level graceful degradation: when `OPENDART_API_KEY` is unset, the adapter returns an empty list with a single INFO log line `dart-disclosure: OPENDART_API_KEY not set, skipping`. Never fails the pipeline; never raises in production. Pinned by a regression test.
- [x] Source-level graceful degradation: HTTP 401 / 403 / 5xx from OpenDART → empty list + INFO log + the source health time series records `failed` for that day (consumed by `u31` consecutive-fail detection).
- [x] Coverage transparency: when DART is registered but returns zero items for a publish window, the existing `u22` reason-codes machinery surfaces a `DOMESTIC_DISCLOSURE_QUIET` (or equivalent) reason rather than misclassifying as a coverage failure. (Quiet day vs. failure day must be distinguishable.)
- [x] Stage 2 prompt: domestic-equity prompt receives DART items in the existing candidate stream — no special bucket needed; the existing prompt already handles disclosure-typed candidates via the `category="disclosure"` routing.
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (expect ~25-35 new tests across adapter + fixtures + tier + redaction enrollment).
- [x] `mkdocs build --strict` ✅ (no doc surface change unless persona-#5-facing README ops doc is updated).

---

## Steps

### Step 1 — OpenDART API Key Provisioning + R10 Fixture Recording

- [x] **Operator action (one-time, off-line from coding session)**: register an OpenDART API key at https://opendart.fsc.go.kr/, store as `OPENDART_API_KEY` GHA secret + local `.env` for fixture recording.
- [x] Record one happy-path response per category against a real API call:
  - 자기주식취득결정 (`pblntf_detail_ty=I001` / equivalent endpoint)
  - 현금배당결정 (`pblntf_detail_ty=I*`)
  - 주요사항보고서(전환사채권발행결정)
  - 최대주주변경
- [x] Record one empty-day response (a window with no matching disclosures).
- [x] Save under `tests/fixtures/sources/dart_disclosure/{category}/sample.json` with a sidecar `.meta.json` capturing the live recording date, the URL queried (with `crtfc_key` parameter redacted to `[REDACTED]`), and a sha256 hash of the raw body for tamper detection.
- [x] **R10 invariant**: fixtures must be byte-equal to the live API response (modulo the redacted API key parameter). Anti-regression: a fixture-loader test confirms each fixture has a sidecar `.meta.json` with a non-empty `recorded_at` field.

### Step 2 — Adapter Implementation

- [x] Create `src/investo/sources/dart_disclosure.py` registered via `@register("dart-disclosure", segments=("domestic-equity",))`.
- [x] Adapter signature: `async def fetch(window: FetchWindow, *, http: AsyncClient) -> list[NormalizedItem]`.
- [x] Use `retry_get` (u11 identity-encoding) with adapter-local UA `Investo/1.0 (https://murphygo.github.io/investo)` — OpenDART is friendly to neutral UAs; no R14 fair-access constraint specific to OpenDART, but the request must include the `crtfc_key` query parameter sourced from `os.environ["OPENDART_API_KEY"]`.
- [x] Parse OpenDART JSON response defensively — `defusedxml` not needed (JSON path); `json.loads` with `RuntimeError` capture is sufficient.
- [x] Map disclosure types to a canonical category enum local to the module: `DartCategory = Literal["buyback","dividend","capital_change","ownership_change"]`.
- [x] Apply `strip_html` to any HTML-tagged disclosure title before stamping into `NormalizedItem.title`.
- [x] Files affected:
  - `src/investo/sources/dart_disclosure.py` (new)
  - `src/investo/sources/__init__.py` (re-export)
- [x] Unit tests at `tests/unit/sources/test_dart_disclosure.py`:
  - 4 fixture-replay tests (one per category) → 1 `NormalizedItem` produced with correct `category="disclosure"`, `published_at` in UTC, `raw_metadata` shape.
  - empty-day fixture replay → empty list, no exception.
  - missing `OPENDART_API_KEY` → empty list, single INFO log.
  - HTTP 401 → empty list, source health records `failed`.
  - HTTP 5xx → empty list, source health records `failed`.
  - malformed JSON body → empty list, source health records `failed`.

### Step 3 — Tier Registry Enrollment

- [x] In `sources/tiers.py`, add `"dart-disclosure": "S"` to the registry mapping. DART is the regulator-of-record source for KOSPI/KOSDAQ disclosures, on par with SEC EDGAR for US — same tier classification.
- [x] Files affected:
  - `src/investo/sources/tiers.py`
- [x] Anti-regression test: fixture replay produces a `SourceOutcome` with `tier="S"`.

### Step 4 — R13 Secret Enrollment + Redaction Test

- [x] Add `"OPENDART_API_KEY"` to `_internal/redaction.py::SECRET_ENV_VARS` (URL-aware policy already strips `crtfc_key=...` query parameters per the u27 chokepoint, but the env var enrollment ensures any accidental log of the env value is also stripped).
- [x] Files affected:
  - `src/investo/_internal/redaction.py`
- [x] Anti-regression test:
  - simulated log line containing the value of `OPENDART_API_KEY` → STRICT-policy redaction strips it.
  - simulated error containing `crtfc_key=abc123def456` query param → URL-aware redaction strips the parameter value.

### Step 5 — Coverage Reason Code (Quiet Day vs Failure Day)

> **Completed** (2026-06-18) — landed after the deferred adapter slice. The prompt's
> "scope 제한" rule limited this session to adapter + segment routing +
> tier registry + plugin contract + tests + fixture. The
> `DOMESTIC_DISCLOSURE_QUIET` reason code work touches the u22 coverage
> machinery and now ships with dedicated segment-coverage tests.

- [x] Extend `u22`'s `SegmentCoverage.reason_codes` with `DOMESTIC_DISCLOSURE_QUIET` (or reuse an existing quiet-day code if one exists). Reason: a publish day with zero new disclosures is normal in Korea (weekends, holidays, low-activity windows); rendering `INSUFFICIENT_COVERAGE` or `SOURCE_FAILED` would be wrong.
- [x] Segment coverage emits `DOMESTIC_DISCLOSURE_QUIET` only when DART responded successfully but returned zero items. HTTP failure paths emit the existing `SOURCE_FAILED` code.
- [x] Files affected:
  - `src/investo/briefing/segments.py` (reason code enum + emit logic)
- [x] Anti-regression tests:
  - DART HTTP 200 with empty list → `DOMESTIC_DISCLOSURE_QUIET` reason emitted.
  - DART HTTP 401 → `SOURCE_FAILED` reason emitted (not `DOMESTIC_DISCLOSURE_QUIET`).

### Step 6 — Verification

- [x] Run targeted DART tests + the full quality gate.
- [ ] Manual: with a real `OPENDART_API_KEY` set and a recent date with known disclosures, run a dry-run publish (`INVESTO_DRY_RUN=1`) and confirm the domestic-equity briefing surfaces the disclosure items in the candidate stream.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable.
- **Module boundary**: adapter lives in `sources/`; routes through the existing aggregator → orchestrator path. No cross-module import added.
- **R8 (no raw stdlib XML)**: OpenDART JSON path; `defusedxml` not needed. If a future OpenDART endpoint returns XML, the adapter must use `defusedxml.ElementTree` — pin this in a comment.
- **R10 (record/replay fixtures, no fabrication)**: enforced. Fixtures must be byte-equal to live API responses. **This unit is blocked on a live API session for fixture recording — the implementation cannot land without real fixtures.**
- **R13 (secret hygiene)**: enforced. `OPENDART_API_KEY` enrolled in `SECRET_ENV_VARS`. URL-aware redaction strips `crtfc_key` query parameters from logs / errors / `raw_metadata`. Anti-regression test pinned.
- **R14 (fair-access UA)**: OpenDART has no specific UA requirement; neutral UA is fine. SEC's `User-Agent` policy does not apply here.
- **No paid APIs**: OpenDART API is free with registration. Compliant.
- **Disclaimer enforcement**: untouched.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (expect ~25-35 new tests)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **Real-time disclosure push** — the adapter polls on the existing per-source schedule. Real-time push (websocket / SSE) is not offered by OpenDART and would require a separate fan-in service.
- **Disclosure body text NLP** — only the disclosure title + filing metadata are surfaced. Full body parsing (e.g., extracting buyback amounts, dividend per share) is a future enrichment unit; persona #5 explicitly rated "타이틀과 회사명만으로도 충분히 가치 있다."
- **KOSDAQ fee-paid premium endpoints** — only the free public OpenDART REST endpoints are used.
- **Cross-listing US ADR equivalents** — KOSPI-listed companies' ADR disclosures (NYSE / NASDAQ) flow through SEC EDGAR (already covered by `sec-edgar-8k`); no double-coverage by this adapter.
- **Historical backfill** — adapter only fetches the current pipeline window. Historical disclosure backfill (for archive enrichment) is a separate ops-time script.

---

## Open questions

- **Live API session scheduling**: this unit is **blocked** on a one-time live API session for R10 fixture recording. The user needs to (1) register an OpenDART API key, (2) run a fixture-recording dev script (which must exist or be authored as part of Step 1), (3) commit the resulting `tests/fixtures/sources/dart_disclosure/**` files. Until this happens, implementation cannot land — fabricated fixtures are forbidden by R10.
- **Endpoint stability**: OpenDART has historically maintained backward compatibility on its public REST endpoints. If a future endpoint deprecation occurs, fixtures may need to be re-recorded; the sidecar `.meta.json` `recorded_at` field will surface stale fixtures during code review.
- **Rate-limit posture**: OpenDART's free tier rate limit (10,000 calls / day at time of writing) is an order of magnitude above the daily pipeline's needs. If a future heavy-usage feature emerges, revisit per-day caching.
- **Tier classification**: this plan classifies `dart-disclosure` as `S` tier per the regulator-of-record convention. If u32's tier registry semantics ever shift to a different rubric, update the registry alongside.
