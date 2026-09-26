# u145 Step 2 — Bounded HF adapter

## Outcome

- Added a fixed `https://api.hfdatalibrary.com/v1` adapter using an injected
  `httpx.AsyncClient`; the endpoint, host, daily/Parquet/clean query, request set, and User-Agent
  are not runtime-configurable.
- Implemented X-API-Key token acquisition followed by one same-host signed download. Signed URLs
  require HTTPS, the exact host and ticker path, a non-empty bounded query, no port, credentials,
  fragment, whitespace, or redirect. The API key is never forwarded to the download.
- Added benchmark-first collection for SPY plus ten sectors, concurrency three, shared rolling
  request accounting, two bounded retries with a fresh token, and complete sibling cancel/drain
  behavior. A clean collection is exactly 22 calls.
- Added strict token JSON and PyArrow Parquet boundaries. Only the seven qualified physical
  columns are accepted; on-wire, decoded, row-count, calendar, ordering, OHLC, volume, and source
  invariants fail closed. PiTrading rows are validated but discarded and only normalized IEX
  bars cross the adapter boundary.

## Secret and transport containment

- Empty, placeholder, whitespace/control-bearing, or oversized keys fail before network access.
  The key appears only in `X-API-Key` on the token request.
- Injected clients with request/response hooks, default query parameters, pre-existing cookies,
  or a mismatched budget fail before network access. Inherited headers are rebuilt from the
  fixed allowlist, and provider `Set-Cookie` state is cleared after every response.
- Central redaction includes `HF_DATA_API_KEY` and signed HF URLs. HTTPX and HTTPCore transport
  logs are rendered as a closed marker so keys, signed queries, provider response headers, and
  transport exception text do not escape.
- Transport/provider exception text, response bodies, raw JSON, signed URLs, raw Parquet, account
  identity, and raw OHLCV structures are never returned or persisted.

## Dependency and policy guard

- Added exact optional dependency `sector = ["pyarrow==25.0.1"]` and updated the lock. Quality CI
  installs the sector extra, preventing PyArrow schema tests from silently skipping.
- Extended the no-paid guard with an AST contract for this sole-provider adapter. It requires
  each fixed identity assignment exactly once, pins the exact token/download call sites and one
  direct request build/send path, and rejects non-allowlisted providers/imports, constructed or
  reassigned hosts, runtime endpoints, additional clients/requests, bound network-method aliases,
  reflective access, and extra network sinks.

## Tests and review

- TS-3/TS-4 cover exact request order/count/header/query, hostile signed URLs, status/retry/
  timeout/redirect behavior, JSON/resource/schema/row failures, IEX normalization, rolling rate
  and collection budgets, concurrency, cancellation draining, secret/log containment, client
  state, dependency pinning, and configuration ceilings. All provider payloads are synthetic.
- Step 2 focused adapter/redaction/policy/workflow tests: 175 passed in 6.04 seconds.
- Step 1+2 focused regression: 208 passed.
- Full repository suite: 4,493 passed in 273.40 seconds.
- Ruff check/format over 580 files, strict mypy over 257 source files, lock check, Anthropic and
  paid-provider policy guards, strict MkDocs, Material theme contract, and diff integrity passed.
- Fresh-eyes review drove closure of every discovered High/Medium issue. Final review found no
  remaining Critical, High, or Medium findings.

## Scope boundary

Step 2 made no live API call and added no snapshot computation, renderer/store, probe workflow,
scheduled/public workflow, Pages navigation, repository write, Telegram path, or daily-briefing
coupling. Step 3 is the next construction boundary; public activation remains gated on five
successful isolated Step 5 probes and separate Step 6 approval.
