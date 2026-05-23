# Code Generation Plan: `u66 crypto-channel-depth`

**Date**: 2026-05-24
**Unit**: u66 crypto-channel-depth
**Stage**: Code Generation
**Status**: Planned (awaiting approval)
**Source**: 2026-05-24 ten-subagent reader-facing review — Gap A (크립토 채널 깊이), independently raised by the 크립토 투자자 + 신뢰성 personas; latest local crypto briefing `archive/crypto/2026/05/2026-05-22.md`
**Estimated Effort**: ~7-10 h
**Dependencies**:
- u1 sources (adapter plugin pattern, registry, `FetchWindow`, flat `raw_metadata`)
- u8 market-aware source window (UTC crypto window handling)
- u45 segment routing exclusivity (`_CRYPTO_ONLY_SOURCES`)
- u49 deterministic market anchor (anchor-table surface)
- u55 core-fact mapping (`core_fact:*` raw_metadata prefix)
- u56 compliance-language-and-observational-tags (crypto disclaimer and observational wording)
- u57 segment-narrative-scope-and-time-reconciliation (segment scope and shared macro boundary)
- u58 crypto-regulation-policy-sources (official policy source priority)

**Downstream consumer**: **u74 market-channel-depth-v2** is implementation-blocked on this unit. u74 consumes the crypto indicator interface that **this plan defines** (see "u74 Interface Contract"). The raw_metadata key names / units fixed here are the contract u74 renders.

---

## Problem Statement

The latest local crypto briefing (`archive/crypto/2026/05/2026-05-22.md`) is readable but still shaped like an equity close recap. It gives BTC/ETH price, policy news, DeFi TVL, and The Block headlines, but it does not show the crypto-native state a crypto reader expects before reading the prose:

1. **No sentiment / breadth / positioning anchor** — there is no Fear & Greed value, BTC dominance line, funding rate, or open interest, so the reader cannot separate a single BTC move from broad market risk appetite or leverage positioning.
2. **No explicit 24h frame contract** — the header table still uses `종가` and the prose says `마감`, even though the crypto market is 24/7 and the generation window is UTC `[2026-05-22T00:00Z, 2026-05-23T00:00Z)`.
3. **Source status conflates "unavailable source" with "signal absent"** — `binance-crypto-market` returned 451, `coingecko-price` returned 0 rows. The rendered body does not separate the two.
4. **Derivatives indicators partly confirmed** — the lead live reachability probe (2026-05-24) confirmed **BTC 펀딩비 and 미결제약정(OI) ARE reachable no-key, geo-safe** via Bybit v5 (primary) → OKX (fallback), so they are IN scope. **24h 청산 (Coinglass) and 거래소 netflow (CryptoQuant/Glassnode) have no no-key source** and render as explicit unavailable rows (scope-out → TECH-DEBT).

This unit is the crypto-depth owner. It must not reopen generic source quality (u54/u62/u65), numeric fact validation (u55), first-viewport layout (u51/u61/u71), or cross-channel depth presentation (u74).

## Goal

Give the crypto briefing a small, deterministic native indicator block and a UTC 24h framing contract, and define the crypto indicator interface that u74 consumes. The implementation lands only no-key, fixture-backed indicators (lead live probe 2026-05-24 confirmed all four):

- Fear & Greed from Alternative.me.
- BTC dominance and global crypto market totals from CoinGecko global market data.
- BTC 펀딩비 + 미결제약정(OI) from Bybit v5 (primary) → OKX (fallback) — both no-key, geo-safe (NOT Binance: GHA 451).
- Existing DeFiLlama TVL/stablecoin data kept as the DeFi structure input.
- Explicit "unavailable" rows only for **24h 청산 and 거래소 netflow** (no no-key source confirmed) — scope-out → TECH-DEBT, never fabricated.

## Existing Coverage / Deduplication

