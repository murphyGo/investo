# u145 Step 3 — Public snapshot computation

## Outcome

- Added the derived-only boundary from normalized HF/IEX bar series to a fixed eleven-record
  public sector snapshot. SPY owns the common as-of date; freshness is resolved against the
  versioned 2026 NYSE calendar and fails closed outside that calendar.
- Reduced every accepted input to at most 64 dates and closes before calculation. Public bundles
  contain no open, high, low, or volume fields, and tests prove changes to those input fields
  cannot change either the bundle or the final snapshot.
- Enforced the approved coverage states: fewer than six SPY observations, fewer than eight
  comparable sectors, or any non-fresh benchmark yields `insufficient`; 6-63 observations yield
  `warming_up`; 64 observations with ten supported sectors yields `partial` because XLRE remains
  structurally absent.

## Metrics, regime, and rank

- Public metrics use shared source-neutral kernels with the price contract selected explicitly:
  simple 1/5/21/63-day return and excess return, 5-day relative acceleration, 20-day simple
  realized volatility, and 20-day maximum drawdown.
- Warming inputs expose only approved 1-day and 5-day return/excess values. Longer horizons,
  acceleration, volatility, drawdown, regime, and rank carry `warming_up` rather than fabricated
  values.
- Full inputs reuse the fixed `sector-regime-v1` policy and deterministic descending midrank
  percentiles with 5/21/63-day weights of 20/50/30 percent. Ties and input mapping order remain
  deterministic.
- Calendar gaps, insufficient history, provider failure, benchmark absence, and numeric failures
  preserve their exact closed reason through metrics, regime, rank, availability, and diagnostics.
  XLRE is always an eleven-card placeholder with no metrics, regime, or rank.

## Provenance and identity

- Every bundle and snapshot pins source id `hf-data-library-iex-daily-v1`, market scope
  `iex_venue_sample`, target/as-of dates, split/dividend-clean adjustment, non-consolidated market
  status, and the required HF Data Library CC BY 4.0 plus IEX attributions.
- The snapshot id is `sha256:` plus the digest of canonical UTF-8 JSON with sorted keys and compact
  separators, excluding the id field itself. The test recomputes this digest independently.
- Model and computation invariants both reject a non-fresh snapshot or manipulated bundle unless
  coverage is `insufficient`, preventing stale rank/regime publication through payload relabeling.

## Tests and review

- Step 3 added 14 focused snapshot-computation tests covering fresh/stale/unknown calendar states,
  coverage thresholds, warming behavior, simple-return semantics, all missing paths, fixed record
  order, deterministic identity, volume non-reachability, and stale-payload bypass attempts.
- Combined u145 Step 1-3 model/kernel/adapter/snapshot and policy regressions: 219 passed.
- Full repository suite: 4,504 passed in 457.06 seconds.
- Ruff check/format over 582 files, strict mypy over 258 source files, lock check, Anthropic and
  paid-provider policy guards, strict MkDocs, Material theme contract, and diff integrity passed.
- Fresh-eyes review initially found two High and one Medium issue: collapsed calendar reasons,
  recomputation from a relabeled stale bundle, and insufficient independent hash/invariant tests.
  The implementation and tests were hardened; final re-review reported zero remaining Critical,
  High, or Medium findings.

## Scope boundary

Step 3 used synthetic bars only. It made no live provider call and added no renderer, artifact
store, workflow, schedule, Pages navigation, repository/public write, Telegram path, or
daily-briefing coupling. Step 4 renderer and derived-only store is the next construction boundary;
activation remains gated on five successful isolated Step 5 probes and separate Step 6 approval.
