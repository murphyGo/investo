# NFR Requirements: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Status**: Complete
**Approved Functional Design**: `aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/functional-design/`
**Requirements**: NFR-002, NFR-003, NFR-005, NFR-006, NFR-007, NFR-008,
US-001, US-003, US-008, US-010

## 1. Security, Rights, and Cost

### AC-1.1 Operator-owned credential boundary

`HF_DATA_API_KEY` is the only new credential. It is supplied by the operator through a
local environment variable or GitHub Actions secret. Code and workflows never register an
account, submit identity data, verify email, request/rotate a key, or persist the key outside
the process environment.

### AC-1.2 Header-only secret transmission

The key is sent only in the documented `X-API-Key` request header to
`https://api.hfdatalibrary.com`. It is never accepted from a CLI argument, config file,
query string, path, stdin, workflow input, artifact, or cache key. Cross-host redirects are
disabled.

### AC-1.3 Central redaction catalogue

`HF_DATA_API_KEY` is added to the project-wide `SECRET_ENV_VARS` catalogue. Its exact runtime
value is redacted by the existing strict chokepoint across exceptions, logs, GitHub Step
Summary, diagnostics, publisher errors, and leak scans. Tests inject a sentinel secret and
prove absence from every output/log/error surface.

### AC-1.4 Credential validation

Missing, blank, placeholder, whitespace/control-containing, or overlong key input fails before
network access with one closed `auth.configuration` code. The rejected value and its length
are not logged. HTTP 401/403 produces `auth.rejected` without response body or headers.

### AC-1.5 Rights and attribution closure

Every public projection contains both approved entries:

- HF Data Library attribution under CC BY 4.0;
- the exact IEX historical-data attribution text/link required by the source license.

Attribution ids/text/links are constants pinned by tests and machine provenance. Missing,
duplicate, reordered-to-hide, non-HTTPS, or changed-host attribution blocks publication.

### AC-1.6 Derived-only public retention

Repository, Actions artifacts/caches, Pages, fixtures, logs, and failure evidence contain no
daily raw OHLCV arrays, provider-shaped objects, response bodies/headers, account information,
or request material. Only the approved aggregate metrics, classifications, coverage,
freshness, and provenance are retained publicly.

### AC-1.7 Zero incremental service cost

u145 adds no paid API, paid plan, trial dependency, hosted server, database, browser service,
or third-party workflow. The documented HF free account is the sole runtime dependency.
`scripts/check_no_paid_apis.py` is extended to pin this identity and reject fallback providers.

### AC-1.8 Public wording leak guard

The rendered pair is scanned before staging for secrets, raw-bar shapes, credential fields,
internal paths, and forbidden unqualified market/flow/volume language. Scan failure is a hard
publication block and never falls back to partially redacted market data.

## 2. Network and Resource Safety

### AC-2.1 Fixed endpoint and request shape

The scheme, host, API version, endpoint path template, ticker allowlist, format, range, and
pagination parameters are code-owned. The implementation rejects runtime URL/symbol/format
overrides and does not follow redirects outside the exact host.

### AC-2.2 Timeout envelope

Each request uses at most 5 seconds connect, 10 seconds read, and 15 seconds total. The full
eleven-symbol collection, including retries, completes within 120 seconds on the GitHub Actions
reference runner or fails visibly.

### AC-2.3 Response envelope

One response is limited to 2 MiB compressed/on-wire bytes, 10,000 decoded rows, 128 fields per
row, nesting depth 8, and 256-character scalar strings. Exceeding any limit stops that ticker
before a large normalized object graph is allocated.

### AC-2.4 Conservative shared rate budget

All tasks and retries share a token budget of at most 100 HTTP requests in any rolling minute.
Initial v1 collection requires at most eleven successful calls plus bounded retries. The
implementation does not use the conflicting 300 requests/minute statement as authority.

### AC-2.5 Bounded concurrency and retry

At most three provider requests are in flight. Only timeout, 429, and 5xx classes are retryable,
for at most two retries per ticker with bounded exponential backoff and `Retry-After` capped at
30 seconds. 400/401/403/404/schema failures are not retried. Total retry sleep remains within
the AC-2.2 run budget.

### AC-2.6 Memory and CPU budget

