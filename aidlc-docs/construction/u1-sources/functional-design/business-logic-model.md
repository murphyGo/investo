# Business-Logic Model — `u1 sources`

**Date**: 2026-04-27
**Source**: u1-sources-functional-design-plan.md (all recommended)

This document is the technology-neutral description of how the unit
behaves. Concrete library calls (`httpx.AsyncClient`, exact retry
helper API) are inputs; the algorithms below are what code generation
must implement.

---

## L1. End-to-end flow

```
orchestrator
    │
    │ target_date: date  (KST trading date)
    ▼
fetch_all(target_date)
    │
    │ open shared httpx.AsyncClient
    │
    │ build FetchWindow(target_date)  -> (start_utc, end_utc)
    │
    │ adapters = list_sources()       -> all registered SourceAdapters
    │
    │ run all adapters concurrently:
    │   for each adapter:
    │     try:
    │       items = await adapter.fetch(client, window)
    │     except SourceFetchError as e:
    │       log WARNING; items = []
    │     except Exception:
    │       re-raise (programmer error)
    │
    │ flatten -> single list[NormalizedItem]
    │
    │ close AsyncClient
    │
    ▼
return list[NormalizedItem]
```

Notes:
- Adapters run concurrently via `asyncio.gather(..., return_exceptions=True)`.
  Each result is inspected; `SourceFetchError` instances become empty
  lists with a log entry, other exceptions are re-raised after the
  gather completes.
- The aggregator does NOT enforce a per-adapter wall-clock cap beyond
  the per-call timeout in the retry helper. The 4-min collect budget is
  honoured because each adapter is bounded by R4's per-adapter ≤ 60 s
  total.

---

## L2. Adapter-internal algorithm

A typical adapter (RSS-style; the FOMC PoC follows this):

```
async def fetch(self, client, window):
    # 1. Build the request
    request = self._build_request(window)        # URL, headers, query
    # 2. Run via shared retry helper (R3, R4, R5)
    response = await retry_get(
        client, request,
        timeout=30, retries=2, backoff=(1, 2),
    )
    # 3. Decode payload
    raw_entries = self._parse(response.content)  # XML/JSON/HTML to list[dict]
    # 4. Convert each entry to NormalizedItem
    items = []
    for entry in raw_entries:
        item = self._to_normalized(entry)        # may return None to skip
        if item is None:
            continue
        # 5. Filter to the requested UTC window (R7)
        if not (window.start_utc <= item.published_at < window.end_utc):
            continue
        items.append(item)
    return items
```

### Step-by-step responsibilities

| Step | What | Where |
|------|------|-------|
| 1 | Build the source-specific HTTP request | adapter (`_build_request`) |
| 2 | Execute with retry/backoff/Retry-After | shared `retry_get` (`sources/_retry.py`) |
| 3 | Parse the response body | adapter (`_parse`) |
| 4 | Map each entry into `NormalizedItem` | adapter (`_to_normalized`) |
| 5 | Drop entries outside the UTC window | adapter (`fetch` outer loop) |

The shared retry helper owns timeout/retry/Retry-After. Adapters own
URL construction, parsing, and source→domain mapping.

---

## L3. Registry algorithm

```
sources/__init__.py:
    from . import fomc_rss        # ← triggers @register class-decorator
    # (more imports as new adapters land)

sources/_registry.py:
    _ADAPTERS: dict[str, SourceAdapter] = {}

    def register(cls):
        if cls.name in _ADAPTERS:
            raise RuntimeError(f"duplicate source name: {cls.name}")
        _ADAPTERS[cls.name] = cls()    # singleton instance per process
        return cls

    def list_sources() -> list[SourceAdapter]:
        return list(_ADAPTERS.values())
```

Key design choices:
- Decorator stores **instances**, not classes. Adapters are stateless
  (R3) so a singleton instance per process is fine and removes
  per-call instantiation noise.
- `list_sources()` returns a fresh list copy so callers cannot mutate
  the registry.

---

## L4. Failure classification

