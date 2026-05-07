# Cross-Check: u22 source-coverage-transparency

**Scope**: u22 source-coverage-transparency
**Date**: 2026-05-07
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 4 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **4** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u22 is a second-reader/operator review follow-up that exposes source-level collection status and coverage reasons so readers understand why each market segment is normal, partial, or insufficient. The unit does not introduce paid sources, accounts, trading, or new external dependencies.

**Plan**: `aidlc-docs/construction/plans/u22-source-coverage-transparency-code-generation-plan.md`
**Goal**: Expose source-level collection status and coverage reasons so readers understand why each market segment is normal, partial, or insufficient.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-001 source aggregation diagnostics | ✅ | `src/investo/sources/aggregator.py`, `src/investo/models/coverage.py`, `tests/unit/sources/test_collect_sources.py` | Aggregator returns a `SourceCollectionReport` carrying per-source `SourceOutcome` (success / zero-items / failed) without leaking secret values from raised errors. |
| FR-002 Korean briefing comprehension | ✅ | `src/investo/briefing/segments.py`, `src/investo/briefing/pipeline.py`, `tests/unit/briefing/test_coverage_badge.py` | Segmented markdown now explains why each segment is partial/insufficient using Korean reason labels and a per-source status callout. |
| FR-003 static web publishing | ✅ | `src/investo/visuals/cards.py`, `src/investo/visuals/render.py`, `tests/unit/visuals/test_cards.py` | DataConfidenceCard adds reason rows and source-status rows so the published SVG reflects the same coverage explanation as the markdown. |
| FR-008 segmented briefing | ✅ | `src/investo/orchestrator/pipeline.py`, `src/investo/briefing/segments.py` | Outcomes are threaded per segment so each domestic/us/crypto briefing shows only its own source results; cross-segment outcome leakage is prevented at construction time. |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/models/coverage.py` | Coverage transparency is computed from existing in-process source results; no new external calls, no paid keys, and no Anthropic SDK introduced. |
| NFR-003 graceful degradation | ✅ | `src/investo/briefing/pipeline.py`, `tests/unit/briefing/test_coverage_badge.py` | Insufficient/partial coverage continues to feed the existing data-limited prompt path and emits a zero-item fallback narrative when applicable. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/orchestrator/pipeline.py`, existing publisher disclaimer guard | Coverage rendering happens before publish; disclaimer verification remains the final gate prior to writing markdown/assets. |
| NFR-006 testing | ✅ | `tests/unit/models/test_coverage.py`, `tests/unit/sources/test_collect_sources.py`, `tests/unit/briefing/test_coverage_badge.py` | New targeted tests + full suite (1074 passed) cover reason codes, source-error sanitization, segment outcome filtering, and reader-facing rendering. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/models/coverage.py` (`sanitize_source_error_message`), `tests/unit/models/test_coverage.py` | Source-error messages are sanitized before being surfaced to readers/visuals so bot-token/chat-id-shaped values cannot leak. `defusedxml` usage in upstream adapters is unchanged. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Segment coverage exposes reason codes such as missing price/news, source failed, and zero items. | ✅ | `src/investo/models/coverage.py` (`CoverageReasonCode`, `COVERAGE_REASON_LABELS`), `src/investo/briefing/segments.py` (`SegmentCoverage.reason_codes`), `tests/unit/models/test_coverage.py`, `tests/unit/briefing/test_coverage_badge.py` |
| Reader-facing markdown explains why a segment is partial or insufficient. | ✅ | `src/investo/briefing/pipeline.py` (reason callout + per-source status block), `tests/unit/briefing/test_coverage_badge.py` |
| Data confidence visual card includes source names or reason categories. | ✅ | `src/investo/visuals/cards.py` (reason row + source row builders), `src/investo/visuals/render.py` (`_render_source_rows`), `tests/unit/visuals/test_cards.py` |
| Sensitive source errors are redacted before public rendering. | ✅ | `src/investo/models/coverage.py` (`sanitize_source_error_message`), `tests/unit/models/test_coverage.py` (bot-token / chat-id / generic high-entropy redaction) |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed
- `uv run mypy --strict src/` — passed
- `uv run pytest -q` — 1074 passed (1037 → 1074, +37 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u20-u24 follow-up wave (no new mkdocs nav/content changes in u22)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u22 does not introduce any LLM client; coverage transparency is computed deterministically from existing source results. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | New `models/coverage.py` lives under shared `models`; sources/briefing/visuals each consume `SourceOutcome` through `models` without cross-unit imports. |
| 무료 API only | ✅ | No new external endpoints or paid keys introduced. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u22 only adds reader-facing diagnostics upstream of that gate. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u22 does not change notifier targets; existing public/operator separation is preserved. |
| R8 (raw_metadata / source provenance) | ✅ | Source error messages are sanitized via `sanitize_source_error_message` before surfacing in markdown or SVG. |
| R13 (no secret values in logs/errors/raw_metadata/fixtures) | ✅ | `sanitize_source_error_message` redacts bot-token-shaped (`\b\d{6,}:[A-Za-z0-9_-]{20,}\b` family) and chat-id-shaped values; `tests/unit/models/test_coverage.py` pins the redaction. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u22 does not introduce any new XML parsing path; existing `defusedxml`-based source adapters remain unchanged. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M1** — clarified `is_data_limited` docstring in `src/investo/briefing/segments.py` (partial/insufficient → data-limited prompt path).
  - **M2** — clarified `build_segment_coverage` docstring in `src/investo/briefing/segments.py` regarding the `Sequence[SourceOutcome]` segment-filtering precondition.
  - **M3** — clarified `sanitize_source_error_message` docstring in `src/investo/models/coverage.py` regarding redaction scope and shape.
- No Critical or High findings.

---

## TECH-DEBT Surfaced by This Unit

Five new low/medium items registered (`docs/TECH-DEBT.md`):

- **DEBT-035 (Low)** — Bot-token / chat-id redaction regex duplicated between `__main__._redact_diagnostic_text` and `models/coverage.sanitize_source_error_message`; consolidate via shared helper.
- **DEBT-036 (Low)** — `_SECRET_ENV_VARS` (6 entries) wider than `__main__._redact_diagnostic_text` (4 entries); single source-of-truth recommended.
- **DEBT-037 (Low)** — `_render_source_rows` in `visuals/render.py` silently truncates after 4 rows; markdown still shows the full list, so this is cosmetic.
- **DEBT-038 (Medium)** — `build_segment_coverage`'s `Sequence[SourceOutcome]` signature does not enforce segment-filtering at the type level; consider `NewType` or runtime guard.
- **DEBT-039 (Low)** — `CoverageReasonCode` literal and `COVERAGE_REASON_LABELS` dict-key set are not pinned in sync by mypy; consider `assert_never` or runtime assert.

---

## Gaps Analysis

No gaps found.

## Proposed Actions

- No requirements/design changes.
- TECH-DEBT updates already registered (DEBT-035..DEBT-039).
- `mkdocs build --strict` to be re-verified once the broader u20-u24 follow-up wave closes.
