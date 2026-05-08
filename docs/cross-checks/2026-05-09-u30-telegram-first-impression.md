# Cross-Check: u30 telegram-first-impression

**Scope**: u30 telegram-first-impression (Steps 1–5)
**Date**: 2026-05-09
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 6 | 100% |
| ⚠️ Partial | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ❌ Gap | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100% (all six DoD items closed).

---

## Plan / Goal

- **Plan**: `aidlc-docs/construction/plans/u30-telegram-first-impression-code-generation-plan.md`
- **Goal**: Raise the information density of the morning Telegram alert (the surface most readers see exactly once) without changing the underlying segment markdown. Persona evaluation 2026-05-07 (#1, P1).

---

## Definition-of-Done Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| Markdown URL masking (`[상세보기](url)`) | ✅ | `notifier/summary.py::_detail_link`; both single-briefing and segmented summaries render `[상세보기](url)`. Tests `test_build_summary_includes_target_date_and_url`, `test_build_segmented_summary_includes_all_labels_and_urls`. |
| One-line market snapshot from collected price items | ✅ | `notifier/summary.py::_market_snapshot_line` + `_snapshot_part_for_*` (`SPX`, `NDX`, `KOSPI`, `BTC`); missing parts omitted gracefully. Test `test_build_segmented_summary_adds_market_snapshot_from_price_items` (also covers `_omits_market_snapshot_when_price_items_missing`). |
| Insufficient-coverage segments collapse / `enabled_segments` toggle | ✅ | `build_segmented_summary(coverage_by_segment=, enabled_segments=)`. Insufficient → `🇰🇷 *국내 증시* [부족] · [상세보기](url)` single line. Env var `INVESTO_TELEGRAM_ENABLED_SEGMENTS` resolved through `resolve_enabled_segments`. Operator-misconfig fallback: empty resolved list → render all published. Tests `test_insufficient_segment_collapses_to_single_line_when_coverage_supplied`, `test_partial_or_normal_segment_keeps_three_line_block`, `test_enabled_segments_filter_drops_other_segments_from_body_and_footer`, `test_enabled_segments_falls_back_to_all_when_filter_excludes_everything`, `test_resolve_enabled_segments_*`. |
| Closed-set action tag at end of each segment conclusion | ✅ | `briefing/action_tag.py::apply_action_tag` (closed set: `[관망]` / `[변동성↑]` / `[강세]` / `[약세]` / `[혼조]` / `[데이터부족]`); Stage 2 `STAGE2_SYSTEM` carries the strict tag contract. `_build_summary_header(data_limited=)` plumbs the override. Off-set tags (`[BUY]`, `[강력매수]`) are stripped → `[관망]`. Data-limited segments forced to `[데이터부족]`. Tests `tests/unit/briefing/test_action_tag.py` (19 tests), `tests/unit/briefing/test_summary_fidelity.py::test_summary_header_*` (4 tests), `tests/unit/notifier/test_summary.py::test_action_tag_is_preserved_in_telegram_one_liner`. |
| Header shows publish KST time + `(전 거래일: YYYY-MM-DD)` label | ✅ | `notifier/summary.py::_publish_time_label` emits `🕐 KST HH:MM · 전 거래일: YYYY-MM-DD` between the title and snapshot rows. Determinism via `now_utc` kwarg. Tests `test_header_includes_kst_publish_time_and_previous_trading_day_label`, `test_publish_time_is_deterministic_when_now_utc_provided`. |
| Watchlist suffix includes price; ticker-only fallback on collection failure | ✅ | `_build_watchlist_price_index` (term → suffix index over price items, with `BTCUSDT → BTC` ticker-prefix expansion); `_decorate_watchlist_with_prices` decorates each `TERM:` segment in the cleaned watchlist text; missing prices leave the term unchanged. Tests `test_watchlist_match_gets_price_suffix_when_price_item_available`, `test_watchlist_match_falls_back_to_ticker_only_when_price_missing`, `test_watchlist_match_decoration_skips_unmatched_terms`. |

---

## Scope Mapping

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-004 Telegram public-channel summary | ✅ | `notifier/summary.py::build_segmented_summary` end-to-end | All six DoD items implemented at the notifier surface; orchestrator threads coverage and env-var-resolved enabled segments. |
| FR-008 segmented briefing | ✅ | per-segment block; `coverage_by_segment` keyed by `MarketSegment` | Per-segment collapse decision; per-segment toggle filtering; per-segment imminent tag preserved (u35 contract intact). |
| NFR-002 cost / no paid APIs | ✅ | All u30 code is pure Python on existing collected price items; no new external endpoints | The watchlist price suffix reuses the existing yfinance / coingecko / binance / FSC-KRX rows already in `items`. |
| NFR-003 graceful degradation | ✅ | Operator misconfiguration of `INVESTO_TELEGRAM_ENABLED_SEGMENTS` (token typos, all-tokens-unknown) falls back to all-published; missing watchlist price falls back to ticker-only; missing `now_utc` tz returns `--:--` | None of the new code paths can produce a link-less alert. |
| NFR-004 compliance / disclaimer boundary | ✅ | Publisher `verify_disclaimer` is unchanged; u30 is a notifier-side / briefing-side rendering change | The Stage 2 closed-set tag contract does not alter the briefing markdown sections; publisher gates remain in force. |
| NFR-005 consistency / DRY | ✅ | Action tag is single chokepoint; segment alias resolution single chokepoint; price index single chokepoint | No duplicated bracket-token parsers, no duplicated env-var parsers. The action_tag closed set is asserted by `tests/unit/briefing/test_action_tag.py::test_closed_set_size`. |
| NFR-006 testing | ✅ | +75 targeted tests (1308 → 1383) | `tests/unit/briefing/test_action_tag.py` (19); `tests/unit/briefing/test_summary_fidelity.py` (+4); `tests/unit/notifier/test_summary.py` (+13). One existing snapshot test (`test_build_segmented_summary_adds_market_snapshot_from_price_items`) updated to accommodate the new header line. |
| NFR-007 secret hygiene (R13) | ✅ | `INVESTO_TELEGRAM_ENABLED_SEGMENTS` is a non-secret env var (segment-id allowlist); price index keys are derived from `raw_metadata` (already redacted upstream); no clock leak (orchestrator passes `now_utc` only when explicit) | u27 `_internal/redaction.py` chokepoint preserved; no logger calls added to u30. |

---

## Architectural / Module-Boundary Notes

- The notifier imports `SegmentCoverage` from `investo.briefing.segments` (allowed — both modules are on the orchestrator side of the boundary; `notifier` already imports `briefing.segments` since u22).
- `briefing/action_tag.py` is purely a briefing-internal helper; nothing outside `briefing/` imports it.
- The orchestrator continues to be the only module that imports `notifier`. `_stage_notify_segmented_briefing` calls `resolve_enabled_segments()` directly (env-var read at notify time, matches u35 `now_utc` lazy-resolution pattern).

## Quality Gate

- `uv run ruff check .` — ✅
- `uv run ruff format --check .` — ✅ (203 files post-format)
- `uv run mypy --strict src/` — ✅ (79 source files)
- `uv run pytest -q` — ✅ (1383 passed)
- `uv run mkdocs build --strict` — ✅

## TECH-DEBT Delta

No new TECH-DEBT items. No DEBT-* resolved.

## Status

u30 telegram-first-impression construction and cross-check **complete**.