| Trigger | Classification | Surfaces as |
|---------|----------------|-------------|
| `httpx.TimeoutException` after retries | transient `SourceFetchError` | log WARNING, `[]` |
| HTTP 5xx after retries | transient `SourceFetchError` | log WARNING, `[]` |
| HTTP 429 after retries | transient `SourceFetchError` | log WARNING, `[]` |
| HTTP 4xx (non-429) | terminal `SourceFetchError` | log WARNING, `[]` (no retry) |
| Body decode error (XML/JSON malformed) | terminal `SourceFetchError` | log WARNING, `[]` |
| Schema mismatch (unexpected key) | terminal `SourceFetchError` | log WARNING, `[]` |
| `pydantic.ValidationError` while building `NormalizedItem` | wrap in terminal `SourceFetchError` | log WARNING, `[]` |
| `KeyError`/`TypeError` from buggy parsing logic | propagate (programmer error) | orchestrator catches, run FAILED |

Rule of thumb: anything traceable to *the source's response* becomes a
`SourceFetchError`. Anything traceable to *our code being wrong*
propagates so we see it.

---

## L5. Logging contract (informational)

Adapters log nothing themselves. The aggregator logs once per failed
adapter at WARNING with structured fields:

| Field | Example |
|-------|---------|
| `source_name` | `"fomc-rss"` |
| `category` | `"calendar"` |
| `error` | `"connection timeout after 2 retries"` |
| `transient` | `True` |

Successful adapters do not log per-item; the aggregator may log
DEBUG-level "{source_name} returned N items" once per call.

The orchestrator owns INFO-level lifecycle logs ("collect started",
"collect produced N items"). This unit stays in WARNING/DEBUG.

---

## L6. Reference-adapter algorithms

> **Extension note (2026-05-01)**: this section originally documented only L6.1 (FOMC RSS PoC). It is now extended with L6.2 (yfinance / US price), L6.3 (CoinGecko / crypto price), L6.4 (FRED / macro) per the 2026-05-01 audit-log entry. The same per-adapter shape (Source / Auth / Format / `name` / `category` / Window filter / NormalizedItem mapping / Edge cases) is reused so cross-adapter review stays mechanical.
>
> **Extension #2 note (2026-05-01)**: L6.5 (Yahoo Finance top stories RSS / news) and L6.6 (SEC EDGAR 8-K Atom / news) added per the 2026-05-01T04:00:00Z audit-log entry. Both adapters use `category="news"`, both apply strict R7 (no relaxation — news has real per-item published_at, no cadence gap), both carry no secrets. SEC EDGAR additionally requires a fair-access User-Agent header (R14).

### L6.1 FOMC RSS PoC (Q5=A)

> **Format correction (2026-04-27, Step 8):** the live feed is **RSS 2.0**, not Atom 1.0 as originally predicted. Field names and date format below have been updated to match the real feed; the audit log Step 8 entry records the divergence.

| Step | Detail |
|------|--------|
| Source | `https://www.federalreserve.gov/feeds/press_all.xml` |
| Auth | none |
| Format | RSS 2.0 |
| Volume | a few entries per day |
| `name` | `"fomc-rss"` |
| `category` | `"calendar"` |
| Window filter | use entry's `<pubDate>` field (RFC 822 / RFC 5322, tz-aware) |
| `NormalizedItem` mapping | title ← `<title>` (HTML-stripped), summary ← `<description>` (HTML-stripped, truncated to 280 chars), url ← `<link>` (only `http`/`https` accepted), published_at ← `<pubDate>` parsed via `email.utils.parsedate_to_datetime` and converted to UTC, raw_metadata ← `{"guid": <guid>, "rss_category": <category>}` |
| Edge cases | entries missing any of `<title>`/`<link>`/`<pubDate>` are dropped; `<pubDate>` returning a naive datetime (e.g. RFC 5322 `-0000`) is dropped; non-http(s) URLs are dropped |