On the reference GitHub Actions profile, normalization plus metrics/rendering for eleven series
of at most 10,000 rows each uses at most 256 MiB peak RSS above interpreter baseline and at most
30 seconds CPU after network completion. A synthetic maximum-shape benchmark records both.

### AC-2.7 No client-side source access

Generated Markdown/JSON/HTML contains no provider endpoint, auth header, JavaScript fetch,
embedded raw history, or browser-side API call. All provider access occurs in the isolated
server-side workflow process.

## 3. Reliability, Freshness, and Recovery

### AC-3.1 Benchmark-first fail-fast

SPY is requested and validated before sector work. Missing, malformed, stale, or insufficient
SPY stops new publication. No absolute-only sector radar is emitted as a fallback.

### AC-3.2 Ticker isolation and coverage threshold

One sector failure is isolated. A promotable partial snapshot needs SPY plus at least eight
comparable sector series. XLRE's structural absence is not counted as a request incident; every
other absence retains a closed reason code.

### AC-3.3 Market-calendar freshness

Freshness uses `America/New_York` and the versioned NYSE holiday calendar. A new snapshot must
match the latest expected completed session and stay within the 36-hour weekday objective.
When the calendar has no authoritative entry for the year/edge case, freshness is `unknown`
and promotion fails rather than assuming weekday-only behavior.

### AC-3.4 Pair integrity

`site_docs/sectors/index.md` and `site_docs/sectors/latest.json` form one validated pair with
the same snapshot id. A missing member, mismatched id, malformed schema, absent attribution,
or different source/as-of identity is never promotable or eligible as last-good.

### AC-3.5 Idempotency

Equal normalized inputs, policy versions, calendar version, and attribution constants produce
byte-identical JSON/Markdown. When the valid existing pair equals newly rendered bytes, the
run reports `unchanged` and performs no rewrite/commit.

### AC-3.6 Recoverable promotion

Both projections are prepared, fsynced where supported, validated, and registered in the
publisher's existing staged-file transaction before git commit. A pre-git failure restores or
retains the complete prior pair. Existing post-git `PublisherGitError` semantics remain honest;
u145 does not claim rollback after a remote push.

### AC-3.7 First-publish fail closed

Before one valid pair exists, any auth/source/freshness/coverage/projection failure writes no
public placeholder and does not add MkDocs navigation. The probe workflow exits non-zero.

### AC-3.8 Last-good hold

After launch, collection failure may leave the prior valid pair byte-identical. The prior
`as_of` and snapshot id remain unchanged. The run records `held_last_good`, exits non-zero in
probe/collection mode, and exposes a closed stale category to the page/status layer without
provider text. It never rewrites old metrics with a fresh timestamp.

### AC-3.9 Key-expiry observability

401/403 on a previously healthy workflow is categorized `auth.rejected` with a fixed operator
message that the 30-day key may require rotation. No automatic registration/rotation attempt
occurs. A manual probe must pass after rotation before schedule is considered healthy.

## 4. Data Integrity and Determinism

### AC-4.1 Numeric contract

Parse numeric fields as `Decimal`. Reuse u139's source-neutral kernels and current numeric
contract: ratios quantized to 10 decimal places with `ROUND_HALF_EVEN`; binary float is limited
to the already approved volatility logarithm/statistics path where applicable and converted
back through its stable decimal representation.

### AC-4.2 Semantic model separation

u139 `SectorSeriesBundle`, `SectorDashboardSnapshot`, `nav_*` fields, CLI, and artifact bytes
remain unchanged. u145 uses sibling public types and `iex_price_*` fields. Serialization cannot
accept a private snapshot where a public one is required or vice versa.

### AC-4.3 Adjustment evidence gate

`PublicAdjustmentPolicy` has no permissive default. Exact raw/split/dividend adjustment
semantics are fixed only after the credentialed live probe and official API documentation
agree. Unknown or contradictory semantics block Step 0 and implementation.

### AC-4.4 Calendar and ordering

Normalized dates are strictly ascending and unique. No forward fill, interpolation, timestamp
truncation across timezones, or provider-order-dependent tie break is allowed.

### AC-4.5 Metric invariants

Property tests cover constant series, scale invariance, identical sector/SPY excess zero,
non-overlapping acceleration identity, volatility non-negativity, drawdown range `[-1, 0]`,
midrank tie equality, and deterministic rank ordering.

