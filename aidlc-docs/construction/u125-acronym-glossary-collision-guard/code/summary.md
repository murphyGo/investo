# u125 Code Summary: acronym-glossary-collision-guard

## Overview

u125 makes glossary expansion identity-safe for ambiguous acronyms. `ESMA` now resolves to the European regulator, E-mini S&P futures codes match only valid futures-code shapes, and known wrong parenthetical pairs are blocked by the surface-quality gate before archive write.

## Files Changed

- `src/investo/briefing/glossary.py` adds `GlossaryEntry`, `GLOSSARY_ENTRIES`, derives `BASELINE_GLOSSARY` from those entries, and replaces broad wildcard matching with exact futures-code boundaries.
- `src/investo/_internal/surface_quality.py` adds `find_glossary_collision_issues(...)` and blocks forbidden public pairs such as `ESMA(미니S&P선물)`.
- `src/investo/briefing/prompts.py` updates the Stage 2 glossary instruction with ESMA/ES futures identity guidance while staying inside the prompt byte budget.
- Tests cover ESMA regulator glossary rendering, E-mini/ES futures matching, ESMA not matching the ES futures wildcard, reader-format dedupe, surface-quality blockers, and prompt guardrails.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Derive `BASELINE_GLOSSARY` from `GLOSSARY_ENTRIES` | Keeps existing callers stable while adding canonical ids and collision metadata. |
| Use `ES*` with `ES[A-Z][0-9]+` matching | Covers `ESM26` and `ESU26` while excluding `ESMA`. |
| Put public wrong-pair blocking in surface quality | The defect is visible in rendered markdown and must fail before archive write. |
| Keep fallback-free deterministic validation | No LLM or external dictionary is needed for known collision pairs. |

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py tests/unit/publisher/test_reader_format.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_prompts.py`
- `uv run --extra dev ruff check src/investo/briefing/glossary.py src/investo/publisher/reader_format/glossary.py src/investo/_internal/surface_quality.py src/investo/briefing/prompts.py tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py tests/unit/publisher/test_reader_format.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_prompts.py`
- `uv run --extra dev ruff format --check src/investo/briefing/glossary.py src/investo/publisher/reader_format/glossary.py src/investo/_internal/surface_quality.py src/investo/briefing/prompts.py tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py tests/unit/publisher/test_reader_format.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_prompts.py`
- `uv run --extra dev mypy src`

## TECH-DEBT

None.
