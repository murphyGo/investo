# Code Generation Plan: `u33 watchlist-depth`

**Date**: 2026-05-08
**Unit**: u33 watchlist-depth
**Stage**: Code Generation

---

## Goal

Extend the watchlist surface for long-horizon trackers: position weighting, event lookahead, per-ticker history, multi-watchlist + multi-channel routing, and cumulative match visualization. All routes must remain free-tier and account-free.

---

## Definition of Done

- [ ] `WatchlistConfig` accepts optional position weight and average cost; matched callouts are sorted by weight.
- [ ] 7-day lookahead callouts surface options / earnings / ex-dividend events using `nasdaq-earnings-calendar` and free SEC schedules already in u1.
- [ ] Per-ticker accumulation page (`docs/watchlist/{TICKER}.md`) appends matched items on each publish.
- [ ] Multi-watchlist support (e.g. sector / account scoping) with explicit segment mapping.
- [ ] Multi-channel routing (Slack / Discord / email) via free webhook integrations only; default behavior unchanged.
- [ ] Daily match-count visualization card aggregates the per-ticker history into a cumulative chart.

---

## Steps

### Step 1 — Position Weight Sorting

- [ ] Extend `WatchlistConfig` with optional weight / avg cost; sort callouts by weight.

### Step 2 — Event Lookahead

- [ ] Reuse `nasdaq-earnings-calendar` adapter and free SEC schedule for 7-day lookahead callouts.

### Step 3 — Per-Ticker Accumulation Page

- [ ] Append matched items to `docs/watchlist/{TICKER}.md` on every publish.

### Step 4 — Multi-Watchlist and Multi-Channel

- [ ] Support multi-watchlist scoping in config and segment binding.
- [ ] Add Slack / Discord / email free-webhook channel adapters.

### Step 5 — Cumulative Match Visualization

- [ ] Render a deterministic per-ticker cumulative chart card.

### Step 6 — Verification

- [ ] Run targeted watchlist / notifier tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #4 (wish-list).
