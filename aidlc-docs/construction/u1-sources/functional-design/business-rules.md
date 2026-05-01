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

---

## R11. Price-category `published_at` semantics (extension 2026-05-01)

Applies to any adapter with `category="price"`.

- `published_at` MUST equal the data point's **market close timestamp**
  expressed as a tz-aware UTC datetime. It is NOT the fetch time and
  NOT the trading-day boundary.
- For US equities (NYSE / NASDAQ / indices like ^GSPC), the close is
  16:00 ET. Adapters MUST resolve ET to UTC via
  `zoneinfo("America/New_York")`, NEVER hard-code an offset, so DST
  transitions Handle automatically (16:00 EDT ≈ UTC 20:00; 16:00 EST
  ≈ UTC 21:00).
- For 24/7 markets (crypto), there is no close. Use the API's
  most-recent quote timestamp (CoinGecko: `last_updated`) parsed to
  tz-aware UTC.
- For markets not yet in scope (e.g. KOSPI), the same principle
  applies: source's documented close time, resolved via the source's
  zoneinfo region, never an offset literal.

**Why not the trading-day boundary (e.g., NY 00:00 ET)**: such a
timestamp would fall *outside* the natural R7 KST window when
`target_date` is the next-day KST trading date — for example,
NY 00:00 EDT = UTC 04:00 on the same calendar day. For a Friday KST
target, the window is `[Thu 15:00 UTC, Fri 15:00 UTC)`; UTC 04:00 Fri
is inside it for the wrong reason (refers to NY's Fri 00:00, not
Thursday's close). The market-close timestamp (UTC 20:00 Thu EDT)
lands in the window for the correct semantic reason.

**Why not fetch time**: idempotence (R9) — two cron runs over the
same `target_date` must yield identical items. Fetch time differs
between runs; close time does not.

**R7 window relaxation for cadence-gapped sources**: when a price /
macro source has natural gaps (US market closed on weekends/holidays;
FRED monthly releases; etc.) the adapter MAY emit the most recent
valid observation regardless of strict R7 membership. The
`published_at` value is still the source's authoritative timestamp
(market close / release date) — what relaxes is only the *filter
predicate*, not the timestamp semantics. Each relaxing adapter
documents its lookback bound in its FD L6.x section. Strict-R7
adapters (FOMC RSS news, CoinGecko 24/7 quotes) follow the original
R7 / R6 contract unchanged.

---

## R12. Source-specific configuration via environment variables (extension 2026-05-01)

Applies when an adapter exposes a list of symbols / coins / series
that the operator may want to override at runtime without a code
change.

- Naming convention: `INVESTO_<ADAPTER_SHORT>_<NOUN>` —
  e.g., `INVESTO_YFINANCE_TICKERS`, `INVESTO_COINGECKO_COINS`,
  `INVESTO_FRED_SERIES`. The `<ADAPTER_SHORT>` matches the adapter's
  module filename (uppercased, no `_price` / `_macro` suffix).
- Format: comma-separated tokens. Whitespace stripped per token. Empty
  tokens dropped. Case preserved (Yahoo tickers are case-sensitive;
  `^GSPC ≠ ^gspc`).
- Defaults live in the adapter module as a module-level
  `_DEFAULT_<NOUN>: Final[tuple[str, ...]]` constant. Adapters MUST
  fall back to the default when:
  - the env var is unset, OR
  - the env var is set but yields zero non-empty tokens after parsing
- Adapters MUST NOT raise on parse failure — defaults are the
  fail-safe. The shared parser lives in `sources/_config.py`
  (added in extension Step 1) so all adapters use one path.
- Defaults must satisfy NFR-002 (free tier only): every default
  symbol/coin/series MUST be reachable on the source's free tier
  without paid upgrade.
- Operators set these env vars in `.github/workflows/daily-briefing.yml`
  if they want non-default coverage; absence of the env var is the
  hot path (zero-config operation).

---

## R13. Source-specific secret handling (extension 2026-05-01)

Applies when an adapter requires an authentication secret that varies
by deployment (currently: FRED API key; future candidates: NewsAPI key).

- Secrets read via `os.environ.get("<SECRET_NAME>")` at fetch time —
  never at module import (so test-suite imports do not require live
  secrets).
- Missing secret (env var unset OR empty string) → adapter raises
  `SourceFetchError(transient=False)` with a clear message
  (`f"{secret_name} not set; {adapter_name} adapter will not run"`)
  and `cause=None`.
- The aggregator catches per R6, the adapter contributes `[]`, the
  run continues with all other adapters. No special-casing for
  "secret missing" vs "source 5xx" — both are R6 isolation cases.
- The orchestrator's boot-time alert (u5) does NOT pre-check these
  secrets at startup. Failure surface stays at fetch time. Rationale:
  keeps R6 isolation pure (one path for all source-side failures) and
  avoids u5 needing per-adapter knowledge of which secrets exist.
- Secret values MUST NOT appear in:
  - log messages (the `_truncate_stderr` cap in `errors.py` is the
    last-line defense; adapters MUST NOT format the secret into
    error strings in the first place)
  - `raw_metadata` (NormalizedItem)
  - test fixtures (recorded fixtures use placeholder values like
    `"REDACTED_FOR_FIXTURE"`; the adapter substitutes the real value
    at request time)
- Adding a new secret-using adapter REQUIRES updating
  `.github/workflows/daily-briefing.yml`'s `env:` block to inject
  the secret from `secrets.<NAME>`. CI cannot inject what the
  workflow file doesn't ask for.

---

## R14. Source-required HTTP request headers (extension 2026-05-Q2)

Applies when a source's published policy requires specific HTTP headers
on every request (currently: SEC EDGAR fair-access User-Agent; future
candidates: any rate-limit-by-UA endpoint, contact-on-abuse endpoints,
APIs that mandate `Accept` / `From` / `X-Application-Id` for compliance).

This rule is the third axis of per-adapter request configuration,
distinct from R12 (user-overridable env-var lists) and R13 (deployment-
varying secrets):

| Axis | Concern | Storage | Override semantics |
|------|---------|---------|---------------------|
| R12 | symbol/coin/series lists | `_DEFAULT_*` ClassVar + env var via `_config.py` | operator may override |
| R13 | authentication secrets | `os.environ.get` at fetch time | per-deployment, never in code |
| R14 | source-mandated compliance headers | module-level `Final` constant in adapter file | NOT overridable — fixed by source policy |

### Rule body

- Required headers MUST be set per request, **in the adapter that
  consumes the source** — NOT in the shared `retry_get` helper. Other
  adapters MUST NOT silently send the same compliance string on
  unrelated requests; UA / `From` / etc. are source-specific.
- The header value lives as a module-level `Final` constant in the
  adapter file (e.g., `_USER_AGENT: Final = "investo investo@example.com"`
  in `sec_edgar_8k.py`). It is NOT a user-override env var (R12 is
  scoped to symbol/coin/series lists; compliance strings are not user
  choice). It is NOT a secret (R13 is scoped to deployment-varying
  authentication credentials; a public identifier of the requester
  is not auth).
- Header values MUST identify the project + a contact mailbox per the
  source's documented policy (SEC's fair-access policy explicitly
  mandates a contact email format like `"YourProjectName your@email"`).
  Generic UA strings (e.g., bare `"Mozilla/5.0"`, default httpx UA
  `"python-httpx/X.Y.Z"`) are forbidden — they violate SEC's policy
  and will be rate-limited or blocked.
- Adapters MUST pass the headers via the existing `retry_get` helper's
  `headers=` kwarg (already supported as of `_retry.py:163`). No new
  helper API. No bypass of the retry/timeout/Retry-After contract.
- Adding a new header-requiring adapter REQUIRES the PR description to
  cite the source's documented policy URL (e.g., SEC's "Accessing
  EDGAR Data" page) so future reviewers can verify the compliance
  string is up-to-date.
- Header values MUST NOT carry secret material. If a source mandates
  a header that contains a credential (e.g. `X-Api-Key`), that header
  is governed by R13, not R14 — the value lives in env, not in code.
