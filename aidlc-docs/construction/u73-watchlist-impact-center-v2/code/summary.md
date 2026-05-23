# u73 watchlist-impact-center-v2 — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u73 watchlist-impact-center-v2
**Status**: Complete (5/5 steps)

## Goal

Turn watchlist hits into a daily "what affected my watchlist today, and what was intentionally ignored?" workflow. Group each day's impacts into **Direct / Related / Uncertain / Rejected**, surface only high-confidence public-eligible groups (Direct/Related) in the briefing body and Telegram first impression, and expose Uncertain/Rejected as collapsed, redaction-safe diagnostics on the static watchlist page for operator/debug trust. No accounts, brokerage, P&L, or recommendation features.

## Scope

In scope: impact-type grouping (Direct/Related/Uncertain/Rejected) over existing match outputs; SOL/BTC-like short-ticker false-positive diagnostics; daily-first watchlist page rendering; public/diagnostic surface boundary for briefing/Telegram.
Out of scope: user accounts, position sizes, brokerage sync, P&L, tax lots; buy/sell/hold recommendations; new market data sources; replacing the watchlist configuration format.

## Stage Decision

- **Functional Design — SKIP** (per plan). u73 extends the existing watchlist domain model with match/impact classification; no new product domain object outside the watchlist layer. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new external source, dependency, secret, or runtime budget. Confirmed at closeout — no NFR file created.

## Deduplication / Non-Overlap (u64 extension, not replacement)

u73 **extends** u64; it does not rewrite the watchlist matcher and does not re-decide accepted matches (plan "Existing Coverage / Deduplication").

- **u64 outputs consumed as-is**: u73 reads u64 `WatchlistMatch.confidence` / `reason` / `matched_alias` directly. `build_impact_center` only **routes** existing accepted matches into buckets — it does not re-score or re-classify them.
- **Rejected is a separate near-miss scan**: `_detect_rejected` runs an independent near-miss scan over configured short ASCII tickers, excluding u64-accepted keys first, so it never reclassifies an accepted match. The matcher (`briefing/watchlist.py`) is unchanged — u64 already rejects SOL/BTC near-misses; u73 only makes those rejections visible.
- **u56 unchanged**: observational-only contract is owned by u56 and untouched; u73 is observational presentation/diagnostics only (AC-73.5).

## Key Deliverables

- **New** `src/investo/briefing/watchlist_impact.py`: grouping (`build_impact_center`) + public projection (`public_impact`) over u64 matches; `_detect_rejected` near-miss scan; deterministic ordering; Rejected 25-item cap.
- **Changed** `src/investo/publisher/watchlist_pages.py`: `render_daily_impact_page` / `write_daily_impact_page` (`site_docs/watchlist/daily.md`); index links to it with a group-semantics guide; per-term table excludes `daily.md`.
- **Changed** `src/investo/briefing/pipeline.py`: body consumes `public_impact(build_impact_center(...))` — only Direct/Related reach the body.
- **Changed** `src/investo/orchestrator/pipeline.py`: on publish, writes `site_docs/watchlist/daily.md` + per-segment backlink.
- **Tests**: new `tests/unit/briefing/test_watchlist_impact.py` (22) + `tests/unit/publisher/test_watchlist_daily_page.py` (8). Net delta +30.

## Group Schema

Priority: **Direct > Related > Uncertain > Rejected** (an explicit u64 rejection always wins over text-only matches).

| Group | Source condition | Public surface |
|-------|------------------|----------------|
| Direct | u64 `structured` match; ticker/asset `strict` or `alias` match | Briefing body, watchlist daily page, Telegram candidate |
| Related | `text` match with long / non-ASCII sector/keyword evidence | Briefing body, watchlist daily page, Telegram (macro/sector context) |
| Uncertain | short `text` match; `text` match against a ticker/asset term (ambiguous) | Collapsed diagnostics only |
| Rejected | configured short ASCII ticker (<=4 chars) + near-miss token (shared-prefix family or uppercase ticker-shaped lookalike, +-2 length, same first letter) that u64 did **not** accept | Collapsed diagnostics only |

## Short-Ticker Noise Handling

- **Rejected / non-Direct**: BTC<->BTM / BTCS (shared prefix), SOL<->SLGL (uppercase ticker-shaped lookalike), "Solana Inc" (no configured alias -> not Direct).
- **Direct preserved**: Bitcoin / BTC-USD / Solana / SOL-USD configured aliases stay Direct.
- Rejected capped at 25 items, deterministic sort.

## Public / Diagnostic Boundary (R13 redaction)

- **Public** (Direct/Related only): rendered with source titles on the daily page, in the briefing body, and in Telegram.
- **Diagnostic** (Uncertain/Rejected): emitted only inside a collapsed `<details><summary>진단: 보류/제외된 후보</summary>` block on the daily page, with titles **redacted** to source name + reason code + offending token + a 6-char title hash. Title / summary / URL are never exposed.
- **Telegram non-leakage** pinned by test: diagnostics are projected out by `public_impact` before the Telegram surface; no Uncertain/Rejected record reaches Telegram or the briefing first viewport.

## Module Boundary

`watchlist_impact.py` is briefing-internal over u64 match outputs; `watchlist_pages.py` is publisher-internal over prepared impact data; the orchestrator wires the daily page write + backlink. No briefing<->publisher<->notifier cross-import added — orchestrator-only cross-unit import rule upheld.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-73.1 | Impacts grouped as Direct / Related / Uncertain / Rejected | MET | `build_impact_center` group schema; `test_watchlist_impact.py` classification tests |
| AC-73.2 | SOL/BTC-like short-ticker false positives rejected/suppressed while valid aliases match | MET | shared-prefix + uppercase ticker-shaped near-miss -> Rejected; BTC-USD/SOL-USD/Bitcoin/Solana stay Direct; false-positive fixtures |
| AC-73.3 | Daily watchlist page prioritizes today's impacts and links to segment/date | MET | `render_daily_impact_page` puts impact groups first; orchestrator backlink; `test_watchlist_daily_page.py` ordering assertion |
| AC-73.4 | Briefing/Telegram first impressions show only high-confidence public-eligible impacts | MET | `public_impact` projection (Direct/Related only) feeds body + Telegram; non-leakage test |
| AC-73.5 | No account/brokerage/P&L/recommendation feature introduced | MET | observational grouping/diagnostics only; u56 unchanged; scope-out preserved |

## FD Divergences Ratified

None. FD was SKIP (classification/presentation over existing u64 match models; no new entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

- **DEBT-075** (Low) — the Rejected near-miss heuristic (uppercase ticker-shaped lookalike) is intentionally broad, so an unrelated uppercase ticker sharing a first letter with a configured short ticker can appear in the Rejected diagnostics block. Diagnostics-only / non-public, so it is operator-trust noise, not a reader-facing error. Suggested additive fix: tighten the lookalike rule with a known-symbol allowlist / edit-distance bound.

## Potential Risks

- **Near-miss heuristic breadth**: the uppercase ticker-shaped lookalike rule is intentionally broad (partly filtered by the +-2 length window). It can list an unrelated uppercase ticker that shares a configured short ticker's first letter in the Rejected diagnostics. Because the block is diagnostics-only and non-public (R13-redacted), this is operator-trust noise rather than a reader error. Tracked as DEBT-075; promote only if the diagnostics block is observed to be materially noisy.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: 141 files clean
- pytest: 2592 passed (+30 net: 22 watchlist-impact + 8 daily-page)
- mkdocs build --strict: pass
