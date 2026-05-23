# u66 crypto-channel-depth — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u66 crypto-channel-depth
**Status**: Complete (9/9 steps)

## Goal

Give the crypto briefing a small, deterministic native indicator block (sentiment / breadth / positioning) and a UTC 24h framing contract, and define the crypto indicator interface that u74 consumes — all from no-key free sources, without weakening compliance, channel separation, or module boundaries (plan Problem Statement gaps 1-4). Equity segments are untouched.

## Scope

In scope (no-key free, lead live probe 2026-05-24 confirmed): 공포·탐욕, BTC 도미넌스 + 전체 시총, BTC 펀딩비 + OI (Bybit→OKX), crypto UTC-24h render/prompt frame, u74 raw_metadata contract.
Scope-out (no no-key source): 24h 청산 (Coinglass key-required) + 거래소 netflow (CryptoQuant/Glassnode paid) → explicit `무료 검증 소스 미확정` unavailable rows, never fabricated → DEBT-071 / DEBT-072.

## Step 1 — Free-Source Reachability (live 2026-05-24)

| Need | Source | Endpoint | Result | Decision |
|------|--------|----------|--------|----------|
| Fear & Greed | `alternative-fng` | Alternative.me `/fng/?limit=1` | 200, no-key | Single source |
| BTC 도미넌스 / 전체 시총 | `coingecko-global-market` | CoinGecko `/api/v3/global` | 200, no-key | Single source |
| BTC 펀딩비 + OI | `bybit-derivatives` | Bybit v5 `/v5/market/tickers?category=linear&symbol=BTCUSDT` | 200, no-key, no geo-block | **Primary** |
| BTC 펀딩비 + OI | `okx-derivatives` | OKX `/api/v5/public/funding-rate` + `/open-interest` | 200, no-key | **Fallback** |
| Binance fapi | — | fapi | sandbox 200 / GHA IP **451 geo-block** | NOT primary (optional last resort only) |
| 24h 청산 | Coinglass | `/api/...` | `{"code":"30001","msg":"API key missing"}` | Scope-out → DEBT-071 |
| 거래소 netflow | CryptoQuant / Glassnode | — | paid / key required | Scope-out → DEBT-072 |
| DeFi TVL / stablecoin | existing `defillama-market-structure` | reused | 200 | No second DeFi adapter |

**Precedence**: 공포탐욕 = Alternative.me single; 도미넌스 = CoinGecko `/global` single; 펀딩비/OI = **Bybit primary → OKX fallback** (both no-key/geo-safe; Binance NOT primary — GHA 451). R10 four-path fixtures (success / empty / malformed) recorded live for all 4 sources. No paid key introduced.

## Key Deliverables

- `src/investo/sources/alternative_fng.py`: no-key adapter `alternative-fng`, `category="macro"`, `indicator="fear_greed"`.
- `src/investo/sources/coingecko_global_market.py`: no-key adapter `coingecko-global-market`, `category="macro"`, `indicator="global_market"` (distinct from the existing per-coin `coingecko-price`).
- `src/investo/sources/bybit_derivatives.py`: no-key adapter `bybit-derivatives` (primary) + `okx-derivatives` (fallback), `category="macro"`, emits `indicator="btc_funding"` + `indicator="btc_oi"`; Bybit→OKX precedence; per-source isolation.
- `src/investo/sources/__init__.py`: all 4 adapters registered (`@register` import path).
- `src/investo/briefing/segments.py`: `alternative-fng`, `coingecko-global-market`, `bybit-derivatives`, `okx-derivatives` added to `_CRYPTO_ONLY_SOURCES`; candidate-preservation priority so native indicators survive crypto caps while u58 official policy stays ahead; absence does NOT downgrade crypto coverage.
- `src/investo/briefing/crypto_indicators.py`: pure renderer extracting indicator rows keyed off the `indicator` raw_metadata tag — 8-row deterministic markdown block (공포탐욕 / BTC 도미넌스 / 전체 시총 / 24h 변동 / BTC 펀딩비 / BTC OI / DeFi TVL / 스테이블코인) + 청산·netflow `무료 검증 소스 미확정` rows; idempotent; never invents unavailable values.
- `src/investo/publisher/crypto_indicators.py`: injection of the rendered block before crypto §① (after `## 한눈에 보기` / shared macro insertion point).
- `src/investo/publisher/anchor_table.py`: crypto first column `종가` → UTC 24h snapshot wording (crypto segment only; domestic/us unchanged).
- `src/investo/briefing/prompts.py`: crypto Stage-2 instructions use `UTC 24h 기준` / `스냅샷` / `구간 내 변동`; `{crypto_indicator_context}` payload; unavailable rows stated as unavailable, not inferred; no cross-segment leakage.
- `src/investo/visuals/cards.py`: crypto card captions match UTC 24h framing.
- Fixtures under `tests/unit/sources/fixtures/api/{alternative-fng,coingecko-global-market,bybit-derivatives,okx-derivatives}/`: success + empty + malformed (+ auth/error where applicable) — R10 four-path, live-recorded 2026-05-24.
- Tests: new adapter tests + Bybit→OKX precedence tests; `tests/unit/briefing/test_segments_exclusivity.py` (crypto-only routing; absence does not downgrade); `tests/unit/publisher/test_crypto_indicators.py` (full/partial/missing rows); u74 raw_metadata contract pin test; crypto anchor wording test; card-caption test; one offline replay derived from `archive/crypto/2026/05/2026-05-22.md`.
- `docs/tech-env.md`: no-key public crypto indicator sources (Alternative.me / CoinGecko global / Bybit / OKX).

