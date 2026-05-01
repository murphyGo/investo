# Code Generation Plan: `u1 sources` — Extension 2026-05-01 (3 new adapters)

**Date**: 2026-05-01
**Unit**: u1 sources (extension)
**Stage**: Code Generation (extension run; the original 10/10 plan closed 2026-04-29)
**Plan source**:
- `aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md` L6.2 / L6.3 / L6.4 (added 2026-05-01)
- `aidlc-docs/construction/u1-sources/functional-design/business-rules.md` R11 / R12 / R13 (added 2026-05-01)
- `aidlc-docs/construction/u1-sources/nfr-requirements/nfr-requirements.md` AC-3.6 / AC-5.5 (added 2026-05-01); AC-7.6 scope clarified
- `aidlc-docs/construction/u1-sources/nfr-requirements/tech-stack-decisions.md` TS-8 / TS-9 / TS-10 (added 2026-05-01)
- `aidlc-docs/audit.md` 2026-05-01 entry (Q1-Q5 design decisions)

---

## Unit Context

### Stories partially closed by this extension
- **US-001 매일 시장 데이터를 자동 수집한다** — covers price/주가, price/crypto, macro categories. News + earnings categories deferred to a later extension.
- **US-008 새 데이터 소스를 단일 모듈 추가로 통합한다** — re-validated via 3 fresh PR-shaped adapter additions. Plugin contract proves stable under non-PoC scrutiny.

### Dependencies
- **Existing u1 code unchanged**: `protocol.py`, `_registry.py`, `_retry.py`, `_sanitize.py`, `_window.py`, `aggregator.py`, `__init__.py` (the last gets a small import-list bump in Step 5).
- **New u1 modules**: `sources/_config.py`, `sources/yfinance.py`, `sources/coingecko.py`, `sources/fred.py`.
- **New external deps**: **zero** (per TS-10 / cumulative dependency delta).
- **New secret**: `FRED_API_KEY` — must be added to GitHub repo Secrets at Operations time; CI workflow file will reference it in Step 5.

