# Code Generation Plan: `u30 telegram-first-impression`

**Date**: 2026-05-08
**Unit**: u30 telegram-first-impression
**Stage**: Code Generation

---

## Goal

Raise the information density of the morning Telegram alert (the surface most readers see exactly once) without changing the underlying segment markdown.

---

## Definition of Done

- [ ] Raw URLs in the Telegram payload are masked as `[상세보기](url)` Markdown.
- [ ] Header line is followed by a one-line market snapshot (e.g. `SPX +0.4 / NDX +0.7 / KOSPI -0.2 / BTC 108.2k(-1.2%)`) using already-collected price data; missing segments degrade gracefully.
- [ ] Insufficient-coverage segments collapse to a single line in the alert (or honor a per-user `enabled_segments` toggle).
- [ ] Each segment conclusion ends with a closed-set action tag (`[관망]` / `[변동성↑]` / etc.) emitted by Stage 2 under a strict tag contract.
- [ ] Header shows publish KST time with a secondary `(전 거래일: YYYY-MM-DD)` label.
- [ ] Watchlist match suffix includes price (reusing yfinance / coingecko data) and falls back to ticker-only on collection failure.

---

## Steps

### Step 1 — URL Masking and Price Snapshot

- [ ] Implement Markdown URL masking in the Telegram renderer.
- [ ] Add the one-line market snapshot using already-collected price candidates.

### Step 2 — Segment Collapse / Toggle

- [ ] Collapse insufficient segments to one line.
- [ ] Plumb an optional `enabled_segments` config toggle.

### Step 3 — Action Tag Contract

- [ ] Extend Stage 2 prompt with a closed-set tag contract and validation in the rendered conclusion.

### Step 4 — KST Time and Watchlist Price

- [ ] Append KST publish time and previous-trading-day label to the header.
- [ ] Add price suffix to watchlist matches with safe ticker-only fallback.

### Step 5 — Verification

- [ ] Run targeted notifier tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #1 (P1).