The PoC proves:
- Plugin contract end-to-end: registration → discovery → invocation
- Shared retry helper handles a real network call
- Window filter behaves correctly across UTC midnight on a known fixture
- `NormalizedItem` validators don't reject realistic source data

---

### L6.2 yfinance / Yahoo Finance v8 chart adapter (extension 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d` (one HTTP per ticker; `range=5d` ensures the prior trading day is in the response even after weekends/holidays) |
| Auth | none |
| Format | JSON |
| Volume | one entry per configured ticker (typically ~10) |
| `name` | `"yfinance-price"` |
| `category` | `"price"` |
| Tickers | comma-separated env var `INVESTO_YFINANCE_TICKERS`; default `("^GSPC", "^IXIC", "^DJI", "^VIX", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA")` |
| Per-fetch concurrency | `asyncio.gather(*[fetch_one(ticker) for ticker in tickers], return_exceptions=True)` inside the adapter — sibling-ticker failure isolation: a 4xx on one ticker yields a logged drop, not a whole-adapter failure. The aggregator's R6 semantics still apply *between* adapters; this is per-ticker isolation *within* one adapter. |
| Window filter | per-ticker `published_at` is the latest valid trading day's close timestamp (see R11). The adapter emits at most one item per ticker — the most recent calendar day in the response with non-null OHLC. **R7 KST window is consulted but not enforced** (FD divergence; same shape as L6.4 FRED). Rationale: KST Monday and Saturday cron fires after a US market weekend, so Friday's NY close lies *outside* the strict R7 window for those targets — strict filtering would silently drop all yfinance data on those days. The 5-day API range guarantees at least one weekday is in the response on any cron firing. The latest-valid policy is robust to US market holidays for the same reason. |
| `NormalizedItem` mapping | `source_name="yfinance-price"`; `category="price"`; `title=f"{ticker} {close:,.2f} ({pct:+.2f}%)"` (e.g., `"^GSPC 5234.18 (+0.42%)"`); `summary=f"O:{open:,.2f} H:{high:,.2f} L:{low:,.2f} C:{close:,.2f} V:{volume:,}"` (truncated to 280 chars); `url=f"https://finance.yahoo.com/quote/{ticker}"`; `published_at` = NY 16:00 ET on the close date, converted to UTC via `zoneinfo("America/New_York")` (R11); `raw_metadata={"ticker": str, "open": str, "high": str, "low": str, "close": str, "volume": str, "prev_close": str}` (string-cast per R8 to keep JSON round-trip stable). |
| Edge cases | response `chart.result[0].timestamp` empty → drop ticker; OHLCV array entries with `null` for any of open/high/low/close → drop that day, fall through to the prior valid day in the 5-day range; missing `previousClose` → `pct` defaults to `0.0` with a comment in `summary`; per-ticker 4xx → logged at DEBUG, ticker dropped, others continue; 5xx → handled by shared `retry_get`. |

The adapter sources prior-day OHLCV — not intra-day — because the briefing is a *daily* digest, not a live ticker. The 5-day range is a defensive choice so weekends and US market holidays don't yield empty windows.

---

