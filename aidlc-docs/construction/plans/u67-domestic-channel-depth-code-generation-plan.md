# Code Generation Plan: `u67 domestic-channel-depth`

**Date**: 2026-05-24
**Unit**: u67 domestic-channel-depth
**Stage**: Code Generation
**Status**: Planned (0/7)
**Source**: 2026-05-24 ten-subagent reader-facing review — Gap B (국내 채널 깊이), independently raised by the 국내 투자자 + 한국어 personas
**Estimated Effort**: ~6-8 h
**Dependencies**:
- u1 sources (adapter plugin pattern, registry, `FetchWindow`)
- u8 market-aware source window (KST window / R7 relaxation)
- u45 segment routing exclusivity (domestic-equity routing)
- u49 deterministic market anchor (anchor-table render pattern)
- u53 krx-foreign-flows-and-sector-etf (foreign-flow + sector ETF surface)
- u57 segment narrative scope and time reconciliation (야간 미국장 → 국내 개장 인과 wording)

---

## Problem Statement

The domestic-equity channel under-serves its readers relative to the US channel:

1. **Index close missing in body** — KOSPI/KOSDAQ 종가·등락률 are not surfaced in the body when `fsc-krx-index-price` returns 0 rows. The KRX REST endpoint frequently returns empty on the KST morning cron (T+1 settlement timing). No deterministic fallback exists.
2. **No 원/달러 환율** — `usd_krw` is mapped in `_core_fact_map.py` (`KRW=X` / `USDKRW=X`) but no source actually fetches it, and it is absent from the domestic body. FX is the primary driver of 외국인 수급, so its absence breaks the §③ 수급 narrative.
3. **Semiconductor / battery sector depth missing** — 삼성전자·SK하이닉스·2차전지 prices are present in the trace metadata but not narrated in the body.
4. **US-overnight → KR-open causality weak** — the body rarely connects the prior US session to the KR open, which is the single most useful framing for a KST-morning reader.

This is a reader-facing **feature gap**, not a defect.

---

## Goal

Give the domestic-equity channel a reliable index-close line, a 원/달러 anchor, sector depth for 반도체/2차전지, and an explicit overnight-US → KR-open bridge — all from free sources, without weakening compliance, channel separation, or module boundaries.

---

## Scope Boundary

In scope:
- A deterministic KOSPI/KOSDAQ index-close fallback when `fsc-krx-index-price` is empty.
- A free 원/달러 환율 source feeding `usd_krw` and a domestic anchor line.
- Sector grouping (반도체 / 2차전지) surfacing in the body via deterministic anchor/prompt hints.
- An overnight-US → KR-open framing rule in the domestic prompt scope.

Out of scope:
- Paid FX or index vendors.
- Intraday / tick-level KR data.
- New personas, accounts, or portfolio features.
- Buy/sell signals or price targets (compliance gate stays intact).

---

## Free-Source Reachability (must verify in Step 1 before coding)

| Need | Candidate free source | Reachability note |
|------|------------------------|-------------------|
| 원/달러 환율 | yfinance `KRW=X` (already mapped) or Stooq `usdkrw` | yfinance v8 chart already used (`yfinance.py`); add `KRW=X` to default tickers. Stooq `usdkrw` is the no-key fallback (`stooq_price.py` pattern). |
| KOSPI/KOSDAQ close fallback | Stooq `^kospi` / `^kosdaq`, or yonhap-market RSS headline parse | Stooq index symbols are no-key. `yonhap_market.py` already collects KR market RSS — a numeric close parse is the news-derived fallback when both KRX + Stooq are empty. |
| 반도체/2차전지 가격 | yfinance/Stooq `005930.KS` (삼성전자), `000660.KS` (SK하이닉스) + battery names | Already collectible via existing adapters; gap is grouping/narration, not fetch. |

All three are no-key free tier. Reachability is **confirmed at plan time for yfinance/Stooq mapping** (both adapters already ship); the only Step-1 unknown is whether Stooq carries `^kospi` reliably on the GHA IP — the yonhap RSS parse is the explicit degradation path.

---

## Stage Decision

Per CLAUDE.md / `/dev-investo`, Functional Design and NFR Requirements are **selective**.

- **Functional Design — REQUIRED (lightweight)**. This unit adds a new deterministic fallback algorithm (index-close source precedence: KRX → Stooq → yonhap-parse) and a new business rule (FX-must-be-present-or-explicitly-absent in the domestic body). These are new algorithm + new numbered rules, so a thin FD pass is justified: extend `u1-sources` FD with the FX adapter (`L6.x`) and add domestic business rules (precedence rule + FX-presence rule). No new domain entities — `NormalizedItem` + `MarketAnchor` are reused.
- **NFR Requirements — SKIPPED**. No new latency, cost, or availability envelope: all sources are existing free-tier patterns reused under the existing R7 window and retry budget. No new `tech-stack-decisions` (no new library; `defusedxml` already governs the yonhap RSS path). Skipping is consistent with u53/u57 which reused the source/anchor stack without an NFR pass.

---

## Implementation Steps

### Step 1 — Confirm free-source reachability and pick precedence

