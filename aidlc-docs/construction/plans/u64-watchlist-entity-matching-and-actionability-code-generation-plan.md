# Code Generation Plan: `u64 watchlist-entity-matching-and-actionability`

**Date**: 2026-05-23
**Unit**: u64 watchlist-entity-matching-and-actionability
**Stage**: Code Generation
**Status**: Complete (8/8)
**Source**: 2026-05-23 review of watchlist mismatch and low-actionability sections
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u18 watchlist relevance
- u28 watchlist usability foundation
- u33 watchlist depth
- u51 TL;DR and action-ratio canary

---

## Problem Statement

The latest US briefing mapped watchlist asset `BTC` to `BTM earnings`, showing that watchlist matching is still too broad in some contexts. Separately, watchpoint sections often say only `관찰/확인/점검/비교` without trigger, source, threshold, or implication.

This combines a correctness problem with a product usefulness problem.

---

## Goal

Make watchlist/entity matching exact enough to avoid cross-asset false positives and make watchpoints actionable without becoming investment advice.

---

## Scope Boundary

In scope:
- Watchlist item/entity matching.
- Claim-level watchlist evidence rendering.
- Watchpoint structure: trigger, source, threshold/range, implication.
- Tests for `BTC` not matching `BTM`.

Out of scope:
- User accounts or per-user portfolios.
- Trading recommendations, price targets, or buy/sell signals.
- Paid data sources.

---

## Implementation Steps

### Step 1 - Pin false-positive matching

- [x] Add tests that `BTC` does not match `BTM`, `BTCS`, `BTM earnings`, or arbitrary uppercase substrings.
- [x] Add tests that `BTC-USD`, `Bitcoin`, `비트코인`, and configured aliases still match.
- [x] Add tests for short US tickers that require symbol boundaries.

### Step 2 - Split entity matching by source field

- [x] Treat structured ticker/symbol fields as higher confidence than title/summary text.
- [x] Require strict boundaries for short ASCII tickers.
- [x] Only allow fuzzy or alias matching for configured aliases and longer terms.

### Step 3 - Add match confidence and reason

- [x] Return watchlist matches with confidence tier and reason code.
- [x] Suppress low-confidence matches from first-viewport callouts.
- [x] Keep low-confidence candidates available only for bounded diagnostics.

### Step 4 - Render claim-level evidence

- [x] Show the source title or source name behind each watchlist hit.
- [x] Avoid rendering matches without a source/evidence reason.
- [x] Cap visible matches to existing UI limits.

### Step 5 - Define watchpoint template

- [x] Update deterministic post-processing or prompt contract so each watchpoint has `무엇을 볼지`, `확인 소스`, `임계값/범위`, and `시사점`.
- [x] Allow `데이터 부족` watchpoints to omit thresholds only when coverage status justifies it.
- [x] Keep wording observational and compliance-safe.

### Step 6 - Add actionability validator

- [x] Warn or repair watchpoints that contain only generic verbs without a trigger/source.
- [x] Reuse u56 compliance language scanner before publish.
- [x] Add tests for generic non-actionable lines.

### Step 7 - Notification alignment

- [x] Keep Telegram summaries concise but include one high-confidence watchlist reason when present.
- [x] Do not include low-confidence diagnostics in public notification text.

### Step 8 - Documentation and gate

- [x] Update watchlist configuration docs for aliases and boundary behavior.
- [x] Run targeted watchlist, reader-format, notifier, and publisher tests.

---

## Definition of Done

- [x] `BTC` never maps to `BTM earnings`.
- [x] Valid BTC aliases still match across crypto sources.
- [x] First-viewport watchlist callouts include evidence reason or are omitted.
- [x] Watchpoints contain source/trigger/threshold/implication unless explicitly data-limited.
- [x] Compliance-safe observational wording is preserved.
