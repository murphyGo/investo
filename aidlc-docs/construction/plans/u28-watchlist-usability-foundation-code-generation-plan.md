# Code Generation Plan: `u28 watchlist-usability-foundation`

**Date**: 2026-05-08
**Unit**: u28 watchlist-usability-foundation
**Stage**: Code Generation

---

## Goal

Make watchlist matching legible to first-time users (onboarding nudge), forgiving across Korean / English aliases, and disciplined under partial coverage so it does not produce false-confidence callouts.

---

## Definition of Done

- [x] When `config/watchlist.json` is absent, the public site first viewport renders an onboarding nudge ("관심 목록 미설정 — config/watchlist.json 추가하세요"). Telegram surface is unchanged.
- [x] `WatchlistConfig` gains an `aliases: dict[str, list[str]]` field with a default core-asset bundle (BTC↔Bitcoin↔비트코인, ETH↔Ethereum↔이더리움, NVDA↔엔비디아, etc.).
- [x] Korean term matching applies a word-boundary heuristic (Hangul particle / whitespace / punctuation) or supports an explicit `exact_match: true` per-term option to suppress partial-string false positives.
- [x] In zero / insufficient coverage segments the watchlist callout switches to a "데이터 수집 부족으로 매칭 판단 보류" branch instead of asserting absence.
- [x] Site callout match cap is raised to 5 entries while Telegram remains capped at 3.
- [x] Single-character / two-character ticker inputs trigger an explicit warning, or are captured via a capitalize / parenthesized-token heuristic.

---

## Steps

### Step 1 — Onboarding Nudge and Unconfigured Branch

- [x] Detect missing config and render the nudge on the site only.
- [x] Skip Telegram impact suffix when unconfigured (preserve current behavior).

### Step 2 — Alias Mapping and Core Bundle

- [x] Extend `WatchlistConfig` schema with `aliases` and a default core bundle.
- [x] Apply alias normalization in the deterministic matcher.

### Step 3 — Korean Word Boundary and Short Ticker Guard

- [x] Add Hangul boundary heuristic (or `exact_match` option) to `term` matching.
- [x] Add validation/warning on 1-2 character ticker inputs and apply the capitalize / parens fallback.

### Step 4 — Coverage Branch and Cap Split

- [x] Branch the callout copy on zero / insufficient coverage.
- [x] Split match caps: 5 for site, 3 for Telegram.

### Step 5 — Verification

- [x] Run targeted watchlist tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #4 (P0 + P1).
