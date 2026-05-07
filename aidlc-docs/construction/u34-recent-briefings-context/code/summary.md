# Code Summary: u34 recent-briefings-context

**Date**: 2026-05-08

## Completed

- Lifted each daily briefing from a single-shot report into a "today inside the weekly arc" narrative by feeding Stage 2 a frozen `RecentBriefingsContext` carrying per-segment per-day publish date, conclusion line, key driver line, watermark, and coverage status for the most recent N publish days (default 5 = 1 trading week).
- Stage 2 system prompt now carries a "최근 N일 컨텍스트" / "Recent-briefings continuity rules" section with the four usage rules: (a) reference yesterday's continuity / divergence, (b) avoid repeating prior-day conclusions verbatim, (c) explicitly say "큰 변화 없음" when no new signal, (d) **no extrapolation beyond the input data candidates** (extension of the u25 numeric integrity rule). Stage 1 classification prompt is unchanged.
- Recent-context block lives on a separate ~500-char-per-segment-per-day budget (50 chars × 4 fields ≪ 500) so it occupies an independent budget from the u13 LLM input candidate cap (96 total / 24 per source) and cannot starve fresh evidence. The block flows into Stage 2 only — Telegram summary, hero callout, visual cards, segment markdown, and Stage 1 are all unchanged.
- Loader reads only `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` files already gated through `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality`. Defensive `redact_text(STRICT)` is applied per extracted field as a belt-and-suspenders measure (R8 / R13 preserved end-to-end).
- Configurable via `INVESTO_RECENT_CONTEXT_DAYS` (default 5, valid `[0, 10]`, `0` disables the feature for a clean A/B); first publish, gap days, and partial coverage all return `RecentBriefingsContext.is_empty() == True` and the pipeline proceeds without raising. Sat / Sun are skipped during business-day walk-back; a 21-day cap prevents an unbounded scan on long gap windows.
- Applied pre-merge fixes that lift the unit from "ships but with regression-pin and observability gaps" to "publish-grade":
  - **M2** — `tests/unit/briefing/test_pipeline_recent_render.py` adds 6 unit tests (4 branch + 2 shape pins) that pin `_render_recent_context_block` / `_render_recent_entry` against future prompt-format drift. Closes the regression-pin gap on the recent-context render path so a renamed sentinel or a reformatted entry shape fails fast at unit level rather than silently shifting the Stage 2 prompt.
  - **M3** — `src/investo/briefing/context.py` `INVESTO_RECENT_CONTEXT_DAYS` parser now emits a warning log when the value is non-numeric, negative, or above the `[0, 10]` upper bound. Missing / blank values stay silent (normal scenario). Closes the observability gap on operator misconfiguration without leaking the value verbatim.
- M1 → cross-references **DEBT-060** (Medium → **High** escalation by this unit). u34 is the fifth consumer of the conclusion / driver / watermark prefix matching logic (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, and now `briefing/context.py::_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX`). The DEBT-060 priority reasoning explicitly named "fifth consumer lands" as the promotion trigger; that condition is now met.

## Files Changed

### New source files

- `src/investo/briefing/context.py` (~290 LOC) — `RecentBriefingsContext` (frozen pydantic v2 + slots, `extra="forbid"`), per-segment per-day entries with publish date / conclusion / drivers / watermark / coverage status, `is_empty()` + `for_segment(...)` resolvers, business-day walk-back (Sat / Sun skip, 21-day cap), conclusion / driver / watermark anchor extraction (DEBT-060 5th consumer), 50-char per-field truncate, defensive `redact_text(STRICT)`, `INVESTO_RECENT_CONTEXT_DAYS` parser with `[0, 10]` clamp + invalid-value warning log (M3 fix).

### Modified source files