### L6.3 CoinGecko Public API adapter (extension 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={comma-joined coin_ids}&price_change_percentage=24h` (single HTTP per fetch — all coins in one call, unlike yfinance) |
| Auth | none (free public tier; documented soft limit ≈ 30 req/min — far above our 1 call per cron fire) |
| Format | JSON |
| Volume | one entry per configured coin (typically 3-5) |
| `name` | `"coingecko-price"` |
| `category` | `"price"` |
| Coins | comma-separated env var `INVESTO_COINGECKO_COINS`; default `("bitcoin", "ethereum", "solana")` (CoinGecko coin IDs, not symbols) |
| Window filter | crypto trades 24/7 — there is no "market close." Each coin's `last_updated` (ISO8601 UTC) is used as `published_at`. Item kept if `published_at` falls within R7 window — at KST 07:00 cron firing time, `last_updated` will typically be within the last few minutes (CoinGecko quotes refresh continuously), which lies inside the window for `target_date = today (KST)`. |
| `NormalizedItem` mapping | `source_name="coingecko-price"`; `category="price"`; `title=f"{symbol.upper()} ${price:,.2f} ({pct_24h:+.2f}%)"` (e.g., `"BTC $67,432.10 (+1.23%)"`); `summary=f"24h vol: ${volume_24h:,.0f}; market cap: ${market_cap:,.0f}; high: ${high_24h:,.2f}; low: ${low_24h:,.2f}"` (truncated to 280); `url=f"https://www.coingecko.com/en/coins/{coin_id}"`; `published_at` = parsed `last_updated` ISO8601 → tz-aware UTC; `raw_metadata={"coin_id": str, "symbol": str, "price_usd": str, "pct_24h": str, "volume_24h": str, "market_cap": str, "high_24h": str, "low_24h": str}` (R8 string-cast). |
| Edge cases | rate-limit 429 → existing `retry_get` honours `Retry-After` (R5); coin id not found → CoinGecko returns it absent from the array (no error) — adapter just skips; new listing with `price_change_percentage_24h` null → defaults to `0.0`; if `last_updated` parses to naive datetime → drop entry per R8; empty array (all coin ids invalid) → terminal `SourceFetchError` (programmer config error, not transient). |

---

### L6.4 FRED API adapter (extension 2026-05-01, Q5)