- u54/u62/u65 own source status, public quality reconciliation, and offline replay. u66 consumes their status values and adds crypto-native data surfaces only.
- u55 owns numeric verification and stale fact gates. u66 adds new `raw_metadata` fields and anchor rows, then relies on u55-style tests for numeric consistency.
- u56 owns compliance language and the crypto disclaimer. u66 uses observational labels only and does not change banned phrase catalogues.
- u57 owns segment boundaries and shared macro injection. u66 routes new indicators to `crypto` only and does not change shared macro matching.
- u58 owns official U.S. crypto policy sources. u66 does not add policy adapters.
- u74 owns cross-channel presentation after u66/u67. u66 **defines** the crypto indicator raw_metadata contract that u74 consumes (see below).

## Scope Boundary

In scope:
- Add `alternative-fng` source adapter for the Alternative.me Fear & Greed endpoint.
- Add `coingecko-global-market` source adapter for CoinGecko `/api/v3/global` market totals and dominance.
- Add `bybit-derivatives` source adapter (BTC 펀딩비 + OI from one Bybit v5 tickers call) with an `okx-derivatives` fallback on Bybit terminal failure. Both no-key, geo-safe; Binance is NOT primary (GHA 451).
- Define a `CryptoIndicator` rendering contract in publisher/briefing helpers with fixed rows: Fear & Greed, BTC dominance, total market cap, 24h market-cap change, DeFi TVL, stablecoin supply, BTC 펀딩비, BTC OI, and explicit unavailable rows for 24h 청산 / 거래소 netflow.
- Change crypto anchor/table wording from equity close language to UTC 24h snapshot language.
- Add prompt context so Stage 2 explains crypto-native indicators without inventing unavailable values.
- Add replay/fixture tests covering the 2026-05-22 defect class.

Out of scope (no no-key free source confirmed — scope-out → TECH-DEBT at closeout, next free ids expected DEBT-071 / DEBT-072):
- **24h 청산 (롱/숏 liquidations)** — Coinglass returns `{"code":"30001","msg":"API key missing"}`; no no-key aggregate liquidation source exists.
- **거래소 netflow** — CryptoQuant / Glassnode are paid / key-required.

Also out of scope:
- Paid APIs, exchange-authenticated (signed) APIs, browser scraping, and Coinglass HTML scraping.
- Binance fapi as the primary funding/OI source (GHA IP 451 geo-block — optional last resort only, with the risk recorded).
- Portfolio/account features, exchange balances, tax advice, and trading recommendations.
- Refactoring generic source health or quality-history severity.
- Backfilling old archives.
- Changing domestic or US-equity anchor wording.

## u74 Interface Contract (raw_metadata key naming / units — load-bearing)

u74 consumes these keys to render its crypto anchor rows. Adapters MUST emit exactly these flat string-typed keys (the `_MetadataValue` union forbids nested dicts; all values stringified per R8). `indicator` is the single disambiguator u74 switches on. No new `Category` enum value is added — all four indicators are `category="macro"`, routed crypto-only.

| u74 row key | Indicator | raw_metadata keys | Value form (string) | Unit | Producer source_name |
|-------------|-----------|-------------------|---------------------|------|----------------------|
| `fear_greed` | 공포·탐욕 지수 | `indicator="fear_greed"`; `value`; `classification`; `window="utc_24h"` | `value`: int 0-100 as str; `classification`: e.g. `"Fear"` | index (0-100) | `alternative-fng` |
| `btc_dominance` | BTC 도미넌스 | `indicator="global_market"`; `btc_dominance_pct` | decimal as str (e.g. `"54.12"`) | % | `coingecko-global-market` |
| (total market cap) | 전체 시총 | `indicator="global_market"`; `total_market_cap_usd`; `market_cap_change_24h_pct` | USD/percent as str | USD / % | `coingecko-global-market` |
| `funding_oi_liquidation` (funding) | BTC 펀딩비 | `indicator="btc_funding"`; `btc_funding_rate`; `funding_source` | rate as str (e.g. `"0.0001"`); `funding_source` ∈ {`"bybit"`,`"okx"`} | rate per funding interval | `bybit-derivatives` / `okx-derivatives` |
| `funding_oi_liquidation` (OI) | BTC OI | `indicator="btc_oi"`; `btc_oi_usd`; `oi_source` | USD notional as str | USD | `bybit-derivatives` / `okx-derivatives` |
| `funding_oi_liquidation` (liquidation) | 24h 청산 | — | — | — | **absent** (scope-out → u74 renders `not_yet_available`) |