- `src/investo/briefing/prompts.py` — `STAGE2_SYSTEM` adds "Recent-briefings continuity rules" with the four usage rules; `STAGE2_USER_TEMPLATE` adds the `{recent_context}` placeholder; new `format_recent_context_section` helper renders the per-segment per-day block. Stage 1 prompt untouched.
- `src/investo/briefing/pipeline.py` — `generate_briefing` signature extended to accept the loaded `RecentBriefingsContext`; new `_render_recent_context_block` / `_render_recent_entry` helpers produce a stable single-line shape per per-day entry. Pinned by the M2 6 unit tests.
- `src/investo/orchestrator/pipeline.py` — new `_load_recent_context_for_run` invoked before `generate_briefing` per segment; briefing Protocol extended; empty / first-publish path returns `RecentBriefingsContext.is_empty() == True` and the pipeline proceeds without raising.

### New test files

- `tests/unit/briefing/test_recent_context.py` — 17 + caplog-strengthened tests covering archive-absent / N=0 / full-5-day / partial-coverage / leak-guard regression / business-day walk-back / 21-day cap / 50-char per-field truncate / `INVESTO_RECENT_CONTEXT_DAYS` valid + invalid (M3 caplog assertions).
- `tests/unit/briefing/test_pipeline_recent_render.py` — 6 new tests (4 branch + 2 shape pins, M2 fix) on `_render_recent_context_block` / `_render_recent_entry`.

### Modified test files

- `tests/unit/briefing/test_prompts.py` — +3 sentinels pinning the `STAGE2_SYSTEM` "Recent-briefings continuity rules" section, the `{recent_context}` placeholder on `STAGE2_USER_TEMPLATE`, and the `format_recent_context_section` helper output shape.
- `tests/unit/orchestrator/test_run_pipeline.py` — +2 integration tests pinning `_load_recent_context_for_run` orchestrator threading (loaded context vs empty / first-publish path).

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-060 promoted Medium → High; description "duplicated 4x" → "duplicated 5x"; suggested fix "4-site import switch" → "5-site import switch"; summary count Medium decremented, High incremented)
- `docs/cross-checks/2026-05-08-u34-recent-briefings-context.md` (new)
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/u34-recent-briefings-context-code-generation-plan.md` (DoD + step checkboxes marked)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — Korean briefing comprehension: Korean conclusion / driver / watermark lines extracted verbatim from gated archive markdown; Stage 2 system prompt carries the four usage rules in Korean.
- **FR-003** — static web publishing: no site-content surface change. The site-rendered briefing still flows through the existing publisher path; mkdocs build is unaffected.
- **FR-008** — segmented briefing: `RecentBriefingsContext.for_segment(...)` per-segment view; archive walk-back per segment; no cross-segment bleed.
- **NFR-002 (cost / no paid APIs)** — loader reads only local `archive/**/*.md`; no HTTP, no LLM, no Anthropic SDK. The single env var added (`INVESTO_RECENT_CONTEXT_DAYS`) is a non-secret integer-string opt-in.
- **NFR-003 (graceful degradation)** — `RecentBriefingsContext.is_empty()`, business-day walk-back with 21-day cap, `INVESTO_RECENT_CONTEXT_DAYS` `[0, 10]` clamp, M3 fix invalid-value warning log. First publish / gap days / partial coverage / `INVESTO_RECENT_CONTEXT_DAYS=0` all degrade cleanly.
- **NFR-004 (compliance / disclaimer)** — loader reads only post-publish archive markdown already gated through `verify_disclaimer` + `briefing.leak_guard.scan` + `summary_quality`; defensive `redact_text(STRICT)` applied per extracted field as a belt-and-suspenders measure.
- **NFR-005 (consistency / DRY)** — `briefing/context.py` reuses the u29 `_CONCLUSION_PREFIX` shape — registered as the 5th consumer cross-referenced under DEBT-060 (escalated Medium → High by this unit). Module boundary preserved.
- **NFR-006 (testing)** — +28 targeted tests (1240 → 1268); covers archive-absent / N=0 / full-5-day / partial-coverage / leak-guard regression / business-day walk-back / 21-day cap / 50-char truncate / `INVESTO_RECENT_CONTEXT_DAYS` valid + invalid / Stage 2 prompt sentinel / orchestrator threading.
- **NFR-007 (R8 / R13)** — defensive `redact_text(STRICT)` at every extracted field; the `_internal/redaction.py` chokepoint introduced by u27 is preserved end-to-end. M3 fix logs invalid env-var values without echoing them verbatim.

## Architecture Summary

```
briefing/
  context.py
    RecentBriefingsContext              # frozen pydantic v2 + slots
                                        #   extra="forbid"
                                        #   per-segment per-day:
                                        #     publish_date, conclusion,
                                        #     drivers, watermark, coverage
    is_empty() / for_segment(segment)
    load_recent_context(N, archive_dir, segments, target_date)
                                        #   walks archive/<segment>/YYYY/MM/YYYY-MM-DD.md
                                        #   business-day walk-back (Sat/Sun skip)
                                        #   21-day scan cap
                                        #   _CONCLUSION_PREFIX / _DRIVER_PREFIX
                                        #     / _WATERMARK_PREFIX (DEBT-060 5th)
                                        #   50-char per-field truncate
                                        #   redact_text(STRICT) defensive
    _resolve_n_from_env()
                                        #   INVESTO_RECENT_CONTEXT_DAYS
                                        #     default 5, [0, 10] clamp
                                        #   M3: warning log on invalid

  prompts.py
    STAGE2_SYSTEM                       # + "Recent-briefings continuity rules"
                                        #   (a) continuity
                                        #   (b) no verbatim repetition
                                        #   (c) "큰 변화 없음" explicit
                                        #   (d) no extrapolation (u25 ext.)
    STAGE2_USER_TEMPLATE                # + {recent_context} placeholder
    format_recent_context_section(...)  # per-segment per-day rendering

  pipeline.py
    generate_briefing(..., recent_context: RecentBriefingsContext)
    _render_recent_context_block(...)   # M2-pinned
    _render_recent_entry(...)           # M2-pinned

