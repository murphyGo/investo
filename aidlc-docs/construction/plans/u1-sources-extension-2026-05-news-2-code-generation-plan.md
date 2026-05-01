# Code Generation Plan: `u1 sources` — Extension #3 2026-05-01 (3 general-news adapters)

**Date**: 2026-05-01
**Unit**: u1 sources (extension #3 — third reopen)
**Stage**: Code Generation (extension run; Extension #2 closed 2026-05-01T05:00:00Z)
**Status**: ✅ CLOSED 2026-05-01T07:00:00Z
**Plan source**:
- `aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md` L6.7 / L6.8 / L6.9 (added 2026-05-01T06:00:00Z)
- `aidlc-docs/construction/u1-sources/functional-design/business-rules.md` (no new R-rule; R7 strict applies; R14 explicitly does NOT apply)
- `aidlc-docs/audit.md` 2026-05-01T06:00:00Z entry (3-adapter bundle scope + per-adapter design notes: utm-strip for The Block, metadata-ns ignore for CNBC, CDATA + `<dc:creator>` for Yonhap)

---

## Unit Context

### Stories partially closed by this extension
- **US-001 매일 시장 데이터를 자동 수집한다** — news category depth grows from 2 adapters → 5 adapters (yahoo-finance-news + sec-edgar-8k from Extension #2; yonhap-market + theblock-crypto + cnbc-top-news from this extension). `Category` enum coverage stays 4/5 (only earnings still TBD); the gain is breadth within news (Korean-language narrative, crypto narrative, US macro/policy narrative).
- **US-008 새 데이터 소스를 단일 모듈 추가로 통합한다** — re-validated for the 3rd extension run. Plugin contract proves stable under three back-to-back PR-shaped adapter-addition cycles in the same calendar day.

### Dependencies
- **Existing u1 code unchanged**: `protocol.py`, `_registry.py`, `_retry.py`, `_sanitize.py`, `_window.py`, `aggregator.py`, `_config.py`, the 6 already-shipped adapters (`yfinance.py`, `coingecko.py`, `fred.py`, `fomc_rss.py`, `yahoo_finance_news.py`, `sec_edgar_8k.py`), `__init__.py` (the last gets a small import-list bump in Step 4).
- **New u1 modules**: `sources/yonhap_market.py`, `sources/theblock_crypto.py`, `sources/cnbc_top_news.py`.
- **New external deps**: **zero** (all three adapters use existing `httpx` / `defusedxml.ElementTree.fromstring` / `_sanitize.strip_html` / `_retry.retry_get` / `email.utils.parsedate_to_datetime`).
- **New secret**: **none** — all three feeds are public RSS, no auth, no compliance UA (R14 does NOT apply for any of the three; SEC remains the only R14-bound adapter).
- **Canonical pattern reference**: FOMC RSS (`fomc_rss.py`, FD §L6.1) — RSS 2.0 + UTF-8 + RFC-822 `<pubDate>` shape, mirrored by all three new adapters.

### Definition of Done
- [ ] 3 new adapters registered: `yonhap-market` (news), `theblock-crypto` (news), `cnbc-top-news` (news)
- [ ] Each adapter has a recorded HTTP fixture under `tests/unit/sources/fixtures/api/<name>/` (real responses; no compliance UA used during recording)
- [ ] R7 strict (no relaxation, no R11 cadence-gap exception) pinned for all three adapters — every `<item>` carries an authoritative `<pubDate>`
- [ ] L6.7 `<dc:creator>` mapping pinned for `yonhap-market` (raw_metadata when present; absence is non-fatal); CDATA-wrapped Korean title/description handled by `strip_html`
- [ ] L6.8 utm-strip behaviour pinned for `theblock-crypto` via dedicated test (`?utm_source=rss&utm_medium=rss` removed from item URLs before NormalizedItem build); `<content:encoded>` ignored, `<description>` used and truncated to 280
- [ ] L6.9 `<metadata:*>` namespace-ignore behaviour pinned for `cnbc-top-news` (no `metadata:*` keys appear in `raw_metadata`); missing `<creator>` is non-fatal
- [ ] `EXPECTED_ADAPTER_COUNT` in `tests/unit/sources/test_plugin_contract.py` bumped 6 → 9; expected name set updated to include all three new slugs
- [ ] DEBT-028 status verified by qa: confirm none of the three news adapters introduces fresh `raw_metadata` numeric serialization paths (all carry strings only). If clean, DEBT-028 stays Medium with age clock continuing; if exposure found, escalate to High.
- [ ] `aidlc-docs/construction/u1-sources/code/summary.md` appended with extension #3 closeout
- [ ] Quality gate green: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest`
- [ ] AIDLC global Build and Test re-runs successfully (the previous green from Extension #2 closeout with 810/810 must still hold; new total expected ≈ 850-870±)

### What this plan does NOT include
- Earnings calendar adapter — still deferred. After Extension #3 closes, `Category` enum coverage stays 4/5; earnings remains the sole gap.
- KOSPI price/index adapter — application design notes "보조: 코스피"; deferred until US briefing content is solid.
- News-side de-duplication / cross-adapter merging (e.g., the same wire story landing in CNBC AND Yonhap with slightly different titles) — out of scope for u1; if it becomes a problem the briefing layer (u2) handles dedup.
- Per-source filtering (e.g., topic restriction on CNBC, ticker restriction on The Block) — out of scope; each feed is consumed whole and R7 is the only filter.
- DEBT-028 fix — not blocking news adapters (string-only fields). The fix lands in a future extension or a dedicated tech-debt sweep.
- Promoting the per-adapter `_strip_tracking_params(url)` helper to a cross-cutting `_sanitize` function — out of scope for this extension. The Block is the only adapter that needs it today; if a second adapter ever needs it, Planner will extract and add a rule.

---

## Steps

### Step 1: `yonhap_market.py` — Yonhap 마켓+ RSS adapter (FD §L6.7)

- [x] **1.1** Recorded HTTP fixture under `tests/unit/sources/fixtures/api/yonhap-market/`:
  - `feed.xml` — real recording: `curl -sS -A "investo-fixture-recorder@example.com" "https://www.yna.co.kr/rss/market.xml" > feed.xml` (no compliance UA required by Yonhap; the recorder UA is purely for fixture-provenance audit and is NOT used by the production adapter)
  - `meta.json` — recording timestamp, source URL, status code (expect 200), content-type (expect `application/rss+xml` or `text/xml`), encoding `utf-8`, byte size, items count (`items_in_recording`), note about RFC-822 `+0900` `<pubDate>` form (KST), note about CDATA-wrapped Korean title/description, note about optional `<dc:creator>` element
- [x] **1.2** `src/investo/sources/yonhap_market.py` — `YonhapMarketAdapter` class with `@register`:
  - `name: ClassVar[str] = "yonhap-market"`, `category: ClassVar[Category] = "news"`
  - `_FEED_URL: Final[str] = "https://www.yna.co.kr/rss/market.xml"`
  - No `_USER_AGENT` constant (no R14 requirement); no env-var override; no per-symbol parameter (single global feed)
  - `async def fetch(self, client, window) -> list[NormalizedItem]`: single `retry_get` call (no headers) → `defusedxml.ElementTree.fromstring(response.content)` (bytes — let parser honour the declared UTF-8) → iterate `<channel>/<item>` → `_to_normalized` → R7 window filter
  - `_to_normalized(item_elem) -> NormalizedItem | None`:
    - extract `<title>` (HTML-strip via `_sanitize.strip_html` — handles CDATA wrappers transparently), `<link>`, `<pubDate>`, `<description>`, `<guid>`, `<dc:creator>` (namespace-aware lookup; optional)
    - drop if any of title / link / pubDate missing
    - validate `<link>` http/https only (AC-7.3)
    - parse `<pubDate>` via `email.utils.parsedate_to_datetime` (handles `+0900` natively); drop if naive (defense)
    - `summary` = HTML-stripped `<description>` truncated to 280 chars (consistent with FOMC RSS pattern); `None` if `<description>` missing
    - `raw_metadata = {"guid": str, "creator": str}` — `creator` key omitted entirely when `<dc:creator>` is absent (do NOT emit empty string; see L6.7 edge case)
  - Module docstring: cite FOMC RSS as canonical pattern reference; note "first Korean-language news adapter; CDATA-wrapped fields handled by `strip_html`; `<dc:creator>` is optional".
- [x] **1.3** `tests/unit/sources/test_yonhap_market.py` — anchor tests via `MockTransport` serving the recorded fixture + inline synthetic XML for edge cases:
  - happy path: real fixture → N items, all fields shape-checked
  - exact-string anchor: title format pin (one real Korean-title item from fixture, exact match — verifies CDATA strip + UTF-8 round-trip)
  - `<link>` validated http/https; non-http(s) `<link>` → entry dropped
  - `<pubDate>` `+0900` form → tz-aware UTC `published_at` (KST → UTC conversion sanity-checked)
  - `<pubDate>` malformed (synthetic) → entry dropped (naive)
  - missing `<title>` / `<link>` / `<pubDate>` → entry dropped
  - missing `<dc:creator>` → entry emitted, `raw_metadata` does NOT contain `creator` key (assert key absent, not assert empty string)
  - present `<dc:creator>` → `raw_metadata["creator"]` populated with the trimmed text
  - empty `<channel>` (no `<item>`) → adapter returns `[]`
  - R7 window filter: target_date crafted so half the fixture items fall in / out of window
  - XML parse error (synthetic malformed) → terminal `SourceFetchError`
  - class identity / `name` / `category` pinned (`category == "news"` explicit)
  - `raw_metadata` keys all string-typed (R8) — DEBT-028 guardrail meta-test
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅, mypy --strict `src/investo/sources/yonhap_market.py` ✅, pytest `tests/unit/sources/test_yonhap_market.py` ✅

**Step 1 acceptance**: `yonhap-market` adapter implementation + tests green; sub-agent code review deferred to Step 4 cross-cutting pass per Extension #1/#2 precedent (single review covering all three new adapters together for consistency).

---

### Step 2: `theblock_crypto.py` — The Block RSS adapter with utm-strip (FD §L6.8)

- [x] **2.1** Recorded HTTP fixture under `tests/unit/sources/fixtures/api/theblock-crypto/`:
  - `feed.xml` — real recording: `curl -sS -A "investo-fixture-recorder@example.com" "https://www.theblock.co/rss.xml" > feed.xml` (recorder UA only; production adapter sends no UA)
  - `meta.json` — recording timestamp, source URL, status code (expect 200), content-type, encoding `utf-8`, byte size, items count, note about RFC-822 `-0400` (US Eastern) `<pubDate>` form, note about `?utm_source=rss&utm_medium=rss` query strings on every `<link>`, note about `<content:encoded>` namespace element being IGNORED by the adapter (we use `<description>` only)
- [x] **2.2** `src/investo/sources/theblock_crypto.py` — `TheBlockCryptoAdapter` class with `@register`:
  - `name: ClassVar[str] = "theblock-crypto"`, `category: ClassVar[Category] = "news"`
  - `_FEED_URL: Final[str] = "https://www.theblock.co/rss.xml"`
  - No `_USER_AGENT`; no env-var override
  - **Adapter-local helper `_strip_tracking_params(url: str) -> str`** (module-private, NOT promoted to `_sanitize`):
    - parse via `urllib.parse.urlparse`; if scheme/netloc empty, return input unchanged (defense)
    - filter query params via `urllib.parse.parse_qsl(keep_blank_values=True)`, removing keys `utm_source`, `utm_medium`, `utm_campaign` (case-sensitive; The Block lowercases all three in practice — document the case rule in helper docstring)
    - rebuild via `urllib.parse.urlencode` + `urllib.parse.urlunparse`; preserve all other query params and the URL fragment
    - return canonical URL
  - `async def fetch(self, client, window) -> list[NormalizedItem]`: single `retry_get` call → `defusedxml.ElementTree.fromstring(response.content)` → iterate `<channel>/<item>` → `_to_normalized` → R7 window filter
  - `_to_normalized(item_elem) -> NormalizedItem | None`:
    - extract `<title>`, `<link>`, `<pubDate>`, `<description>`, `<guid>`
    - **explicitly ignore** `<content:encoded>` (namespaced; we only read unprefixed local names — same approach as L6.9)
    - drop if any of title / link / pubDate missing
    - validate `<link>` http/https
    - **call `_strip_tracking_params(link)` BEFORE building NormalizedItem** — the canonical URL goes into `NormalizedItem.url`; the original tracked URL is NOT stored anywhere (no `raw_metadata.original_url` — out of scope; if future signal needs the tracked URL, FD divergence followed by R-rule)
    - parse `<pubDate>` via `email.utils.parsedate_to_datetime`; drop if naive
    - `summary` = HTML-stripped `<description>` truncated to 280 chars; `None` if missing
    - `raw_metadata = {"guid": str}` (no creator field — The Block doesn't expose one in the feed)
  - Module docstring: cite FOMC RSS as canonical pattern reference; note "first crypto-narrative news adapter; URLs canonicalized to strip `utm_*` tracking params via per-adapter helper; `<content:encoded>` namespace element ignored — `<description>` used".
- [x] **2.3** `tests/unit/sources/test_theblock_crypto.py` — anchor tests via `MockTransport` serving the recorded fixture + inline synthetic XML for edge cases:
  - happy path: real fixture → N items, all fields shape-checked; assert NO emitted item URL contains `utm_source=` or `utm_medium=`
  - **explicit utm-strip test** (synthetic, isolated unit-test of the helper):
    - input: `https://www.theblock.co/x?utm_source=rss&utm_medium=rss&id=1` → output: `https://www.theblock.co/x?id=1`
    - input: `https://www.theblock.co/y?utm_source=rss&utm_medium=rss&utm_campaign=daily` → output: `https://www.theblock.co/y` (all three stripped, empty query)
    - input: `https://www.theblock.co/z?id=1&utm_source=rss` → output: `https://www.theblock.co/z?id=1` (preserves non-utm params)
    - input: `https://www.theblock.co/w?id=1#section` → output: `https://www.theblock.co/w?id=1#section` (no utm; fragment preserved unchanged)
    - input: `https://www.theblock.co/no-query` → output: `https://www.theblock.co/no-query` (no query, no-op)
  - utm-strip integration test: synthetic feed item with utm-tracked link → emitted NormalizedItem.url has utm params removed
  - `<content:encoded>` ignore test: synthetic feed item with both `<description>Short body</description>` and `<content:encoded>Long body</content:encoded>` → `summary` derives from `<description>` (truncated to 280), NOT from `<content:encoded>`
  - `<link>` validated http/https; non-http(s) `<link>` → entry dropped
  - `<pubDate>` `-0400` form → tz-aware UTC `published_at`
  - missing `<title>` / `<link>` / `<pubDate>` → entry dropped
  - empty `<channel>` → returns `[]`
  - R7 window filter: target_date crafted so half the fixture items fall in / out of window
  - XML parse error → terminal `SourceFetchError`
  - class identity / `name` / `category` pinned
  - `raw_metadata` keys all string-typed (R8) — DEBT-028 guardrail meta-test
- [x] **2.4** Quality gate: ruff ✅, ruff format ✅, mypy --strict `src/investo/sources/theblock_crypto.py` ✅, pytest `tests/unit/sources/test_theblock_crypto.py` ✅

**Step 2 acceptance**: `theblock-crypto` adapter + utm-strip helper + tests green; utm-strip behaviour explicitly pinned at the unit level (not just the integration level); sub-agent code review deferred to Step 4.

---

### Step 3: `cnbc_top_news.py` — CNBC US Top News RSS adapter (FD §L6.9)

- [x] **3.1** Recorded HTTP fixture under `tests/unit/sources/fixtures/api/cnbc-top-news/`:
  - `feed.xml` — real recording: `curl -sS -A "investo-fixture-recorder@example.com" "https://www.cnbc.com/id/100003114/device/rss/rss.html" > feed.xml`
  - `meta.json` — recording timestamp, source URL, status code (expect 200), content-type, encoding `utf-8`, byte size, items count, note about RFC-822 `GMT` `<pubDate>` form, note about declared `xmlns:media` and `xmlns:cn` (or `xmlns:metadata`) namespaces at the `<rss>` root, note about CNBC feed having NO `<creator>` / `<dc:creator>` element (missing-creator case is the norm, not the exception)
- [x] **3.2** `src/investo/sources/cnbc_top_news.py` — `CnbcTopNewsAdapter` class with `@register`:
  - `name: ClassVar[str] = "cnbc-top-news"`, `category: ClassVar[Category] = "news"`
  - `_FEED_URL: Final[str] = "https://www.cnbc.com/id/100003114/device/rss/rss.html"`
  - No `_USER_AGENT`; no env-var override
  - `async def fetch(self, client, window) -> list[NormalizedItem]`: single `retry_get` call → `defusedxml.ElementTree.fromstring(response.content)` → iterate `<channel>/<item>` → `_to_normalized` → R7 window filter
  - `_to_normalized(item_elem) -> NormalizedItem | None`:
    - extract `<title>`, `<link>`, `<pubDate>`, `<description>`, `<guid>` ONLY
    - **explicitly ignore all namespaced child elements**: `<media:*>`, `<cn:*>`, `<metadata:*>` (any element name containing `:` or any qualified name with a registered namespace prefix at parse time). Use `entry.findtext("title")` etc. — unprefixed local names — so any namespace-prefixed sibling is naturally not matched. **Do NOT add namespace-prefixed keys to `raw_metadata`** (this is the `metadata:*` ignore guarantee).
    - **Do NOT use string-substitution namespace stripping** (same anti-pattern guard as L6.6 / L6.9).
    - drop if any of title / link / pubDate missing
    - validate `<link>` http/https
    - parse `<pubDate>` via `email.utils.parsedate_to_datetime` (handles `GMT` natively); drop if naive
    - `summary` = HTML-stripped `<description>` truncated to 280; `None` if missing
    - `raw_metadata = {"guid": str}` — no `creator` key ever (CNBC feed has none; document this as the spec-correct behaviour, not a bug)
  - Module docstring: cite FOMC RSS as canonical pattern reference; note "CNBC US Top News; namespace-prefixed elements (`media:*`, `cn:*`, `metadata:*`) are explicitly ignored; the feed has no `<dc:creator>` element so `raw_metadata` carries `guid` only".
- [x] **3.3** `tests/unit/sources/test_cnbc_top_news.py` — anchor tests via `MockTransport` serving the recorded fixture + inline synthetic XML for edge cases:
  - happy path: real fixture → N items, all fields shape-checked
  - **`metadata:*` ignore test**: synthetic feed item with `<metadata:foo>bar</metadata:foo>` and `<media:thumbnail url="..."/>` siblings → emitted NormalizedItem.raw_metadata contains ONLY `{"guid": "..."}` — assert NO key starts with `metadata:` / `media:` / `cn:` / contains a colon
  - missing `<creator>` is the norm (real fixture exercise) — NormalizedItem emitted; `raw_metadata` has no `creator` key (consistent with Yonhap's missing-creator handling, but here it's the always-case)
  - `<link>` validated http/https; non-http(s) `<link>` → entry dropped
  - `<pubDate>` `GMT` form → tz-aware UTC `published_at`
  - missing `<title>` / `<link>` / `<pubDate>` → entry dropped
  - empty `<channel>` → returns `[]`
  - R7 window filter: target_date crafted so half the fixture items fall in / out of window
  - XML parse error → terminal `SourceFetchError`
  - class identity / `name` / `category` pinned
  - `raw_metadata` keys all string-typed (R8) — DEBT-028 guardrail meta-test
- [x] **3.4** Quality gate: ruff ✅, ruff format ✅, mypy --strict `src/investo/sources/cnbc_top_news.py` ✅, pytest `tests/unit/sources/test_cnbc_top_news.py` ✅

**Step 3 acceptance**: `cnbc-top-news` adapter + tests green; namespace-ignore behaviour explicitly pinned; sub-agent code review deferred to Step 4.

---

### Step 4: Registration + plugin contract bump 6→9 + cross-cutting QA + closeout

- [x] **4.1** `src/investo/sources/__init__.py` — add 3 imports (`from . import (cnbc_top_news, coingecko, fomc_rss, fred, sec_edgar_8k, theblock_crypto, yahoo_finance_news, yfinance, yonhap_market)` — alpha-sorted, ruff will normalise; star-import contract list extended with the 3 new module names + 3 new adapter classes).
- [x] **4.2** `tests/unit/sources/test_plugin_contract.py` — bump `EXPECTED_ADAPTER_COUNT` 6 → 9; expected name set extended to `{"fomc-rss", "yfinance-price", "coingecko-price", "fred-macro", "yahoo-finance-news", "sec-edgar-8k", "yonhap-market", "theblock-crypto", "cnbc-top-news"}`; autouse fixture re-registers all 9 productively-known adapters (3 new imports + 3 new `register()` calls); `leaked` set in star-import test extended with the 6 new symbols (3 modules `cnbc_top_news` / `theblock_crypto` / `yonhap_market` + 3 classes `CnbcTopNewsAdapter` / `TheBlockCryptoAdapter` / `YonhapMarketAdapter`). 7/7 plugin-contract tests green (test count unchanged; expected values updated).
- [x] **4.3** Run full quality gate at the project level:
  - `ruff check .` ✅
  - `ruff format --check .` ✅ (~125 files; was 121 at Extension #2 close)
  - `mypy --strict src/` ✅ (46 source files expected — was 43 + the 3 new adapters)
  - `pytest` ✅ (810 + Step 1 + Step 2 + Step 3 tests; expect ~870±)
  - `mkdocs build --strict` ✅ (no docs change in this extension)
- [x] **4.4** Cross-cutting QA review (single sub-agent dispatch covering all 5 news adapters end-to-end — yahoo-finance-news + sec-edgar-8k + yonhap-market + theblock-crypto + cnbc-top-news). Review focus:
  - **DEBT-028 reconfirm**: meta-tests across all 5 news adapters confirm `raw_metadata` carries strings only (no float / int paths). If clean, DEBT-028 stays Medium with age clock continuing; if exposure found, escalate to High in the closeout.
  - **The Block utm-strip behaviour**: helper unit tests pin all 4 input shapes (utm-only, mixed, fragment-preserving, no-op); integration test confirms emitted URLs are canonical
  - **Yonhap CDATA stripping**: real-fixture title round-trip preserves Korean characters; HTML tags inside CDATA are stripped by `strip_html`
  - **CNBC `metadata:*` namespace-ignore**: synthetic test confirms no namespace-prefixed key leaks into `raw_metadata`; `media:*` and `cn:*` similarly ignored
  - **Cross-cutting consistency check** against the 6 existing adapters (fomc_rss / yfinance / coingecko / fred / yahoo_finance_news / sec_edgar_8k): naming, class shape, `_FEED_URL` constant style, error-classification contract, `_to_normalized` method shape, fixture-recording convention, R7 window-filter semantics
  - **R13 / R14 audit**: zero secret material in any of the 3 new adapters; zero compliance-UA usage (R14 still applies only to sec-edgar-8k); zero credentials in fixture files
  - **No `raw_metadata.original_url` regression**: confirm The Block does NOT store the pre-canonicalization URL (per FD §L6.8 / DoD)
- [x] **4.5** Apply review findings: any Critical/High → fix before proceeding; Medium → fix-or-debt-or-skip per skill protocol; Low → cosmetic fix in-place where cheap.
- [x] **4.6** Closeout artifacts:
  - Append `## Construction — u1 sources — Extension #3 CLOSED (3 general-news adapters delivered)` entry to TOP of `aidlc-docs/audit.md` mirroring the Extension #2 closeout shape (Timestamp / Trigger / Decision / Affected docs / Status / Context).
  - Update `aidlc-docs/aidlc-state.md` u1 row: replace "Extension #3 in progress" with "Extension #3 closed"; bump test counts; note "5 news adapters total (yahoo-finance-news + sec-edgar-8k + yonhap-market + theblock-crypto + cnbc-top-news); Category enum still 4/5 (only earnings TBD)". Global Build and Test row re-verified (fourth re-verification — base 2026-05-01, post-Ext-#1, post-Ext-#2, post-Ext-#3).
  - Append `## Extension #3 closeout (2026-05-01)` section to `aidlc-docs/construction/u1-sources/code/summary.md` mirroring the Extension #2 closeout structure (deliverables table; new test inventory delta; news-depth count 2 → 5; FD §L6.7/§L6.8/§L6.9 newly-pinned algorithms; The Block utm-strip helper note; CNBC namespace-ignore note; Yonhap CDATA + `<dc:creator>` note; cross-cutting review summary; DEBT-028 status post-verification; final quality gate pin).

**Step 4 acceptance**: u1 sources Extension #3 CLOSED. Unit becomes eligible for `/cross-check` re-run. Plan CLOSED.

---

## Step Dependency Graph

```
1 yonhap-market      (independent — depends only on existing _retry / _sanitize / models; FD §L6.7)
2 theblock-crypto    (independent — adds adapter-local _strip_tracking_params; FD §L6.8)
3 cnbc-top-news      (independent — adds namespace-ignore handling; FD §L6.9)
   ├─ Steps 1, 2, 3 are independent — could run in parallel,
   │  but per `dev-investo` "one step per execution" rule they
   │  run sequentially. Recommended order: 1 → 3 → 2 (Yonhap is
   │  the simplest FOMC-RSS-clone surface and re-validates the
   │  existing pattern; CNBC adds the namespace-ignore concern
   │  as a small delta on top; The Block goes last because the
   │  utm-strip helper is the only genuinely new code in this
   │  extension and benefits from going last when the test
   │  scaffolding from steps 1/3 is fresh in the developer's
   │  mind. Alphabetical order (cnbc → theblock → yonhap) is an
   │  acceptable alternative; complexity order is preferred.)
   ▼
4 registration / contract bump 6→9 + cross-cutting QA + closeout   (depends on 1, 2, 3)
```

---

## Estimated Scope

- 4 plan steps, each yielding ~1 commit
- 3 new source modules (`yonhap_market`, `theblock_crypto`, `cnbc_top_news`); ~120 LOC source per module (~360 LOC total — slightly larger than Extension #1's per-module average due to The Block's utm-strip helper + CNBC's explicit namespace-ignore comments)
- ~30-50 new tests (~10-17 per adapter; The Block has the most due to the 5-input utm-strip unit tests + the integration test)
- 3 new fixture directories with `feed.xml` + `meta.json` each
- Solo dev: ~2-3 hours
- Zero new external deps

---

## NFR AC Coverage Map (extension #3 delta)

| AC / Rule | Pinned at step |
|-----------|----------------|
| (no new ACs) | n/a |
| R7 strict (no relaxation) for all three news adapters | 1 / 2 / 3 |
| R8 raw_metadata string-cast (DEBT-028 guardrail) | 1.3 / 2.3 / 3.3 (meta-tests) |
| R13 secret hygiene (zero secret material) | 4.4 (cross-cutting audit) |
| R14 source-mandated compliance header — explicitly does NOT apply to any of the three; sec-edgar-8k remains the only R14-bound adapter | 4.4 (audit confirms) |
| AC-2.2 (no paid APIs) | 1 / 2 / 3 (all three feeds public, no auth) |
| AC-7.2 sanitize (HTML strip) — every news adapter calls `strip_html` | 1.2 / 2.2 / 3.2 |
| AC-7.3 (http/https URL validation) | 1.3 / 2.3 / 3.3 |
| AC-7.4 (tz-aware `published_at`) | 1.3 / 2.3 / 3.3 |
| AC-7.6 (defusedxml only — XML adapters; existing grep test catches violations) | reused; 4.3 quality gate confirms grep test still green |
| AC-5.2 (EXPECTED_ADAPTER_COUNT 6→9) | 4.2 |
| AC-5.3 (duplicate-name detection re-validated) | 4.2 (autouse fixture re-runs across 9 adapters) |
| L6.7 `<dc:creator>` optional + CDATA Korean-title behaviour | 1.3 |
| L6.8 utm-strip URL canonicalization + `<content:encoded>` ignored | 2.3 |
| L6.9 `<metadata:*>` namespace-ignore + missing-creator-as-norm | 3.3 |

No new NFR ACs are added in this extension. All AC additions happened in Extension #1 (AC-3.6 / AC-5.5). Extension #2 added R14 to business-rules; Extension #3 adds zero new R-rules.

---

## How to Approve

This plan is the single source of truth for the u1 Extension #3 Code Generation. Reply **approve** to begin Step 1; **changes [N]** to revise step N before approval.