None of these indicators map to an existing `CoreFact`, so they do NOT register `core_fact:*` keys (non-core context, `warn` not `unverified`, per u55). u74 must consume these keys; it must not invent or re-derive them. `btc_price_24h` / `eth_price_24h` (u74 crypto rows 1-2) remain produced by the existing `coingecko-price` adapter — u66 does not change those.

## Free-Source Reachability

Lead live reachability probe (2026-05-24, confirmed) + this-workspace spot check:

| Need | Fixed source | Endpoint | Result | Data contract |
|------|--------------|----------|--------|---------------|
| Fear & Greed | `alternative-fng` | `https://api.alternative.me/fng/?limit=1` | HTTP 200, no-key | `data[0].value`, `value_classification`, `timestamp`, `time_until_update` |
| BTC dominance / global totals | `coingecko-global-market` | `https://api.coingecko.com/api/v3/global` | HTTP 200, no-key (rate ~5-15/min → once/day OK) | `data.market_cap_percentage.btc`, `data.market_cap_percentage.eth`, `data.total_market_cap.usd`, `data.total_volume.usd`, `data.market_cap_change_percentage_24h_usd`, `data.updated_at` |
| BTC 펀딩비 + OI (primary) | `bybit-derivatives` | `https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT` | HTTP 200, no-key, no geo-block | `result.list[0].fundingRate`, `result.list[0].openInterest`, `result.list[0].openInterestValue` |
| BTC 펀딩비 (fallback) | `okx-derivatives` | `https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP` | HTTP 200, no-key | `data[0].fundingRate` |
| BTC OI (fallback) | `okx-derivatives` | `https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USD-SWAP` | HTTP 200, no-key | `data[0].oiUsd` |
| DeFi TVL / stablecoin supply | existing `defillama-market-structure` | `https://api.llama.fi/v2/chains`, `https://stablecoins.llama.fi/stablecoins?includePrices=true` | existing adapter + HTTP 200 spot check | Reuse current `NormalizedItem` output; do not add a second DeFi adapter |

**Precedence**: 공포·탐욕 = Alternative.me (single). 도미넌스 = CoinGecko `/global` (single). 펀딩비/OI = **Bybit primary → OKX fallback** (both no-key, geo-safe). Binance fapi is NOT primary — sandbox 200 but **GHA IP 451 geo-block** (crypto archive already shows `binance-crypto-market` status 451); optional last resort only, with the risk recorded.

Confirmed unreachable no-key (scope-out → TECH-DEBT):

| Need | Source | Result |
|------|--------|--------|
| 24h 청산 (롱/숏) | Coinglass | ❌ `{"code":"30001","msg":"API key missing"}` |
| 거래소 netflow | CryptoQuant / Glassnode | ❌ paid / key required |

These two rows default to `not_available_no_key_source` and are never fabricated. A future unit may promote a row only after a no-key JSON endpoint has a recorded fixture, R10 replay coverage, and a stable upstream terms check.

## Stage Decision

Functional Design is **REQUIRED (lightweight)** because this unit adds source adapters (including a non-trivial Bybit→OKX funding/OI precedence) and a new crypto indicator presentation contract. Extend the u1 source FD with:

- L6.13 `alternative-fng`
- L6.14 `coingecko-global-market`
- L6.15 `bybit-derivatives` (+ `okx-derivatives` fallback) — funding/OI precedence algorithm
- R16 crypto indicator contract: no-key indicators (Fear & Greed, dominance, funding, OI) may render values via the u74 raw_metadata contract; only 24h 청산 / netflow (no no-key source) render explicit unavailable rows. UTC-24h frame replaces 전일 종가 for the crypto segment.

NFR Requirements are **SKIPPED**. The implementation adds no secrets, no paid vendor, no new library, and no new availability envelope. It uses existing async `httpx` retry and per-source isolation; no XML so `defusedxml` is not invoked. Cost remains zero. Consistent with u67 (domestic-channel-depth, reused source/anchor stack without an NFR pass).

## Implementation Steps

### Step 1 - Register source contracts and fixtures

