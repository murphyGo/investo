# Code Generation Plan: `u98 watchpoint-card-list-redesign`

Date: 2026-06-10
Last Updated: 2026-06-11
Status: Backlog
Source: 2026-06-10 ten-subagent reader review and stage-specific design discussion of the 2026-06-09 generated bundle

## Problem Statement

The §⑥ watchpoint section still reads like a diagnostic grid rather than a reader-facing watch list. The six-column table is hard to scan on mobile, repeats source language, and can expose weak cells such as `데이터부족` across multiple columns. Prior u87 work cleaned broken rows, but the table shape itself still creates a poor narrative experience.

## Goal

Keep the existing watchpoint extraction and validation contract, but render §⑥ as compact cards or grouped lists that preserve source, current signal, confirmation conditions, confidence, and watchlist relevance in a mobile-readable shape.

## Existing Coverage / Deduplication

- u72 introduced the action matrix and validation contract.
- u87 rehabilitated broken observation extraction and markdown sanitation.
- u64 owns watchlist/actionability structure checks.
- u56 compliance scanning already runs around reader-format conversion.
- This unit changes the rendered shape only.

## Scope Boundary

In scope:
- Keep `render_watchpoint_matrix()` as the public entry point.
- Change its output from a six-column markdown table to the canonical compact card format defined below.
- Sanitize raw URLs, broken markdown fragments, trace hashes, and dangling link text.
- Collapse unusable rows to the existing data-limited note.

Out of scope:
- Changing watchlist matcher semantics.
- Adding source adapters or numeric extraction.
- Changing Telegram summary behavior.
- Replacing u64 validation regexes.

## Stage Decision

Functional Design: skip. This is a reader-format refinement over the existing watchpoint renderer.

NFR Requirements: skip. This is pure string rendering and prompt-contract adjustment with no new dependency or runtime service.

## Dependencies

- u64, u72, and u87 are complete prerequisites.
- u98 reuses u87 sanitation and all-limited collapse logic; it does not reimplement those behaviors.
- u98 should run after u96 and u97 for product priority. It can run earlier only as an isolated renderer cleanup.

## Fixed Contracts

### Public API

`render_watchpoint_matrix(text: str, *, section_marker: str = "⑥", segment: str | None = None, coverage_limited: bool = False) -> str` keeps the same callable signature and markdown-in/markdown-out semantics.

### Canonical Card Format

Every valid row renders exactly as:

```markdown
#### 관찰 신호: {short_signal}

- 출처: {source}
- 현재: {current}
- 확인 조건: 상방 {upside}; 하방 {downside}
- 신뢰도: {confidence}
- 관심 영향: {watchlist_impact}
```

Rules:
- preserve row order after existing u87 filtering
- use `MAX_VISIBLE_ROWS` for card count
- append `_관전 신호 {omitted}건 추가 — 본문 참조._` when rows are omitted
- one blank line between cards
- no six-column markdown table header

### Field Mapping

| Parsed row field | Card label | Missing/default behavior | Collapse contribution |
|------------------|------------|--------------------------|----------------------|
| `signal` | heading `{short_signal}` | row is unusable when missing or `데이터부족` | yes |
| `source` | `출처` | render `확인 소스 미상` | no |
| `current` | `현재` | render `현재 신호 부족` | no |
| `upside` | `확인 조건` | render `상방 데이터 부족` | no |
| `downside` | `확인 조건` | render `하방 데이터 부족` | no |
| `confidence` | `신뢰도` | use existing closed enum; default `데이터부족` | yes |
| `implication` | `관심 영향` | render `관심 영향 데이터 부족` | no |

A section collapses to `DATA_LIMITED_NOTE` only when every parsed row is unusable or every surviving row has `confidence == DATA_LIMITED_CONFIDENCE`.

### Prompt Contract

Stage 2 must continue to emit parser-compatible structured watchpoint bullets under the u64/u72/u87 source+trigger+implication contract. Prompt edits may change only the reader-facing wording that asks for card-populatable fields; they must not change matcher semantics, numeric evidence extraction, confidence enum, advice bans, or Telegram behavior.

### Sanitation Contract

Call the existing u87 sanitation/filtering path before card rendering. Add regression coverage that card rendering still removes:
- raw URLs
- broken markdown fragments
- `input_hash`, `stage1_hash`, `stage2_hash`
- dangling Korean particles left after link removal

## Implementation Steps

1. Inspect `src/investo/publisher/watchpoint_matrix.py`.
   - Keep the function name and import path `render_watchpoint_matrix`.
   - Keep the callable signature unchanged.
   - Keep existing row parsing and confidence values.
   - Identify the point where valid rows become markdown output.

2. Replace table output with a card renderer.
   - Use the canonical card format above.
   - Use bounded line lengths and deterministic ordering.
   - Escape markdown-sensitive text consistently.

3. Filter unusable rows before rendering.
   - Drop rows where every substantive field is empty or `데이터부족`.
   - Drop diagnostic trace lines and bare links.
   - Collapse all-empty or all-limited sections to `DATA_LIMITED_NOTE`.

4. Strengthen sanitation.
   - Reuse the existing u87 sanitizer/filter helpers where present.
   - Add card-rendering regression fixtures that prove raw URLs, broken markdown, trace hashes, and dangling particles do not reappear.

5. Update `src/investo/briefing/prompts.py`.
   - Ask Stage 2 for structured watchpoint bullets that populate the card fields.
   - Keep the observational-only rule and advice bans.
   - Include one positive example and one rejected example that match the new reader-facing shape.

6. Add tests.
   - `tests/unit/publisher/test_watchpoint_matrix.py`
     - no six-column table header
     - canonical card shape for valid rows
     - `- 출처: {source}` survives rendering
     - all-limited collapse
     - mixed valid/unusable rows
     - partially populated rows and defaults
     - raw URL and broken markdown removal
     - `input_hash`/`stage1_hash`/`stage2_hash` removal
     - idempotence
     - unchanged callable signature
     - byte preservation outside §⑥ when called through reader-format path
   - `tests/unit/briefing/test_prompts.py`
     - prompt preserves parser-compatible watchpoint bullets and observational-only constraints.
   - `tests/unit/publisher/test_segment_reader_format.py`
     - pre/post compliance scan still wraps watchpoint conversion.
   - Add one real 2026-06-09 §⑥ sample fixture to prove the mobile-hostile table shape is replaced.

## Acceptance Criteria

- Rendered §⑥ does not contain the old table header.
- Valid watchpoints render as canonical card blocks.
- All-`데이터부족` rows do not produce multiple low-value cards.
- Raw URLs, broken markdown fragments, and trace hashes do not appear in §⑥ output.
- `render_watchpoint_matrix()` keeps its callable signature and markdown-in/markdown-out semantics.
- Existing compliance scan order remains active.
- Output outside §⑥ is byte-preserved for fixtures that only exercise watchpoint conversion.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py
uv run --extra dev ruff check src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py
uv run --extra dev mypy src
```

## Non-Goals

- No watchlist matcher rewrite.
- No new watchpoint source data.
- No Telegram behavior change.
- No numeric validator change.
- No broad section redesign outside §⑥.
