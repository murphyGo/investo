# Cross-Check: u33 watchlist-depth

**Scope**: u33 watchlist-depth (Steps 1–6)
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

**Overall Compliance**: 100% (all six DoD items closed; two DoD sub-clauses — "average cost" portfolio metadata and the "email" channel — intentionally omitted because the project scope rules out portfolio/accounting state and there is no free, account-less SMTP relay).

---

## Plan / Goal

- **Plan**: `aidlc-docs/construction/plans/u33-watchlist-depth-code-generation-plan.md`
- **Goal**: Extend the watchlist surface for long-horizon trackers — position weighting, event lookahead, per-ticker history, multi-watchlist + multi-channel routing, and cumulative match visualization. Persona evaluation 2026-05-07 (#4, wish-list).

---

## Definition-of-Done Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| Optional position weight + sorted callouts | ✅ | `WatchlistConfig.weights`; `WatchlistMatch.weight`; matcher sort `(-weight, term, source, title)`. Tests `test_matches_sorted_by_weight_desc`, `test_unweighted_terms_break_alphabetically`, `test_negative_weights_rejected_at_validation`. Average-cost field intentionally out of scope (no portfolio/accounting layer). |
| 7-day lookahead callouts | ✅ | `render_watchlist_impact(now_utc=)` + `_watchlist_d_suffix`. Reuses u35 `NormalizedItem.scheduled_at`. Tests `test_render_appends_d_suffix_for_scheduled_match`, `…_omits_when_now_utc_not_supplied`, `…_skips_for_past_scheduled_at`, `…_skips_beyond_seven_days`. |
| Per-ticker accumulation page | ✅ | `publisher/watchlist_pages.update_watchlist_pages` + per-day marker idempotence; orchestrator publish-stage hook. Tests `test_update_creates_per_term_page`, `…_replaces_same_day_section_idempotent`, `…_preserves_prior_day_section`, `…_writes_index_listing_each_term`, `…_includes_weight_when_present`, `…_skips_weight_label_when_zero`, `…_handles_korean_term`. |
| Multi-watchlist with segment mapping | ✅ | `WatchlistScope` + `WatchlistConfig.scopes` + `for_segment_scope(segment)`. Tests `test_for_segment_scope_returns_self_when_no_scopes`, `…_merges_terms_for_matching_segment`, `…_skips_scopes_bound_to_other_segments`, `…_unbound_scope_applies_to_all_segments`, `test_scope_weight_overrides_root_weight`. |
| Multi-channel webhook routing | ✅ | `notifier/webhooks.py` Slack + Discord adapters; `INVESTO_WATCHLIST_WEBHOOKS` env var; `__main__` post-publish fan-out. Tests `test_load_endpoints_*`, `test_dispatch_uses_slack_text_field`, `test_dispatch_uses_discord_content_field`, `test_dispatch_swallows_4xx_failures`, `test_dispatch_skips_empty_text`. Email channel intentionally omitted (no free SMTP relay). |
| Cumulative match SVG card | ✅ | `visuals/watchlist_chart.render_cumulative_match_chart`; embedded in `site_docs/watchlist/index.md` via `_maybe_write_index`. Tests `test_chart_lists_terms_sorted_by_count_desc`, `…_breaks_ties_alphabetically`, `…_caps_visible_bars_and_collapses_overflow`, `…_is_deterministic`, `…_escapes_xml_unsafe_terms`, `…_uses_self_contained_svg`. |

---

## Scope Mapping

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-004 Telegram public-channel summary | ✅ | The Telegram one-liner already shows watchlist matches; u33 adds D-N suffix on lookahead matches via the same `render_watchlist_impact` helper. | Telegram surface unchanged in shape — only an optional D-N substring is appended for forward-scheduled matches. |
| FR-007 operator alerts | ✅ | Webhook fan-out is observability, not an operator alert. | Boot-alert dedup, Telegram retries, etc. unchanged. |
| FR-003 static web publishing | ✅ | New `site_docs/watchlist/{slug}.md` and `site_docs/watchlist/index.md` pages | mkdocs build --strict ✅. |
| NFR-002 cost / no paid APIs | ✅ | All u33 code is local I/O + free Slack / Discord webhooks. No paid SaaS. | Per the email-channel sub-clause, we explicitly skip a paid SMTP relay. |
| NFR-003 graceful degradation | ✅ | Webhook fan-out best-effort (4xx / 5xx / connection error swallowed); idempotent per-day section replacement; rollback snapshots wired in. | Watchlist features off by default (empty config / unset env). |
| NFR-004 compliance / disclaimer boundary | ✅ | Watchlist pages do NOT carry the public briefing markdown — they are append-only metadata pages | The disclaimer gate runs only on the per-segment archive markdown, unchanged. |
| NFR-005 consistency / DRY | ✅ | Single `WatchlistMatch` shape carries weight; single sort comparator; single SVG chart helper; webhook payload-shape helper | No duplicated env-parsers (load_webhook_endpoints is the chokepoint). |
| NFR-006 testing | ✅ | +36 targeted tests (1450 → 1486) | 12 watchlist + 10 webhooks + 7 watchlist-pages + 7 chart = 36. |
| NFR-007 secret hygiene (R13) | ✅ | Webhook URLs are secrets; the dispatch helper redacts the URL via the u27 chokepoint before logging on failure; success path logs no URL. The `INVESTO_WATCHLIST_WEBHOOKS` env var is read once and never echoed. | Per-ticker pages do not carry any secret-shaped substrings (matched item fields already pass through u22 redaction at collection time). |

---

## Architectural / Module-Boundary Notes

- `notifier/webhooks.py` only imports from `_internal/redaction` + `models` + `httpx` — no orchestrator hop.
- `publisher/watchlist_pages.py` imports `briefing.watchlist.WatchlistMatch` (allowed — both modules sit on the orchestrator-only-import side of the boundary, and the publisher already imports briefing types via u29's hero block).
- `visuals/watchlist_chart.py` is pure SVG rendering — no I/O.
- `__main__` orchestrates the webhook fan-out alongside the existing weekly-digest dispatch; the dry-run flag short-circuits both.

## Quality Gate

- `uv run ruff check .` — ✅
- `uv run ruff format --check .` — ✅ (226 files)
- `uv run mypy --strict src/` — ✅ (90 source files)
- `uv run pytest -q` — ✅ (1486 passed)
- `uv run mkdocs build --strict` — ✅

## TECH-DEBT Delta

No new TECH-DEBT items. No DEBT-* resolved.

The DoD sub-clauses that were intentionally omitted:
- **Average cost field** — out of scope. Adding a cost-basis field crosses into portfolio / accounting state, which the project explicitly avoids ("no portfolio / accounting / cost-basis logic").
- **Email channel** — there is no free, account-less SMTP relay we could integrate without a paid SaaS. Operators wanting email can pipe their Slack / Discord webhooks through their own forwarding tools.

## Status

u33 watchlist-depth construction and cross-check **complete**.
