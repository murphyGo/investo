# u33 Watchlist Depth — Code Generation Summary

**Date**: 2026-05-09
**Unit**: u33 watchlist-depth
**Status**: ✅ Complete (6/6 steps)

---

## Goal

Extend the watchlist surface for long-horizon trackers: position weighting, event lookahead, per-ticker history, multi-watchlist + multi-channel routing, and cumulative match visualization. All routes free-tier, account-free, no portfolio / accounting / cost-basis logic. Persona evaluation 2026-05-07 (#4, wish-list).

## Steps

### Step 1 — Position weight sorting
- `WatchlistConfig.weights: dict[str, float]` (canonical-uppercase ASCII keys; rejects negatives at validation time, defaults to 0.0).
- `WatchlistMatch.weight` field copied at match time.
- `match_watchlist_items` sorts results by `(-weight, term.casefold(), source_name, title)` so high-conviction positions surface first.
- Average-cost field intentionally omitted — out of scope; the project does not carry portfolio / accounting state.

### Step 2 — Event lookahead in watchlist
- `render_watchlist_impact(now_utc=)` accepts a runtime instant; per-match render adds ` D-N` suffix when the match's item carries a `scheduled_at` within 7 days of `now_utc`.
- Past events and far-future events (>7 days) leave the line unchanged.
- Reuses u35's `NormalizedItem.scheduled_at` plumbing — no new adapters needed.

### Step 3 — Per-ticker accumulation page
- New module `publisher/watchlist_pages.py`. `update_watchlist_pages(target_date, matches, *, pages_root=)` writes one `site_docs/watchlist/{slug}.md` per term; per-day `<!-- u33 entry YYYY-MM-DD begin/end -->` markers make re-runs idempotent.
- Slug rule: ASCII tickers preserved upper-case; Korean asset names preserved verbatim; bracketed numeric tickers (`[005930]`) preserved literally. Multiple consecutive non-slug characters collapse to a single hyphen.
- Per-term page also gets a per-day section heading (`## YYYY-MM-DD`) and bulleted source/kind/title lines (with optional weight).
- A regenerated `site_docs/watchlist/index.md` lists every term page (with cumulative match count) and embeds the Step 5 SVG chart at the top.
- Orchestrator `_stage_publish_segments` now accepts `items=` and threads them through to `update_watchlist_pages` after the per-segment archive write; snapshots the rewritten files for atomic rollback.

### Step 4 — Multi-watchlist + multi-channel routing
- New `WatchlistScope` model carrying its own term lists, optional `weights` overrides, and optional `segments` binding.
- New `WatchlistConfig.scopes: dict[str, WatchlistScope]` + `for_segment_scope(segment)` helper that returns a flattened `WatchlistConfig` merging the root + every scope whose `segments` is empty or contains the given segment. Scope-level weights override root weights for the same term; aliases / exact_match_terms carry over from the root unchanged.
- New `notifier/webhooks.py` with `WebhookEndpoint(channel: 'slack' | 'discord', url: str)`. `load_webhook_endpoints(raw=None)` parses the `INVESTO_WATCHLIST_WEBHOOKS` env var (JSON list); `dispatch_watchlist_alert(text, *, http, endpoints)` fans out best-effort (POST `{"text": ...}` for Slack, `{"content": ...}` for Discord; 4xx / 5xx / connection error logged at WARNING and swallowed).
- `__main__` now broadcasts a one-line `Investo daily briefing — YYYY-MM-DD published\n{briefing_url}` to every configured webhook after a non-FAILED, non-dry-run pipeline returns.
- Email channel intentionally skipped — no free, account-less SMTP relay. Operators wanting email can pipe Slack/Discord via their own forwarding tools.

### Step 5 — Cumulative match visualization
- New `visuals/watchlist_chart.render_cumulative_match_chart(counts_by_term)` deterministic SVG. Sort by count desc → term alphabetical; cap at 8 visible bars; remainder collapses into `기타 N건` row. Empty mapping yields a friendly placeholder card. Pure: same input → byte-identical SVG.
- The per-term index page (`site_docs/watchlist/index.md`) embeds the chart at the top.

### Step 6 — Verification
Full quality gate:
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (226 files post-format)
- `uv run mypy --strict src/` ✅ (90 source files)
- `uv run pytest -q` ✅ (1486 passed)
- `uv run mkdocs build --strict` ✅

## New / Modified Files

### New source
- `src/investo/notifier/webhooks.py`
- `src/investo/publisher/watchlist_pages.py`
- `src/investo/visuals/watchlist_chart.py`

### New tests
- `tests/unit/briefing/test_watchlist_u33.py` (12 — Step 1 weight sort + Step 2 D-N suffix + Step 4 multi-scope merge)
- `tests/unit/notifier/test_webhooks.py` (10 — env parser + Slack/Discord shapes + best-effort failure swallow)
- `tests/unit/publisher/test_watchlist_pages.py` (7 — first-write / idempotent replace / multi-day preservation / index / weight render / Korean term)
- `tests/unit/visuals/test_watchlist_chart.py` (7 — empty / sort / tie-break / overflow cap / determinism / xml escape / self-contained)

### Modified source
- `src/investo/briefing/watchlist.py` — `WatchlistScope`, `WatchlistConfig.weights` + `scopes`, `WatchlistMatch.weight`, weight-aware sort in `match_watchlist_items`, `for_segment_scope`, `render_watchlist_impact(now_utc=)` + `_watchlist_d_suffix`.
- `src/investo/orchestrator/pipeline.py` — `_stage_publish_segments(items=)` + watchlist page snapshot/rollback hook.
- `src/investo/__main__.py` — webhook fan-out post-publish.

### Modified tests
- (none beyond the new files listed above)

## Test Delta

- 1450 → 1486 (+36 tests).

## TECH-DEBT

- None new.
- DoD's "average cost" + "email channel" intentionally omitted (out of scope). Documented above.

## Source

Persona evaluation 2026-05-07: persona #4 (wish-list).