| Step | Detail |
|------|--------|
| Source | `https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={key}&file_type=json&sort_order=desc&limit=2` (one HTTP per series; `limit=2` returns latest + prior so the adapter can compute delta) |
| Auth | API key required (free, single registration at fred.stlouisfed.org); read from env var `FRED_API_KEY`; missing → `SourceFetchError(transient=False)` per R13 |
| Format | JSON |
| Volume | one entry per configured series (typically 5) |
| `name` | `"fred-macro"` |
| `category` | `"macro"` |
| Series | comma-separated env var `INVESTO_FRED_SERIES`; default `("CPIAUCSL", "UNRATE", "DFF", "DGS10", "DEXKOUS")` (CPI / 실업률 / Fed funds rate / 10Y T / KRW-USD) |
| Per-fetch concurrency | `asyncio.gather` per-series, identical pattern to L6.2 |
| Window filter | each observation has a `date` field (release date in NY local time, naive). Convert to UTC via `zoneinfo("America/New_York")` at midnight (FRED publishes at NY market open / morning ET). Item kept if `published_at` falls within R7 window. **Important**: many FRED series are monthly/weekly — most fetches will return a "stale" prior-month observation. The aggregator's KST-window filter would drop these unconditionally, breaking the macro stream. Mitigation: this adapter widens the filter to `[target_date - 65 days, target_date + 1 day]` ET → UTC and emits at most ONE item per series (the most recent valid one). The 65-day window covers the worst case where a monthly indicator's *latest* observation is `"."` (revision in progress) and the adapter falls through to the prior month's release ≈ 60 days before target. The R7 window is *consulted but not enforced* for this adapter (FD divergence noted; ratified in R11 / extension audit entry). |
| `NormalizedItem` mapping | `source_name="fred-macro"`; `category="macro"`; `title=f"{series_id} {value} ({delta:+.4f} from prior)"` (e.g., `"CPIAUCSL 311.054 (+0.4210 from prior)"`; 4 decimals chosen at implementation time so basis-point-scale changes in DGS10 / DFF are visible); `summary` describes the series + previous observation date + previous value (truncated to 280); `url=f"https://fred.stlouisfed.org/series/{series_id}"`; `published_at` = release date (NY midnight ET → UTC tz-aware); `raw_metadata={"series_id": str, "value": str, "previous_value": str, "release_date": str, "previous_release_date": str}` (R8 string-cast). |
| Edge cases | placeholder value `"."` (FRED's missing-data sentinel) → skip that observation, look at next-most-recent in the response; only one observation in window (no prior to compute delta) → emit item with `delta="n/a"`; release date older than 35 days → skip series (operational signal that the series is dormant); `FRED_API_KEY` missing or empty string → `SourceFetchError(transient=False)` raised on the first ticker dispatched (other series in the same fetch_all run are untouched — adapter contributes `[]`); 401/403 from FRED (bad key) → terminal `SourceFetchError(transient=False)`; rate-limit 429 → handled by `retry_get` (FRED documents 120 req/min per key — far above our N≤10 series). |

The FRED adapter is the only one in this extension that diverges from R7 (KST window filter). Rationale: macro releases follow irregular schedules (CPI = monthly, unemployment = monthly, fed funds = daily, T-yields = daily) and a strict 24-hour window would silently drop most of the briefing content. The compromise widens the consultation window to 35 days and emits at most one item per series, preserving "single source of truth per release".

---

### L6.5 Yahoo Finance top stories RSS adapter (extension #2 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://finance.yahoo.com/news/rssindex` (single HTTP per fetch — full feed in one call) |
| Auth | none (no API key, no compliance header — Yahoo's RSS endpoint is openly accessible; httpx's default UA is acceptable) |
| Format | RSS 2.0 (`<rss version="2.0">` → `<channel>` → repeated `<item>`) |
| Volume | feed typically carries 20-40 items at any time; R7 KST window selects only items within `[target_date 00:00 KST, (target_date+1) 00:00 KST)` UTC, so steady-state output is ≈ a handful to a couple dozen items |
| `name` | `"yahoo-finance-news"` |
| `category` | `"news"` |
| Per-item cap | none — R7 strict is the natural cut (per Q3 of the 2026-05-01T04:00:00Z audit decision) |
| Window filter | **strict R7 — no relaxation**. Each `<item>` carries an authoritative `<pubDate>` (ISO 8601 with `Z` suffix per the recorded fixture; tz-aware after parse). Items outside the UTC window are dropped client-side after fetch. Unlike L6.2 (yfinance) and L6.4 (FRED), Yahoo's news feed has no cadence gap — articles publish continuously across all weekdays / weekends — so the strict-R7 guarantee from the original FD applies unchanged. R11's "cadence-gapped sources" relaxation clause does NOT apply. |
| `NormalizedItem` mapping | `source_name="yahoo-finance-news"`; `category="news"`; `title=<title>` (HTML-stripped via `_sanitize.strip_html`); **`summary=None`** (Yahoo's `rssindex` feed does NOT carry a `<description>` element per the recorded fixture; per R8 the field is optional, and u2's downstream "skip-or-default" pattern handles `None` summaries cleanly — synthesizing a fake summary from the title would be a synthetic-content R8 violation); `url=<link>` (validated via the existing AC-7.3 http/https-only check; non-http(s) URLs drop the entry); `published_at` = `<pubDate>` parsed via **`datetime.fromisoformat`** (Yahoo emits ISO 8601 `Z`-suffixed timestamps such as `"2026-04-30T17:30:48Z"`; the original FD claim of `email.utils.parsedate_to_datetime` was empirically wrong — `parsedate_to_datetime` rejects this `Z` form on Python 3.11. The implementation substitutes the trailing `Z` with `+00:00` before calling `fromisoformat` to preserve tz-awareness. Implementation divergence ratified in audit log entry 2026-05-01T05:00:00Z; this prose intentionally pins the parser choice so future re-readers do NOT "fix" the code back to the broken `parsedate_to_datetime` form) → tz-aware UTC; `raw_metadata={"guid": str, "rss_source": str}` where `rss_source` is the `<source>` element's text content (e.g. `"AP"`, `"Reuters"`, `"Bloomberg"`) — R8 string-cast applies trivially since both fields are already strings. |
| Edge cases | items missing any of `<title>`/`<link>`/`<pubDate>` are dropped; `<pubDate>` parsing to a naive datetime is dropped (defense-in-depth — Yahoo's `Z`-suffixed form is tz-aware, but RFC 5322 `-0000` would parse naive); non-http(s) URLs dropped (AC-7.3); duplicate `<guid>`s within a single fetch are not deduplicated (the briefing layer is responsible for de-dup if it cares); empty feed (`<channel>` with no `<item>`) → adapter returns `[]`, no raise; XML parse error → terminal `SourceFetchError` per the standard L4 classification (handled via `defusedxml.ElementTree.fromstring`, NFR-007 AC-7.6). |

The adapter has no secret, no compliance header, no env-var override (the feed has no per-symbol parameter — it's a single global top-stories stream), and no per-item cap. The single-URL fetch + strict-R7 filter keeps this the simplest adapter in the unit.

---

### L6.6 SEC EDGAR 8-K filings Atom adapter (extension #2 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&output=atom` (single HTTP per fetch; `count=40` returns the most recent 40 filings — sufficient because SEC publishes 8-Ks intraday on every weekday and R7 is strict) |
| Auth | **No API key**, but a SEC fair-access User-Agent header is functionally required per R14. Missing or generic UA (e.g., bare `"Mozilla/5.0"`, default httpx UA) → SEC returns HTTP 403 / rate-limits the IP. The adapter MUST send `User-Agent: investo investo@example.com` on every request. The compliance string is NOT a secret (it's a public identifier of the requester); it lives as `_USER_AGENT: Final` in `sec_edgar_8k.py` itself, not in `_config.py` (different concern from R12 user overrides). |
| Format | **Atom 1.0** (different from L6.1's RSS 2.0 and L6.5's RSS 2.0). Root: `<feed xmlns="http://www.w3.org/2005/Atom">`; entries: `<entry>` with children `<title>`, `<link rel="alternate" href="...">`, `<summary type="html">`, `<updated>`, `<id>`. **Encoding**: ISO-8859-1 per SEC's documented response. The XML declaration carries the encoding, so `defusedxml.ElementTree.fromstring(response.content)` (bytes input, not `response.text`) is the correct call — let the XML parser handle the declared encoding rather than assuming UTF-8. **Namespace handling**: the default Atom namespace `http://www.w3.org/2005/Atom` requires either ElementTree's namespace-prefix syntax (`"{http://www.w3.org/2005/Atom}entry"`) or a small helper that prepends the namespace to each tag name. Adapters MUST NOT strip namespaces by string substitution — that's brittle to future Atom extensions (e.g., `media:content`). |
| Volume | `count=40`; R7 KST window narrows to typically 5-30 same-day filings on a weekday (heavy on earnings season, light otherwise). Weekend cron fires return `[]` because SEC doesn't publish 8-Ks on weekends — this is acceptable (no R11-style relaxation needed since news ≠ price; an empty news stream on Saturday is correct, not degraded). |
| `name` | `"sec-edgar-8k"` |
| `category` | `"news"` |
| Per-item cap | none — R7 strict is the natural cut. SEC's `count=40` is an upper bound on what the API returns, not a per-day cap our adapter imposes. |
| Window filter | **strict R7 — no relaxation**. `<updated>` is ISO 8601 with timezone offset (e.g. `2026-04-30T17:30:48-04:00`), tz-aware after parse → convert to UTC. Items outside `[target_date 00:00 KST, (target_date+1) 00:00 KST)` UTC dropped. SEC publishes intraday on every weekday so a Mon-Fri KST cron always finds same-day or next-day-overlap content; weekend KST cron returns `[]` per the volume note above. |
| `NormalizedItem` mapping | `source_name="sec-edgar-8k"`; `category="news"`; `title` = parsed company-and-CIK from the raw `<title>` text `"8-K - Company Name (CIK) (Filer)"` — extract via regex or a 3-step split (split on first ` - `, split on `(`, strip `)`); resulting title shape `f"{form_type}: {company_name} (CIK {cik})"` (HTML-stripped via `_sanitize.strip_html`, although the title is plain text on SEC's feed — the strip is defensive in case SEC ever escapes entities); `summary` = parsed from `<summary type="html">` body — strip HTML via `_sanitize.strip_html`, then preserve the **Item codes** (e.g. `"Item 2.02: Results of Operations and Financial Condition"`, `"Item 5.02: Departure of Directors..."`) which are the key event signal worth surfacing — they map 8-K filings to event types and are the single most valuable text cue for the briefing-side LLM; truncated to 280 chars (R8); `url` = `<link rel="alternate" href="...">` (the filing-detail page on sec.gov, validated http/https only per AC-7.3); `published_at` = `<updated>` parsed as ISO 8601 (already tz-aware due to `-04:00` offset) → converted to UTC; `raw_metadata={"accession_no": str, "filer_cik": str, "form_type": "8-K", "items": str}` where `items` is the comma-joined list of Item codes extracted from the summary (e.g. `"Item 2.02,Item 9.01"`). All R8 string-cast applies trivially. |
| Edge cases | **missing/wrong UA → 403 from SEC** (the edge case worth pinning explicitly per R14): the adapter MUST send the UA on every request (not lazily — the very first probe needs the header); 403 surfaces as terminal `SourceFetchError(transient=False)` after retries, the aggregator catches per R6, the run continues. Title parsing failure (regex/split doesn't match the expected `"8-K - Company (CIK) (Filer)"` shape) → drop entry, log DEBUG, continue with siblings — defense against SEC schema changes. Summary parsing failure (no `<b>Filed:</b>` / `<b>AccNo:</b>` markers) → emit item with empty Item-codes list, raw_metadata `items=""`, summary = HTML-stripped body as-is; do NOT drop the item (the title + URL alone still carry signal). `<entry>` missing any of `<title>`/`<link>`/`<updated>` → dropped per the standard L4 / L6.1 contract. Non-http(s) `link href` (vanishingly unlikely on sec.gov but defensive) → dropped per AC-7.3. XML parse error → terminal `SourceFetchError` (`defusedxml.ElementTree.fromstring`, NFR-007 AC-7.6). Rate-limit 429 → handled by shared `retry_get` (R5); SEC's documented limit is 10 req/sec per IP, far above our 1 call per cron fire — but if the project ever scales to multiple cron fires per day, the limit could become a real constraint. |

The 8-K adapter is the only one in u1 that requires a source-mandated request header (R14). It has no secret, no env-var override (the feed is a single global stream — no per-CIK or per-form filter exposed at the operator level), and no per-item cap.

---

## L7. Sequence (happy path, single adapter)

```
orchestrator             fetch_all              FomcRssAdapter      retry_get      RSS server
     │                       │                          │                │              │
     │  fetch_all(date)      │                          │                │              │
     │──────────────────────▶│                          │                │              │
     │                       │ open AsyncClient         │                │              │
     │                       │ build FetchWindow        │                │              │
     │                       │ list_sources() = [fomc]  │                │              │
     │                       │ adapter.fetch(client,    │                │              │
     │                       │       window)            │                │              │
     │                       │─────────────────────────▶│                │              │
     │                       │                          │ retry_get(...) │              │
     │                       │                          │───────────────▶│              │
     │                       │                          │                │  GET feed    │
     │                       │                          │                │─────────────▶│
     │                       │                          │                │   200 + XML  │
     │                       │                          │                │◀─────────────│
     │                       │                          │ response       │              │
     │                       │                          │◀───────────────│              │
     │                       │                          │ parse Atom     │              │
     │                       │                          │ filter window  │              │
     │                       │  list[NormalizedItem]    │                │              │
     │                       │◀─────────────────────────│                │              │
     │  list[NormalizedItem] │                          │                │              │
     │◀──────────────────────│                          │                │              │
```

---

## L8. Out of scope for this stage

- Specific HTTP library calls (`client.get(...)`) — Code Generation.
- Backoff jitter — defaults to none for now; revisit if 429 patterns
  emerge in operations.
- Caching responses across calls — no caching in v1; cron runs are
  daily, source data is large enough not to warrant it.
- Persisting raw responses for replay — Code Generation may add a
  fixture-recording mode under `tests/fixtures/`, but it is not part
  of the runtime behaviour.
