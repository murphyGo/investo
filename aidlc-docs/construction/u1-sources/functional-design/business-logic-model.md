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

## L6. Reference-adapter algorithm — FOMC RSS PoC (Q5=A)

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
