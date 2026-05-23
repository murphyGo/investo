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
>
> **Extension #3 note (2026-05-01)**: L6.7 (Yonhap 마켓+ RSS / news), L6.8 (The Block RSS / news), and L6.9 (CNBC US Top News RSS / news) added per the 2026-05-01T06:00:00Z audit-log entry. All three adapters use `category="news"`, all three apply strict R7 (no relaxation), all three carry no secrets and no compliance headers (R14 does NOT apply). All three use UTF-8 encoding and RFC 822 `<pubDate>` (which `email.utils.parsedate_to_datetime` handles natively on Python 3.11 — no L6.5-style ISO 8601 surprise). L6.8 (The Block) introduces adapter-local URL canonicalization to strip `?utm_source=rss&utm_medium=rss` tracking parameters from `<link>` items before storing — this is per-adapter logic, not a cross-cutting rule (no R-rule added). L6.9 (CNBC) explicitly ignores `<metadata:*>` namespace elements (no signal for the briefing layer). After this extension, news adapter count rises from 2 → 5; `Category` enum coverage stays at 4/5 (only earnings TBD).

> **Extension #4 note (2026-05-03)**: L6.10 (Nasdaq Stocks RSS / news) added per the 2026-05-03 audit-log entry. The adapter uses `category="news"`, strict R7, no secret, and a non-secret adapter-local browser-compatible User-Agent because live fixture recording showed the official Nasdaq feed hangs/fails without a UA; the production UA is the same shape used for fixture recording. This is not R14 fair-access compliance (SEC-only); it is a pragmatic source-access header pinned by tests. News adapter count rises from 5 → 6; total adapter count rises from 9 → 10; `Category` enum coverage stays 4/5 (only earnings TBD).

> **Extension #5 note (2026-05-03)**: L6.11 (Nasdaq Earnings Calendar JSON / earnings) added to close the final `Category` gap. The adapter uses `category="earnings"`, no secret, no paid API, and the same non-secret browser-compatible Nasdaq access headers as L6.10. Because Nasdaq supplies report buckets (pre-market / after-hours / not-supplied) rather than exact timestamps, `published_at` is anchored to UTC midnight on `window.target_date` and the bucket is preserved in `raw_metadata["report_time"]`. Category coverage rises from 4/5 → 5/5.

> **Extension #6 note (2026-05-24)**: L6.12 (`stooq-kr-market` / domestic index + FX) added per the 2026-05-24 u67 (domestic-channel-depth) audit-log entry. The adapter is the **deterministic domestic index-close + 원/달러 fallback** for the domestic-equity segment: Stooq CSV (`usdkrw` for FX, `^kospi` for the index) primary, with a Yonhap `market.xml` RSS numeric-close parse as the terminal index fallback. It carries `category="price"` (R11 KST market-close `published_at` semantics), no secret, no paid key, and no compliance header (R14 does NOT apply). The Yonhap parse path uses `defusedxml` (NFR-007 AC-7.6). New domestic business rule **R15** (index-close precedence + FX-presence + overnight bridge) governs how its values combine with the existing `fsc-krx-index-price` source. No new domain entity — `NormalizedItem` + `MarketAnchor` reused.

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