- [ ] Add recorded HTTP fixtures under `tests/unit/sources/fixtures/api/alternative-fng/`, `tests/unit/sources/fixtures/api/coingecko-global-market/`, `tests/unit/sources/fixtures/api/bybit-derivatives/`, and `tests/unit/sources/fixtures/api/okx-derivatives/` (pin the lead 2026-05-24 live payload shapes; if a live re-probe is blocked in sandbox/GHA, fall back to those captured shapes and note the divergence).
- [ ] Record success + empty + malformed + auth/error fixtures per source (R10 four-path coverage).
- [ ] Add FD entries L6.13/L6.14/L6.15 and R16 in the u1 source functional-design docs.
- [ ] Document env-var policy: all adapters have no default symbol list and no required secret; pin the Bybit→OKX precedence (Binance NOT primary; 451 risk recorded).
- [ ] Acceptance: fixture files contain the exact fields listed in Free-Source Reachability; docs state the no-key contract and precedence; no paid key introduced.

### Step 2 - Implement `alternative-fng` adapter

- [ ] Add `src/investo/sources/alternative_fng.py` with `AlternativeFearGreedAdapter.name = "alternative-fng"` and `category = "macro"`.
- [ ] Parse `value` as float-compatible string, preserve `value_classification`, and derive `published_at` from the Unix `timestamp` in UTC.
- [ ] Emit one `NormalizedItem` titled `Crypto Fear & Greed {value} ({classification})`.
- [ ] Store flat `raw_metadata`: `indicator=fear_greed`, `value`, `classification`, `timestamp`, `time_until_update`, `window=utc_24h`.
- [ ] Register the module in `src/investo/sources/__init__.py`.
- [ ] Acceptance: malformed payload raises `SourceFetchError` only for source-level schema failure; missing optional `time_until_update` becomes an empty string; R13 no secret.

### Step 3 - Implement `coingecko-global-market` adapter

- [ ] Add `src/investo/sources/coingecko_global_market.py` with `CoinGeckoGlobalMarketAdapter.name = "coingecko-global-market"` and `category = "macro"`.
- [ ] Fetch `https://api.coingecko.com/api/v3/global` through the shared `retry_get` path.
- [ ] Emit one `NormalizedItem` titled `Global crypto market cap ${total_market_cap_usd}; BTC dominance {btc_pct}%`.
- [ ] Store flat `raw_metadata`: `indicator=global_market`, `btc_dominance_pct`, `eth_dominance_pct`, `total_market_cap_usd`, `total_volume_usd`, `market_cap_change_24h_pct`, `updated_at`.
- [ ] Register the module in `src/investo/sources/__init__.py`.
- [ ] Acceptance: missing BTC dominance or total market cap drops the item with source-level schema failure; no nested metadata is written.

### Step 3b - Implement `bybit-derivatives` adapter (+ OKX fallback)

- [ ] Add `src/investo/sources/bybit_derivatives.py` with `BybitDerivativesAdapter.name = "bybit-derivatives"` and `category = "macro"`.
- [ ] One Bybit v5 `tickers` call yields two items: `indicator=btc_funding` (`btc_funding_rate`, `funding_source=bybit`) and `indicator=btc_oi` (`btc_oi_usd`, `oi_source=bybit`).
- [ ] Add the OKX fallback path on Bybit terminal failure (`okx-derivatives`): fetch OKX funding-rate + open-interest, emit the same contract keys with `funding_source=okx` / `oi_source=okx`.
- [ ] Do NOT wire Binance fapi as primary; if added at all it is optional last resort with the GHA 451 risk noted (prefer NOT adding it). Per-source isolation: a funding/OI failure must not drop other crypto items.
- [ ] Register the module(s) in `src/investo/sources/__init__.py`.
- [ ] Acceptance: Bybit-success fixture yields funding + OI items; Bybit-failure → OKX fixture yields the same contract keys with `*_source=okx`; no nested metadata; R13 no secret.

### Step 4 - Route and prioritize crypto-native indicators