- [ ] Confirm yfinance `KRW=X` and Stooq `usdkrw` return a usable close on the GHA path (record a fixture for each).
- [ ] Confirm Stooq `^kospi` / `^kosdaq` reachability; if unreliable, pin the yonhap-RSS numeric parse as the index fallback.
- [ ] Document the index-close precedence (KRX → Stooq → yonhap-parse) and the FX precedence (KRW=X → Stooq usdkrw) in the FD.
- [ ] Acceptance: a written precedence table + recorded fixtures for each chosen source; no paid key introduced.

### Step 2 — 원/달러 source wiring

- [ ] Add `KRW=X` (and/or Stooq `usdkrw`) to the domestic default fetch set so `usd_krw` is populated.
- [ ] Ensure the value flows through `_core_fact_map.py` `usd_krw` mapping with no double-counting.
- [ ] Keep per-source isolation: an FX fetch failure must not drop other domestic items.
- [ ] Acceptance: a domestic run with KRX empty still yields a populated `usd_krw` core fact.

### Step 3 — KOSPI/KOSDAQ index-close fallback

- [ ] Implement the index-close fallback chain so a non-empty KOSPI/KOSDAQ close + 등락률 is available when `fsc-krx-index-price` returns 0 rows.
- [ ] Add the yonhap-RSS numeric close parser as the terminal fallback (`defusedxml` only; no raw stdlib XML).
- [ ] Tag the fallback provenance so the trace footer shows which source supplied the close.
- [ ] Acceptance: with `fsc-krx-index-price` mocked to 0 rows, the body still carries a KOSPI close line with provenance.

### Step 4 — Domestic anchor / sector grouping

- [ ] Extend the deterministic anchor render (u49 pattern) so the domestic table carries KOSPI/KOSDAQ close, 등락률, and 원/달러.
- [ ] Add a 반도체 (삼성전자/SK하이닉스) + 2차전지 grouping hint into the domestic prompt scope so the LLM narrates the sector instead of dropping prices to the trace only.
- [ ] Keep the anchor table deterministic (LLM may not invent the numbers).
- [ ] Acceptance: domestic anchor table renders index close + FX; sector names appear in the §③ body when their prices are present.

### Step 5 — Overnight-US → KR-open framing rule

- [ ] Add a domestic-prompt rule (`prompts.py`) instructing an explicit prior-US-session → KR-open bridge in §① / §②, scoped to domestic only (no cross-segment leakage — reuse u57 / `cross_segment_lint.py`).
- [ ] Keep wording observational and compliance-safe (u56 gate unchanged).
- [ ] Acceptance: domestic body contains a US-overnight causality sentence; `cross_segment_lint` does not flag scope leakage.

### Step 6 — Tests

- [ ] Source fixtures: FX (KRW=X / Stooq), Stooq index, yonhap numeric parse.
- [ ] Fallback-precedence unit tests (KRX empty → Stooq → yonhap).
- [ ] Anchor-render tests for index close + FX rows.
- [ ] Prompt-scope tests for the overnight bridge rule + cross-segment lint clean.
- [ ] Acceptance: targeted sources / briefing / publisher tests pass; ruff + mypy strict clean on changed scope.

### Step 7 — Documentation and gate

- [ ] Update `docs/tech-env.md` source list and the domestic env-var docs for the new FX / index tickers.
- [ ] Update the u1-sources FD with the FX adapter entry and the new domestic business rules.
- [ ] Write the unit `code/summary.md` (AC traceability, FD divergences, TECH-DEBT, final gate).
- [ ] Acceptance: mkdocs build strict passes; summary present.

---

## Step Dependency Graph

```
Step 1 (reachability + precedence)
  ├─> Step 2 (FX wiring)
  └─> Step 3 (index fallback)
        └─> Step 4 (anchor + sector)  ── needs 2 + 3
              └─> Step 5 (overnight framing)
                    └─> Step 6 (tests) ─> Step 7 (docs + gate)
```

## Acceptance Criteria

- **AC-1** — When `fsc-krx-index-price` returns 0 rows, the domestic body still carries a KOSPI (and KOSDAQ when available) close + 등락률 line with source provenance.
- **AC-2** — `usd_krw` is populated from a free source and a 원/달러 anchor line appears in the domestic body.
- **AC-3** — 반도체 (삼성전자/SK하이닉스) and 2차전지 are narrated in §③ when their prices are collected, not left trace-only.
- **AC-4** — The domestic body contains an explicit overnight-US → KR-open bridge sentence, scoped to domestic with no cross-segment leakage.
- **AC-5** — No paid key is introduced; all new fetches are free-tier; per-source isolation holds; `defusedxml` governs any RSS parse; channel separation and disclaimer gates are untouched.

## NFR AC Coverage Map

NFR Requirements stage is SKIPPED (see Stage Decision). The unit inherits existing envelopes:
- NFR-002 (cost 0) — enforced by free-source-only AC-5.
- R7 window / retry budget — reused unchanged from u8.
- R13 secret hygiene — no secret introduced (no-key sources).

## How to Approve

Reply with one of:
1. **Request Changes** — name the step / AC to revise.
2. **Continue to Next Stage** — approve this plan; `investo-developer` starts at Step 1.
