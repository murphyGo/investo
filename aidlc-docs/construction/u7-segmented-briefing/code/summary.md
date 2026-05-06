# Code Summary: `u7 segmented briefing`

**Date**: 2026-05-07
**Stage**: Code Generation
**Status**: Complete

## Scope

Implemented FR-008: one production pipeline run now creates three independent market briefings:

- `domestic-equity` — 국내 증시
- `us-equity` — 미국 증시
- `crypto` — 크립토

The unit prevents one source group from dominating unrelated markets by routing collected items into segment-specific input sets before LLM generation.

## Implementation

| Area | Files | Result |
|------|-------|--------|
| Segment routing | `src/investo/briefing/segments.py` | Added deterministic `segment_items()` and segment constants/labels/thresholds. |
| Segment-aware prompts | `src/investo/briefing/prompts.py`, `src/investo/briefing/pipeline.py` | Added optional `segment` and `data_limited` generation context while keeping prompt text centralized in `prompts.py`. |
| Segmented archive paths | `src/investo/publisher/paths.py`, `src/investo/publisher/writer.py` | Added optional `segment` path support: `archive/{segment}/YYYY/MM/YYYY-MM-DD.md`; default unsegmented path remains readable. |
| Orchestration | `src/investo/orchestrator/pipeline.py` | Production `run_pipeline` now generates all three segments in fixed order, writes all three files, and commits/pushes them together. Any segment generation failure skips the whole publish step. |
| Telegram summary | `src/investo/notifier/summary.py` | Added `build_segmented_summary()` to send one UTF-16-aware Telegram message with all three labels, one-line summaries, and all three links. |

## Tests

Added or updated coverage for:

- segment routing and data-limited threshold behavior
- segment prompt context without live Claude
- segmented archive path and GitHub Pages URL helpers
- writer support for segmented archive paths
- production orchestrator segmented generate/publish flow
- all-three-or-fail generation behavior
- Telegram segmented summary and URL preservation under truncation
- end-to-end integration flow with three segment archives and one Telegram message

## Verification

Final gate:

- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy --strict src/` ✅
- `uv run pytest -q` ✅
- `uv run mkdocs build --strict` ✅

## Notes

- Historical unsegmented files remain available under `archive/YYYY/MM/YYYY-MM-DD.md`.
- `PipelineResult.briefing_url` remains a single URL for backwards compatibility; segmented runs use the domestic-equity URL there, while the Telegram message includes all three links.
- No new external service, secret, or paid API was introduced.
