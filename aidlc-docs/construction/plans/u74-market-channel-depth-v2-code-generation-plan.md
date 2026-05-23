# Code Generation Plan: `u74 market-channel-depth-v2`

**Date**: 2026-05-24
**Unit**: u74 market-channel-depth-v2
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-05-24 ten-subagent user-quality review of channel-specific briefing usefulness
**Estimated Effort**: ~6-9 h
**Dependencies**:
- u53 krx-foreign-flows-and-sector-etf
- u57 segment-narrative-scope-and-time-reconciliation
- u66 crypto-channel-depth
- u67 domestic-channel-depth

**Readiness**: Blocked for full implementation until u66 either lands or defines its crypto indicator output interface. Before u66, u74 may only add the shared presentation scaffold and explicit "not yet available" rows for u66-owned crypto indicators.

---

## Problem Statement

Domestic and crypto channel-depth gaps were identified separately. u67 has already closed a major domestic slice, and u66 owns crypto-native indicators. The remaining gap is consistency: each channel should expose its native anchors and missing-data states in a comparable way, while preserving segment boundaries.

Without a common presentation contract:
- One channel may silently omit unavailable native indicators while another renders explicit data limitations.
- Cross-market explanations may appear ad hoc and risk segment leakage.
- Crypto-native indicators landed by u66 may not be presented in a stable anchor block.
- Domestic u67 outputs could drift from the rest of the channel presentation if each section formats independently.

---

## Goal

Create a channel-depth v2 presentation contract:
- Every segment has a deterministic native anchor block.
- Missing native anchors render explicit rows with reason, not silent omissions.
- Crypto consumes u66 indicators when available.
- Domestic consumes u67 outputs without reopening source precedence.
- Cross-market cause-map language is allowed only through u57-approved macro/systemic links.

Minimal channel anchor schema:

| Segment | Order | Row key | Korean label | Required? | Producer | Missing reason enum | Counts as numeric fact? |
|---------|-------|---------|--------------|-----------|----------|---------------------|-------------------------|
| domestic-equity | 1 | `kospi_close` | KOSPI | yes | u67 anchor output | `source_empty`, `market_closed`, `not_collected` | yes when value present |
| domestic-equity | 2 | `kosdaq_close` | KOSDAQ | optional | u67 anchor output | `source_empty`, `market_closed`, `not_collected` | yes when value present |
| domestic-equity | 3 | `usd_krw` | 원/달러 | yes | u67 FX output | `source_empty`, `not_collected` | yes when value present |
| domestic-equity | 4 | `sector_depth` | 반도체/2차전지 | optional | u53/u67 sector inputs | `not_collected`, `insufficient_items` | no |
| us-equity | 1 | `sp500` | S&P 500 | yes | u49/u55 anchors | `source_empty`, `market_closed`, `not_collected` | yes when value present |
| us-equity | 2 | `nasdaq_composite` | Nasdaq Composite | optional | u49/u55 anchors | `source_empty`, `market_closed`, `not_collected` | yes when value present |
| us-equity | 3 | `dow` | Dow | optional | u49/u55 anchors | `source_empty`, `market_closed`, `not_collected` | yes when value present |
| us-equity | 4 | `macro_yield_or_event` | 금리/매크로 | optional | u57/u59 BundleContext/macro inputs | `not_collected`, `stale`, `insufficient_items` | no unless u55 verifies numeric fact |
| crypto | 1 | `btc_price_24h` | BTC 24h | yes | u66/u49 anchor output | `not_yet_available`, `source_empty`, `not_collected` | yes when value present |
| crypto | 2 | `eth_price_24h` | ETH 24h | optional | u66/u49 anchor output | `not_yet_available`, `source_empty`, `not_collected` | yes when value present |
| crypto | 3 | `btc_dominance` | BTC 도미넌스 | optional | u66 indicator output | `not_yet_available`, `source_empty`, `not_collected` | yes when value present |
| crypto | 4 | `fear_greed` | 공포·탐욕 | optional | u66 indicator output | `not_yet_available`, `source_empty`, `not_collected` | no |
| crypto | 5 | `funding_oi_liquidation` | 펀딩/OI/청산 | optional | u66 indicator output | `not_yet_available`, `source_empty`, `not_collected` | no |

---

## Existing Coverage / Deduplication

This unit does not reopen u67 and does not duplicate u66.

- u67 owns domestic KOSPI/KOSDAQ/FX/sector/overnight-US bridge implementation and source precedence.
- u66 owns crypto-native indicator collection and UTC 24h framing.
- u57 owns BundleContext and cross-segment scope reconciliation.
- u53 owns earlier domestic/sector/macro source depth.

u74 standardizes the reader-facing presentation contract and cross-channel cause-map behavior after those pieces exist.

---

## Scope Boundary

In scope:
- Channel-specific anchor block schema.
- Explicit missing-data rows with source/status reasons.
- Crypto indicator presentation once u66 supplies values.
- Domestic presentation consumption of u67 values.
- Cross-market cause-map text guarded by u57 scope rules.

