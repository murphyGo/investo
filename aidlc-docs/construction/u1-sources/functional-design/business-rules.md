# Business Rules — `u1 sources`

**Date**: 2026-04-27
**Source**: u1-sources-functional-design-plan.md (all recommended)

Rules are listed in order of precedence: a higher-numbered rule cannot
override a lower-numbered one without an explicit ADR.

---

## R1. Free-tier APIs only (NFR-002, US-009)

- An adapter must reach its source without an API key, OR with a key
  that the source itself documents as "free" with no metered billing.
- Adding a new adapter requires the PR description to state the source
  URL, the rate limit, and the explicit "no paid tier required"
  declaration.
- The `/code-review` skill enforces this at review time. There is no
  runtime hook (Q8=A).

**Violation**: paid keys, OAuth flows that require a billing
account, "$0 free trial then auto-charge" patterns. Reject in review.

---

## R2. Plugin module shape (US-008)

- One adapter per file: `src/investo/sources/<name>.py`.
- The file defines exactly one adapter class.
- The class applies `@register` at the class level (decorator on the
  class, not on a method). Registration uses the class's `name`
  attribute as the registry key.
- `src/investo/sources/__init__.py` imports every adapter module so
  the decorator runs at package import time (Q1=A).
- Re-registration with a duplicate `name` raises `RuntimeError` at
  import — fail loudly, never silently overwrite.

---

## R3. Async + connection pooling (Q2=A)

- Every adapter implements `async def fetch(client, target_date)`.
- `client` is a shared `httpx.AsyncClient` opened by `fetch_all` via
  `async with`. Adapters MUST NOT create their own `AsyncClient`.
- Adapters MAY pass per-request kwargs (`headers`, `params`, `timeout`)
  but the connection pool comes from the shared client.

---

## R4. Timeout + retry policy (Q3=A)

| Knob | Default |
|------|---------|
| Per-request timeout | 30 seconds |
| Retries | 2 (so 3 total attempts max) |
| Backoff | exponential — 1 s, then 2 s |
| Retried errors | connection errors, 5xx responses, 429 |
| Total budget per adapter | ≤ 60 s wall-clock |

- Adapters that need different knobs override them via constructor
  parameters with these as defaults — they do NOT redefine the retry
  loop.
- The shared retry helper lives in `sources/_retry.py` (private). Every
  adapter consumes it; no inline retry loops.
- After retries exhausted, the helper raises `SourceFetchError(...,
  transient=True)`.

---

## R5. Rate-limit handling — HTTP 429 (Q7=A)

- 429 is included in the retryable set (R4).
- If the response carries `Retry-After`, the helper sleeps for
  `min(parsed_retry_after_seconds, 30)` instead of the default
  exponential backoff.
- If `Retry-After` is missing or unparseable, fall back to the default
  backoff schedule.
- Cap at 30 s so a hostile or sleepy server cannot blow the whole
  collect budget.

---

## R6. Failure isolation contract (Q4=A)

- An adapter that raises `SourceFetchError` does NOT fail the run.
  `fetch_all` catches it, logs at WARNING with `source_name` and the
  error message, and the adapter contributes `[]`.
- Any other exception (programmer error, unexpected library bug)
  propagates out of `fetch_all`. The orchestrator's stage-level guard
  picks it up and converts to a pipeline FAILED outcome.
- Logging format (suggestion, not normative — to be confirmed in code
  generation): `"source %s failed: %s (transient=%s)" % (name, msg, transient)`.

---

## R7. Date range — UTC window (Q6=A)

- Each adapter receives `target_date: date` interpreted as a **KST
  trading date** (the date the orchestrator decided to publish for).
- The adapter MUST filter source data to the UTC window
  `[target_date 00:00 KST, (target_date+1) 00:00 KST)` translated to
  UTC.
- Adapters that cannot filter at the API level (e.g. RSS feeds with no
  date param) filter client-side after fetching.
- Source-side timezones (e.g. NY local time on yfinance) are converted
  to UTC and compared against the window — adapters MUST NOT do
  per-source timezone bookkeeping in `target_date` semantics.

---

## R8. NormalizedItem field rules

When constructing `NormalizedItem`:

- `source_name` MUST equal the adapter's class-level `name`. Adapters
  do not override it per item — the registry key and the provenance
  field are the same string.
- `category` MUST equal the adapter's class-level `category`. An
  adapter only emits items of one category.
- `published_at` MUST be tz-aware (the model enforces; the rule
  emphasises that adapters must convert source timestamps to a
  tz-aware datetime, NOT pass the source's bare local datetime).
- `url` is set when the source emits a stable canonical URL for the
  item; otherwise `None`. Synthetic URLs (e.g. `?fake=...`) are
  forbidden.
- `raw_metadata` may carry source-specific provenance (e.g. RSS
  `<guid>` value, source-side ETag). Use `str` for IDs even if the
  source provides numerics so JSON round-trip stays stable. No
  nested dicts (the model rejects).

---

## R9. Idempotence

- Two calls with the same `target_date` and the same source state
  return equal `NormalizedItem` lists (modulo set order — items are
  not ordered).
- Adapters MUST NOT emit timestamps from `datetime.now()` for
  `published_at`. The published-at value comes from the source.

---

## R10. Test fixtures and offline replay

- Every adapter has a recorded fixture under `tests/fixtures/api/<name>/`
  (HTTP body bytes + status + headers) so the test suite can run
  offline and deterministically.
- The shared retry helper accepts an injected `httpx.AsyncClient` so
  tests pass in a `MockTransport`-backed client.
- No test hits a real external endpoint. CI is not allowed to depend
  on third-party uptime.