- [ ] Add `alternative-fng`, `coingecko-global-market`, `bybit-derivatives`, and `okx-derivatives` to `_CRYPTO_ONLY_SOURCES` in `src/investo/briefing/segments.py`.
- [ ] Add candidate-preservation priority so these native indicators survive crypto candidate caps before generic news, while preserving u58 official policy priority above them.
- [ ] Keep the indicators crypto-only; no fan-out to domestic-equity, us-equity, or shared macro. Absence must not flip crypto coverage status (mirror the existing `binance-crypto-market` "must not downgrade otherwise usable coverage" note).
- [ ] Acceptance: `segment_items()` routes the adapters only to `crypto`; cap tests show u58 policy items remain ahead of native indicators; absence does not downgrade crypto status.

### Step 5 - Define the crypto indicator block

- [ ] Add a pure helper, `src/investo/publisher/crypto_indicators.py`, that extracts indicator rows from crypto `NormalizedItem` inputs keyed off the `indicator` raw_metadata tag.
- [ ] Render a deterministic markdown table before crypto §①, after `## 한눈에 보기` and the shared macro block insertion point.
- [ ] Fixed rows and labels:
  - `공포·탐욕`: value + classification from `alternative-fng`, else `수집 안 됨`.
  - `BTC 도미넌스`: percent from `coingecko-global-market`, else `수집 안 됨`.
  - `전체 시총`: USD compact number + 24h change from `coingecko-global-market`, else `수집 안 됨`.
  - `BTC 펀딩비`: rate + source tag from `bybit-derivatives`/`okx-derivatives`, else `수집 안 됨`.
  - `BTC 미결제약정`: USD notional + source tag, else `수집 안 됨`.
  - `DeFi TVL`: current existing DeFiLlama item value, else `수집 안 됨`.
  - `스테이블코인 공급`: existing DeFiLlama stablecoin value, else `수집 안 됨`.
  - `24h 청산 / 거래소 순유출입`: `무료 검증 소스 미확정`.
- [ ] Acceptance: the renderer never invents unavailable values and is idempotent on repeated formatting passes; values are deterministic (LLM may not invent numbers).

### Step 6 - Replace equity close wording with UTC 24h framing

- [ ] Update `src/investo/publisher/anchor_table.py` so crypto tables label the first column as UTC 24h snapshot language, while domestic/us tables keep current wording.
- [ ] Update `src/investo/briefing/prompts.py` crypto instructions: use "UTC 24h 기준", "스냅샷", and "구간 내 변동"; avoid "전일 종가" and equity-market close framing for crypto.
- [ ] Update `src/investo/visuals/cards.py` crypto card captions to match UTC 24h framing.
- [ ] Acceptance: rendered crypto markdown for a fixture window contains `UTC 24h` wording and no `전일 종가` phrase outside quoted source titles; equity segments unchanged.

### Step 7 - Stage 2 prompt grounding

- [ ] Add a compact `{crypto_indicator_context}` payload for crypto Stage 2 only.
- [ ] Include the confirmed indicators (Fear & Greed, dominance, funding, OI) plus explicit unavailable row states (24h 청산 / netflow).
- [ ] Prompt rule: the LLM may explain available indicator direction observationally (u56 gate unchanged), and must state unavailable rows as unavailable rather than omit or infer them; no cross-segment leakage (u57 / `cross_segment_lint`).
- [ ] Acceptance: prompt snapshot tests show crypto-only context injection; domestic/us prompts are byte-compatible apart from shared template version comments already present.

### Step 8 - Tests and replay validation

- [ ] Add unit tests for the new adapters with recorded fixtures and malformed payload fixtures (R10 four-path); funding/OI Bybit→OKX precedence tests.
- [ ] Add routing tests in `tests/unit/briefing/test_segments_exclusivity.py` (crypto-only; absence does not downgrade status).
- [ ] Add renderer tests for full/partial/missing indicator rows.
- [ ] Add a raw_metadata contract test asserting the exact `indicator` / key names / units u74 consumes (contract pin).
- [ ] Add crypto anchor wording tests in `tests/unit/publisher/test_anchor_table.py` and card-caption tests in `tests/unit/visuals/test_cards.py`.
- [ ] Add one offline replay fixture derived from `archive/crypto/2026/05/2026-05-22.md` showing the new indicator block and UTC 24h wording.
- [ ] Acceptance: targeted source/briefing/publisher/visual tests pass; ruff + mypy strict clean on changed scope.

