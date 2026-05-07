# Code Summary: u25 summary-fidelity-and-content-trust

**Date**: 2026-05-08

## Completed

- Hardened the first-viewport summary line so truncated marker-only or conjunction-tail strings can no longer reach published archive files. Producer (`briefing/pipeline.py::_summary_sentence`, `_clean_summary_line`, `_split_into_sentences`) and gate (`briefing/summary_quality.py::_validate_summary_value`) now share a 4-pattern reject set covering marker-only (`^\d+\.$`), list-marker-only (`^[-*]\s*$`), conjunction-tail (e.g. `^.*\bvs\.$`), and empty/whitespace candidates. Producer-side rejection falls back to the existing data-limited path; gate-side rejection blocks the publish.
- Added a deterministic per-segment timestamp watermark line `**기준 시각**: YYYY-MM-DD KST [start_utc, end_utc)` directly below each segment H1. The watermark is rendered by `_render_timestamp_watermark` and inserted by `_enhance_reader_experience`. Window resolution uses a new `_SEGMENT_MARKET_TZ` / `_SEGMENT_MARKET_TZ_LABEL` mapping that mirrors `sources/aggregator._window_for_adapter` (KST for domestic, America/New_York for us, UTC for crypto), so the visible window matches the actual data-collection window. Pure derivation from `(target_date, segment)` — no clock reads — keeps the watermark deterministic.
- Stage 2 system prompt rewritten to forbid arithmetic over input figures (no sums, averages, unit conversions) and to limit numeric output to values explicitly present in the Stage 1 candidate JSON. ⑤ section grouping labels neutralised (no "주도주" / "부진" / "주의" verbatim wording) so the briefing reads as observation rather than implicit recommendation.
- Verified the `summary_quality` gate is invoked on the actual segmented publish path: invocation already lives at `orchestrator/pipeline.py:497` and is regression-pinned by `tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_segment_summary_quality_failure_writes_nothing`. u25 only widened the gate's reject set; no new invocation needed.
- Pinned the contract that producer-side rejection mirrors the gate-side reject set in the `summary_quality` module docstring, so a future widening that lands in only one site is visible to reviewers. The drift risk is registered as DEBT-047 with a single-helper extraction proposal.
- Added 23 targeted tests in `tests/unit/briefing/test_summary_fidelity.py` covering producer-side rejection, gate-side rejection, watermark rendering, segment timezone routing, and a 2026-05-06 archive regression for all three segments (us / crypto / domestic) confirming the previously-published truncated summaries no longer pass on republish. Added 2 assertions to `tests/unit/briefing/test_prompts.py` pinning the no-arithmetic clause and the ⑤ neutral grouping labels.
- Applied M3 pre-merge: `_render_timestamp_watermark` docstring example values corrected from KST 16:00Z / 13:00Z to the actual 15:00Z / 15:00Z values produced by the function. M1 / M2 / M4 deferred to DEBT-046 / DEBT-047 / DEBT-048.

## Files Changed

### Modified source files

- `src/investo/briefing/pipeline.py` (`_summary_sentence` rewrite, `_clean_summary_line` post-check, `_is_unsafe_summary_candidate`, `_split_into_sentences`, `_SEGMENT_MARKET_TZ` / `_SEGMENT_MARKET_TZ_LABEL`, `_render_timestamp_watermark`, watermark insertion in `_enhance_reader_experience`)
- `src/investo/briefing/summary_quality.py` (extended reject set + module docstring spelling out the producer ↔ gate contract)
- `src/investo/briefing/prompts.py` (Stage 2 numeric integrity clause + ⑤ neutral grouping labels)

### New test files

- `tests/unit/briefing/test_summary_fidelity.py` (23 new regression tests — producer / gate / watermark / 2026-05-06 archive regression)

### Modified test files