### L6.7 Yonhap 마켓+ RSS adapter (extension #3 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://www.yna.co.kr/rss/market.xml` (single HTTP per fetch — full feed in one call) |
| Auth | none (no API key, no compliance header — Yonhap's RSS endpoint is openly accessible; httpx's default UA is acceptable) |
| Format | RSS 2.0 (`<rss version="2.0">` → `<channel>` → repeated `<item>`); **encoding `utf-8`** declared in the XML header. **CDATA wrapping**: `<title>` and `<description>` content is wrapped in `<![CDATA[ ... ]]>` per the recorded fixture. defusedxml's parser unwraps CDATA transparently and returns the inner text via `.findtext`; no special-case adapter code required. `_sanitize.strip_html` then removes any embedded HTML markup (Yonhap's descriptions occasionally contain inline `<a>` tags). |
| Volume | feed typically carries ~30-50 items at any time; R7 KST window selects only items within `[target_date 00:00 KST, (target_date+1) 00:00 KST)` UTC. Steady-state output ≈ a handful to a couple dozen items per fetch. |
| `name` | `"yonhap-market"` |
| `category` | `"news"` |
| Per-item cap | none — R7 strict is the natural cut |
| Window filter | **strict R7 — no relaxation**. Each `<item>` carries an authoritative `<pubDate>` in RFC 822 format with explicit `+0900` (KST) offset (e.g. `"Wed, 30 Apr 2026 14:23:00 +0900"`); tz-aware after parse via `email.utils.parsedate_to_datetime`. Items outside the UTC window dropped client-side after fetch. Yonhap publishes throughout the KST business day with bursts during market open/close — no cadence gap, R11's relaxation clause does NOT apply. |
| `NormalizedItem` mapping | `source_name="yonhap-market"`; `category="news"`; `title=<title>` (CDATA-unwrapped by parser; HTML-stripped via `_sanitize.strip_html` defensively); `summary=<description>` (CDATA-unwrapped; HTML-stripped; truncated to 280 chars per R8); `url=<link>` (validated AC-7.3 http/https-only); `published_at` = `<pubDate>` parsed via `email.utils.parsedate_to_datetime` → tz-aware UTC (input is `+0900`, output normalized to `UTC` via `.astimezone(UTC)`); `raw_metadata={"guid": str, "rss_source": str}` where `rss_source` defaults to `"연합뉴스"` if `<source>` is absent (Yonhap items typically omit `<source>` because the entire feed IS Yonhap-authored). |
| Edge cases | items missing any of `<title>`/`<link>`/`<pubDate>` dropped; `<pubDate>` parsing to a naive datetime (defense-in-depth — Yonhap's `+0900` form is tz-aware, but a malformed `-0000` would parse naive) dropped; non-http(s) URLs dropped (AC-7.3); empty feed → adapter returns `[]`, no raise; XML parse error → terminal `SourceFetchError` (`defusedxml.ElementTree.fromstring`, NFR-007 AC-7.6); **encoding garble defense**: if the feed ever serves non-UTF-8 bytes despite the declared `encoding="utf-8"` header, `defusedxml.fromstring(response.content)` raises `ParseError` which surfaces as terminal `SourceFetchError` per the standard contract (no silent "fix-up" attempted — encoding correctness is a source-side guarantee). |

The Yonhap adapter is the **first Korean-language news source** in u1. The briefing layer (u2) treats its title/summary as Korean text natively — no translation step. The adapter has no secret, no compliance header, no env-var override (the feed is a single global market+ stream), and no per-item cap.

---

### L6.8 The Block RSS adapter (extension #3 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://www.theblock.co/rss.xml` (single HTTP per fetch — full feed in one call) |
| Auth | none (no API key, no compliance header — The Block's RSS endpoint is openly accessible; httpx's default UA is acceptable) |
| Format | RSS 2.0 (`<rss version="2.0">` → `<channel>` → repeated `<item>`); encoding `utf-8`. Optional Dublin Core namespace (`xmlns:dc="http://purl.org/dc/elements/1.1/"`) for `<dc:creator>` (author name); `<category>` elements are repeated (one per tag — typical values like `"Markets"`, `"DeFi"`, `"Bitcoin"`). |
| Volume | feed typically carries ~20-30 most-recent items; R7 KST window narrows steady-state to ≈ a handful to a dozen per fetch (The Block publishes intraday US-EDT, with weekend slowdown). |
| `name` | `"theblock-crypto"` |
| `category` | `"news"` |
| Per-item cap | none — R7 strict is the natural cut |
| Window filter | **strict R7 — no relaxation**. Each `<item>` carries an authoritative `<pubDate>` in RFC 822 format with explicit `-0400` (EDT) offset (e.g. `"Wed, 30 Apr 2026 09:15:00 -0400"`); tz-aware after parse via `email.utils.parsedate_to_datetime`. Items outside the UTC window dropped client-side. Weekend cron fires return reduced (not empty) results since The Block publishes Saturday/Sunday at lower volume — strict R7 is correct (no R11 relaxation). |
| URL canonicalization (adapter-local) | **utm-strip** (extension #3 closeout 2026-05-01: FD prose corrected to match implementation; original 2-key spec ratified as inferior to the actual 5-key pattern): every `<link>` ends with `utm_*` tracking parameters per the recorded fixture. The adapter strips the **full standard utm-set** (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` — five keys, not two) before storing so the canonical URL — without tracking — lands in `NormalizedItem.url`. Implementation: `urllib.parse.urlsplit(link)` → `parse_qsl(query, keep_blank_values=False)` → filter out keys in the 5-key utm set → `urlencode(remaining)` → `urlunsplit((scheme, netloc, path, new_query, fragment))`. Note `keep_blank_values=False` (not `True`) — empty-value tracking params are dropped along with the named ones; this is harmless because non-tracking params with legitimately empty values are not a real-world pattern on The Block's URLs. The helper is a small private function in `theblock_crypto.py` (not promoted to `_sanitize` or a project-wide rule — only this adapter has the concern). The original `<link>` value (with utm params) is NOT stored in `raw_metadata` — the canonical URL is the single source of truth, no tracking-param leak via `raw_metadata`. **Test coverage**: a dedicated unit test asserts that an item with `?utm_source=rss&utm_medium=rss&other=keep` strips only the utm keys and preserves `other=keep`. |
| `NormalizedItem` mapping | `source_name="theblock-crypto"`; `category="news"`; `title=<title>` (HTML-stripped); `summary=<description>` (HTML-stripped, truncated to 280 chars); `url` = utm-stripped `<link>` (then validated AC-7.3 http/https-only); `published_at` = `<pubDate>` parsed via `parsedate_to_datetime` → tz-aware UTC; `raw_metadata` carries `{"guid": str}` always plus optionally `creator` (from `<dc:creator>` text) and `categories` (comma-joined text of all `<category>` elements, e.g. `"Markets,DeFi,Bitcoin"`) (extension #3 closeout 2026-05-01: FD prose corrected to match implementation; key names are `creator` / `categories` — not the originally-spec'd `rss_creator` / `rss_categories` — to align with the yonhap precedent in §L6.7. **When the source field is absent the key is OMITTED entirely** — empty-string sentinel is NOT used. Rationale: matches yonhap's omit-when-absent pattern, keeps `raw_metadata` minimal, lets downstream consumers use plain `dict.get()` with a `None` default rather than disambiguating empty-string-vs-missing). |
| Edge cases | items missing any of `<title>`/`<link>`/`<pubDate>` dropped; non-http(s) URLs dropped after utm-strip (defense — utm-strip preserves scheme); naive datetime dropped; empty feed → `[]`; XML parse error → terminal `SourceFetchError`; **utm-strip on a link without query params** → no-op (helper handles empty query string gracefully); **utm-strip on a link where utm-keys appear in the path or fragment** → not stripped (helper operates only on the query component, which is the documented tracking-param location). |

The Block adapter is the only one in u1 (as of Extension #3) that performs URL canonicalization. The decision to keep the helper adapter-local (not promoted to `_sanitize`) follows YAGNI — if a future news adapter faces the same tracking-param issue, the pattern can be extracted at that point. No R-rule added in this extension.

---

### L6.9 CNBC US Top News RSS adapter (extension #3 2026-05-01)

| Step | Detail |
|------|--------|
| Source | `https://www.cnbc.com/id/100003114/device/rss/rss.html` (single HTTP per fetch — full feed in one call; the numeric `id` in the URL identifies the "Top News" channel within CNBC's CMS, distinct from `/id/19854910` for "World News" etc.) |
| Auth | none (no API key, no compliance header — CNBC's RSS endpoints are openly accessible; httpx's default UA is acceptable) |
| Format | RSS 2.0 (`<rss version="2.0">` → `<channel>` → repeated `<item>`); encoding `utf-8`. **Multiple namespaces declared** at the `<rss>` root: at minimum `xmlns:media="http://search.yahoo.com/mrss/"` (for media thumbnails) and `xmlns:cn="http://nbcnews.com/rss/namespace"` (CNBC's own metadata: `cn:lastPubDate`, `cn:source`, `cn:type`, etc.). **Adapter ignores ALL namespace-prefixed elements entirely** — only the canonical RSS 2.0 `<title>`, `<link>`, `<pubDate>`, `<description>`, `<guid>` element children are read. Rationale: CNBC's `<metadata:*>` fields carry no signal the briefing layer needs, and surfacing them would only enlarge `raw_metadata` for no value. The adapter's `_to_normalized` uses `entry.findtext("title")` etc. which only matches unprefixed local names — any namespace-prefixed sibling is naturally ignored without a registered handler. **No string-substitution namespace stripping** (same anti-pattern guard as L6.6). |
| Volume | feed typically carries ~30 most-recent top-stories items; R7 KST window narrows steady-state to a dozen or two per fetch (CNBC publishes 24/7 with diurnal variation). |
| `name` | `"cnbc-top-news"` |
| `category` | `"news"` |
| Per-item cap | none — R7 strict is the natural cut |
| Window filter | **strict R7 — no relaxation**. Each `<item>` carries an authoritative `<pubDate>` in RFC 822 format with `GMT` zone (e.g. `"Wed, 30 Apr 2026 13:15:00 GMT"`); tz-aware after parse via `parsedate_to_datetime` (`GMT` is treated as `+0000`). Items outside the UTC window dropped client-side. CNBC publishes 24/7 with no cadence gap — R11 relaxation does NOT apply. |
| `NormalizedItem` mapping | `source_name="cnbc-top-news"`; `category="news"`; `title=<title>` (HTML-stripped); `summary=<description>` (HTML-stripped, truncated to 280 chars; CNBC `<description>` typically contains a short paragraph plus an embedded `<img>` tag — `strip_html` removes the img markup cleanly); `url=<link>` (validated AC-7.3 http/https-only); `published_at` = `<pubDate>` parsed via `parsedate_to_datetime` → tz-aware UTC (input `GMT` → output `UTC` is identity); `raw_metadata={"guid": str}` (no `<source>` / `<dc:creator>` surfaced — see Q6 metadata-namespace decision; CNBC's `<guid>` is a stable URL-shaped identifier, sufficient for downstream dedup). |
| Edge cases | items missing any of `<title>`/`<link>`/`<pubDate>` dropped; non-http(s) URLs dropped; naive datetime dropped (defense — `GMT` parses tz-aware via `parsedate_to_datetime`); empty feed → `[]`; XML parse error → terminal `SourceFetchError`; **namespace-extension robustness**: a synthetic feed with an unexpected `<media:content>` or `<cn:newField>` element MUST NOT crash the parser and MUST NOT appear in `raw_metadata` — the test suite includes a synthetic-fixture case asserting this. |

The CNBC adapter completes the general-news trio. The `<metadata:*>`-ignore decision keeps `raw_metadata` minimal and uniform with sibling adapters. No secret, no compliance header, no env-var override, no per-item cap.

### L6.10 Nasdaq Stocks RSS adapter (extension #4 2026-05-03)

| Aspect | Design |
|--------|--------|
| Source | `https://www.nasdaq.com/feed/rssoutbound?category=Stocks` (single HTTP per fetch; official Nasdaq category RSS endpoint listed from `https://www.nasdaq.com/nasdaq-RSS-Feeds`) |
| Auth | none (no API key, no paid account, no GitHub Secret). The adapter sends a fixed, non-secret browser-compatible User-Agent because local recording showed Nasdaq's RSS endpoint can hang/fail without one. The production UA matches the fixture-recording UA shape. This is adapter-local access hygiene, not R14 SEC fair-access compliance. |
| Format | RSS 2.0 (`<rss version="2.0">` → `<channel>` → repeated `<item>`); UTF-8 XML declaration; `dc:creator` and `nasdaq:tickers` namespace fields are optional. Required fields use unprefixed RSS names: `<title>`, `<link>`, `<pubDate>`. Namespace values are looked up by fully-qualified Clark names via `_xml_namespaces.py`; no string namespace stripping. |
| Volume | feed returns the latest Nasdaq `Stocks` topic stories (observed fixture: 15 entries). R7 KST window narrows by authoritative per-item `pubDate`. |
| Per-item cap | none — R7 strict is the natural cut. |
| Window filter | **strict R7 — no relaxation**. Each `<item>` carries an authoritative RFC 822 `<pubDate>` with explicit `+0000` offset; parsed via `email.utils.parsedate_to_datetime` and converted to UTC. |
| `NormalizedItem` mapping | `source_name="nasdaq-stocks-news"`; `category="news"`; `title=<title>` (HTML/entity stripped via `_sanitize.strip_html`); `summary=<description>` (HTML stripped, truncated to 280 chars); `url=<link>` (validated AC-7.3 http/https-only); `published_at=<pubDate>` parsed to tz-aware UTC; `raw_metadata={"guid": str, "creator": str, "category": str, "tickers": comma-joined str}` with optional keys omitted when absent/empty. |
| Edge cases | missing any of `<title>`/`<link>`/`<pubDate>` dropped; non-http(s) URLs dropped; naive or unparseable dates dropped; empty `<channel>` returns `[]`; malformed XML raises terminal `SourceFetchError`; empty `<nasdaq:tickers>` omits the `tickers` key rather than storing an empty string. |

The Nasdaq adapter adds official exchange-side US market commentary to the news cohort. It introduces no secrets and no numeric `raw_metadata` values, so DEBT-028 remains scoped to the yfinance / CoinGecko / FRED numeric adapters.

### L6.11 Nasdaq Earnings Calendar JSON adapter (extension #5 2026-05-03)

| Aspect | Design |
|--------|--------|
| Source | `https://api.nasdaq.com/api/calendar/earnings?date={YYYY-MM-DD}` (single HTTP per fetch; target date from `FetchWindow.target_date`) |
| Auth | none (no API key, no paid account, no GitHub Secret). Sends browser-compatible `User-Agent`, `Origin`, and `Referer` headers because the public Nasdaq API expects browser-shaped access. |
| Format | JSON object with `data.rows[]`; each row includes `time`, `symbol`, `name`, `marketCap`, `fiscalQuarterEnding`, `epsForecast`, `noOfEsts`, `lastYearRptDt`, and `lastYearEPS`. |
| Volume | daily calendar; observed May 4, 2026 fixture has many rows. Adapter emits one item per valid row. |
| `name` | `"nasdaq-earnings-calendar"` |
| `category` | `"earnings"` |
| Per-item cap | none — date-scoped endpoint is the natural cut. |
| Window filter | The endpoint is date-scoped rather than timestamp-scoped. Nasdaq provides report buckets, not exact report datetimes. The adapter sets `published_at` to UTC midnight on the target date so the item is anchored inside the target KST window; `raw_metadata["report_time"]` carries `pre-market`, `after-hours`, or `not-supplied`. |
| `NormalizedItem` mapping | `title=f"{symbol} earnings — {report_time} — EPS forecast {epsForecast}"` with missing optional pieces omitted; `summary` combines company name, fiscal quarter, market cap, estimate count, and last-year EPS (truncated to 280 chars); `url=https://www.nasdaq.com/market-activity/stocks/{symbol}/earnings`; `raw_metadata` includes non-empty string fields: `symbol`, `company_name`, `report_time`, `fiscal_quarter_ending`, `eps_forecast`, `no_of_ests`, `market_cap`, `last_year_eps`, `last_year_report_date`. |
| Edge cases | malformed JSON raises terminal `SourceFetchError`; non-object payload / missing `data` / non-list `rows` raise terminal `SourceFetchError`; `rows: null` returns `[]`; rows missing required `symbol` or `name` are dropped; `"N/A"` and empty optional strings are omitted from `raw_metadata`; HTML in text fields is stripped. |

The earnings adapter closes the final category gap without adding a new secret or paid API. It intentionally does not model after-hours events as next-day UTC timestamps because doing so would drop valid target-date earnings events from the KST window.

### L6.12 Stooq KR market + Yonhap index-fallback adapter (extension #6 2026-05-24)

| Aspect | Design |
|--------|--------|
| Source (FX) | `https://stooq.com/q/l/?s=usdkrw&f=sd2t2ohlcv&h&e=csv` (Stooq CSV quote line; one HTTP per symbol). Live 2026-05-24: 200 / close 1518.21. |
| Source (index) | `https://stooq.com/q/l/?s=^kospi&...&e=csv` for KOSPI (live 200 / close 7847.71). KOSDAQ has **no Stooq symbol** — `^kosdaq` + 4 variants all returned `N/D` live, so KOSDAQ is sourced only via the Yonhap fallback. |
| Source (index fallback) | `https://www.yna.co.kr/rss/market.xml` (Yonhap 마켓+ RSS; UA required — same feed as L6.7 `yonhap-market`). Best-effort numeric-close parse of index headlines, used only when KRX + Stooq are both empty for that index. |
| Auth | none — no API key, no paid tier (R1). FX `KRW=X` via yfinance is NOT used (live HTTP 429 on the GHA path; ratified divergence from the u67 plan reachability table). |
| Format | Stooq: CSV (header + one quote row per symbol). Yonhap: RSS 2.0 parsed via `defusedxml.ElementTree.fromstring` (NFR-007 AC-7.6); numeric index values are pattern-extracted from CDATA-unwrapped headline/description text. |
| `name` | `"stooq-kr-market"` |
| `category` | `"price"` |
| Per-symbol isolation | each symbol (FX, KOSPI, KOSDAQ-via-Yonhap) is fetched/parsed independently — a single symbol failure yields a logged drop, not a whole-adapter failure. The aggregator's R6 semantics still apply between adapters; this is per-symbol isolation within the adapter (same shape as L6.2 yfinance). |
| Window filter | R11 KST market-close semantics. Stooq emits the latest valid close (R11 cadence-gap relaxation applies — KST-morning cron may fire before KRX settlement). `published_at` is the KR market close resolved via `zoneinfo("Asia/Seoul")`, never an offset literal. |
| `NormalizedItem` mapping | `source_name="stooq-kr-market"`; `category="price"`; FX `title=f"원/달러 {close:,.2f}"`, index `title=f"{label} {close:,.2f} ({pct:+.2f}%)"`; `summary` carries OHLC where Stooq supplies it (Yonhap-parsed index rows summarise the headline source); `published_at` = KR close → UTC; `raw_metadata` string-cast per R8 with a `provenance` key recording which tier supplied the value (`"stooq"` / `"yonhap-parse"`) so the trace footer can attribute the close (R15a). |
| Edge cases | Stooq CSV `N/D` close → symbol dropped, fall through to the next precedence tier; Yonhap parse finds no numeric index headline → that index close is **omitted** (surfaced via coverage badge, not a hard fail — R15a / NFR-003); Stooq 429 → handled by shared `retry_get` (R5); XML parse error on Yonhap → terminal `SourceFetchError` (`defusedxml`); naive datetime → dropped per R8. |

The adapter is the first domestic deterministic index/FX fallback and the only u1 adapter combining a CSV primary with an RSS terminal fallback. It introduces no secret, no paid key, and no compliance header. Domestic business rule **R15** governs how its output combines with `fsc-krx-index-price` (KRX) and the §③ 수급 / §①–§② overnight-bridge narrative. Two close-out TECH-DEBT items recorded: DEBT-068 (Yonhap parse is best-effort — a dedicated free KRX index RSS would harden the terminal tier) and DEBT-069 (domestic anchors are close-only — Yahoo KR history 429 leaves the note column `—`).

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
