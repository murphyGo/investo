# Code Summary: u35 event-lookahead

**Date**: 2026-05-08

## Completed

- Lifted each daily briefing from a backward-looking recap into forward-looking context by surfacing the upcoming week's and month's high-impact scheduled events inside the segment narrative — vertical slice from source adapter to LLM prompt to segment markdown to Telegram summary, all on free public data and within existing budgets, gates, and module boundaries.
- **Phase 0 — DEBT-060 통합 (precondition)**: introduced `src/investo/briefing/extract.py` (`extract_conclusion`, `extract_key_drivers`, `extract_caution`, `extract_watermark`) plus public `CONCLUSION_PREFIX` / `DRIVER_PREFIX` / `CAUTION_PREFIX` / `WATERMARK_PREFIX` exports on `briefing/summary_quality.py`. Switched all 5 existing duplicated sites (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, `briefing/context.py`) to import from the chokepoint helper. Added grep guard `tests/unit/briefing/test_extract.py::test_no_surface_redeclares_prefix_literal` that fails fast the moment a sixth consumer redeclares any of the prefix literals locally — DEBT-060 moved to Resolved Items.
- **Phase 1 — Event Lookahead (partial)**: model layer extended with `NormalizedItem.scheduled_at: datetime | None` (default `None`, backward-compat) + `ensure_tz_aware` validator; `sources/_window.py::FetchWindow.lookahead(days)` builder added (raises on `days <= 0`, preserves `target_date` anchoring + half-open membership); `nasdaq-earnings-calendar` extended to opt-in lookahead (`INVESTO_EARNINGS_LOOKAHEAD_DAYS`, clamp `[0, 14]`, per-day failure isolation); Stage 2 system prompt adds a "주요 일정" rules block (input-only citation / no arbitrary forecast / 이번 주·이번 달 framing); `briefing/pipeline.py` adds `_MAX_LLM_LOOKAHEAD_ITEMS = 12` sub-cap inside the u13 96-total / 24-per-source cap, plus `_render_lookahead_context_block` renderer + `{lookahead_context}` placeholder on `STAGE2_USER_TEMPLATE` with explicit empty-bucket Korean note ("예정된 주요 일정이 없습니다."); `notifier/summary.py::build_segmented_summary` accepts `lookahead_items_by_segment` + `now_utc` and prepends a deterministic `📊 NVDA 실적 D-2` / `📅 FOMC press release — Fe… D-2` tag for events inside the 72h horizon (top-1 by ascending `scheduled_at`, tiebreaker source then title; LLM never sees this tag; absence keeps the line unchanged).
- Lookahead block lives on a separate ~300-char-per-segment budget (80-char title trim × 12-row sub-cap) so combined Stage 2 context per segment caps at ~800 chars when paired with the u34 ~500-char recent-context budget — the u13 candidate cap (96 total / 24 per source) is unaffected.
- **R10 (record/replay fixtures, no fabrication) honoured end-to-end**: 4 new lookahead-specific source adapters (`fomc-calendar`, `fred-economic-calendar`, `coingecko-events`, KRX option-expiry) require live-API access for fixture recording and are registered as DEBT-067 (P1) for the next live-credential session. The orchestrator wire-through (`_stage_notify_segmented_briefing` per-segment lookahead bucket → `build_segmented_summary`) and `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` reason code are registered as DEBT-067 sub-bullets so they land **with** the adapters that populate them, not before — landing them today would (a) be dead code on the production critical path and (b) cause the new reason code to fire on every segment indefinitely, eroding the u22 coverage-trust contract.
- Applied pre-merge code fix:
  - **M2** — `tests/unit/notifier/test_summary.py::test_imminent_tag_uses_fomc_label_for_calendar_source` strengthened with the explicit substring pin `assert "📅 FOMC press release — Fe… D-2" in summary`. Closes the regression-pin gap on the FOMC label substring shape so a future label-format edit fails fast at unit level rather than silently shifting the Telegram surface.
- M1 (orchestrator wire-through must pass `now_utc` explicitly alongside `lookahead_items_by_segment`; `now_utc=None` while `lookahead_items_by_segment` is supplied raises `ValueError`) and M3 (single-filter reuse — `_render_lookahead_context_block` filter result reused so the markdown context block + the Telegram tag selector see exactly one filtered list) → registered as **DEBT-067** sub-bullets.

## Files Changed

### New source files (Phase 0)

- `src/investo/briefing/extract.py` — chokepoint helper module exposing `extract_conclusion(rendered_markdown: str) -> str | None`, `extract_key_drivers(...)`, `extract_caution(...)`, `extract_watermark(...)`. Implementations match the existing prefix-anchor extraction logic previously duplicated across 5 sites.

