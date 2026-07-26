# u138 Code Summary

**Unit**: `u138 price-source-endpoint-lifecycle-repair`
**Status**: Complete (6/6)
**Production closeout**: 2026-07-26

## Delivered

- Consolidated Yahoo snapshot and history parsing on query2 with the fixed
  `range=1y`, `interval=1d` contract.
- Preserved critical-first collection, enrichment isolation, per-ticker
  failure isolation, target-date replay bounds, and R12 critical-basket
  overrides.
- Added same-run history fallback and one truthful `yfinance-price` outcome
  before generation, coverage, visuals, quality, publication, and notification.
- Retired both Stooq runtime adapters, identities, routes, core-source entries,
  and request literals.
- Added `yonhap-index-close` and `fred-fx-close`. Yonhap requires an exact
  target-date RSS `pubDate`; FRED emits DEXKOUS with the existing redacted key
  path.
- Split consecutive source degradation from pipeline failure alerts. Successful
  and partial pipeline states now receive truthful, distinct operator headings.

## Review Corrections

Fresh-eyes review found and closed four issues before production:

1. Yonhap stale/future RSS headlines could be relabelled with the replay date.
2. A partial pipeline could receive a contradictory success heading.
3. History fallback could bypass `INVESTO_YFINANCE_TICKERS`.
4. Direct Yahoo snapshots could select a post-target row in a historical replay.

The follow-up review confirmed all four closed with no new findings.

## Validation

- Ruff check and format: pass.
- mypy: 248 source files, no issues.
- pytest: 4099 passed.
- no-paid API and Anthropic-SDK guards: pass.
- strict MkDocs build and `git diff --check`: pass.
- Exact GHA replay:
  [`30200378661`](https://github.com/murphyGo/investo/actions/runs/30200378661).
- Pages deployment:
  [`30200904739`](https://github.com/murphyGo/investo/actions/runs/30200904739).
- Production content commit: `ce6ab25`.

## Residual Degradation

The replay remained fully publishable but reported five independent auxiliary
source failures: missing BEA and Congress keys, Binance HTTP 451, CNBC HTTP 403,
and malformed Korea policy RSS XML. These are now reported as source
degradation, not as a failed briefing.
