# Code Generation Plan: u164 crypto-price-time-basis-repair

Date:2026-10-09. Status:PLANNED, Functional Design/NFR draft not approved.
Priority:P0-2. Estimate:8–16h plus qualification. [Design](../u164-crypto-price-time-basis-repair/design-brief.md).
Coverage:US-001/002/003/007/008; FR-001/006/008/010/017/021; NFR-001/002/003/005/006/007/008.

## Scope and steps

Reuse u1 CoinGecko, u54/u70 freshness, u95 budget, u152 watchpoints and u144 finalization. u138 US query2 repair is not this snapshot mismatch. No Binance/Coinbase integration, source-count bump, event/news activation or old archive rewrite in initial work.

- [ ] 1. Characterize previous UTC window vs current response with synthetic fixtures. Locate every `price_usd`/`pct_24h`/cap/volume/high/low reader via `rg` and characterize missingfield behavior.
- [ ] 2. Add validated optional snapshot clock in `sources/_window.py`, thread through `sources/aggregator.py` and `orchestrator/pipeline.py`. Preserve explicit override origin from `__main__.py`/runtime input; injected/default collection seams retain behavior.
- [ ] 3. Repair `sources/coingecko.py` timestamp eligibility and nullable/non-finite normalization. Preserve actual timestamps; add time-basis metadata, boundary/null/future tests.
- [ ] 4. Update located price/snapshot/watchpoint/visual/summary/public projection consumers and `briefing/segments.py` accounting to distinguish snapshot and target close. Verify actual final public text/cards without0-fill; retain existing core membership/6h staleness.
- [ ] 5. Verify Demo free access/attribution and GHA. If keyrequired, qualify free path before adding declared optional key in public daily and `ops/private-runtime/production-briefing.yml`, env/runtime tests. No Pro fallback or assumed key.
- [ ] 6. Validate focused/full/static/policy checks, source-spec/plugin parity and R13; record provider/historical gates separately.
- [ ] 7. After authorized integration/current-owner pin update, observe10 scheduled runs with usable coinvalues, truthful timebasis, finalization and public side effects.

## Validation and registration

Existing tests: `tests/unit/sources/test_coingecko.py`, `test_aggregator.py`, `test_window.py`, `test_source_specs.py`, `test_plugin_contract.py`; `tests/unit/briefing/test_segments.py`; located snapshot/watchpoint and public finalizer suites; public env/private runtime tests. Use MockTransport/frozen clocks, full pytest/Ruff/format/mypy/no-paid guards, `git diff --check`.

First repair: existing import/name `coingecko-price`, price/tierB, UTC crypto item/outcome routing via SOURCE_SPECS, `INVESTO_COINGECKO_COINS`;44adapters unchanged. A later qualified provider addition needs module/import, source-name, tier/window/item/outcome spec, core capability decision, config, fixtures, plugin count/names and consumer tests in its own plan.