### Definition of Done
- [ ] 3 new adapters registered: `yfinance-price` (price), `coingecko-price` (price), `fred-macro` (macro)
- [ ] Each adapter has a recorded HTTP fixture under `tests/unit/sources/fixtures/api/<name>/`
- [ ] AC-3.6 (missing FRED key → `SourceFetchError(transient=False)`) pinned
- [ ] AC-5.5 (env-var override per-adapter) pinned for all 3 adapters
- [ ] R11 (price `published_at` = market close UTC, DST-aware) pinned with both EDT and EST anchor cases
- [ ] R12 (env-var override convention) pinned via shared `_config.py` test
- [ ] R13 (secret handling) pinned via FRED test
- [ ] `EXPECTED_ADAPTER_COUNT` in `tests/unit/sources/test_plugin_contract.py` bumped 1 → 4; expected name set updated
- [ ] `.github/workflows/daily-briefing.yml` injects `FRED_API_KEY` env from `secrets.FRED_API_KEY`
- [ ] `CONTRIBUTING.md` documents env-var override + secret-using-adapter procedure
- [ ] `aidlc-docs/construction/u1-sources/code/summary.md` appended with extension closeout
- [ ] Quality gate green: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest`
- [ ] AIDLC global Build and Test re-runs successfully (the previous green from 2026-05-01 must still hold)

### What this plan does NOT include
- News adapter (NewsAPI / SEC EDGAR / etc.) — deferred. FR-001 AC for news category remains unmet after this extension; tracked as a follow-up.
- Earnings calendar adapter — deferred similarly.
- Real-time / intraday data — out of scope for daily briefing.
- KOSPI adapter — application design notes "보조: 코스피"; deferred until US briefing content is solid.

---

## Steps

### Step 1: `_config.py` — env-var symbol parser (R12 helper) ✅

- [x] **1.1** `src/investo/sources/_config.py` — single function `parse_symbol_list(env_var_name: str, defaults: tuple[str, ...]) -> tuple[str, ...]`. Implementation uses a generator-with-walrus inside `tuple(...)` to split-strip-filter in one pass: `tuple(stripped for token in raw.split(",") if (stripped := token.strip()))`. Returns `defaults` on empty result. ~5 LOC, no `Final` needed (functional, not module-level state).
- [x] **1.2** `tests/unit/sources/test_config.py` — **10** anchor tests (planned 9; added one extra for `",,,"` since it's the most likely real-world bug source). All 9 planned cases plus a defaults-not-mutated assertion that also pins fresh-tuple-return identity (`result is not _DEFAULTS`).
- [x] **1.3** Quality gate green: `ruff check` ✅, `ruff format --check` ✅ (auto-applied; the inline walrus generator was reformatted onto one line), `mypy --strict src/investo/sources/_config.py` ✅, `pytest tests/unit/sources/test_config.py -v` ✅ **10/10**, full suite `pytest` ✅ **730/730** (was 720 before this step).

**Step 1 acceptance**: ✅ `parse_symbol_list` importable; 10 tests green; gate clean; full-suite regression-free. Adapter steps depend on this module — ready for Step 2.

---

### Step 2: `yfinance.py` — Yahoo Finance v8 chart adapter (Q1=B, Q2=A, Q3=A; FD L6.2) — implementation + tests ✅; sub-agent review pending

- [x] **2.1** Recorded HTTP fixtures under `tests/unit/sources/fixtures/api/yfinance-price/`:
  - `GSPC.json` (1.6 KB) — real Yahoo response for `^GSPC` (URL-encoded as `%5EGSPC`)
  - `AAPL.json` (1.6 KB) — real Yahoo response for AAPL
  - `INVALID.json` — synthetic, Yahoo's documented not-found error shape
  - `meta.json` describing each (status / size / source-url-template / note)
- [x] **2.2** `src/investo/sources/yfinance.py` (~260 LOC) — `YFinancePriceAdapter` class with `@register`:
  - `name: ClassVar[str] = "yfinance-price"`, `category: ClassVar[Category] = "price"`
  - `_DEFAULT_TICKERS: Final[tuple[str, ...]] = ("^GSPC", "^IXIC", "^DJI", "^VIX", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA")`
  - `_FEED_URL_TEMPLATE = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"`
  - `async def fetch(self, client, window)`: read tickers via `parse_symbol_list("INVESTO_YFINANCE_TICKERS", self._DEFAULT_TICKERS)`; per-ticker `asyncio.gather(*[self._fetch_one(client, ticker, window) for ticker in tickers], return_exceptions=True)`; loop results: `NormalizedItem` → keep, `Exception` → log DEBUG and skip (per-ticker isolation), `None` → skip.
  - `async def _fetch_one(self, client, ticker, window) -> NormalizedItem | None`: call `retry_get`; parse JSON; pick latest valid `(timestamp, open, high, low, close, volume)` from the response (drop entries with any-null OHLC); compute `pct = (close - prev_close) / prev_close * 100`; build `NormalizedItem` per L6.2 mapping; filter via `window.contains(published_at)`; return None if outside window.
  - Helper `_resolve_close_timestamp(date_local) -> datetime` — given a NY-local date, returns 16:00 ET on that date as a UTC tz-aware datetime via `zoneinfo("America/New_York")` (R11 DST handling).
- [x] **2.3** `tests/unit/sources/test_yfinance.py` — **13 anchor tests** all green using `MockTransport` to serve the recorded fixtures + inline synthetic JSON for null-OHLC / DST / env-override / isolation cases. **Side-update during 2.3**: FD L6.2 + business-rules R11 patched to document R7 window relaxation (the original L6.2 wording would have produced empty yfinance output on KST Monday/Saturday cron fires due to the US weekend gap).
  - happy path: 2 tickers (`^GSPC` + `AAPL`) → 2 items with correct title/summary/url shape
  - empty window (target_date older than fixture's data) → `[]`
  - per-ticker isolation: 1 valid + 1 returning HTTP 404 → adapter returns 1 item, no raise
  - missing `previousClose` → item still emitted, `pct` defaults to 0.0
  - all-null OHLCV day → fall through to prior valid day in the 5-day range
  - Yahoo error-shape (`chart.error` non-null) → that ticker dropped, no raise
  - **R11 DST anchor tests**:
    - July (EDT): close timestamp `published_at` = `UTC 20:00` for NY 16:00 close (assert exact UTC datetime)
    - January (EST): close timestamp `published_at` = `UTC 21:00` for NY 16:00 close
    - DST transition Sunday (e.g., 2026-03-08): adapter does NOT crash on the spring-forward day (defensive — Yahoo doesn't trade on Sunday but the timestamp resolver should not throw)
  - **R12 env override**: `INVESTO_YFINANCE_TICKERS="META,GOOGL"` → adapter fetches exactly those 2; default unaffected
  - title format anchor: `"^GSPC 5,234.18 (+0.42%)"` exact-string match
  - summary format anchor: `"O:5,210.40 H:5,240.00 L:5,198.20 C:5,234.18 V:3,114,205,500"` exact-string match
  - `raw_metadata` keys all present and all string-typed (R8)
- [ ] **2.4** Sub-agent code review (general-purpose, per `dev-investo` Step 5.1) covering: correctness (per-ticker isolation actually isolates; null-handling in nested arrays; DST resolver edge cases), safety (no key/secret leakage — yfinance has none, but pin the assertion), maintainability (no logic duplicated from `_retry` or `_sanitize`). **Pending — see "How to proceed" below.**
- [x] **2.5** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (39 src files), pytest ✅ **743/743** (was 730 before this step, +13 new yfinance tests). No regressions in any other unit's test suite.

**Step 2 acceptance**: `yfinance-price` adapter registered; tests green; sub-agent review APPROVE / APPROVE_WITH_NOTES (any Critical/High → fix before proceeding; Medium → propose fix/plan/skip per skill protocol).

---

### Step 3: `coingecko.py` — CoinGecko Public API adapter (FD L6.3) — implementation + tests ✅; sub-agent review deferred to Step 5.7

- [x] **3.1** Recorded HTTP fixture: `tests/unit/sources/fixtures/api/coingecko-price/markets.json` (2.6 KB) — real CoinGecko response for 3 default coins, full markets shape (`last_updated` / `market_cap` / `total_volume` / `high_24h` / `low_24h` / `price_change_percentage_24h`). The null-pct edge case is covered by a synthetic JSON in tests rather than recorded fixture (CoinGecko didn't return null for our default coins on the recording day, but the production behavior is documented).
- [x] **3.2** `src/investo/sources/coingecko.py` (~165 LOC) — `CoinGeckoPriceAdapter`:
  - `name = "coingecko-price"`, `category = "price"`
  - `_DEFAULT_COINS = ("bitcoin", "ethereum", "solana")`
  - `_FEED_URL = "https://api.coingecko.com/api/v3/coins/markets"` with query params `vs_currency=usd`, `ids=<comma-joined>`, `price_change_percentage=24h`
  - `async def fetch(self, client, window)`: read coins via `parse_symbol_list("INVESTO_COINGECKO_COINS", self._DEFAULT_COINS)`; single `retry_get` call (NOT per-coin); parse JSON array; one `NormalizedItem` per response entry; filter by `window.contains(published_at)`; per-entry `ValidationError` → drop and continue (sibling-coin isolation within the single response).
  - `_parse_last_updated(raw_str) -> datetime`: ISO8601 → tz-aware UTC; raise on naive (per R8).
- [x] **3.3** `tests/unit/sources/test_coingecko.py` — **15 anchor tests** all green covering: 3 coins happy path with real fixture; exact title-format pin (`"BTC $76,105.00 (+0.33%)"`, `"ETH $2,253.73 (-0.90%)"`); summary format pin (high/low values from real fixture); URL uses coin_id (not symbol); 8 raw_metadata keys + R8 string-cast; null pct fallback to 0.0; naive last_updated dropped (sibling continues); empty array → terminal SourceFetchError(transient=False); non-list response → terminal; outside R7 window dropped (strict R7 enforced for crypto since 24/7 source); published_at exact-equals construct from ISO8601 with Z + millisecond precision; env override → query-string `ids` parameter pinned via httpx request capture; env unset → defaults pinned; env empty → defaults pinned; class identity. Rate-limit 429 path is already covered by `test_retry.py` (shared `retry_get` helper); not duplicated here.
- [ ] **3.4** Sub-agent code review — deferred to Step 5.7 cross-cutting review per user direction (3 adapters reviewed together for consistency).
- [x] **3.5** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (40 src files), pytest ✅ **758/758** (was 743 before this step, +15 new coingecko tests).

**Step 3 acceptance**: `coingecko-price` adapter registered; tests green; review pass.

---

### Step 4: `fred.py` — FRED API adapter (Q5; FD L6.4; R13 secret handling) — implementation + tests ✅; sub-agent review deferred to Step 5.7

- [x] **4.1** Synthetic fixtures (FRED requires an API key not provisioned during fixture recording — `meta.json` documents the rationale):
  - `CPIAUCSL.json` — monthly CPI happy path, 2 valid observations, delta computable
  - `UNRATE.json` — monthly unemployment with `"."` placeholder as latest (real FRED behaviour)
  - `DFF.json` — daily Federal Funds Rate, 2 consecutive business days
  - `meta.json` — fixtures-are-synthetic flag, source-url-template
- [x] **4.2** `src/investo/sources/fred.py` (~265 LOC) — `FredMacroAdapter`:
  - `name = "fred-macro"`, `category = "macro"`
  - `_DEFAULT_SERIES = ("CPIAUCSL", "UNRATE", "DFF", "DGS10", "DEXKOUS")`
  - `_FEED_URL_TEMPLATE = "https://api.stlouisfed.org/fred/series/observations"` with query params `series_id`, `api_key`, `file_type=json`, `sort_order=desc`, `limit=2`
  - `async def fetch(self, client, window)`:
    1. `api_key = os.environ.get("FRED_API_KEY", "")`
    2. if not `api_key`: raise `SourceFetchError(self.name, cause=None, transient=False)` with message per R13
    3. read series via `parse_symbol_list("INVESTO_FRED_SERIES", self._DEFAULT_SERIES)`
    4. per-series `asyncio.gather` (same pattern as yfinance Step 2)
    5. each entry: pick most-recent non-`"."` observation in the response; build `NormalizedItem` per L6.4 mapping; `published_at` = release date at NY midnight ET → UTC; widened-window filter (35-day lookback) per L6.4 divergence note
  - `_resolve_release_timestamp(date_str)` — parse `YYYY-MM-DD` as NY-local midnight via `zoneinfo`; return tz-aware UTC datetime
- [x] **4.3** `tests/unit/sources/test_fred.py` — **17 anchor tests** all green covering:
  - **AC-3.6 / R13**: missing `FRED_API_KEY` → `SourceFetchError(transient=False)`, `cause is None`, message contains `"FRED_API_KEY"` + `"fred-macro"`; empty-string key → same; defense-in-depth: missing key triggers raise BEFORE any HTTP request fires (pinned via captured-requests list)
  - **Secret hygiene** (R13): sentinel `_SENTINEL_KEY = "REDACTED_KEY_VALUE_12345_DO_NOT_LEAK"` value asserted absent from `raw_metadata`; key sent in URL params (FRED requires it) but absent from terminal-error string + repr (test bypasses adapter's silent gather to inspect `_fetch_one` directly)
  - **L6.4 algorithm**: CPI happy path with exact title/summary/raw_metadata pinning + UTC tz-aware DST-correct `published_at` (`2026-04-01 04:00 UTC` for NY midnight EDT); UNRATE `"."` placeholder fall-through to prior observation; DFF daily-series happy path with delta=0; 3 series concurrent fetch
  - **Per-series isolation**: 1 valid + 1 404 → 1 item emitted, no raise; all-`"."`-placeholders series → empty result, no raise
  - **Widened window (65d lookback)**: 60-day-old observation outside lookback → dropped; 30-day-old observation at boundary → included
  - **R12 env override**: comma-separated env var → exactly those series in URL params; env unset → 5 default series attempted; class identity
  - **Side-update during 4.3**: bumped lookback constant 35d→65d (and updated FD L6.4) after discovering monthly-indicator `"."`-fall-through case puts prior release at ~60d before target. Tests + spec realigned in lockstep.
- [ ] **4.4** Sub-agent code review with secret-hygiene focus — deferred to Step 5.7 cross-cutting review per user direction.
- [x] **4.5** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (41 src files), pytest ✅ **775/775** (was 758 before this step, +17 new fred tests).

**Step 4 acceptance**: `fred-macro` adapter registered; tests green; secret-hygiene review pass.

---

### Step 5: `__init__.py` discovery + plugin contract bump + workflow secret + CONTRIBUTING + closeout ✅

- [x] **5.1** `src/investo/sources/__init__.py` — added 4 imports (alpha-sorted by ruff into a tuple-form `from . import (coingecko, fomc_rss, fred, yfinance)`).
- [x] **5.2** `tests/unit/sources/test_plugin_contract.py` — bumped `EXPECTED_ADAPTER_COUNT` 1→4; expected name set `{"fomc-rss", "yfinance-price", "coingecko-price", "fred-macro"}`; autouse fixture re-registers all 4 productively-known adapters; `leaked` set in star-import test extended with new adapter names. 7/7 plugin-contract tests green.
- [x] **5.3** `.github/workflows/daily-briefing.yml` — `FRED_API_KEY` injected from `secrets.FRED_API_KEY` into the `python -m investo` env. Header comment block updated to "5 required + 1 optional". Per R13: absent secret → `fred-macro` raises `SourceFetchError(transient=False)`; aggregator R6 catches; other adapters unaffected.
- [x] **5.4** `CONTRIBUTING.md` — added two new subsections under "Adding a new data source":
  - **Configurable symbol/coin/series lists (R12)** — env-var convention, shared `parse_symbol_list` helper, defaults-as-ClassVar
  - **Adapters that need an authentication secret (R13)** — fetch-time read, missing-secret pattern, secret-hygiene rules, daily-briefing.yml update reminder
  - Operator runbook updated with new "GitHub Secrets (optional — per-adapter)" section listing `FRED_API_KEY`
- [x] **5.5** `aidlc-docs/construction/u1-sources/code/summary.md` — appended "Extension closeout (2026-05-01)" with: deliverables table; +55 test inventory delta; AC-3.6 + AC-5.5 + AC-7.6 scope clarification; 3 ratified FD divergences (L6.2 R7 relaxation, L6.4 35d→65d, L6.4 title 2dp→4dp); cross-cutting review summary; DEBT-028 registration note; final quality gate pin.
- [x] **5.6** Final quality gate (after Step 5.7 fixes applied):
  - `ruff check .` ✅ (one auto-fixed import-order issue in `__init__.py` from the manual 4-line add)
  - `ruff format --check .` ✅ (114 files)
  - `mypy --strict src/` ✅ (41 source files; was 38)
  - `pytest` ✅ **775/775** (was 720 at extension start; +55 new tests)
  - `mkdocs build --strict` ✅ (still clean — no docs change in extension)
- [x] **5.7** Cross-cutting sub-agent code review covering yfinance/coingecko/fred + `_config` together. Result: **APPROVE_WITH_NOTES**. 0 Critical / 0 High requiring code change / 2 Medium (M1 raw_metadata precision drift; M2 spec example precision drift) / 3 Low (cosmetic). Applied immediately:
  - **H1** (3 stale "35 days" comments in `fred.py` after the 35d→65d bump) — fixed
  - **L3** (`fred.py` module docstring mischaracterized per-series 401 behaviour) — fixed
  - **M2** (FD L6.4 title delta example showed 2dp but code/tests pin 4dp) — FD example updated
  - **M1** (cross-adapter `raw_metadata` precision inconsistency) — registered as **DEBT-028 (Medium)**; address before next adapter lands

**Step 5 acceptance**: ✅ `aidlc-state.md` u1 row updated to extension-complete; the global Build and Test row marked re-verified; ready for `/cross-check` re-run on u1. Plan CLOSED.

---

## Step Dependency Graph

```
1 _config (R12 helper)
  ├── 2 yfinance     (depends on 1, FD L6.2, R11)
  ├── 3 coingecko    (depends on 1, FD L6.3)
  ├── 4 fred         (depends on 1, FD L6.4, R13)
  └── 5 closeout     (depends on 1, 2, 3, 4)
```

Steps 2 / 3 / 4 are independent and could in principle run in parallel — but per `dev-investo` rule "one step per execution" they run sequentially in this plan. Recommended order: 1 → 2 → 3 → 4 → 5 (yfinance first because R11 / DST handling is the trickiest piece; CoinGecko is the simplest; FRED has the most novel surface — secret handling — so it benefits from going last when the helpers are stable).

---

## Estimated Scope

- 5 plan steps, each yielding ~1 commit
- 4 new source modules (`_config`, `yfinance`, `coingecko`, `fred`); ~600 LOC source
- ~50-70 new tests (config helper + 3 adapters + plugin contract bump)
- Solo dev: ~1 day
- Zero new external deps

---

## NFR AC Coverage Map (extension delta)

| AC | Pinned at step |
|----|----------------|
| AC-3.6 (missing secret → graceful degradation) | 4 |
| AC-5.5 (env-var override convention) | 1 (helper) + 2/3/4 (per-adapter) |
| R11 (price published_at = market close UTC, DST-aware) | 2 |
| R12 (env-var override convention) | 1 |
| R13 (secret handling) | 4 |
| AC-5.2 (EXPECTED_ADAPTER_COUNT 1→4) | 5 |
| AC-7.6 scope (XML adapters only — JSON adapters out of scope) | 5 (re-verify the existing test still passes; no change needed because the grep is pattern-based, not adapter-list-based) |

---

## How to Approve

This plan is the single source of truth for the u1 extension Code Generation. Reply **approve** to begin Step 1; **changes [N]** to revise step N before approval.
