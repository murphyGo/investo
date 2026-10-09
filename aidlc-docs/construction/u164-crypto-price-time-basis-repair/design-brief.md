# u164 Functional Design / NFR: crypto price time basis

Status:DRAFT, 2026-10-09; not approved. Priority:P0-2.
Source facts/candidates: [review](../source-reliability-20261009/review.md).

## Confirmed defect and bounded scope

Existing `coingecko-price`/`sources/coingecko.py`, categoryprice/tierB/UTC crypto/core, `/coins/markets`, default bitcoin/ethereum/solana. Current aggregate USD price/24h change/cap/volume and source `last_updated` are not target-day closes.23/25runszero; live3/3 normalized timestamps fell outside the previous UTC day. One403 is a separate issue.

First repair explicitly supports **조회 시점 가격** in normal schedules using the existing provider. No historical close recovery is claimed. Preserve u54 freshness/u144 finalization/u152 observation contracts; no widening of news windows or new provider activation.

## Fixed contract

- `FetchWindow` gains optional immutable `price_snapshot_at: datetime | None = None`; default callers retain date filtering. Collector threads one run clock into this field only for normal scheduled operation without explicit target-date replay override.
- CoinGecko live mode accepts `snapshot_received_at - 6h <= last_updated <= snapshot_received_at`. Capture response receipt UTC after HTTP completes; clock is replaceable in offline tests. `price_snapshot_at` remains the single run reference and permission boundary, so an update during the request is not incorrectly rejected against run start. Keep `published_at=last_updated`; stale/future timestamps are excluded with diagnostics. Do not backdate or silently adjust clocks.
- Metadata: `price_time_basis=live_snapshot`, actual `price_as_of`, retrieval/reference `observed_at`, `report_target_date`. Prompts/snapshots/watchpoints/cards/summary disclose 조회시점가격 and as-of; no 전일종가 claim.
- Manual historical replay leaves snapshot fieldunset and excludes future current prices. Missing historical evidence remains missing.
- Missing/non-finite change/high/low/volume/cap is omitted through consumers, never0-filled. Retain a true provider zero only wherevalid. Unsupported OHLC and aggregate figures cannot be fabricated.
- Existing core/name/spec/tier/window/config remain. Core stale threshold is not relaxed. Binance exchange-only USDT/volume is not aggregate USD CoinGecko data.

## Candidate and credential gates

Current no-key request works locally, but current Demo docs require a key header. Record free account limits/attribution and GHA before activation; if needed `COINGECKO_DEMO_API_KEY` is read atfetch time, wired to both workflowtemplates, absent → isolated source failure, no Pro API/paid fallback. This is a proposed optional key path, not an existing credential.

History is defer: same-provider `/coins/{id}/history`, selected-date00UTC snapshot,00:35 availability, Demo365days/keyrequired; BTC local200 only. It is not anOHLC or24h change source.

Binance market-data-only `/klines` and Coinbase Exchange candles are defer: localBTC200, all-coins/GHA/region/publicdisplay terms unresolved. Binance same provider retains `binance-crypto-market`; Coinbase must use new `coinbase-crypto-close`. Coinbase max300/bucket rows outside range need filtering; USD/USDT and venue/global volume staydistinct. Qualify before separately registering any adapter.

## Acceptance / NFR

1. Normal schedule accepts3 valid current prices with original as-of and explicit label; historical replay receives none of those future prices.
2.6h/future/adjacent-day/null boundaries pass; missing optional figures never become0 through final output.
3. First repair retains44registry/spec parity and actual core freshness; historical readers do not treat snapshot asclose.
4. Key/provider rights/limits are explicit; no paid or auto-provider fallback. NFR-001/002/003/005/006/007/008: no extraHTTP for first snapshot repair, existing response/retrycaps, frozen injected clocks, R13 and offline tests.

Operations target: usable BTC/ETH/SOL≥9/10 distinct scheduled runs, accurate labels10/10. Candidate and credential gates stayopen if unqualified.
