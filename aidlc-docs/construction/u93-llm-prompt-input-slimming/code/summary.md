# u93 LLM Prompt Input Slimming — Code Summary

## Status

Complete on 2026-06-10.

## Scope Delivered

- Added Stage 1 prompt-field shaping helpers in `briefing/_assembly/prompt_fields.py`.
  - `title`: 180 visible characters
  - `summary`: 320 visible characters
  - `url`: scheme + host + first 96 path/query characters
- Updated `serialize_items_for_prompt` to cap only prompt-facing `title`, `summary`, and `url`.
- Preserved item count, dense ids, key order, source/category fields, timestamps, candidate selection, and macro payloads.
- Changed optional Stage 2 context formatters so blank recent-context, lookahead, carryover, and bundle-context inputs return `""` instead of adding empty-note headings/prose.
- Kept non-empty context block headings and bodies stable.
- Replaced the Stage 2 footer-section prompt rule with a compact publisher-gate note:
  - `Publisher gates enforce compliance/disclaimer; emit only six sections.`

## Behavior Boundaries

- No `_select_llm_candidate_items` count cap or priority rule changed.
- No Claude CLI flag, timeout, retry, or budget behavior changed.
- No deterministic publish-boundary validator was removed.
- No generated markdown format requirement was intentionally weakened.

## Validation

- `uv run --extra dev pytest tests/unit/briefing -q`
  - 834 passed
- `uv run --extra dev pytest tests/unit/briefing/test_pipeline_unit.py tests/unit/briefing/test_pipeline_pbt.py tests/unit/briefing/test_prompts.py tests/unit/briefing/test_pipeline_lookahead_render.py tests/unit/briefing/test_pipeline_recent_render.py tests/unit/briefing/test_prompts_carryover.py -q`
  - 117 passed
- `uv run --extra dev ruff check src/investo/briefing tests/unit/briefing`
  - All checks passed
- `uv run --extra dev mypy src`
  - Success: no issues found in 193 source files

## Prompt Byte Pins

- Stage 2 system prompt is pinned below the pre-u93 baseline of `19670` bytes.
- Representative domestic, US, and crypto Stage 1 fixtures assert lower serialized byte length versus the pre-u93 uncapped payload.

## Notes For Next Units

- u94 should compare u92 `prompt_bytes` attempt logs before/after this commit before increasing segment concurrency.
- u95 can use the reduced empty-context behavior when evaluating workflow critical-path budgets on quiet-source days.