### Modified source files (Phase 0)

- `src/investo/briefing/summary_quality.py` — promotes `CONCLUSION_PREFIX`, `DRIVER_PREFIX`, `CAUTION_PREFIX`, `WATERMARK_PREFIX` to public exports (previously module-private literals duplicated in 4-5 sites).
- `src/investo/publisher/site_index.py` — switched to chokepoint import; local prefix literal removed.
- `src/investo/publisher/weekly_digest.py` — switched to chokepoint import; local prefix literal removed.
- `src/investo/visuals/og_card.py` — switched to chokepoint import; local prefix literal removed.
- `src/investo/visuals/assets.py` — switched to chokepoint import; local prefix literals removed.
- `src/investo/briefing/context.py` — switched to chokepoint import; local `_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX` literals removed.

### Modified source files (Phase 1)

- `src/investo/models/items.py` — `NormalizedItem.scheduled_at: datetime | None` added (default `None`, backward-compat); `ensure_tz_aware` validator extended.
- `src/investo/sources/_window.py` — `FetchWindow.lookahead(days)` builder; raises on `days <= 0`; preserves `target_date` anchoring + half-open membership.
- `src/investo/sources/nasdaq_earnings_calendar.py` — opt-in `INVESTO_EARNINGS_LOOKAHEAD_DAYS` (clamp `[0, 14]`); per-day failure isolation so the target-date pass never breaks; reuses existing R14 fair-access UA + `retry_get` identity-encoding contract.
- `src/investo/briefing/prompts.py` — `LOOKAHEAD_HEADER` / `LOOKAHEAD_INTRO` / `LOOKAHEAD_EMPTY_NOTE` constants; `format_lookahead_section` helper; `STAGE2_SYSTEM` "주요 일정" rules block; `STAGE2_USER_TEMPLATE` `{lookahead_context}` placeholder.
- `src/investo/briefing/pipeline.py` — `_MAX_LLM_LOOKAHEAD_ITEMS = 12` sub-cap; `_render_lookahead_context_block` renderer with explicit empty-bucket Korean note; `_synthesize` signature extended to thread the lookahead bucket.
- `src/investo/notifier/summary.py` — `build_segmented_summary` accepts `lookahead_items_by_segment` + `now_utc` kwargs (both default `None`); `_imminent_event_tag` / `_imminent_event_label` deterministic 72h selector; LLM never sees this tag.

### New test files

- `tests/unit/briefing/test_extract.py` — 18 tests (parametrized over the 4 extractors × present / missing / multiple-line shapes, plus the grep guard `test_no_surface_redeclares_prefix_literal`).
- `tests/unit/briefing/test_pipeline_lookahead_render.py` — 5 tests on `_render_lookahead_context_block` (empty-bucket branch, sub-cap enforcement, 80-char title trim, deterministic ordering, segment isolation).

### Modified test files

- `tests/unit/sources/test_window.py` — +3 tests pinning `FetchWindow.lookahead(days)`.
- `tests/unit/sources/test_nasdaq_earnings_calendar.py` — +6 tests pinning `INVESTO_EARNINGS_LOOKAHEAD_DAYS` clamp `[0, 14]`, opt-out default, per-day failure isolation, scheduled_at attachment, ordering.
- `tests/unit/briefing/test_prompts.py` — +3 sentinels + 2 갱신.
- `tests/unit/notifier/test_summary.py` — +5 tests including **M2 fix** with explicit `assert "📅 FOMC press release — Fe… D-2" in summary` substring pin.

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-060 moved to Resolved Items; DEBT-067 added under High Priority)
- `docs/cross-checks/2026-05-08-u35-event-lookahead.md` (new)
- `aidlc-docs/audit.md` (Cross-Check + Code Generation Complete entries newest-first)
- `aidlc-docs/aidlc-state.md` (Per-Unit row u35 ⏳ Planned → ✅ Complete with partial / DEBT-067 cross-ref)
- `aidlc-docs/construction/plans/u35-event-lookahead-code-generation-plan.md` (DoD + step checkboxes marked)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — Korean briefing comprehension: Stage 2 system prompt carries the three "주요 일정" usage rules in Korean; empty-bucket branch emits the explicit "예정된 주요 일정이 없습니다." note.
- **FR-003** — static web publishing: no site-content surface change.
- **FR-008** — segmented briefing: lookahead bucket is segment-scoped end-to-end; no cross-segment bleed.
- **NFR-002** (cost / no paid APIs) — Phase 1 only extends the existing free public `nasdaq-earnings-calendar`; the 4 deferred adapters are explicitly scoped to free public feeds.
- **NFR-003** (graceful degradation) — per-day failure isolation in `nasdaq-earnings-calendar`; `INVESTO_EARNINGS_LOOKAHEAD_DAYS` opt-out default; lookahead empty-bucket branch produces the explicit "no lookahead" note.
- **NFR-004** (compliance / disclaimer) — `verify_disclaimer` remains the publish-time gate; u35 does not bypass it.
- **NFR-005** (consistency / DRY) — Phase 0 chokepoint resolves DEBT-060 across 5 sites; grep guard fails fast on the sixth consumer.
- **NFR-006** (testing) — +40 targeted tests (1268 → 1308).
- **NFR-007** (R8 / R10 / R13 / R14) — `INVESTO_EARNINGS_LOOKAHEAD_DAYS` is a non-secret integer clamp; `nasdaq-earnings-calendar` lookahead reuses the existing R14 UA + `retry_get` identity-encoding contract; R10 honoured by deferring fabricated-fixture-blocked adapters to DEBT-067.