- `tests/unit/briefing/test_prompts.py` (+2 assertions for the no-arithmetic clause and the ⑤ neutral grouping labels)

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-046 / DEBT-047 / DEBT-048 added)
- `docs/cross-checks/2026-05-08-u25-summary-fidelity-and-content-trust.md` (new)
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/u25-summary-fidelity-and-content-trust-code-generation-plan.md` (DoD + step checkboxes marked, implementation notes appended)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — Korean briefing comprehension: producer and gate now reject truncated summaries before they reach the reader-facing first viewport.
- **FR-003** — static web publishing: archive files always carry a deterministic `**기준 시각**` watermark line so readers can verify the collection window without leaving the page.
- **FR-008** — segmented briefing: watermark window per segment uses the same timezone routing as the adapter aggregator, so each domestic / us / crypto briefing reflects its own market window.
- **NFR-002 (cost / no paid APIs)** — prompt + producer + gate logic only; no Anthropic SDK introduced, no paid call surface added.
- **NFR-003 (graceful degradation)** — producer-side rejection falls back to the existing data-limited summary path; gate-side rejection blocks the publish without secret leakage.
- **NFR-004 (compliance / disclaimer)** — `verify_disclaimer` remains the publish-time gate; summary-quality gate operates upstream.
- **NFR-005 (consistency / DRY)** — producer ↔ gate contract documented in `summary_quality` module docstring; drift risk registered as DEBT-047.
- **NFR-006 (testing)** — +25 targeted tests (1147 → 1172): producer / gate / watermark / segment timezone / prompt assertions / 2026-05-06 archive regression.
- **NFR-007 (R8 / R13)** — no new redaction surfaces or env-var sources introduced; u27's chokepoint coverage unchanged.

## Architecture Summary

```
briefing/
  pipeline.py
    _summary_sentence(...)            # producer entry; rejects 4 unsafe shapes
    _clean_summary_line(...)          # post-check: re-reject after markdown cleanup
    _is_unsafe_summary_candidate(...) # 4-pattern guard (mirror of gate's reject set)
    _split_into_sentences(...)        # KO/EN-aware splitter
    _SEGMENT_MARKET_TZ                # {domestic: KST, us: America/New_York, crypto: UTC}
    _SEGMENT_MARKET_TZ_LABEL          # display label per segment
    _render_timestamp_watermark(...)  # YYYY-MM-DD KST [start_utc, end_utc)
    _enhance_reader_experience(...)   # inserts watermark immediately under H1

  summary_quality.py
    _validate_summary_value(...)      # gate; 4-pattern reject set (mirror of producer)
    # module docstring: contract that producer and gate share the reject set

  prompts.py
    STAGE2_SYSTEM
      ⓐ numeric integrity rules        # no sums / averages / unit conversions
      ⓑ ⑤ neutral grouping labels      # no 주도주 / 부진 / 주의 verbatim wording
```

The producer ↔ gate reject contract is the single most important post-condition: any future widening must land in both `_is_unsafe_summary_candidate` and `_validate_summary_value` until DEBT-047 is resolved by extracting a single shared helper. The watermark is pure derivation — `(target_date, segment) → window` — and shares the timezone-routing intent with `sources/aggregator._window_for_adapter`; DEBT-046 captures the cross-module SOT proposal so the watermark cannot drift from the actual collection window.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M3 (`_render_timestamp_watermark` docstring example values corrected to 15:00Z / 15:00Z) applied pre-merge.
- M1 deferred → DEBT-046 (Medium) — single source-of-truth for `_SEGMENT_MARKET_TZ` across briefing and sources.
- M2 deferred → DEBT-047 (Medium) — extract `is_unsafe_summary_value(str) -> bool` so producer ↔ gate share one helper.
- M4 deferred → DEBT-048 (Low) — `_NUMBER_DOT_ONLY_RE` is a proper subset of `_LIST_MARKER_ONLY_RE`; retained for grep-ability today.
- Cross-check: `docs/cross-checks/2026-05-08-u25-summary-fidelity-and-content-trust.md`.
- Stage 3 numeric self-check explicitly deferred to u32 per plan.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/` (66 source files)
- `uv run pytest -q` (1172 passed; 1147 → 1172, +25 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave.
