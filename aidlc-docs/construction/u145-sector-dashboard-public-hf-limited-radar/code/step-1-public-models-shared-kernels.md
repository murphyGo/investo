# u145 Step 1 — Public models and shared kernels

## Outcome

- Added frozen sibling public models for validated IEX bars, source-neutral value series,
  parsed/bundle state, public coverage, IEX-price metric slots, sector availability, provenance,
  snapshots, rendered pairs, and closed build outcomes.
- Pinned the fixed HF request set, `iex_venue_sample` scope, source id, adjustment/transport
  literals, exact HF Data Library and IEX attribution text/HTTPS links, and XLRE's structural
  value-free absence.
- Added `PublicCoverageSummary` rather than widening the frozen u139 type. Public warming-up now
  represents 6-63 benchmark observations and partial/normal requires 64+, while private model
  fields and serialized bytes remain unchanged.
- Extracted source-neutral return, excess, non-overlapping acceleration, volatility, drawdown,
  and descending-midrank kernels. Existing u139 `nav_*` functions remain public wrappers with
  their prior signatures, outputs, log-volatility convention, validation order, and messages.
  The shared volatility kernel requires an explicit `simple` or `log` convention so Step 3 can
  implement the approved public simple-return volatility without changing u139.

## Model invariants

- The only requested identities are SPY plus the ten qualified HF sector ETFs; XLRE cannot be
  requested, parsed, normalized, or placed in a value bundle.
- Parsed and close-only bundles partition every requested identity into exactly one success or
  closed failure. Bundle coverage, benchmark counts, provenance dates, and series end dates
  cross-check.
- Public snapshots contain exactly eleven fixed sector records. Provider-, transient-, and
  insufficient-history-unavailable records suppress every metric, regime, and rank value and
  must match `coverage.missing_tickers`. XLRE additionally requires the
  `provider_unavailable` diagnostic.
- Partial/normal records require all eleven price metric values plus complete primary regime and
  rank. Scope/source/attribution literals cannot be broadened through validation input.
- Public snapshots/bundles expose only derived close series or aggregates; no raw OHLCV arrays,
  signed URLs, request material, provider text, secrets, or account identity enter a public DTO.

## Compatibility and tests

- TS-1 covers JSON round-trip/order properties, invalid OHLC rows, exact request partition,
  public 64-row coverage thresholds, fixed provenance/attribution, XLRE absence, unavailable
  leakage, and closed outcome variants.
- TS-2 covers pure kernel invariants, property-tested u139 wrapper equivalence, fixed formula
  vectors, legacy validation messages, and the golden u139 wrapper digest
  `1edbea4830774b00938d1660d54c1be1140c2ff312e93e6c8b8e65f8222d5b73`.
- Final focused public/kernel tests: 33 passed.
- u139 plus public sector/model regression: 190 passed.
- Full repository suite: 4,388 passed in 277.04 seconds.
- `uv lock --check`, Ruff check, Ruff format check across 578 files, strict mypy across 256
  source files, and `git diff --check` passed.

## Review

Fresh-eyes review initially found one High invariant gap: `insufficient_history` was not included
in the unavailable suppression/coverage set. The model and two regressions were corrected.
Re-review found no remaining Critical, High, or Medium findings and independently reran the 33
focused tests plus scoped Ruff. Strong JSON parsing/canonical-byte verification for
`RenderedPublicSectorProjection` remains assigned to the already planned Step 4 renderer/store
boundary; substring presence is not treated as promotion validation.

## Scope boundary

Step 1 adds no network client, PyArrow dependency, secret access, workflow, repository/public
write, Pages navigation, schedule, Telegram path, or daily-briefing coupling. Step 2 remains the
first adapter step and requires separate approval.
