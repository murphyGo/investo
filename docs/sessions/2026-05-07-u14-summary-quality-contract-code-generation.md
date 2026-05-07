# Session Log: 2026-05-07 - u14 summary-quality-contract - Code Generation

## Overview

- **Date**: 2026-05-07
- **Unit**: u14 summary-quality-contract
- **Stage**: Code Generation
- **Steps**: Step 1 Contract and Extraction; Step 2 Tests

## Work Summary

Implemented a stable reader-summary contract for segmented briefing headers. The first viewport now strips markdown links/emphasis and numbered-list markers before rendering `오늘의 결론`, `핵심 동인`, and `주의할 점`. Segmented Telegram summaries now reuse the clean rendered conclusion line when available.

## Files Changed

- Modified: `src/investo/briefing/pipeline.py`
- Modified: `src/investo/notifier/summary.py`
- Modified: `tests/unit/briefing/test_budget_happy_path.py`
- Modified: `tests/unit/notifier/test_summary.py`
- Modified: `aidlc-docs/construction/plans/u14-summary-quality-contract-code-generation-plan.md`
- Created: `aidlc-docs/construction/u14-summary-quality-contract/code/summary.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep the six-section briefing body unchanged | u14 targets first-viewport summary trust without widening the LLM output contract. |
| Use deterministic markdown/list cleanup before rendering header fields | Prevents visible artifacts such as `주의할 점: 1.` and cut emphasis syntax. |
| Let Telegram prefer rendered `오늘의 결론` | Reuses the same stable reader-facing summary source across site and channel. |

## Code Review Results

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety | ✅ |
| Reliability | ✅ |
| Maintainability | ✅ |
| Test Coverage | ✅ |

## Potential Risks

- The summary cleaner is intentionally conservative and may keep more context than a human-written headline when a section starts with a subtitle followed by a sentence.

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed
- `uv run mypy --strict src/` — passed
- `uv run pytest tests/unit/briefing/test_budget_happy_path.py tests/unit/notifier/test_summary.py -q` — 27 passed
- `uv run pytest -q` — 979 passed

## TECH-DEBT Items

- None.
