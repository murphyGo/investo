# Business Rules: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Status**: Complete

## Source and Identity Rules

### R1. Single fixed provider

HF Data Library is the sole u145 source. Runtime-configurable base URLs, fallback providers,
HTML scraping, browser automation, TradingView collection, and direct IEX PCAP downloads are
forbidden.

### R2. Closed request set

Only `SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY` are requested. Runtime symbol
extension is rejected. XLRE is never requested or substituted.

### R3. Benchmark authority

SPY is mandatory and defines the comparison calendar and snapshot `as_of`. Without a valid
SPY close series, no price metric, regime, or rank is public.

### R4. XLRE explicit absence

The public snapshot and page always contain XLRE with availability `unavailable`, reason
`provider_unavailable`, and no metric/rank/regime value. Silent omission and proxy mapping are
invalid states.

## Credential and Request Rules

### R5. Operator-owned credential

The API key must come from `HF_DATA_API_KEY` under operator ownership. Registration data,
email verification, key creation, and 30-day rotation are external operator actions.

### R6. Secret non-observability

The key is sent only in the documented `X-API-Key` header. It is absent from URLs, exceptions,
logs, fixtures, subprocess arguments, snapshot ids, cache keys, test names, and artifacts.

### R7. Conservative rate contract

Use no more than 100 requests/minute even where another provider page advertises a higher
limit. Concurrency and retries share one bounded request budget.

### R8. Fixed network envelope

HTTPS and the exact HF API host are mandatory. Redirects to another host, unbounded response
bodies, unbounded pagination, and provider text echoed to logs are rejected.

### R9. Probe before payload assumptions

Endpoint parameters, response schema, date representation, adjustment semantics, empty/error
shape, and row ordering are fixed only from a credentialed live probe. No implementation may
guess them from marketing copy.

## Bar and Calendar Rules

### R10. Daily-bar validity

Each row requires date-only identity, finite positive OHLC, `low <= open/close <= high`, and
non-negative integer volume. Duplicate dates, interior disorder, ticker mismatch, and future
dates fail that ticker.

### R11. Close-only metric input

u145 calculations consume only normalized close values and dates. Open/high/low/volume are
validated for source integrity but do not enter v1 metrics or rank.

### R12. Same-as-of comparability

A sector is comparable only when it contains the SPY `as_of` and every SPY calendar date
required by the metric window. Calendar gaps produce explicit missing reasons; they are not
forward-filled or interpolated.

### R13. Freshness

A new snapshot must represent the latest expected completed U.S. trading session within the
36-hour weekday target, accounting for weekends and market holidays. Unknown freshness blocks
promotion.

### R14. History depth

64 benchmark observations are required for full 63D calculations. Fewer observations may
produce `warming_up`; fewer than the minimum needed for truthful short metrics remain missing.

## Metric and Classification Rules

### R15. Source-neutral kernel, semantic wrappers

Mathematical kernels are shared with u139. u139 `nav_*` APIs and model bytes remain unchanged;
u145 exposes `iex_price_*` outputs. A generic name must not erase the reader-facing source
semantics.

### R16. Simple returns

`return_h = close_t / close_(t-h) - 1` on SPY calendar endpoints. No log return, dividend
reconstruction, interpolation, or annualization is applied to return fields.

### R17. Non-overlapping acceleration

Acceleration is current 5-trading-day SPY-excess return minus the immediately preceding,
non-overlapping 5-trading-day SPY-excess return. It requires dates `t-10`, `t-5`, and `t`.

### R18. Realized volatility

Twenty one close observations produce twenty daily simple returns. Sample standard deviation
is annualized by `sqrt(252)`. It is labeled IEX close-to-close realized volatility.

### R19. Drawdown

Twenty-one close observations produce the minimum `close / running_peak - 1` across the
20-session window. It is never called loss probability or risk forecast.

### R20. Regime policy

`sector-regime-v1` at 10 bps remains primary. Strength uses 21D SPY excess and acceleration
uses R17. Existing hysteresis and sensitivity bands are reused; public v1 need not display
the sensitivity table.

### R21. Rank denominator

Rank uses 5D/21D/63D SPY-excess midrank percentiles, requires at least eight comparable sectors
and two available horizons, and prints `rank/comparable_count`. Missing sectors are never placed
last as if they had a measured score.

### R22. Volume exclusion

IEX volume cannot enter return, acceleration, regime, rank, summary selection, color, quadrant,
or composite score. If shown in a later approved slice, it must be named `IEX activity sample`
and remain visually separate.

## Coverage and Output Rules

### R23. Fixed eleven-card surface

Every public render contains the eleven sector identities in fixed universe order or a clearly
documented deterministic ranked order with XLRE retained. Record count is always eleven.

### R24. Coverage state precedence

`insufficient > warming_up > partial > normal`. With HF v1, a valid production snapshot is
normally `partial` because XLRE is structurally unavailable. At least eight comparable sectors
plus SPY are required for a ranked radar.

### R25. Derived-only retention

Public and repository artifacts contain metrics, states, provenance, and coverage only. Daily
bar arrays, provider-shaped payloads, response headers, and raw request/response samples are
forbidden outside test fixtures recorded only after terms and probe approval.

### R26. Mandatory qualification language

The first viewport states `IEX venue sample`, `10/11 sectors available`, and `XLRE unavailable`.
The page may not say `미국 시장 전체`, `전체 거래량`, `자금 유입/유출`, or unqualified
`거래강도`.

### R27. Mandatory attribution

HF Data Library CC BY 4.0 attribution and the provider-required IEX citation/link appear in
the Markdown and machine provenance. Missing or malformed attribution blocks publication.

### R28. Deterministic pair

Markdown and JSON come from one immutable snapshot and share one SHA-256 snapshot id. Equal
normalized inputs and policy version produce byte-identical outputs.

### R29. First-publish fail closed

No placeholder, empty dashboard, or fabricated last-good artifact is created before the first
valid snapshot.

### R30. Last-good truth

On later collection failure, the valid prior derived pair may remain byte-identical. Its `as_of`
is never advanced, and the workflow exposes a stale status. A failed run never commits only a
freshness timestamp over old metrics.

### R31. Isolated activation

Five isolated GitHub Actions probes must pass before scheduled collection, MkDocs navigation,
or existing daily pipeline integration is enabled. Probe failures stay red and do not publish.

### R32. Private compatibility

u139 models, CLI, output bytes, privacy checks, and public non-interference tests must remain
green. u145 cannot reinterpret private NAV output as price evidence.

### R33. Phase boundary

Telegram, actual flow, earnings actual, constituent breadth, narrative generation, and
attention metrics remain out of scope regardless of source availability.
