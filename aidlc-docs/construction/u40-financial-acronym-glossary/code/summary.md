# u40 financial-acronym-glossary Code Summary

**Date**: 2026-05-09
**Status**: Complete

## Implementation

- Added `briefing/glossary.py` with a curated `BASELINE_GLOSSARY` of 34 financial acronyms, futures-code patterns, Korean market terms, and crypto terms.
- Added deterministic first-appearance auditing via `audit_glossary_compliance()` and brief-header rendering via `render_glossary_callout()`.
- Extended the Stage 2 system prompt with the `약자 풀어쓰기 룰` and examples such as `EIA(에너지정보청)` and `프로그램매매(기관자동주문)`.
- Wired `_enhance_reader_experience()` to surface a capped `> **용어 가이드**` callout for missing first-use glosses without blocking publication.

## Verification

- `uv run pytest tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py tests/unit/briefing/test_prompts.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`