orchestrator/pipeline.py
  _load_recent_context_for_run(...)     # invoked before generate_briefing
                                        #   empty / first-publish path:
                                        #     RecentBriefingsContext.is_empty()
                                        #   pipeline proceeds without raising
```

The recent-context block flows into Stage 2 only — Telegram summary, hero callout, visual cards, segment markdown, and Stage 1 are all unchanged. The orchestrator continues to be the only cross-unit importer; `briefing/context.py` lives inside `briefing/` and does not import `sources` / `publisher` / `notifier`.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M2 (6 unit tests in `tests/unit/briefing/test_pipeline_recent_render.py` — 4 branch + 2 shape pins — pin `_render_recent_context_block` / `_render_recent_entry` against future prompt-format drift) applied pre-merge.
- M3 (`src/investo/briefing/context.py` `INVESTO_RECENT_CONTEXT_DAYS` parser warning log on non-numeric / negative / out-of-range values; missing / blank values stay silent) applied pre-merge.
- M1 → cross-references DEBT-060 (Medium → **High** escalation by this unit). u34 is the fifth consumer; the DEBT-060 promotion trigger ("fifth consumer lands") is met.
- No Critical or High findings introduced by u34.
- No new TECH-DEBT items registered by u34 itself; DEBT-060 priority promoted Medium → High.
- Cross-check: `docs/cross-checks/2026-05-08-u34-recent-briefings-context.md`.
- Source: user direct request 2026-05-08 — "최근 N일의 시황을 컨텍스트에서 알고 있는 상태로 작성하면 좋을 듯". Wave 4.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/` (70 source files)
- `uv run pytest -q` (1268 passed; 1240 → 1268, +28 new tests)
- `uv run mkdocs build --strict` (passed; no site content change in u34)

> **Permission-restricted environments**: when the editor sandbox refuses to write into `aidlc-docs/` or `docs/`, fall back to Bash heredoc (`cat <<'EOF' > <abs-path>`) for documentation deliverables. Source / test changes always go through the editor in the supported path.
