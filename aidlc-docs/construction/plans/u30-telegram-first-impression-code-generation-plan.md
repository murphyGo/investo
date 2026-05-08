# Code Generation Plan: `u30 telegram-first-impression`

**Date**: 2026-05-08
**Unit**: u30 telegram-first-impression
**Stage**: Code Generation

---

## Goal

Raise the information density of the morning Telegram alert (the surface most readers see exactly once) without changing the underlying segment markdown.

---

## Definition of Done

- [x] Raw URLs in the Telegram payload are masked as `[상세보기](url)` Markdown.
- [x] Header line is followed by a one-line market snapshot (e.g. `SPX +0.4 / NDX +0.7 / KOSPI -0.2 / BTC 108.2k(-1.2%)`) using already-collected price data; missing segments degrade gracefully.
- [x] Insufficient-coverage segments collapse to a single line in the alert (or honor a per-user `enabled_segments` toggle). — both implemented (`coverage_by_segment` collapses, `INVESTO_TELEGRAM_ENABLED_SEGMENTS` filters).
- [x] Each segment conclusion ends with a closed-set action tag (`[관망]` / `[변동성↑]` / etc.) emitted by Stage 2 under a strict tag contract. — `briefing/action_tag.py` enforces the closed set and rescues from raw section ① text when the sentence picker clipped at a Korean terminator; off-set tags are stripped and replaced with `[관망]`; data-limited segments are forced to `[데이터부족]`.
- [x] Header shows publish KST time with a secondary `(전 거래일: YYYY-MM-DD)` label. — `🕐 KST HH:MM · 전 거래일: YYYY-MM-DD`.
- [x] Watchlist match suffix includes price (reusing yfinance / coingecko data) and falls back to ticker-only on collection failure. — `_decorate_watchlist_with_prices` decorates `TERM:` segments per match; missing prices leave the term unchanged.

---

## Steps

### Step 1 — URL Masking and Price Snapshot

- [x] Implement Markdown URL masking in the Telegram renderer.
- [x] Add the one-line market snapshot using already-collected price candidates.

### Step 2 — Segment Collapse / Toggle

- [x] Collapse insufficient segments to one line.
- [x] Plumb an optional `enabled_segments` config toggle.

### Step 3 — Action Tag Contract

- [x] Extend Stage 2 prompt with a closed-set tag contract and validation in the rendered conclusion.

### Step 4 — KST Time and Watchlist Price

- [x] Append KST publish time and previous-trading-day label to the header.
- [x] Add price suffix to watchlist matches with safe ticker-only fallback.

### Step 5 — Verification

- [x] Run targeted notifier tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #1 (P1).
