# Code Generation Plan: `u1 sources` — Extension #2 2026-05-01 (2 news adapters)

**Date**: 2026-05-01
**Unit**: u1 sources (extension #2 — second reopen)
**Stage**: Code Generation (extension run; Extension #1 closed 2026-05-01T03:00:00Z)
**Plan source**:
- `aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md` L6.5 / L6.6 (added 2026-05-01T04:00:00Z)
- `aidlc-docs/construction/u1-sources/functional-design/business-rules.md` R14 (added 2026-05-01T04:00:00Z)
- `aidlc-docs/audit.md` 2026-05-01T04:00:00Z entry (Q1-Q4 design decisions + lead's User-Agent placement judgment + R14 add rationale)

---

## Unit Context

### Stories partially closed by this extension
- **US-001 매일 시장 데이터를 자동 수집한다** — covers news category for the first time. After this extension `Category` enum coverage is 4/5 (calendar / price / macro / **news**); only earnings still deferred.
- **US-008 새 데이터 소스를 단일 모듈 추가로 통합한다** — re-validated for the 2nd extension run. Plugin contract proves stable under repeated PR-shaped adapter additions.

### Dependencies
- **Existing u1 code unchanged**: `protocol.py`, `_registry.py`, `_retry.py`, `_sanitize.py`, `_window.py`, `aggregator.py`, `_config.py`, `yfinance.py`, `coingecko.py`, `fred.py`, `fomc_rss.py`, `__init__.py` (the last gets a small import-list bump in Step 3).
- **New u1 modules**: `sources/yahoo_finance_news.py`, `sources/sec_edgar_8k.py`.
- **New external deps**: **zero** (both adapters use existing `httpx` / `defusedxml.ElementTree.fromstring` / `_sanitize.strip_html` / `_retry.retry_get`).
- **New secret**: **none** (Yahoo Finance news RSS is open; SEC EDGAR's User-Agent is a compliance string per R14, not a secret — lives in code as `_USER_AGENT: Final`).

### Definition of Done
- [ ] 2 new adapters registered: `yahoo-finance-news` (news), `sec-edgar-8k` (news)
- [ ] Each adapter has a recorded HTTP fixture under `tests/unit/sources/fixtures/api/<name>/` (real responses; SEC fixture recorded with the production UA)
- [ ] R7 strict (no relaxation, no R11 cadence-gap exception) pinned for both adapters
- [ ] R14 (source-mandated compliance header) pinned for `sec-edgar-8k` via a UA-header capture test
- [ ] L6.5 `summary=None` behaviour pinned (Yahoo's `rssindex` has no `<description>`)
- [ ] L6.6 Item-code extraction pinned (e.g., `"Item 2.02,Item 9.01"` in `raw_metadata.items`)
- [ ] L6.6 Atom 1.0 namespace handling pinned (no string-substitution ns stripping)
- [ ] `EXPECTED_ADAPTER_COUNT` in `tests/unit/sources/test_plugin_contract.py` bumped 4 → 6; expected name set updated to include both new slugs
- [ ] DEBT-028 status verified by qa: confirm neither news adapter introduces fresh `raw_metadata` numeric serialization paths (both carry strings only). If clean, DEBT-028 stays Medium; if exposure found, escalate to High.
- [ ] `aidlc-docs/construction/u1-sources/code/summary.md` appended with extension #2 closeout
- [ ] Quality gate green: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest`
- [ ] AIDLC global Build and Test re-runs successfully (the previous green from 2026-05-01 with 775/775 must still hold; new total expected ≈ 800±)

### What this plan does NOT include
- Earnings calendar adapter — deferred. After Extension #2 closes, FR-001 AC for earnings remains unmet; tracked as a follow-up extension #3 candidate.
- KOSPI adapter — application design notes "보조: 코스피"; deferred until US briefing content is solid.
- News-side de-duplication / cross-adapter merging (e.g., the same Reuters story landing in Yahoo Finance news AND a future NewsAPI feed) — out of scope for u1; if it becomes a problem the briefing layer (u2) handles dedup.
- Per-CIK or per-Item-code filtering on the SEC feed — out of scope; the feed is consumed whole and R7 is the only filter.
- DEBT-028 fix — not blocking news adapters (string-only fields). The fix lands in a future extension or a dedicated tech-debt sweep.

---

## Steps

### Step 1: `yahoo_finance_news.py` — Yahoo Finance top stories RSS adapter (FD L6.5)

- [x] **1.1** Recorded HTTP fixture under `tests/unit/sources/fixtures/api/yahoo-finance-news/`:
  - `feed.xml` — real recording: `curl -sL https://finance.yahoo.com/news/rssindex > feed.xml` (the recording pass must be done from a network with US access; capture status code = 200, content-type `application/rss+xml`)
  - `meta.json` — recording timestamp, source URL, status, content-type, byte size, note about no `<description>` field, note about ISO 8601 `Z`-suffix `<pubDate>` form (different from L6.1 FOMC's RFC 822 form)
- [x] **1.2** `src/investo/sources/yahoo_finance_news.py` — `YahooFinanceNewsAdapter` class with `@register`:
  - `name: ClassVar[str] = "yahoo-finance-news"`, `category: ClassVar[Category] = "news"`
  - `_FEED_URL: Final[str] = "https://finance.yahoo.com/news/rssindex"`
  - No `_DEFAULT_*` constant (no per-symbol parameter — single global feed); no `_USER_AGENT` constant (no R14 requirement); no env-var override
  - `async def fetch(self, client, window) -> list[NormalizedItem]`: single `retry_get` call → `defusedxml.ElementTree.fromstring(response.content)` → iterate `<channel>/<item>` → `_to_normalized` → R7 window filter
  - `_to_normalized(item_elem) -> NormalizedItem | None`:
    - extract `<title>` (HTML-strip via `_sanitize.strip_html`), `<link>`, `<pubDate>`, `<guid>`, `<source>`
    - drop if any of title/link/pubDate missing
    - validate `<link>` http/https only (AC-7.3)
    - parse `<pubDate>` via `email.utils.parsedate_to_datetime` (handles both RFC 822 `-0000` and ISO 8601 `Z` forms); drop if naive (R8 / R11 indirect)
    - `summary=None` (per L6.5 — feed has no `<description>`)
    - `raw_metadata={"guid": str, "rss_source": str}`
- [x] **1.3** `tests/unit/sources/test_yahoo_finance_news.py` — anchor tests via `MockTransport` serving the recorded fixture + inline synthetic XML for edge cases:
  - happy path: real fixture → N items, all fields shape-checked
  - exact-string anchor: title format pin (one real item from fixture, exact match)
  - `summary is None` for every emitted item (L6.5 specific)
  - `<link>` validated http/https; non-http(s) `<link>` → entry dropped
  - `<pubDate>` ISO 8601 `Z` form → tz-aware UTC `published_at`
  - `<pubDate>` RFC 822 `-0000` form (synthetic) → entry dropped (naive)
  - missing `<title>` / `<link>` / `<pubDate>` → entry dropped
  - empty `<channel>` (no `<item>`) → adapter returns `[]`
  - R7 window filter: target_date crafted so half the fixture items fall in / out of window
  - XML parse error (synthetic malformed) → terminal `SourceFetchError`
  - class identity / `name` / `category` pinned
  - `raw_metadata` keys all string-typed (R8)
  - **DEBT-028 audit**: a meta-test asserting `raw_metadata` contains only `str` values (no `float` / `int`) — this is the qa-side guardrail referenced in the audit entry
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (42 src files expected — was 41 + `yahoo_finance_news.py`), pytest ✅ (775 + Step 1 tests, no regressions)

**Step 1 acceptance**: `yahoo-finance-news` adapter implementation + tests green; sub-agent code review deferred to Step 4 cross-cutting pass per Extension #1 precedent (single review covering both new adapters together for consistency).

---

### Step 2: `sec_edgar_8k.py` — SEC EDGAR 8-K Atom adapter (FD L6.6, R14)

- [x] **2.1** Recorded HTTP fixture under `tests/unit/sources/fixtures/api/sec-edgar-8k/`:
  - `feed.atom` — real recording: `curl -sL -A "investo investo@example.com" 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&output=atom' > feed.atom` (the UA header is FUNCTIONALLY REQUIRED — recording without it returns 403; verify the recording pass actually returns 200)
  - `meta.json` — recording timestamp, source URL, status, content-type (`application/atom+xml`), byte size, ISO-8859-1 encoding note, namespace note (`xmlns="http://www.w3.org/2005/Atom"`), exact `User-Agent` value used at recording time (audit trail)
- [x] **2.2** `src/investo/sources/sec_edgar_8k.py` — `SecEdgar8kAdapter` class with `@register` (note: class spelled `SecEdgar8kAdapter` — Python lowercase-after-digit naming, not `8K`):
  - `name: ClassVar[str] = "sec-edgar-8k"`, `category: ClassVar[Category] = "news"`
  - `_FEED_URL: Final[str] = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&output=atom"`
  - `_USER_AGENT: Final[str] = "investo investo@example.com"` — R14 compliance string. Module-level constant per the lead's judgment + R14's storage rule. NOT in `_config.py`. NOT in env. Comment block above the constant cites SEC's fair-access policy with a stable URL (e.g. `https://www.sec.gov/os/accessing-edgar-data`) and explains why this is R14, not R12 or R13.
  - `_ATOM_NS: Final[str] = "http://www.w3.org/2005/Atom"` — used as the namespace prefix for ElementTree calls (`f"{{{_ATOM_NS}}}entry"`). NOT stripped via string substitution (R14 helper note + L6.6 edge case).
  - `_TITLE_REGEX: Final[re.Pattern[str]] = re.compile(...)` — extracts company + CIK from `"8-K - Company Name (CIK) (Filer)"` shape
  - `_ITEM_CODE_REGEX: Final[re.Pattern[str]] = re.compile(r"Item \d+\.\d+")` — extracts Item codes from the HTML-stripped summary body
  - `async def fetch(self, client, window)`: single `retry_get` call WITH `headers={"User-Agent": _USER_AGENT}` → `defusedxml.ElementTree.fromstring(response.content)` (bytes — let the parser honour ISO-8859-1) → iterate `<entry>` via namespace-aware path → `_to_normalized` → R7 window filter
  - `_to_normalized(entry_elem) -> NormalizedItem | None`:
    - extract `<title>`, `<link rel="alternate">` href, `<summary type="html">`, `<updated>`
    - drop if any of title/link/updated missing
    - parse title via `_TITLE_REGEX`; drop entry on regex miss (defense against schema change)
    - validate link http/https
    - parse `<summary>` body: HTML-strip via `_sanitize.strip_html`; extract Item codes via `_ITEM_CODE_REGEX.findall(...)`; if zero matches, items list is `[]` and entry is still emitted (defense per L6.6 edge case)
    - parse `<updated>` ISO 8601 (already tz-aware due to `-04:00` offset) → convert to UTC; drop if naive (defense)
    - extract accession number + CIK via small regex on the summary body's `<b>AccNo:</b>` / `<b>Filed:</b>` markers (or via the entry's `<id>` element, which carries the accession number canonically — TBD at impl time, document the chosen path in the test docstring)
    - build NormalizedItem per L6.6 mapping
- [x] **2.3** `tests/unit/sources/test_sec_edgar_8k.py` — anchor tests via `MockTransport` serving the recorded fixture + inline synthetic Atom for edge cases:
  - happy path: real fixture → N items, all fields shape-checked
  - **R14 UA-header pinning test**: `MockTransport` captures the request, asserts `request.headers["user-agent"]` exactly equals `"investo investo@example.com"` (case-insensitive httpx header matching). This is the rule-enforcement test for R14.
  - **R14 negative test**: assert that the adapter does NOT silently fall back to httpx's default UA if the constant is somehow `""` (hypothetical regression — the test imports the constant, asserts non-empty + contains an `@`)
  - title parsing: real-fixture title (e.g. `"8-K - APPLE INC (0000320193) (Filer)"`) → parsed company `"APPLE INC"`, CIK `"0000320193"`, NormalizedItem.title shape `"8-K: APPLE INC (CIK 0000320193)"`
  - title parsing failure (synthetic, malformed title) → entry dropped, no raise
  - Item-code extraction: real fixture has at least one entry with multiple Item codes → `raw_metadata.items` is comma-joined `"Item X.YY,Item A.BB"` (order preserved as found in summary)
  - Item-code extraction zero matches (synthetic summary without Item codes) → entry emitted, `raw_metadata.items=""`, summary = HTML-stripped body
  - Atom namespace handling: the test fixture is parsed using ElementTree's namespace-prefix syntax; a synthetic feed with an additional `media:content` extension element MUST NOT crash the parser
  - encoding: assert that `defusedxml.ElementTree.fromstring(response.content)` is called with bytes (not `response.text`) so ISO-8859-1 is honoured
  - `<updated>` with `-04:00` offset → tz-aware UTC `published_at`
  - missing `<title>` / `<link>` / `<updated>` → entry dropped
  - non-http(s) `<link href>` (synthetic — sec.gov never does this in practice) → entry dropped
  - 403 from SEC (synthetic — simulates missing/wrong UA at the transport level) → terminal `SourceFetchError(transient=False)` after retries
  - R7 window filter: target_date crafted so half the fixture entries fall in/out of window
  - XML parse error (synthetic malformed) → terminal `SourceFetchError`
  - class identity / `name` / `category` pinned
  - `raw_metadata` keys all string-typed (R8)
  - **DEBT-028 audit**: meta-test asserting `raw_metadata` contains only `str` values (mirror of Step 1.3's guardrail)
- [x] **2.4** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (43 src files expected), pytest ✅ (Step 1 total + Step 2 tests, no regressions)

**Step 2 acceptance**: `sec-edgar-8k` adapter implementation + tests green; UA-header pinning test passes; sub-agent code review deferred to Step 4.

---

### Step 3: `__init__.py` discovery + plugin contract bump 4→6

- [x] **3.1** `src/investo/sources/__init__.py` — add 2 imports (`from . import (coingecko, fomc_rss, fred, sec_edgar_8k, yahoo_finance_news, yfinance)` — alpha-sorted, ruff will normalise). Star-import contract list extended.
- [x] **3.2** `tests/unit/sources/test_plugin_contract.py` — bump `EXPECTED_ADAPTER_COUNT` 4 → 6; expected name set extended to `{"fomc-rss", "yfinance-price", "coingecko-price", "fred-macro", "yahoo-finance-news", "sec-edgar-8k"}`; autouse fixture re-registers all 6 productively-known adapters; `leaked` set in star-import test extended with new adapter names. 7/7 plugin-contract tests green (test count unchanged; expected values updated).
- [x] **3.3** Quality gate: ruff ✅, ruff format ✅, mypy --strict ✅ (43 src files), pytest ✅ (full suite green; 775 → 810).

**Step 3 acceptance**: registry + plugin contract reflect the new 6-adapter reality; full quality gate green; ready for cross-cutting QA.

---

### Step 4: Cross-cutting QA review + closeout

- [ ] **4.1** Single sub-agent code review covering both new adapters together (per Extension #1 precedent). Review focus:
  - Correctness: title-parsing regex robustness; Atom namespace handling; `defusedxml` fromstring on bytes (encoding); R7 window-filter semantics for tz-aware datetimes; per-item summary `None` handling at the model layer
  - Compliance / R14: UA constant placement; UA value identifies the project + a contact mailbox; UA passed via `retry_get(headers=...)` not via inline `client.get(...)`
  - Safety / R13: zero secret material in either adapter (UA is public); zero credentials in `raw_metadata`; zero credentials in fixture files
  - Maintainability: no logic duplicated from `_retry` / `_sanitize` / `_window`; consistent style with the 4 existing extension adapters
  - **Cross-cutting consistency check** against the 4 existing adapters (fomc_rss / yfinance / coingecko / fred): naming, class shape, `_FEED_URL` constant style, error-classification contract, `_to_normalized` method shape, fixture-recording convention
  - **DEBT-028 verification**: explicit assertion that neither news adapter writes float / int values into `raw_metadata`. If verified clean, DEBT-028 stays Medium with age clock continuing. If new exposure found, escalate DEBT-028 to High in the closeout.
- [ ] **4.2** Apply review findings: any Critical/High → fix before proceeding; Medium → fix-or-debt-or-skip per skill protocol; Low → cosmetic fix in-place where cheap.
- [ ] **4.3** `aidlc-docs/construction/u1-sources/code/summary.md` — append "Extension #2 closeout (2026-05-01)" section with: deliverables table; new test inventory delta; `Category` enum coverage 3/5 → 4/5; R14 newly-pinned rule; cross-cutting review summary; DEBT-028 status post-verification; final quality gate pin.
- [ ] **4.4** Final quality gate (after Step 4.2 fixes applied):
  - `ruff check .` ✅
  - `ruff format --check .` ✅ (~118 files)
  - `mypy --strict src/` ✅ (43 source files; was 41)
  - `pytest` ✅ (775 + Step 1 + Step 2 tests; expect ~800±)
  - `mkdocs build --strict` ✅ (no docs change in this extension)
- [ ] **4.5** `aidlc-docs/aidlc-state.md` — u1 row updated to extension-#2-closed; remove "Extension #2 in progress" suffix; bump test counts; note "Category enum 4/5 (calendar/price/macro/news); only earnings still TBD". Global Build and Test row re-verified (third re-verification — base 2026-05-01, post-Extension-#1, post-Extension-#2).
- [ ] **4.6** Audit log entry at top of `aidlc-docs/audit.md`: "Construction — u1 sources — Extension #2 CLOSED (2 news adapters delivered)" mirroring the Extension #1 closeout shape.

**Step 4 acceptance**: u1 sources Extension #2 CLOSED. Unit becomes eligible for `/cross-check` re-run. Plan CLOSED.

---

## Step Dependency Graph

```
1 yahoo-finance-news      (depends on existing _retry / _sanitize / models; FD L6.5)
2 sec-edgar-8k            (depends on existing _retry / _sanitize / models; FD L6.6, R14)
   ├─ Steps 1 and 2 are independent — could run in parallel,
   │  but per `dev-investo` "one step per execution" rule they
   │  run sequentially. Recommended order: 1 → 2 (Yahoo is simpler
   │  and surfaces RSS-parse infra; SEC is novel — Atom + UA — so
   │  benefits from going second).
   ▼
3 registration / contract bump 4→6   (depends on 1 and 2)
   ▼
4 cross-cutting QA + closeout        (depends on 1, 2, 3)
```

---

## Estimated Scope

- 4 plan steps, each yielding ~1 commit
- 2 new source modules (`yahoo_finance_news`, `sec_edgar_8k`); ~250-350 LOC source total
- ~25-35 new tests (15-20 per adapter is the going rate per Extension #1)
- Solo dev: ~half a day
- Zero new external deps

---

## NFR AC Coverage Map (extension #2 delta)

| AC / Rule | Pinned at step |
|-----------|----------------|
| R7 strict (no relaxation) for both news adapters | 1 / 2 |
| R8 raw_metadata string-cast (DEBT-028 guardrail) | 1.3 / 2.3 (meta-tests) |
| R14 source-mandated compliance header (UA) | 2.3 (UA-capture test) |
| AC-2.2 (no paid APIs) | 1 / 2 (both free; SEC UA is compliance, not auth) |
| AC-7.3 (http/https URL validation) | 1.3 / 2.3 |
| AC-7.6 (defusedxml only — XML adapters) | 1.2 / 2.2 (`defusedxml.ElementTree.fromstring`) |
| AC-5.2 (EXPECTED_ADAPTER_COUNT 4→6) | 3 |
| AC-5.3 (duplicate-name detection re-validated) | 3 (autouse fixture re-runs) |
| L6.5 `summary=None` behaviour | 1.3 |
| L6.6 Atom-namespace + Item-code extraction | 2.3 |

No new NFR ACs are added in this extension. All AC additions happened in Extension #1 (AC-3.6 / AC-5.5).

---

## How to Approve

This plan is the single source of truth for the u1 Extension #2 Code Generation. Reply **approve** to begin Step 1; **changes [N]** to revise step N before approval.
