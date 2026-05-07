# Code Generation Plan: `u25 summary-fidelity-and-content-trust`

**Date**: 2026-05-08
**Unit**: u25 summary-fidelity-and-content-trust
**Stage**: Code Generation

---

## Goal

Stop first-viewport summary lines from publishing as truncated marker-only or conjunction-tail strings, and prevent Stage 2 LLM arithmetic hallucinations that erode reader trust.

---

## Definition of Done

- [x] `_summary_sentence` rejects marker-only outputs (e.g. `^\d+\.$`) and conjunction-tail outputs (e.g. `^.*\bvs\.$`) and falls back to the data-limited path.
- [x] `summary_quality` gate is verified to be invoked on the actual segmented publish path and rejects the additional truncation patterns above.
- [x] Stage 2 system prompt forbids arithmetic over input figures and limits numeric output to values explicitly present in the Stage 1 candidate JSON.
- [x] Stage 2 ⑤ section prompt language is rewritten neutrally (no "주도주" / "부진" / "주의" verbatim wording) to avoid implicit recommendations.
- [x] Brief header includes a deterministic timestamp watermark line `**기준 시각**: YYYY-MM-DD KST [start_utc, end_utc)`.
- [x] Regression coverage added for the three 2026-05-06 archive segments confirming the previously-published truncated summaries no longer pass the gate on republish.

---

## Steps

### Step 1 — Summary Sentence and Gate Hardening

- [x] Extend `_summary_sentence` reject set to cover marker-only and conjunction-tail tokens after markdown stripping.
- [x] Wire `summary_quality` invocation assertion onto the segmented publish path (test, not runtime overhead).
- [x] Pin behavior with regression fixtures derived from 2026-05-06 us / crypto / domestic archives.

### Step 2 — Stage 2 Prompt Trust Contract

- [x] Add a no-arithmetic clause to the Stage 2 system prompt covering sums, averages, and unit conversions.
- [x] Replace recommendation-flavored ⑤ section labels with neutral observation labels.

### Step 3 — Timestamp Watermark

- [x] Render the `**기준 시각**` watermark line directly under the segment H1 using the existing per-segment market window already plumbed through u8.

### Step 4 — Verification

- [x] Run targeted briefing/publisher tests and the full quality gate.

---

## Implementation Notes (2026-05-08)

* `summary_quality` gate was already wired into the segmented publish
  path at ``orchestrator/pipeline.py:497`` and pinned by
  ``test_run_pipeline_segment_summary_quality_failure_writes_nothing``
  in ``tests/unit/orchestrator/test_run_pipeline.py``. No new
  invocation needed; this unit only widened the gate's reject set.
* Producer-side rejection mirrors the gate-side reject set
  (``_is_unsafe_summary_candidate`` in ``briefing/pipeline.py``) so
  the producer never emits what the gate would block. The two reject
  lists are documented as a contract in the
  ``summary_quality`` module docstring.
* Watermark uses the same segment→tz mapping as the adapter routing
  in ``sources/aggregator._window_for_adapter`` so the visible
  watermark matches the actual data-collection window. Pure derivation
  from ``(target_date, segment)`` — no clock reads, deterministic.
* Stage 2 prompt no-arithmetic clause is a producer-side hint only.
  Stage 3 numeric cross-reference is deferred to a follow-up unit
  (per plan: "Stage 3 numeric cross-reference 는 u32 로 이월").
* Files changed:
  * ``src/investo/briefing/pipeline.py`` — ``_summary_sentence``,
    ``_clean_summary_line``, new helpers, watermark rendering.
  * ``src/investo/briefing/summary_quality.py`` — extended reject set
    + module docstring spelling out the contract.
  * ``src/investo/briefing/prompts.py`` — STAGE2_SYSTEM neutral ⑤
    grouping labels + numeric integrity rules.
  * ``tests/unit/briefing/test_summary_fidelity.py`` (new) — 23
    regression tests for producer / gate / watermark.
  * ``tests/unit/briefing/test_prompts.py`` — refreshed assertions for
    the new prompt language; added two assertions for u25 rules.

---

## Source

Persona evaluation 2026-05-07: persona #1, #2, #3 (P0).