### AC-4.6 Structural absence invariant

For every generated snapshot, XLRE is present exactly once, `provider_unavailable`, and has no
metric value, complete regime, or rank. Property/state tests reject every illegal combination.

### AC-4.7 Volume non-reachability

Tests use adversarially changed volume values with identical closes and prove the complete
snapshot and Markdown/JSON bytes are unchanged. Static call-graph/source tests prevent volume
from entering public metric/rank/regime/summary builders.

### AC-4.8 Projection round trip

PBT covers valid public snapshot JSON round-trip, stable ordering, and rejection of unknown
fields, missing provenance, wrong market scope, wrong source id, or malformed attribution.

## 5. Public UX and Accessibility

### AC-5.1 First-viewport scope disclosure

Before any rank or metric, the page visibly states `IEX venue sample`, `10/11 sectors`, `XLRE
unavailable`, and that the data is not whole-market volume or fund flow. The disclosure is not
inside `<details>` and is pinned by rendered-order tests.

### AC-5.2 Eleven-sector discoverability

All eleven sector identities are present on every page state. Unavailable sectors remain
distinguishable from measured laggards through text, not color alone.

### AC-5.3 Deterministic readable values

Display percentages and percentage points use two decimals with half-even rounding. Rank shows
`ordinal/comparable_count`. Missing metrics use `—` plus a textual availability reason.

### AC-5.4 Static mobile/accessibility gate

The page uses semantic headings/table headers, descriptive attribution links, no color-only
meaning, and existing MkDocs responsive behavior. Validate at 390×844 and desktop viewport
before Pages activation; the limitation banner and first four table columns remain readable.

### AC-5.5 Advice and narrative boundary

The deterministic renderer contains no generated causal narrative, prediction, target,
recommendation, overweight/underweight instruction, or personalized language. Existing public
language and leak scans run over the final bytes.

## 6. Operations and Activation

### AC-6.1 Separate workflow

Qualification runs in a dedicated manual workflow with least-privilege read access and no
Pages/deployment/write permission. It does not invoke the daily briefing pipeline, Telegram,
or publisher git push.

### AC-6.2 Five-run qualification

Five isolated GitHub Actions runs must succeed with fresh data before enabling schedule,
repository writes, Pages navigation, or deployment. Evidence records run id, commit, target
date, supported count, as-of, duration, request count, and closed status codes—never secret,
URL, response body, or raw bar.

### AC-6.3 Activation commit separation

The commit that adds probe-only code/workflow cannot also enable scheduled collection or Pages
navigation. Activation is a separate reviewed step after the five-run record is complete.

### AC-6.4 Rotation runbook

The runbook documents 30-day key replacement, secret update, manual probe, failure diagnosis,
revocation, and rollback/disable steps. It never stores identity data or the key itself.

### AC-6.5 Observability

One bounded summary reports source id, target/as-of, freshness, request success/failure counts,
coverage state, outcome, duration, and reason codes. Cardinality is bounded by the fixed ticker
set. Provider response text and per-row data are absent.

### AC-6.6 Regression gate

Before activation, focused tests, PBT, strict mypy, Ruff check/format, no-paid guard, leak scan,
workflow static validation, `mkdocs build --strict`, private u139 tests, and existing sector/public
pipeline regression tests all pass.

## Test Strategy IDs

- **TS-1**: model/PBT round-trip, ordering, invalid-state, XLRE structural absence.
- **TS-2**: pure metric invariants and u139 wrapper compatibility/golden hashes.
- **TS-3**: adapter fixtures for success, empty, malformed, oversized, duplicate, calendar,
  401/403/404/429/5xx/timeout, and redirect cases.
- **TS-4**: secret sentinel across logs, exceptions, summaries, artifacts, URLs, subprocess
  arguments, and leak scanners.
- **TS-5**: rendered pair, attribution, first-viewport order, forbidden wording/raw shape,
  volume non-reachability, and mobile/accessibility checks.
- **TS-6**: idempotent promotion, pair mismatch, first-publish failure, last-good hold, stale
  `as_of`, pre-git rollback, and post-git error semantics.
- **TS-7**: workflow permission/schedule/navigation negative assertions and five-run evidence
  schema.
- **TS-8**: maximum-shape response/parser benchmark and 120-second/256-MiB resource evidence.