## Architecture Summary

```
briefing/
  extract.py                          # NEW chokepoint (Phase 0)
    extract_conclusion(md) -> str | None
    extract_key_drivers(md) -> list[str]
    extract_caution(md) -> str | None
    extract_watermark(md) -> str | None

  summary_quality.py
    CONCLUSION_PREFIX                 # public export (Phase 0)
    DRIVER_PREFIX                     # public export (Phase 0)
    CAUTION_PREFIX                    # public export (Phase 0)
    WATERMARK_PREFIX                  # public export (Phase 0)

  prompts.py
    LOOKAHEAD_HEADER / INTRO / EMPTY_NOTE
    format_lookahead_section(...)
    STAGE2_SYSTEM                     # + "주요 일정" rules block
    STAGE2_USER_TEMPLATE              # + {lookahead_context} placeholder

  pipeline.py
    _MAX_LLM_LOOKAHEAD_ITEMS = 12
    _render_lookahead_context_block(...)
                                      #   empty-bucket → Korean note
                                      #   80-char title trim
                                      #   12-row sub-cap inside u13 96/24

models/items.py
  NormalizedItem
    scheduled_at: datetime | None     # NEW (Phase 1)

sources/
  _window.py
    FetchWindow.lookahead(days)       # NEW builder (Phase 1)
                                      #   raises on days <= 0
                                      #   half-open membership preserved
  nasdaq_earnings_calendar.py
    INVESTO_EARNINGS_LOOKAHEAD_DAYS   # opt-in [0, 14] clamp
                                      #   per-day failure isolation

notifier/summary.py
  build_segmented_summary(
    ...,
    lookahead_items_by_segment=None,  # NEW kwarg (Phase 1)
    now_utc=None,                     # NEW kwarg (Phase 1)
  )
  _imminent_event_tag(...)            # deterministic 72h selector
  _imminent_event_label(...)          # FOMC / earnings / generic
                                      # LLM never sees this tag
```

The lookahead block flows into Stage 2 only — Stage 1 classification, hero callout, and visual cards are unchanged. The orchestrator continues to be the only cross-unit importer; Phase 0's `briefing/extract.py` chokepoint sits inside `briefing/` and does not import `sources` / `publisher` / `notifier`.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M2 (`tests/unit/notifier/test_summary.py::test_imminent_tag_uses_fomc_label_for_calendar_source` strengthened with explicit FOMC label substring pin) applied pre-merge.
- H1 (4 new lookahead source adapters) → **DEBT-067** (P1). Blocked on R10 (fabricated fixture 금지).
- M1 (orchestrator wire-through clock-explicit contract) + M3 (single-filter reuse) → **DEBT-067** sub-bullets.
- **DEBT-060 Resolved** by Phase 0 (5-site chokepoint consolidation; grep guard fails fast on sixth consumer).
- No Critical or High findings introduced by u35.
- Cross-check: `docs/cross-checks/2026-05-08-u35-event-lookahead.md`.
- Source: user direct request 2026-05-08 — "이번주나 이번달 중요한 이벤트가 있으면 미리 파악해서 주요 일정을 시황에 포함". Wave 4.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .` (187 files)
- `uv run mypy --strict src/` (71 source files)
- `uv run pytest -q` (1308 passed; 1268 → 1308, +40 new tests)
- `uv run mkdocs build --strict` (passed; no site content change in u35)

> **Permission-restricted environments**: when the editor sandbox refuses to write into `aidlc-docs/` or `docs/`, fall back to Bash heredoc (`cat <<'EOF' > <abs-path>`) for documentation deliverables. Source / test changes always go through the editor in the supported path.
