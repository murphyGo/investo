# Code Generation Plan: u164 crypto-price-time-basis-repair

Date:2026-10-09. Status:CODE COMPLETE — 6/7; operational qualification and step7 pending. Functional Design/NFR authorized by user development instruction.
Priority:P0-2. Estimate:8–16h plus qualification. [Design](../u164-crypto-price-time-basis-repair/design-brief.md).
Coverage:US-001/002/003/007/008; FR-001/006/008/010/017/021; NFR-001/002/003/005/006/007/008.

## Scope and steps

## Stage Decision

Functional Design and NFR Requirements: Required and completed in linked unit artifacts before code generation; new snapshot/replay/nullable display contract needs explicit rules. NFR Design: reuse u1/u54/u95 isolation, bounded retry and deterministic consumer patterns; separate stage skipped because no new logical component. Infrastructure Design: skipped, existing GitHub runtime and optional secret-header mechanism only. Requirement source is the listed FR/US/NFR IDs,25-run audit and user's explicit development/per-unit integration instruction. Public source, credential, GHA and operational acceptance gates remain separate.

Reuse u1 CoinGecko, u54/u70 freshness, u95 budget, u152 watchpoints and u144 finalization. u138 US query2 repair is not this snapshot mismatch. No Binance/Coinbase integration, source-count bump, event/news activation or old archive rewrite in initial work.

- [x] 1. Characterize previous UTC window vs current response with synthetic fixtures. Locate every `price_usd`/`pct_24h`/cap/volume/high/low reader via `rg` and characterize missingfield behavior.
- [x] 2. Add validated optional snapshot clock in `sources/_window.py`, thread through `sources/aggregator.py` and `orchestrator/pipeline.py`. Preserve explicit override origin from `__main__.py`/runtime input; injected/default collection seams retain behavior.
- [x] 3. Repair `sources/coingecko.py` timestamp eligibility and nullable/non-finite normalization. Preserve actual timestamps; add time-basis metadata, boundary/null/future tests.
- [x] 4. Update located price/snapshot/watchpoint/visual/summary/public projection consumers and `briefing/segments.py` accounting to distinguish snapshot and target close. Verify actual final public text/cards without0-fill; retain existing core membership/6h staleness.
- [x] 5. Verify Demo free access/attribution and prepare GHA wiring (local code complete; live GHA/credential qualification remains operational follow-up). If keyrequired, qualify free path before adding declared optional key in public daily and `ops/private-runtime/production-briefing.yml`, env/runtime tests. No Pro fallback or assumed key.
- [x] 6. Validate focused/full/static/policy checks, source-spec/plugin parity and R13; record provider/historical gates separately.
- [ ] 7. After authorized integration/current-owner pin update, observe10 scheduled runs with usable coinvalues, truthful timebasis, finalization and public side effects.

## Validation and registration

Existing tests: `tests/unit/sources/test_coingecko.py`, `test_aggregator.py`, `test_window.py`, `test_source_specs.py`, `test_plugin_contract.py`; `tests/unit/briefing/test_segments.py`; located snapshot/watchpoint and public finalizer suites; public env/private runtime tests. Use MockTransport/frozen clocks, full pytest/Ruff/format/mypy/no-paid guards, `git diff --check`.

First repair: existing import/name `coingecko-price`, price/tierB, UTC crypto item/outcome routing via SOURCE_SPECS, `INVESTO_COINGECKO_COINS`;44adapters unchanged. A later qualified provider addition needs module/import, source-name, tier/window/item/outcome spec, core capability decision, config, fixtures, plugin count/names and consumer tests in its own plan.

## Completion evidence

Full regression6292 passed/503.81s on main756c4e3f; independent review CLOSED with no open findings, including R13 key redaction and public card metric preservation. Independent final suites148 plus11 real publisher tests PASS. Ruff/format677/mypy292 and four policy guards PASS. Strict documentation/Material/diff checks PASS after final document update. The optional Demo credential is absent in the checked runtime environment; no private pin or activation was changed. Step5 live qualification and step7 ten scheduled observations remain explicit operational follow-up.
