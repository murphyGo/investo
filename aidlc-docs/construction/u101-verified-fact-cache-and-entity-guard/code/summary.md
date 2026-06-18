# u101 verified-fact-cache-and-entity-guard — Code Summary

Date: 2026-06-18
Status: Complete

## Implemented

- Added `FactSnapshot` and `VerifiedFactBundle` models for high-drift entity facts.
- Added the no-key `fed-board-leadership` official source adapter for `fed.current_chair`.
- Registered the source as Tier S and routed it to the US-equity Fed-policy family.
- Added `briefing.fact_context` to build, render, and persist sanitized fact snapshots.
- Injected the verified facts block into Stage 2 prompts for every generated segment.
- Added a publish-boundary entity fact guard for current Fed chair person-role claims.
- Wired the guard after reader-format and before publish, with segment-level partial publish.
- Added focused tests for models, source parsing, prompt injection, guard behavior, plugin registration, and orchestrator wiring.

## Validation

```bash
uv run ruff check --fix src/investo/models/facts.py src/investo/sources/fed_board_leadership.py src/investo/briefing/fact_context.py src/investo/publisher/entity_fact_guard.py src/investo/briefing/prompts.py src/investo/briefing/pipeline.py src/investo/briefing/_core/orchestration.py src/investo/orchestrator/pipeline.py tests/unit/models/test_facts.py tests/unit/sources/test_fed_board_leadership.py tests/unit/briefing/test_fact_context.py tests/unit/briefing/test_prompts.py tests/unit/publisher/test_entity_fact_guard.py tests/unit/sources/test_plugin_contract.py tests/unit/orchestrator/test_run_pipeline.py
uv run pytest tests/unit/models/test_facts.py tests/unit/sources/test_fed_board_leadership.py tests/unit/briefing/test_fact_context.py tests/unit/briefing/test_prompts.py tests/unit/publisher/test_entity_fact_guard.py tests/unit/sources/test_plugin_contract.py tests/unit/orchestrator/test_run_pipeline.py
uv run mypy --strict src/investo/models/facts.py src/investo/sources/fed_board_leadership.py src/investo/briefing/fact_context.py src/investo/publisher/entity_fact_guard.py
git diff --check
```

Result: 143 focused tests passed; scoped ruff passed; strict mypy passed; `git diff --check` passed.
