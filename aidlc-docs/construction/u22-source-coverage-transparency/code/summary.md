# Code Summary: u22 source-coverage-transparency

**Date**: 2026-05-07

## Completed

- Added a shared `SourceOutcome` / `SourceCollectionReport` / `SourceStatus` model layer with `sanitize_source_error_message` so per-source success / zero-item / failure status flows through the pipeline without leaking secret-shaped values.
- Extended `SegmentCoverage` with `reason_codes` and `source_outcomes` so segment-level coverage carries machine-readable reasons (`missing_price`, `missing_news`, `source_failed`, `zero_items`, ...) plus per-source status.
- Rendered Korean reason callouts and a per-source status block in segmented briefing markdown so partial/insufficient segments explain themselves without exposing raw error text.
- Extended `DataConfidenceCard` with reason rows and source-status rows, and updated SVG rendering to surface those rows in the visual data-confidence card.
- Threaded segment-filtered `source_outcomes` through the orchestrator so each domestic-equity / us-equity / crypto briefing only sees its own source results.
- Applied M1-M3 pre-merge docstring clarifications for `is_data_limited`, `build_segment_coverage`, and `sanitize_source_error_message`.

## Files Changed

- `src/investo/models/coverage.py` (new)
- `src/investo/models/__init__.py`
- `src/investo/sources/aggregator.py`
- `src/investo/sources/__init__.py`
- `src/investo/briefing/segments.py`
- `src/investo/briefing/pipeline.py`
- `src/investo/visuals/cards.py`
- `src/investo/visuals/render.py`
- `src/investo/orchestrator/pipeline.py`
- `tests/unit/models/test_coverage.py` (new)
- `tests/unit/sources/test_collect_sources.py` (new)
- `tests/unit/briefing/test_coverage_badge.py` (new)
- `tests/unit/briefing/test_segments.py`
- `tests/unit/briefing/test_budget_happy_path.py`
- `tests/unit/visuals/test_cards.py`
- `tests/unit/visuals/test_render.py`
- `tests/integration/test_pipeline.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `aidlc-docs/construction/plans/u22-source-coverage-transparency-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`

## Linked Requirements / FRs / NFRs / ACs

- **FR-001** — source aggregation now exposes per-source outcomes through `SourceCollectionReport`.
- **FR-002** — segment markdown explains partial/insufficient coverage in Korean.
- **FR-003** — visual data-confidence card includes reason and source-status rows.
- **FR-008** — outcomes are scoped per market segment so segment-level transparency holds under the all-three-or-fail flow.
- **NFR-002 / NFR-003 / NFR-004** — no paid APIs; data-limited path and disclaimer gate are unchanged.
- **NFR-006** — +37 targeted tests (models / sources / briefing / visuals).
- **NFR-007 (R8 / R13)** — `sanitize_source_error_message` redacts bot-token / chat-id-shaped values and high-entropy tokens before public rendering.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M1-M3 docstring clarifications applied (`is_data_limited`, `build_segment_coverage`, `sanitize_source_error_message`).
- New TECH-DEBT registered: DEBT-035, DEBT-036, DEBT-037, DEBT-038, DEBT-039.
- Cross-check: `docs/cross-checks/2026-05-07-u22-source-coverage-transparency.md`.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q` (1074 passed; 1037 → 1074, +37 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u20-u24 follow-up wave.
