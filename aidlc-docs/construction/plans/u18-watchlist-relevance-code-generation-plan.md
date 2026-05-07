# Code Generation Plan: `u18 watchlist-relevance`

**Date**: 2026-05-07
**Unit**: u18 watchlist-relevance
**Stage**: Code Generation

---

## Goal

Add a lightweight personal relevance layer so the daily briefing highlights items connected to the user's watched assets, sectors, and keywords.

---

## Definition of Done

- [x] A non-secret watchlist config supports tickers, crypto assets, sectors, and keywords.
- [x] Relevant collected items are highlighted before generic market narrative.
- [x] No-match days are explicit and do not invent impact.
- [x] Telegram summary can include one watchlist-impact line within message limits.
- [x] No accounts, paid sources, automatic trading, or portfolio accounting are introduced.

---

## Steps

### Step 1 — Config and Matching

- [x] Define the watchlist config location and validation rules.
- [x] Match collected items by ticker, asset, sector, and keyword.
- [x] Add no-match behavior.

### Step 2 — Briefing and Telegram UX

- [x] Add watchlist context to the briefing generation flow.
- [x] Render a concise "내 관심 자산 영향" section or callout.
- [x] Add Telegram impact line when relevant.

### Step 3 — Tests

- [x] Test config validation.
- [x] Test matching and no-match fallback.
- [x] Test prompt/context shape and Telegram length behavior.
