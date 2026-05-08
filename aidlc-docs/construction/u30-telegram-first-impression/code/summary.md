# u30 Telegram First-Impression — Code Generation Summary

**Date**: 2026-05-09
**Unit**: u30 telegram-first-impression
**Status**: ✅ Complete (5/5 steps)

---

## Goal

Raise the information density of the morning Telegram alert without changing the underlying segment markdown. Persona evaluation 2026-05-07 (#1, P1) cited the alert as the surface most readers see exactly once.

## Steps

### Step 1 — URL Masking and Price Snapshot (already closed before this session)
- Markdown URL masking (`[상세보기](url)`) in both single-briefing and segmented summaries.
- One-line market snapshot derived from already-collected price `NormalizedItem` rows (SPX / NDX / KOSPI / BTC) prepended to the segmented header.

### Step 2 — Segment Collapse / Toggle
- `build_segmented_summary` accepts `coverage_by_segment: Mapping[MarketSegment, SegmentCoverage] | None`. When supplied and a segment's status is `insufficient`, the block collapses to a single line: `🇰🇷 *국내 증시* [부족] · [상세보기](url)` (no separate conclusion line).
- `enabled_segments: Sequence[MarketSegment] | None` filters body + footer to the listed segments. `resolve_enabled_segments(raw=None)` reads `INVESTO_TELEGRAM_ENABLED_SEGMENTS` (comma-separated, accepts canonical ids and short aliases `domestic` / `us` / `crypto`) and returns the canonical-ordered tuple. A list that filters to zero segments falls back to all-published — operator misconfiguration must not produce a link-less alert.
- Orchestrator `_stage_notify_segmented_briefing` now computes `coverage_by_segment` from `routed.coverage_for_segment(...)` (mirrors `_stage_prepare_segment_visual_assets`) and threads `resolve_enabled_segments()` from the env var.

### Step 3 — Action Tag Contract
- New module `src/investo/briefing/action_tag.py` declares the closed set: `[관망]`, `[변동성↑]`, `[강세]`, `[약세]`, `[혼조]`, `[데이터부족]`. Default tag is `[관망]`; data-limited segments are forced to `[데이터부족]`.
- `apply_action_tag(conclusion, *, data_limited, section_text=None)` is a pure function that:
  1. Forces `[데이터부족]` when `data_limited=True`.
  2. Preserves a trailing in-set tag verbatim, normalising whitespace.
  3. Strips a trailing off-set bracket token (e.g. `[BUY]`, `[강력매수]`) and replaces it with `[관망]`.
  4. Rescues a closed-set tag from the raw section ① body (`section_text`) when `_summary_sentence` clipped the conclusion at a Korean sentence terminator before the tag.
  5. Otherwise appends `[관망]`.
- Stage 2 `STAGE2_SYSTEM` prompt adds the closed-set contract: section ① must end with exactly one tag, and the post-processor strips off-set tags. The prompt explicitly forbids the LLM from emitting `[데이터부족]` (publisher decides that branch).
- `briefing/pipeline.py::_build_summary_header` now takes `data_limited: bool` and routes the conclusion through `apply_action_tag`. `_enhance_reader_experience` derives `effective_data_limited` and passes it through. Both data-limited and normal callsites propagate the flag.
- The notifier preserves the bracketed tag through `_clean_summary_text` (the markdown-link regex requires `[text](url)` shape, so a bare `[강세]` is not stripped).

### Step 4 — KST Time and Watchlist Price
- Header second line: `🕐 KST HH:MM · 전 거래일: YYYY-MM-DD`. Computed by `_publish_time_label(now_utc, target_date)` — converts `now_utc` to `Asia/Seoul`, falls back to `--:--` when `now_utc` lacks tz info.
- `_build_watchlist_price_index(price_items)` builds a casefolded `term → "(+1.2%)"` index keyed on ticker / symbol / coin_id / index_name / asset_name, plus `BTCUSDT → BTC` ticker-prefix expansion. `_format_watchlist_suffix` prefers pct alone (most readers' actionable signal); falls back to compact absolute price when only price is known; emits empty string otherwise.
- `_decorate_watchlist_with_prices(text, prices)` parses the watchlist line at the `건 확인 — ` boundary, splits matches on `;`, and decorates each `TERM: TITLE` segment to `TERM(+1.2%): TITLE` when the index has a hit; misses leave the segment ticker-only (the safe fallback).
- `_one_line_summary` accepts `watchlist_prices` and applies the decorator only when watchlist text is non-empty and not a u28 site-only branch (onboarding nudge, coverage-hold).

### Step 5 — Verification
Full quality gate:
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (203 files, post-format)
- `uv run mypy --strict src/` ✅ (79 source files)
- `uv run pytest -q` ✅ (1383 passed, +75 new tests over the pre-u30 baseline of 1308)
- `uv run mkdocs build --strict` ✅

---

## New / Modified Files

### New
- `src/investo/briefing/action_tag.py` (~120 LOC) — closed-set + `apply_action_tag` + `_scavenge_in_set_tag`.
- `tests/unit/briefing/test_action_tag.py` (19 tests).

### Modified — source
- `src/investo/briefing/pipeline.py` — `_build_summary_header(data_limited=False)`, `_enhance_reader_experience(data_limited=False)`, both call-sites thread the flag.
- `src/investo/briefing/prompts.py` — Stage 2 closed-set tag contract block.
- `src/investo/notifier/summary.py` — `build_segmented_summary(coverage_by_segment=, enabled_segments=)`, `resolve_enabled_segments`, `_publish_time_label`, `_build_watchlist_price_index`, `_decorate_watchlist_with_prices`, `_one_line_summary(watchlist_prices=)`, `_segment_summary_block(coverage=, watchlist_prices=)`.
- `src/investo/orchestrator/pipeline.py` — `_stage_notify_segmented_briefing(coverage_by_segment=)`, computes per-segment coverage in the run-pipeline notify branch and passes `resolve_enabled_segments()`.

### Modified — tests
- `tests/unit/notifier/test_summary.py` — Step 2 (collapse + toggle, 7 tests), Step 3 (action tag preservation, 1 test), Step 4 (KST header + watchlist price, 5 tests). Adjusted one existing snapshot test to accommodate the new header line.
- `tests/unit/briefing/test_summary_fidelity.py` — 4 action-tag integration tests on `_build_summary_header`.

---

## Test Delta

- 1308 → 1383 (+75 tests).

## TECH-DEBT

No new tech-debt items raised by u30. The notifier env var follows the existing `INVESTO_<SCOPE>_<NOUN>` convention.

## Source

Persona evaluation 2026-05-07 (persona #1, P1).
