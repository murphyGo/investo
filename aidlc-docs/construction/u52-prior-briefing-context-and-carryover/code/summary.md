# u52 Prior Briefing Context + Carryover — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u52 prior-briefing-context-and-carryover
**Status**: Complete (6 implementation steps; optional FR registration deferred by design)
**Commit**: `224a422` (`Land u51 + u52 + u53 — reader-format, prior-briefing carryover, KRX flows + sector ETFs`)

## Goal

Make each segment aware of unresolved or resolved items from the same segment's prior briefings, so daily output can track event lifecycle rather than reading like a standalone preview.

## Key Deliverables

- `models/carryover.py`: frozen pydantic v2 `CarryoverItem` and `BriefingCarryover` contracts with closed event/status sets.
- `briefing/carryover_parser.py`: archive markdown walker for the prior N business days, using existing extraction chokepoints and deterministic matching against today's candidates.
- `briefing/prompts.py` and `briefing/pipeline.py`: `{carryover_context}` prompt placeholder and CARRY-* prompt rules.
- `publisher/carryover.py`: deterministic `## Watchlist Carryover` table renderer and idempotent injector.
- Orchestrator wire-through via `_load_carryover_for_run` and `_inject_carryover_into_segments`, with per-segment isolation and empty-bundle no-op behavior.
- Regression coverage in `tests/unit/models/test_carryover.py`, `tests/unit/briefing/test_carryover_parser.py`, `tests/unit/briefing/test_prompts_carryover.py`, `tests/unit/publisher/test_carryover_renderer.py`, and `tests/unit/orchestrator/test_carryover_wire.py`.

## Quality Gate

This unit landed as part of the combined Wave 7 commit with u51/u53. Combined gate at closeout:

| Gate | Result |
|------|--------|
| `ruff check .` | clean |
| `ruff format --check` | clean |
| `mypy --strict src/` | clean |
| `pytest -q` | 1910 passed after the combined u51/u52/u53 wave |
| `mkdocs build --strict` | clean |

## Notes

- FR registration was left deferred intentionally in the plan because this is a direct user-evaluation correction layered over existing FR-002/FR-006/FR-008 behavior.
- Empty carryover does not publish placeholder text. The prompt may receive a no-carryover note, but the public markdown stays clean.
