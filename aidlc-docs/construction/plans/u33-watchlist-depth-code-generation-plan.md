# Code Generation Plan: `u33 watchlist-depth`

**Date**: 2026-05-08
**Unit**: u33 watchlist-depth
**Stage**: Code Generation

---

## Goal

Extend the watchlist surface for long-horizon trackers: position weighting, event lookahead, per-ticker history, multi-watchlist + multi-channel routing, and cumulative match visualization. All routes must remain free-tier and account-free.

---

## Definition of Done

- [x] `WatchlistConfig` accepts optional position weight; matched callouts are sorted by weight desc. — `WatchlistConfig.weights` field; matcher sorts by `(-weight, term, source, title)`. (Average-cost field skipped — no portfolio/accounting layer in scope.)
- [x] 7-day lookahead callouts surface scheduled events using `scheduled_at` from u35 lookahead items already in u1. — `render_watchlist_impact(now_utc=)` adds " D-N" suffix for matches whose item carries a `scheduled_at` within 7 days.
- [x] Per-ticker accumulation page (`site_docs/watchlist/{TICKER}.md`) appends matched items on each publish. — `publisher/watchlist_pages.update_watchlist_pages` writes idempotently per (term, target_date).
- [x] Multi-watchlist support with explicit segment mapping. — `WatchlistConfig.scopes: dict[str, WatchlistScope]` + `for_segment_scope(segment)` helper.
- [x] Multi-channel routing (Slack / Discord) via free webhook integrations. — `notifier/webhooks.py` + `INVESTO_WATCHLIST_WEBHOOKS` env var; `__main__` fans out post-publish (skips on FAILED + dry-run). (Email skipped — no free, account-less SMTP relay we could rely on.)
- [x] Daily match-count visualization card. — `visuals/watchlist_chart.render_cumulative_match_chart` SVG embedded in the per-term index page.

---

## Steps

### Step 1 — Position Weight Sorting

- [x] Extend `WatchlistConfig` with optional weight; sort callouts by weight.

### Step 2 — Event Lookahead

- [x] Render " D-N" suffix in watchlist callout for matches with `scheduled_at` inside the 7-day horizon. — reuses u35 lookahead-stamped `NormalizedItem.scheduled_at`.

### Step 3 — Per-Ticker Accumulation Page

- [x] Append matched items to `site_docs/watchlist/{TICKER}.md` on every publish.

### Step 4 — Multi-Watchlist and Multi-Channel

- [x] Support multi-watchlist scoping in config + segment binding (`scopes` + `for_segment_scope`).
- [x] Add Slack / Discord free-webhook channel adapters; email deferred.

### Step 5 — Cumulative Match Visualization

- [x] Render a deterministic per-ticker cumulative chart card; embedded in `site_docs/watchlist/index.md`.

### Step 6 — Verification

- [x] Run targeted watchlist / notifier / publisher tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #4 (wish-list).