Out of scope:
- New domestic source adapters.
- New crypto source adapters beyond what u66 implements.
- Paid data providers.
- Cross-channel prediction or trade recommendations.
- Rewriting u57 lint rules except to add a specific channel-depth fixture if needed.

---

## Stage Decision

- **Functional Design — REQUIRED only if implementation introduces a new shared channel-depth model**. If the implementation uses existing anchor/BundleContext models and only changes rendering, skip FD. If a new model is needed, add a thin FD extension documenting the schema and missing-data rule.
- **NFR Requirements — SKIP**. No new source or dependency in this unit; u66/u67 own their source/NFR implications.

---

## Implementation Steps

### Step 1 — Define channel anchor schema `[ ]`
- [ ] Implement the minimal schema table above, not a newly invented row set.
- [ ] Use only the missing reason enum values listed above unless implementation discovers an existing narrower enum to reuse.
- [ ] Map each row to its existing producer: u67 domestic, u66 crypto, u49/u55 generic anchors, u57 BundleContext.
- **Acceptance**: schema table exists in code comments/docs/tests and avoids source duplication.

### Step 2 — Implement explicit missing-data rendering `[ ]`
- [ ] Update anchor renderer so unavailable native rows render as explicit `데이터 없음/미수집/지연` rows when relevant.
- [ ] Ensure missing rows do not count as successful numeric facts.
- [ ] Keep output concise and not alarmist.
- **Acceptance**: partial-channel fixture shows explicit missing rows without invented values.

### Step 3 — Consume crypto and domestic outputs `[ ]`
- [ ] For crypto, consume u66 indicators when present and label unavailable indicators if u66 marks them missing.
- [ ] For domestic, reuse u67 KOSPI/KOSDAQ/FX/sector outputs without changing precedence.
- [ ] For US equity, preserve existing index/macro/sector anchors and add missing rows only where schema requires them.
- **Acceptance**: each channel fixture renders native anchors through the same renderer contract.

### Step 4 — Add cross-market cause-map guard `[ ]`
- [ ] Render a compact cause-map line only when u57 BundleContext permits the linkage.
- [ ] Forbid unapproved cross-segment ticker leakage.
- [ ] Keep wording observational: "연결 고리" / "관찰" rather than prediction.
- **Acceptance**: allowed macro/systemic link fixture passes; forbidden ticker-only linkage fixture fails or omits the cause map.

Allowed cause-map rules:

| Cause-map type | Required `BundleContext` evidence | Permitted wording | Forbidden behavior |
|----------------|-----------------------------------|-------------------|--------------------|
| `geopolitical_oil_macro` | u57 shared macro key present in at least two segments | `유가/지정학 이슈가 여러 자산군의 변동성 연결 고리로 관찰됩니다.` | price prediction or ticker-specific causality |
| `fed_policy_event` | Fed/FOMC/rate event shared by domestic/us or us/crypto | `금리 이벤트가 할인율/달러 경로의 공통 변수로 남아 있습니다.` | buy/sell or guaranteed direction |
| `global_systemic_risk` | u57 systemic-risk allowed key across segments | `공통 위험 요인으로 변동성 확대 여부를 점검합니다.` | unrelated single-segment event leakage |

Forbidden links are omitted and logged/replay-reported; they are not demoted into public prose.

### Step 5 — Tests and gate `[ ]`
- [ ] Complete-channel fixture.
- [ ] Partially missing-channel fixture.
- [ ] Forbidden cross-segment leakage fixture.
- [ ] u66-not-yet-present fixture where crypto indicator rows render `not_yet_available`.
- [ ] Missing rows do not increase numeric-success counts.
- [ ] When u70 is present, anchor values remain single-source across table/body/trace-visible/chart surfaces.
- [ ] Run targeted anchor/publisher/briefing tests, plus ruff/mypy and mkdocs if site output changes.

---

## Acceptance Criteria

- **AC-74.1** — Each channel has a deterministic native anchor block schema.
- **AC-74.2** — Missing native anchors render explicit reason rows instead of silent omission or invented values.
- **AC-74.3** — Crypto presentation consumes u66 indicators when available and labels missing indicators when not.
- **AC-74.4** — Domestic presentation consumes u67 outputs without changing source precedence.
- **AC-74.5** — Cross-market cause-map language is limited to u57-approved links and remains observational.

---

## Tests / Validation

Expected test areas:
- `tests/unit/publisher/test_anchor_table*.py`
- `tests/unit/orchestrator/test_bundle_context.py`
- `tests/unit/publisher/test_cross_segment_lint.py`
- `tests/unit/briefing/test_prompts*.py`

Minimum local gate:
- Targeted pytest for changed areas.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if models change.
- `uv run mkdocs build --strict` if rendered site docs change.

---

## Non-Goals

- Re-implementing u66 or u67.
- New market data vendors.
- A portfolio dashboard.
- Historical archive backfill.
