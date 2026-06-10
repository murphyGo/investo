# u95 Workflow And Enrichment Critical Path Budget — Code Summary

## Status

Complete on 2026-06-10.

## Scope Delivered

- Enabled uv cache in `.github/workflows/daily-briefing.yml` keyed by `uv.lock`.
- Added `actions/setup-node@v6` with npm cache for Claude Code CLI installation.
- Reduced OG-card raster apt packages from `libcairo2 libcairo2-dev` to runtime `libcairo2`.
- Added market-anchor history budget parsing via `INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S`.
- Wrapped Yahoo history fetch in `asyncio.wait_for`; timeout/failure returns empty anchors/history and logs elapsed/degraded reason.
- Added visual prep concurrency parsing via `INVESTO_VISUAL_PREP_CONCURRENCY`.
- Reworked `_stage_prepare_segment_visual_assets` to prepare segments through a bounded semaphore and reassemble results/path order by `SEGMENT_ORDER`.

## Behavior Boundaries

- Workflow triggers, permissions, cron schedule, and required secrets are unchanged.
- Claude CLI install and `claude --version` preflight remain explicit.
- Market-anchor degradation remains best-effort and publishable.
- Visual asset failure still degrades to text-only publish.
- No visual policy, curated asset selection, chart sidecar schema, or public chart UI changed.

## Validation

- `uv run --extra dev pytest tests/unit/orchestrator/test_daily_briefing_env_script.py tests/unit/orchestrator/test_stage_context_budget.py tests/unit/orchestrator/test_run_pipeline.py -q`
  - 103 passed
- `uv run --extra dev pytest tests/unit/orchestrator tests/unit/sources tests/unit/publisher -q`
  - 1439 passed
- `uv run --extra dev pytest tests/integration/test_pipeline.py -q`
  - 7 passed
- `uv run --extra dev ruff check src/investo/orchestrator tests/unit/orchestrator tests/unit/sources tests/unit/publisher tests/integration/test_pipeline.py`
  - All checks passed
- `uv run --extra dev mypy src`
  - Success: no issues found in 193 source files

## Notes For Operation

- Keep `INVESTO_VISUAL_PREP_CONCURRENCY` at default `1` until u92 `visual_assets` timing shows meaningful critical-path cost.
- Use `INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S` only to shorten a persistently slow Yahoo-history path; timeout degrades chart history and non-domestic market anchors.