## u74 Interface Contract (R16a — as implemented)

| u74 row key | Indicator | raw_metadata keys | Producer |
|-------------|-----------|-------------------|----------|
| `fear_greed` | 공포·탐욕 | `indicator="fear_greed"`; `value` (0-100); `classification`; `window="utc_24h"` | `alternative-fng` |
| `btc_dominance` + (total cap) | 도미넌스 / 시총 | `indicator="global_market"`; `btc_dominance_pct`; `total_market_cap_usd`; `market_cap_change_24h_pct` | `coingecko-global-market` |
| `funding_oi_liquidation` (funding) | BTC 펀딩비 | `indicator="btc_funding"`; `btc_funding_rate`; `funding_source` ∈ {bybit,okx} | `bybit-derivatives` / `okx-derivatives` |
| `funding_oi_liquidation` (OI) | BTC OI | `indicator="btc_oi"`; `btc_oi_usd`; `oi_source` ∈ {bybit,okx} | `bybit-derivatives` / `okx-derivatives` |
| `funding_oi_liquidation` (liquidation) | 24h 청산 | — | **absent** → u74 renders `not_yet_available` |

No new `Category` enum value. No `core_fact:*` keys (non-core context, `warn` per u55). `coingecko-price` (BTC/ETH 24h price; u74 rows 1-2) unchanged.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-1 | Crypto briefings render native indicator block (공포탐욕 / 도미넌스 / 시총 / 펀딩 / OI / DeFi TVL / 스테이블 + 청산·netflow unavailable rows) | MET | `crypto_indicators.py` renderer; `test_crypto_indicators.py` full/partial/missing |
| AC-2 | 3 no-key adapters (+OKX fallback) with recorded fixtures, flat metadata, per-source isolation, crypto-only routing; Bybit→OKX precedence (Binance not primary) | MET | 4 adapters + R10 four-path fixtures; `test_segments_exclusivity.py`; Bybit→OKX precedence tests |
| AC-3 | Four indicators exposed via u74 raw_metadata contract (exact `indicator`/keys/units) | MET | R16a contract pin test |
| AC-4 | Crypto anchor/table/card/prompt use UTC 24h framing; equity segments retain close framing | MET | `anchor_table.py` / `cards.py` / `prompts.py`; anchor wording + card-caption tests; equity unchanged |
| AC-5 | Stage-2 crypto prompt gets deterministic indicator context; cannot infer unavailable values | MET | `{crypto_indicator_context}` payload; prompt snapshot tests; crypto-only injection |
| AC-6 | 24h 청산 + netflow scoped out, registered TECH-DEBT, no fabricated values | MET | explicit `무료 검증 소스 미확정` rows; DEBT-071 / DEBT-072 |
| AC-7 | u58 policy priority stays ahead of native indicators; u54/u62/u65 quality surfaces not reimplemented | MET | candidate-preservation priority in `segments.py`; cap tests show u58 ahead |
| AC-8 | No paid API/secret/scraping/signed endpoint; Anthropic SDK untouched; module boundary intact; channel separation + disclaimer untouched; R13 no secret | MET | all no-key public market-data; adapters import only models; renderer pure; gates untouched; `check_no_paid_apis` exit 0 |

## FD Divergences Ratified

None material. The lead live probe scope was implemented as planned: Bybit confirmed no-key / geo-safe as the funding/OI primary (the concurrent-draft "defer all derivatives" path was correctly rejected at plan time). The two scope-outs (청산 / netflow) are designed boundaries (R16d), not divergences. FD additions: `u1-sources` L6.13 / L6.14 / L6.15 + R16 (R16a contract / R16b Bybit→OKX / R16c UTC-24h / R16d scope-out), tagged `(extension 2026-05-24)`.

## TECH-DEBT Registered

- **DEBT-071** — 24h 청산 (롱/숏 liquidations) has no no-key aggregate source (Coinglass key-required). Liquidation row renders as explicit unavailable; u74 liquidation leg `not_yet_available`. Low.
- **DEBT-072** — 거래소 netflow has no no-key source (CryptoQuant / Glassnode paid). Netflow row renders as explicit unavailable. Low.

## Potential Risks

- **Bybit/OKX primary not yet observed on the live GHA IP** — confirmed in sandbox / this workspace, but the funding/OI primary has not run on a GitHub Actions IP. If both Bybit and OKX geo-block on the GHA path, the BTC 펀딩비 / OI indicator rows degrade to `수집 안 됨` (crypto coverage is NOT downgraded — designed degradation, mirrors `binance-crypto-market`). First-run GHA observation recommended to confirm reachability.

## Verification Gate

- ruff check: clean
- ruff format: clean
- mypy --strict: 137 files clean
- pytest: 2488 passed
- mkdocs build --strict: pass
- `check_no_paid_apis`: exit 0
- R10 four-path fixtures (success / empty / malformed) recorded live 2026-05-24 for all 4 crypto sources.

## Downstream

u74 market-channel-depth-v2 is now **unblocked** — its crypto indicator interface is the R16a raw_metadata contract pinned here.
