# 2026-06-25 u118 Code Generation

## Unit

`u118 briefing-generation-side-effect-boundary`

## Result

Complete.

## Implementation

- Added `src/investo/briefing/generation_contract.py` with immutable `GenerationInput` and `GenerationResult`.
- Added `generate_briefing_from_input(...)` as the canonical structured generation API.
- Kept `generate_briefing(...)` compatible as a wrapper returning `Briefing`.
- Changed macro lineage construction to return a tuple in `GenerationResult`.
- Updated the default orchestrator generation path to pass explicit `WatchlistConfig` into the canonical request.
- Preserved custom segment generator seams and skipped LLM loop extraction because it did not simplify the stage-specific validation paths.

## Validation

- Focused briefing/orchestrator/integration tests.
- Scoped ruff check and format check.
- `mypy src`.
- Full pytest.
- `mkdocs build --strict`.
