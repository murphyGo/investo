# Cross-Check: u35 event-lookahead

**Scope**: u35 event-lookahead (Phase 0 DEBT-060 통합 + Phase 1 partial)
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 7 | 78% |
| ⚠️ Partial | 1 | 11% |
| 🔄 Deferred | 1 | 11% |
| ❌ Gap | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **9** | **100%** |

**Overall Compliance**: 89% (Phase 0 fully landed; Phase 1 vertical slice landed end-to-end except for the 4 new lookahead-specific source adapters + their orchestrator wire-through, both of which are blocked on live-API fixture recording per R10 and have been registered as DEBT-067).

---

## Plan / Goal

- **Plan**: `aidlc-docs/construction/plans/u35-event-lookahead-code-generation-plan.md`
- **Goal**: Lift each daily briefing from a backward-looking recap into forward-looking context by surfacing the upcoming week's and month's high-impact scheduled events (FOMC / FRB calendar, US macro releases, Big Tech earnings, KRX option-expiry, crypto token unlocks / major upgrades) inside the segment narrative — vertical slice from source adapter to LLM prompt to segment markdown to Telegram summary, all on free public data and within existing budgets, gates, and module boundaries.
- **Bundled scope**: u35 also lands **Phase 0 — DEBT-060 통합** as a precondition before adding the fifth conclusion-extraction surface to a sixth. Phase 0 introduces `src/investo/briefing/extract.py` (`extract_conclusion`, `extract_key_drivers`, `extract_caution`, `extract_watermark`) plus public `CONCLUSION_PREFIX` / `DRIVER_PREFIX` / `CAUTION_PREFIX` / `WATERMARK_PREFIX` exports on `briefing/summary_quality.py`, and switches the 5 existing duplicated sites (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, `briefing/context.py`) to import the chokepoint helpers. The Phase 0 grep guard (`tests/unit/briefing/test_extract.py::test_no_surface_redeclares_prefix_literal`) fails fast the moment a sixth consumer redeclares any of the prefix literals locally.

---

## Partial-Implementation Justification (R10 — Fabricated Fixture 금지)

u35 Phase 1 is intentionally a **partial** implementation. Per project rule R10 (`record/replay fixtures`) the source-adapter test layer is forbidden from carrying fabricated payloads — every fixture must be the byte output of a live API recording. Four of the planned lookahead adapters (`fomc-calendar`, `fred-economic-calendar`, `coingecko-events`, KRX option-expiry) require **live API access** that is unavailable inside the offline coding session that delivered Phase 0 + Phase 1 partial; landing the adapters with synthesized fixtures would directly violate R10 and contaminate the regression baseline. Landing the orchestrator wire-through (`_stage_notify_segmented_briefing` per-segment lookahead bucket → `build_segmented_summary`) and the `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` reason code without any populating adapter would (a) be dead code on the production critical path until Phase 2 lands and (b) cause the new reason code to fire on **every** segment indefinitely, eroding the u22 coverage-trust contract that readers rely on.

Three sub-decisions follow:

1. **Adapter layer** — `nasdaq-earnings-calendar` (which already has a live-recorded fixture set under `tests/fixtures/sources/nasdaq_earnings_calendar/`) extends to opt-in lookahead (`INVESTO_EARNINGS_LOOKAHEAD_DAYS`, clamp `[0, 14]`, per-day failure isolation). The four new adapters are registered as `DEBT-067` (P1) for the next live-credential session.
2. **Orchestrator wire-through + reason code** — registered as sub-bullets under `DEBT-067` so they land **with** the adapters that populate them, not before. The `notifier/summary.py::build_segmented_summary` `lookahead_items_by_segment` kwarg already accepts the bucket and defaults to `None` (backward-compat); the `_imminent_event_tag` / `_imminent_event_label` deterministic 72h selector is fully implemented and tested today.
3. **Stage 2 prompt + segment markdown + briefing pipeline** — fully landed end-to-end this session (DoD items 4 / 5 / 6 / 8). The 12-row sub-cap (`_MAX_LLM_LOOKAHEAD_ITEMS`) sits inside the existing u13 96-total / 24-per-source candidate cap so a future high-volume adapter cannot starve backward evidence. The `{lookahead_context}` placeholder + `_render_lookahead_context_block` empty-bucket branch produce the explicit "no lookahead" Korean note today, so the prompt path is observable from the moment a real lookahead bucket arrives.

Net effect: Phase 0 is the load-bearing investment (DEBT-060 was promoted Medium → High by u34 specifically because u35 was the imminent sixth-consumer trigger), and Phase 1 lands every layer u35 itself owns *except* the four new adapters and the two surfaces that sit immediately downstream of them. The user-visible Telegram imminent tag goes live the moment any one of the four DEBT-067 adapters lands.