### Step 9 - Documentation and closeout

- [ ] Update `docs/tech-env.md` with the no-key public crypto indicator sources (Alternative.me, CoinGecko global, Bybit, OKX).
- [ ] Update `aidlc-docs/aidlc-state.md` from Backlog to In Progress/Complete during implementation, preserving the plan link.
- [ ] Register the two scope-out TECH-DEBT items (next free ids, expected DEBT-071 liquidation / DEBT-072 netflow) at closeout.
- [ ] Write `aidlc-docs/construction/u66-crypto-channel-depth/code/summary.md` with AC traceability, FD divergences, and the scope-out debt.
- [ ] Run `git diff --check` and `mkdocs build --strict`.
- [ ] Acceptance: code summary exists, docs build strict passes, scope-out debt registered.

## Step Dependency Graph

```
Step 1 (contracts + fixtures + precedence)
  ├─> Step 2 (fng adapter)
  ├─> Step 3 (global-market adapter)
  └─> Step 3b (funding + OI adapter, Bybit→OKX)
        └─> Step 4 (routing/priority)  ── needs 2 + 3 + 3b
              └─> Step 5 (indicator block)
                    └─> Step 6 (UTC 24h frame)
                          └─> Step 7 (Stage 2 prompt grounding)
                                └─> Step 8 (tests + replay) ─> Step 9 (docs + closeout)
```

## Acceptance Criteria

1. Crypto briefings render a native indicator block containing Fear & Greed, BTC dominance, total crypto market cap, BTC 펀딩비, BTC OI, DeFi TVL, stablecoin supply, and explicit unavailable rows for 24h 청산 / 거래소 netflow.
2. `alternative-fng`, `coingecko-global-market`, and `bybit-derivatives` (+ `okx-derivatives` fallback) are no-key source adapters with recorded fixtures, flat metadata, per-source isolation, and crypto-only routing; funding/OI follow Bybit→OKX precedence (Binance not primary).
3. The four indicators are exposed through the u74 raw_metadata contract (exact `indicator` / key names / units).
4. Crypto anchor/table/card/prompt wording uses UTC 24h snapshot framing and does not use equity close language for generated crypto prose; equity segments retain close framing.
5. The Stage 2 crypto prompt receives a deterministic indicator context and cannot infer values for unavailable indicators.
6. 24h 청산 and 거래소 netflow are explicitly scoped out (no no-key source) and registered as TECH-DEBT; no fabricated values appear.
7. u58 official crypto-policy priority remains ahead of new native indicators; u54/u62/u65 source-quality surfaces are not reimplemented.
8. No paid API, API secret, browser scraping, or authenticated (signed) exchange endpoint is introduced; Anthropic SDK untouched; module boundary intact; channel separation and disclaimer gates untouched; R13 no secret.

## Tests / Validation

Local validation for implementation:

- `uv run pytest tests/unit/sources/test_alternative_fng.py tests/unit/sources/test_coingecko_global_market.py tests/unit/sources/test_bybit_derivatives.py -q`
- `uv run pytest tests/unit/briefing/test_segments_exclusivity.py tests/unit/publisher/test_crypto_indicators.py tests/unit/publisher/test_anchor_table.py tests/unit/visuals/test_cards.py -q`
- `uv run pytest tests/integration/test_briefing_reader_format.py -q`
- `uv run ruff check src/investo/sources src/investo/briefing src/investo/publisher src/investo/visuals tests/unit/sources tests/unit/briefing tests/unit/publisher tests/unit/visuals`
- `uv run mypy --strict src/investo`
- `mkdocs build --strict`

## Non-Goals

- Implementing 24h liquidations or exchange netflow from unverified or key-required endpoints.
- Wiring Binance fapi as the primary funding/OI source (GHA 451).
- Changing crypto regulation policy source priority.
- Changing the generic quality status algorithm.
- Rewriting the chart engine or moving chart payloads; u75 owns chart data externalization.
- Rendering buy/sell advice, target prices, or directional recommendations.

## How to Approve

Reply with one of:
1. **Request Changes** — name the step / AC to revise.
2. **Continue to Next Stage** — approve this plan; `investo-developer` starts at Step 1.
