# Code Generation Plan: `u18 watchlist-relevance`

**Date**: 2026-05-07
**Unit**: u18 watchlist-relevance
**Stage**: Code Generation

---

## Goal

Add a lightweight personal relevance layer so the daily briefing highlights items connected to the user's watched assets, sectors, and keywords.

---

## Definition of Done

- [ ] A non-secret watchlist config supports tickers, crypto assets, sectors, and keywords.
- [ ] Relevant collected items are highlighted before generic market narrative.
- [ ] No-match days are explicit and do not invent impact.
- [ ] Telegram summary can include one watchlist-impact line within message limits.
- [ ] No accounts, paid sources, automatic trading, or portfolio accounting are introduced.

---

## Steps

### Step 1 — Config and Matching

- [ ] Define the watchlist config location and validation rules.
- [ ] Match collected items by ticker, asset, sector, and keyword.
- [ ] Add no-match behavior.

### Step 2 — Briefing and Telegram UX

- [ ] Add watchlist context to the briefing generation flow.
- [ ] Render a concise "내 관심 자산 영향" section or callout.
- [ ] Add Telegram impact line when relevant.

### Step 3 — Tests

- [ ] Test config validation.
- [ ] Test matching and no-match fallback.
- [ ] Test prompt/context shape and Telegram length behavior.
