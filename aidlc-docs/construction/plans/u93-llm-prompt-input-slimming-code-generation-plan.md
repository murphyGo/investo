# Code Generation Plan: `u93 llm-prompt-input-slimming`

**Date**: 2026-06-09
**Unit**: u93 llm-prompt-input-slimming
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-04/09 daily briefing speed investigation
**Estimated Effort**: ~5-8 h
**Dependencies**:
- u13 llm-input-candidate-cap complete
- u83 briefing-pipeline-decomposition complete
- u92 daily-briefing-runtime-observability recommended first for measurement

---

## Problem Statement

The briefing generation path performs two LLM stages per non-empty segment:

1. Stage 1 classification receives up to 96 selected `NormalizedItem` records.
2. Stage 2 synthesis receives grouped evidence plus a large system prompt and optional context blocks.

u13 already bounds the number of candidate items. It does not bound the prompt-only size of each candidate field. Stage 1 currently serializes `title`, `summary`, full `url`, and timestamp for every selected candidate. Stage 2 also carries mechanical rules that are now enforced by deterministic gates in publisher/validator code, plus empty optional context blocks on quiet days.

The result is avoidable prompt bytes before the model starts reasoning. Reducing prompt bytes should lower latency and retry risk without reducing evidence coverage.

## Goal

Reduce prompt byte size while preserving the same source evidence, candidate order, macro-priority preservation, and publish-boundary safety gates.

The target outcome is a smaller prompt for representative domestic, US, and crypto segment fixtures with unchanged generated-briefing contracts: six sections, disclaimer, numeric gates, compliance gates, watchpoint matrix, meaning lines, and quality replay behavior.

## Existing Coverage / Deduplication

- u13 owns item-count caps: 96 total, 24 per source, macro-priority and lookahead sub-caps. u93 must not change those constants.
- u55 owns numeric fact gates; u56 owns compliance language gates; u61 owns first-viewport summary gate; u72/u87 own watchpoint matrix structure; u76 owns meaning-line placement. u93 must not remove those deterministic validators.
- u83 decomposed prompt assembly into `_core`, `_assembly`, and `_reader_enhance`; u93 should use those seams rather than re-expanding `briefing/pipeline.py`.

## Scope Boundary

In scope:
- Add deterministic prompt-field truncation for Stage 1 serialization.
- Omit empty optional context blocks from Stage 2 prompt rendering.
- Compact Stage 2 prompt text by removing mechanical instructions that are already enforced by deterministic gates, while preserving model-facing reasoning requirements.
- Add prompt byte-count assertions for representative fixtures.

Out of scope:
- Changing `_select_llm_candidate_items` count caps or priority rules.
- Changing model provider, Claude CLI invocation, timeout values, or retry count.
- Changing generated markdown format requirements.
- Removing any publish-boundary validator.

## Stage Decision

- **Functional Design — SKIP.** This is a prompt/input contract refinement over the existing u2 segmented generation flow.
- **NFR Requirements — SKIP.** No new dependency, external service, secret, or runtime surface. It reduces prompt bytes under NFR-001 and NFR-002.

## Implementation Steps

### Step 1 — add prompt-field caps

- [ ] Add private prompt-field cap constants in `src/investo/briefing/_assembly/prompt_fields.py`:
  - title cap: 180 visible characters,
  - summary cap: 320 visible characters,
  - URL cap: scheme + host + first 96 path/query characters.
- [ ] Implement deterministic truncation that preserves valid UTF-8 and appends `...` only when truncation occurs.
- [ ] Keep macro payload fields untruncated except for string values already owned by the macro payload builder.

### Step 2 — apply caps to Stage 1 serialization

- [ ] Update `serialize_items_for_prompt` in `src/investo/briefing/_core/orchestration.py` to use the prompt-field helper.
- [ ] Preserve JSON key order and item id numbering.
- [ ] Preserve timestamp format.
- [ ] Update prompt snapshot tests so the new shorter payload is intentionally pinned.

### Step 3 — omit empty optional Stage 2 blocks

- [ ] Update context rendering helpers so empty recent context, carryover, lookahead, and bundle-context blocks return `""`.
- [ ] Update `STAGE2_USER_TEMPLATE` rendering so empty block placeholders do not add section headings or "none" prose.
- [ ] Keep non-empty context block headings stable so existing context-enabled tests still pass.

### Step 4 — compact Stage 2 system prompt

- [ ] Review `src/investo/briefing/prompts.py::STAGE2_SYSTEM`.
- [ ] Remove duplicated mechanical rules that deterministic gates already enforce:
  - canonical disclaimer footer,
  - first-viewport short disclaimer,
  - forbidden advice phrase blocking,
  - markdown section-count validation,
  - deterministic watchpoint matrix placement,
  - deterministic meaning-line length/placement.
- [ ] Keep model-facing instructions that require reasoning:
  - segment scope,
  - evidence-backed synthesis,
  - no invented facts,
  - observational wording,
  - required macro actual preservation,
  - cross-market scope discipline.
- [ ] Add a short "publisher gates enforce formatting and compliance" note so the model understands that mechanical gates exist without listing every phrase.

### Step 5 — pin prompt-size reduction

- [ ] Add tests with representative domestic, US, and crypto item sets.
- [ ] Assert Stage 1 prompt byte length is lower than the pre-u93 fixture baseline recorded in the test file.
- [ ] Assert Stage 2 prompt byte length is lower when optional context blocks are empty.
- [ ] Assert non-empty context blocks still appear with their existing headings.

## Acceptance Criteria

1. Stage 1 prompt serialization caps title, summary, and URL fields deterministically without changing item count, item ids, source names, categories, timestamps, or macro payloads.
2. Empty optional context blocks do not emit headings or "no context" prose into Stage 2 prompts.
3. Non-empty optional context blocks are preserved.
4. `STAGE2_SYSTEM` is smaller and still contains the model-facing reasoning constraints listed in Step 4.
5. Existing generated-briefing validation tests stay green: six-section parsing, disclaimer, compliance, numeric validation, watchpoint matrix, meaning-line normalization, and quality replay.
6. u92 prompt-byte logs show lower prompt bytes for representative fixture runs after u93 lands.

## Tests / Validation

- `tests/unit/briefing/test_prompts.py` for compact system prompt required clauses.
- `tests/unit/briefing/test_pipeline_unit.py` or a new prompt serialization test for Stage 1 caps.
- `tests/unit/briefing/test_recent_context.py`, `test_carryover_parser.py`, and lookahead-context tests for empty/non-empty optional blocks.
- `tests/unit/briefing/test_failure_contract.py` for retry feedback compatibility.
- Local gate: `uv run pytest tests/unit/briefing -q`, `uv run ruff check src/investo/briefing tests/unit/briefing`, `uv run mypy --strict src`.

## Non-Goals

- Removing any evidence item selected by u13.
- Shortening or weakening deterministic publish gates.
- Changing generated article length.
- Changing Claude CLI flags or model selection.
- Adding a new prompt templating engine.
