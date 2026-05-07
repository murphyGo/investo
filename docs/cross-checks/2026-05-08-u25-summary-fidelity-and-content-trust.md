# Cross-Check: u25 summary-fidelity-and-content-trust

**Scope**: u25 summary-fidelity-and-content-trust
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 6 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u25 is a Wave 1 P0 follow-up from the 2026-05-07 persona evaluation (personas #1, #2, #3). It hardens the first-viewport summary line so truncated marker-only or conjunction-tail strings can no longer reach published archive files, removes Stage 2 LLM arithmetic hallucinations from the trust contract, neutralises ⑤ section recommendation-flavored labels, and adds a deterministic timestamp watermark under each segment H1 so readers can tell at a glance when the data was collected. The unit does not introduce paid sources, accounts, trading, new external dependencies, or new NFR surfaces. Stage 3 numeric self-check is explicitly deferred to u32.

**Plan**: `aidlc-docs/construction/plans/u25-summary-fidelity-and-content-trust-code-generation-plan.md`
**Goal**: Stop first-viewport summary lines from publishing as truncated marker-only or conjunction-tail strings, prevent Stage 2 LLM arithmetic hallucinations that erode reader trust, and surface a deterministic timestamp watermark so readers can verify the collection window.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/briefing/pipeline.py` (`_summary_sentence`, `_clean_summary_line`, `_split_into_sentences`), `tests/unit/briefing/test_summary_fidelity.py` | Producer-side rejection prevents marker-only (`^\d+\.$`) and conjunction-tail (e.g. `^.*\bvs\.$`) summary candidates from reaching the gate; gate-side reject set widened in lock-step. |
| FR-003 static web publishing | ✅ | `src/investo/briefing/pipeline.py` (`_render_timestamp_watermark`, `_enhance_reader_experience`), `tests/unit/briefing/test_summary_fidelity.py` | Each segment H1 is followed by a `**기준 시각**: YYYY-MM-DD KST [start_utc, end_utc)` watermark line derived deterministically from `(target_date, segment)` and the per-segment market-window timezone (KST/America-NY/UTC). |
| FR-008 segmented briefing | ✅ | `src/investo/briefing/pipeline.py` (`_SEGMENT_MARKET_TZ`, `_SEGMENT_MARKET_TZ_LABEL`), `tests/unit/briefing/test_summary_fidelity.py` | Watermark window mirrors the adapter routing logic in `sources/aggregator._window_for_adapter` so the visible window matches the actual data-collection window for each of domestic / us / crypto. |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/briefing/prompts.py` (numeric integrity rules, ⑤ neutral grouping labels) | u25 changes are prompt + producer + gate logic only; no new external dependency, no Anthropic SDK introduced, no paid call surface added. |
| NFR-003 graceful degradation | ✅ | `src/investo/briefing/pipeline.py`, `src/investo/briefing/summary_quality.py` | Producer-side rejection falls back to the existing data-limited summary path; gate-side rejection blocks the publish without secret leakage. Existing PARTIAL/FAIL paths unchanged. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/orchestrator/pipeline.py:497` (unchanged), `src/investo/briefing/summary_quality.py` | `verify_disclaimer` remains the publish-time gate; summary-quality gate operates upstream of the disclaimer surface. |
| NFR-005 consistency / DRY | ✅ | `src/investo/briefing/summary_quality.py` (module docstring contract), `src/investo/briefing/pipeline.py::_is_unsafe_summary_candidate` | Producer and gate carry the same 4-pattern reject set with a shared contract documented in the `summary_quality` module docstring. Drift risk registered as DEBT-047 (extract single helper). |
| NFR-006 testing | ✅ | `tests/unit/briefing/test_summary_fidelity.py` (23 tests), `tests/unit/briefing/test_prompts.py` (+2 assertions), full quality gate | +25 targeted tests (1147 → 1172): producer-side rejection, gate-side rejection, watermark rendering, segment timezone routing, prompt no-arithmetic clause, ⑤ neutral grouping labels, 2026-05-06 archive regression fixtures (us / crypto / domestic). |
| NFR-007 secret hygiene (R8 / R13) | ✅ | u27's `redact_text` chokepoint (unchanged) | u25 does not introduce new redaction surfaces or new env-var sources; existing chokepoint coverage unchanged. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `_summary_sentence` rejects marker-only outputs (e.g. `^\d+\.$`) and conjunction-tail outputs (e.g. `^.*\bvs\.$`) and falls back to the data-limited path. | ✅ | `src/investo/briefing/pipeline.py` (`_summary_sentence`, `_clean_summary_line`, `_is_unsafe_summary_candidate`, `_split_into_sentences`); `tests/unit/briefing/test_summary_fidelity.py::TestSummarySentenceRejects` |
| `summary_quality` gate is verified to be invoked on the actual segmented publish path and rejects the additional truncation patterns above. | ✅ | Gate already wired at `src/investo/orchestrator/pipeline.py:497`; pinned by `tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_segment_summary_quality_failure_writes_nothing`. Gate reject set widened in `src/investo/briefing/summary_quality.py::_validate_summary_value`; pinned by `tests/unit/briefing/test_summary_fidelity.py::TestSummaryQualityGate`. |
| Stage 2 system prompt forbids arithmetic over input figures and limits numeric output to values explicitly present in the Stage 1 candidate JSON. | ✅ | `src/investo/briefing/prompts.py` (numeric integrity clause); `tests/unit/briefing/test_prompts.py` (new assertion). |
| Stage 2 ⑤ section prompt language is rewritten neutrally (no "주도주" / "부진" / "주의" verbatim wording) to avoid implicit recommendations. | ✅ | `src/investo/briefing/prompts.py` (⑤ neutral grouping labels); `tests/unit/briefing/test_prompts.py` (new assertion). |
| Brief header includes a deterministic timestamp watermark line `**기준 시각**: YYYY-MM-DD KST [start_utc, end_utc)`. | ✅ | `src/investo/briefing/pipeline.py` (`_render_timestamp_watermark`, `_enhance_reader_experience` insertion point, `_SEGMENT_MARKET_TZ`, `_SEGMENT_MARKET_TZ_LABEL`); `tests/unit/briefing/test_summary_fidelity.py::TestTimestampWatermark`. |
| Regression coverage added for the three 2026-05-06 archive segments confirming the previously-published truncated summaries no longer pass the gate on republish. | ✅ | `tests/unit/briefing/test_summary_fidelity.py::TestArchiveRegression20260506` (us / crypto / domestic). |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed
- `uv run mypy --strict src/` — passed (66 source files)
- `uv run pytest -q` — 1172 passed (1147 → 1172, +25 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave (no new mkdocs nav/content changes in u25)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u25 only modifies prompt strings, producer logic, and the publish-time summary gate; no LLM client introduced. Stage 2 still calls `claude -p` via subprocess. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | All u25 changes are inside `briefing/` (`pipeline.py`, `summary_quality.py`, `prompts.py`). No cross-unit import added; orchestrator continues to be the only caller of the briefing surface. |
| 무료 API only | ✅ | No new external endpoints or paid keys introduced. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u25 only widens the upstream summary-quality gate and adds a deterministic watermark line above the disclaimer surface. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u25 does not change notifier targets; existing public/operator separation is preserved. |
| R8 (raw_metadata / source provenance) | ✅ | u25 does not touch `raw_metadata` or source-provenance rendering. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | New summary-rejection error paths use sanitized strings; no secret-shaped values introduced into prompts, watermark output, or test fixtures. u27's chokepoint covers the unchanged surfaces. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u25 does not introduce any new XML parsing path; existing `defusedxml`-based source adapters remain unchanged. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M3** — `_render_timestamp_watermark` docstring example values corrected from KST 16:00Z / 13:00Z to the actual 15:00Z / 15:00Z values produced by the function so future readers do not misinterpret the documented contract. Implementation behaviour unchanged.
- Deferred to TECH-DEBT:
  - **M1** → DEBT-046 (Medium) — `_SEGMENT_MARKET_TZ` is declared in `briefing/pipeline.py` separately from `sources/aggregator._window_for_adapter` and `sources/_window.py:_KST`. The module boundary forbids `briefing → sources` imports, so a watermark vs. window drift cannot be caught at type-check time. Fix is a single source-of-truth move into `investo.models` (e.g., `models/segments.py`) so both surfaces import the same constant.
  - **M2** → DEBT-047 (Medium) — `briefing/pipeline.py::_is_unsafe_summary_candidate` and `briefing/summary_quality.py::_validate_summary_value` carry the same 4-pattern reject set in two places. Today a `summary_quality` module docstring documents the contract, but a future widening lands in only one site by default. Fix is to extract a public `is_unsafe_summary_value(str) -> bool` from `summary_quality` and have the producer import it.
  - **M4** → DEBT-048 (Low) — `summary_quality._NUMBER_DOT_ONLY_RE` is a proper subset of `_LIST_MARKER_ONLY_RE`. The redundant constant is intentionally retained for grep-ability today, but it is technically dead code. Cleanup option is to add a `# covers \d+\. via _LIST_MARKER_ONLY_RE` comment to the LIST docstring and drop `_NUMBER_DOT_ONLY_RE`.
- No Critical or High findings.

---

## TECH-DEBT Surfaced by This Unit

Three new items registered (`docs/TECH-DEBT.md`):

- **DEBT-046 (Medium)** — `_SEGMENT_MARKET_TZ` single source-of-truth. Constant declared in `briefing/pipeline.py` separately from `sources/aggregator._window_for_adapter` and `sources/_window.py:_KST`; module boundary (briefing → sources import 금지) forbids direct import. Fix: move into `investo.models` (e.g., `models/segments.py`) and import from both surfaces. Prevents future watermark-vs-window false display.
- **DEBT-047 (Medium)** — Producer ↔ gate reject set unification. `briefing/pipeline.py::_is_unsafe_summary_candidate` and `briefing/summary_quality.py::_validate_summary_value` hold the same 4 regexes separately. Fix: extract a public `is_unsafe_summary_value(str) -> bool` from `summary_quality` and have the producer call it. Removes drift risk by construction.
- **DEBT-048 (Low)** — `summary_quality._NUMBER_DOT_ONLY_RE` is a proper subset of `_LIST_MARKER_ONLY_RE`. Retained intentionally for grep-ability but technically dead. Fix: add a `# covers \d+\.` comment on `_LIST_MARKER_ONLY_RE` and remove `_NUMBER_DOT_ONLY_RE`.

---

## Gaps Analysis

No gaps found. Stage 3 numeric self-check is explicitly out of scope for u25 and is carried in u32 (trust-traceability-deep-dive) per the persona-driven plan.

## Proposed Actions

- No requirements/design changes.
- TECH-DEBT updates already registered (DEBT-046, DEBT-047, DEBT-048).
- `mkdocs build --strict` to be re-verified once the broader u25-u33 follow-up wave closes.