---

## Scope Mapping

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/briefing/prompts.py::STAGE2_SYSTEM` (LOOKAHEAD_HEADER / LOOKAHEAD_INTRO / LOOKAHEAD_EMPTY_NOTE), `format_lookahead_section` helper, "주요 일정" rules block | Stage 2 system prompt carries the three "주요 일정" usage rules (input-only citation / no arbitrary forecast / 이번 주·이번 달 framing) in Korean. Empty-bucket branch emits the explicit "예정된 주요 일정이 없습니다." note so the LLM cannot silently skip the section. |
| FR-003 static web publishing | ✅ | No site-content surface change at the publisher layer; segment markdown receives the lookahead bucket via `{lookahead_context}` placeholder + `_render_lookahead_context_block` renderer (briefing-side only) | mkdocs build is unaffected. The lookahead block flows through the existing publisher path; archive entries continue to gate on `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality`. |
| FR-008 segmented briefing | ✅ | `briefing/pipeline.py::_render_lookahead_context_block` per-segment iteration; `notifier/summary.py::build_segmented_summary` per-segment imminent tag selection | Lookahead bucket is segment-scoped end-to-end; no cross-segment bleed. Empty-segment branch returns the explicit "no lookahead" note and the Telegram one-line summary stays unchanged (kwarg defaults to `None`). |
| NFR-002 cost / no paid APIs | ✅ | `nasdaq-earnings-calendar` lookahead is an opt-in env-var clamp on the existing free public JSON endpoint; no new external endpoints landed by Phase 1 | The four new adapters (DEBT-067) are explicitly scoped to **free public** feeds (Federal Reserve press_monetary RSS, FRED / Treasury / BLS public release-schedule, CoinGecko events public endpoint, KRX option-expiry public feed). Paid CME FedWatch / Investing.com scraping / Truflation are out of scope. |
| NFR-003 graceful degradation | ✅ | Per-day failure isolation in `nasdaq-earnings-calendar` lookahead loop; `FetchWindow.lookahead(days)` raises on `days <= 0`; lookahead empty-bucket branch produces the explicit "no lookahead" note | `INVESTO_EARNINGS_LOOKAHEAD_DAYS` clamps to `[0, 14]`; opt-out is the default (env unset = 0 days = backward-compat). The empty-bucket path is exercised by the test suite. |
| NFR-004 compliance / disclaimer boundary | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u35 reads only post-publish archive markdown via the existing chokepoint and adds no new publish-time bypass | The lookahead block flows into Stage 2 only; the rendered briefing continues to gate on `verify_disclaimer` + `summary_quality` before atomic write. |
| NFR-005 consistency / DRY | ✅ | Phase 0 — `briefing/extract.py` chokepoint + 4 public prefix exports on `briefing/summary_quality.py`; 5-site import switch (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, `briefing/context.py`); grep guard `test_no_surface_redeclares_prefix_literal` | DEBT-060 resolved by Phase 0. The grep guard fails fast the moment a sixth consumer redeclares any of the prefix literals locally; the next consumer to land must import from `briefing/extract.py`. |
| NFR-006 testing | ✅ | +40 targeted tests (1268 → 1308) | `tests/unit/briefing/test_extract.py` (18 — parametrized + grep guard); `tests/unit/briefing/test_pipeline_lookahead_render.py` (5); `tests/unit/sources/test_window.py` (+3); `tests/unit/sources/test_nasdaq_earnings_calendar.py` (+6); `tests/unit/briefing/test_prompts.py` (+3 + 2 갱신); `tests/unit/notifier/test_summary.py` (+5). |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `INVESTO_EARNINGS_LOOKAHEAD_DAYS` is a non-secret integer clamp; `nasdaq-earnings-calendar` lookahead reuses the existing `retry_get` identity-encoding + R14 fair-access UA contract; no new env var carries credentials | u27 `_internal/redaction.py` chokepoint preserved end-to-end; lookahead block is gated through the same `redact_text` defensive path as recent-context. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Forward-looking event coverage extends across 3 segments via free public sources only. | ⚠️ Partial | `nasdaq-earnings-calendar` lookahead opt-in landed (Step 1); 4 new adapters (`fomc-calendar`, `fred-economic-calendar`, `coingecko-events`, KRX option-expiry) deferred to **DEBT-067** under R10 (fabricated fixture 금지) — see Partial-Implementation Justification above. The existing `fomc-rss` adapter continues to surface scheduled meeting press releases. |
| Model layer expresses scheduled time distinct from publish time. | ✅ | `src/investo/models/items.py::NormalizedItem.scheduled_at: datetime | None` (default `None`, backward-compat); `ensure_tz_aware` validator extended; pinned by existing model unit tests + `test_window.py` lookahead pin. |
| `FetchWindow.lookahead(days)` builder added; aggregator stays single-pass; per-adapter env-var opt-in. | ✅ | `src/investo/sources/_window.py::FetchWindow.lookahead(days)` raises on `days <= 0`, preserves `target_date` anchoring + half-open membership; pinned by `tests/unit/sources/test_window.py` (+3 tests). |
| Stage 2 system prompt adds a "주요 일정" section + the three usage rules; Stage 1 untouched. | ✅ | `src/investo/briefing/prompts.py::STAGE2_SYSTEM` carries the three usage rules (input-only citation / no arbitrary forecast / 이번 주·이번 달 framing); Stage 1 prompt unchanged. Pinned by `tests/unit/briefing/test_prompts.py` (+3 sentinels + 2 갱신). |
| Briefing pipeline applies lookahead sub-cap inside the u13 96-total / 24-per-source cap. | ✅ | `briefing/pipeline.py::_MAX_LLM_LOOKAHEAD_ITEMS = 12`; sits inside the existing u13 cap; pinned by `test_pipeline_lookahead_render.py`. |
| Segment markdown receives the lookahead bucket via `{lookahead_context}` placeholder + `_render_lookahead_context_block` renderer; empty-bucket branch emits the "no lookahead" note. | ✅ | `briefing/pipeline.py::_render_lookahead_context_block` + `STAGE2_USER_TEMPLATE` `{lookahead_context}` placeholder; empty-bucket branch emits explicit Korean "예정된 주요 일정이 없습니다." note; pinned by `test_pipeline_lookahead_render.py` (5 tests including empty-bucket branch). |
| Telegram summary one-line summary prepends a deterministic imminent-event tag (D-1 / D-2) when `scheduled_at` falls inside the 72h horizon. | ✅ | `notifier/summary.py::build_segmented_summary` accepts `lookahead_items_by_segment` + `now_utc`; `_imminent_event_tag` / `_imminent_event_label` selects top-1 by ascending `scheduled_at` (tiebreaker source then title); LLM never sees this tag; absence keeps line unchanged (kwarg defaults to `None`). M2 fix pinned by `tests/unit/notifier/test_summary.py::test_imminent_tag_uses_fomc_label_for_calendar_source` (`assert "📅 FOMC press release — Fe… D-2" in summary`). |
| `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` reason code wiring. | 🔄 Deferred | Registered under **DEBT-067** sub-bullet alongside the source adapters that will populate the bucket. Landing the wiring without the adapters would always show `LOOKAHEAD_DATA_MISSING` and degrade the u22 coverage contract's reader-trust signal. |
| Token / character budget guard: lookahead block ~300 chars per segment via 80-char title trim + 12-row sub-cap; separate budget from u34 recent-context. | ✅ | `briefing/pipeline.py` 80-char title trim + `_MAX_LLM_LOOKAHEAD_ITEMS = 12`; lives separately from the u34 `~500 chars / segment / day` recent-context budget so combined Stage 2 context per segment caps at ~800 chars. |
| R8 (defusedxml only) and R13 (secret hygiene) preserved. | ✅ | `nasdaq-earnings-calendar` lookahead reuses the existing R14 fair-access UA + `retry_get` identity-encoding contract; no new XML parsing path; `INVESTO_EARNINGS_LOOKAHEAD_DAYS` is a non-secret integer; u27 `_internal/redaction.py` chokepoint unchanged. |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed (187 files)
- `uv run mypy --strict src/` — passed (71 source files)
- `uv run pytest -q` — 1308 passed (1268 → 1308, +40 new tests)
- `uv run mkdocs build --strict` — passed (no site content change in u35)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u35 is a Stage 2 prompt-context + notifier-tag layer; no LLM client introduced. The lookahead block flows into the existing Claude Code CLI subprocess as plain text; the imminent tag is computed deterministically from `scheduled_at` + `now_utc` only. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | New helpers live inside `briefing/extract.py`, `briefing/pipeline.py`, `sources/_window.py`, `notifier/summary.py`; the orchestrator continues to be the only cross-unit importer. No `briefing → sources` / `briefing → publisher` / `briefing → notifier` import added. |
| 무료 API only (no paid keys) | ✅ | Phase 1 only extends the existing free public `nasdaq-earnings-calendar`; the 4 deferred adapters (DEBT-067) are explicitly scoped to free public feeds. No paid API key surface introduced. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u35 does not bypass it. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u35 does not change notifier targets. The imminent tag is a content surface inside the existing public-channel summary. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | `scheduled_at` is added as a top-level optional field; `raw_metadata` shape unchanged. |
| R10 (record/replay fixtures, no fabrication) | ✅ | Honoured — the four new adapters are deferred to DEBT-067 specifically because R10 forbids landing them with fabricated payloads. `nasdaq-earnings-calendar` lookahead path uses the existing live-recorded fixture set. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | `INVESTO_EARNINGS_LOOKAHEAD_DAYS` is a non-secret integer; `_internal/redaction.py` chokepoint preserved end-to-end; lookahead block is gated through the same defensive `redact_text` path as recent-context. |
| R14 (SEC fair-access UA policy) | ✅ | `nasdaq-earnings-calendar` lookahead reuses the adapter-local browser-compatible UA from u1 extension #5; no new SEC-class endpoint introduced this session. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u35 introduces no new XML parsing path. |

---

## QA Verdict

- **Verdict**: APPROVE_AFTER_FIXES
- **Pre-merge code fix applied**:
  - **M2** — `tests/unit/notifier/test_summary.py::test_imminent_tag_uses_fomc_label_for_calendar_source` strengthened with the explicit substring pin `assert "📅 FOMC press release — Fe… D-2" in summary`. Closes the regression-pin gap on the FOMC label substring shape so a future label-format edit fails fast at unit level rather than silently shifting the Telegram surface.
- **Deferred to TECH-DEBT (no Critical / High findings outstanding from u35 itself)**:
  - **H1** — 4 new lookahead source adapters (`fomc-calendar`, `fred-economic-calendar`, `coingecko-events`, KRX option-expiry) → registered under **DEBT-067** (P1). Blocked on R10 (live-API fixture recording).
  - **M1** — orchestrator wire-through (`_stage_notify_segmented_briefing` per-segment lookahead bucket → `build_segmented_summary`) → registered under **DEBT-067** sub-bullet. The wire-through must pass `now_utc` explicitly alongside `lookahead_items_by_segment`; `now_utc=None` while `lookahead_items_by_segment` is supplied raises `ValueError` so the notifier stays clock-free (testability + determinism).
  - **M3** — single-filter reuse (`briefing/pipeline.py::_render_lookahead_context_block` filter result must be reused so the markdown context block + the Telegram tag selector see exactly one filtered list) → registered under **DEBT-067** sub-bullet.
- **Resolved by this unit**:
  - **DEBT-060** (High) — Phase 0 lands `briefing/extract.py` + 4 public prefix exports on `briefing/summary_quality.py`; all 5 surfaces (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, `briefing/context.py`) now import from the chokepoint; grep guard `test_no_surface_redeclares_prefix_literal` fails fast on a sixth consumer redeclaring any prefix literal locally. Moved to Resolved Items.
- No Critical or High findings introduced by u35.

---

## TECH-DEBT Surfaced by This Unit

- **Resolved**: **DEBT-060** — moved to Resolved Items by Phase 0; 5-site chokepoint consolidation.
- **New**: **DEBT-067** (P1) — u35 이월 사항 — 4 lookahead 어댑터 + orchestrator wire-through + `LOOKAHEAD_DATA_MISSING` reason code. Source: u35 QA H1 + M1 + M3, 2026-05-08. Effort: ~6-10h adapters + ~30 min wire-through + ~30 min reason code.

---

## Gaps Analysis

- **Partial — DoD #1 (forward-looking event coverage)**: 4 of the planned adapters are deferred to DEBT-067 under R10. Mitigation: the entire downstream pipe (model field, FetchWindow.lookahead, prompt, render, sub-cap, notifier tag selector) lands today and is observable; the moment any one of the 4 adapters lands, the user-visible Telegram imminent tag and the segment "주요 일정" block populate without further code change beyond the wire-through.
- **Deferred — DoD #6 (`SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING`)**: deliberate — landing the reason code without any populating adapter would fire on every segment indefinitely and erode the u22 coverage-trust contract. Cross-referenced under DEBT-067.

## Proposed Actions

- No requirements / design changes.
- TECH-DEBT updates: **DEBT-060 Resolved**; **DEBT-067 (P1)** added.
- Quality gate verified end-to-end at the close of u35: `ruff` ✅, `ruff format` ✅ (187 files), `mypy --strict` ✅ (71 source files), `pytest` ✅ (1308/1308), `mkdocs build --strict` ✅.
