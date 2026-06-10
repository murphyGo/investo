# Code Generation Plan: `u99 daily-thesis-layer`

Date: 2026-06-10
Last Updated: 2026-06-11
Status: Backlog
Source: 2026-06-10 ten-subagent reader review and stage-specific design discussion of the 2026-06-09 generated bundle

## Problem Statement

The segment briefings explain local facts, but they do not consistently tell the reader the cross-market story of the day. A reader should see one bounded "오늘의 큰 그림" line before diving into domestic equity, US equity, or crypto detail. The line must be grounded in shared bundle context and must not invent numbers or predictions.

## Goal

Compute a deterministic daily thesis from successful segment signals and inject the same bounded line before §① in each successful segment when enough shared evidence exists.

## Existing Coverage / Deduplication

- u57 handles shared narrative scope.
- u74 handles channel depth and cross-market cause-map gating.
- `BundleContext` already moves shared context across segments.
- This unit adds a small rendered thesis line; it does not add a third LLM or replace cause-map logic.
- u97 evidence tiers are the preferred upstream signal; u99 must not promote `watchlist_only` or low-confidence evidence into a strong thesis.

## Scope Boundary

In scope:
- Add structured daily-thesis or macro-signal fields to bundle context.
- Render a shared "오늘의 큰 그림" line before §①.
- Omit or downgrade the line under partial or data-limited conditions.
- Keep insertion idempotent.

Out of scope:
- Adding new data sources.
- Generating new predictions, price targets, or advice.
- Changing u74 forbidden cause-map type handling.
- Rewriting segment conclusions.

## Stage Decision

Functional Design: skip. This is a bundle-context and publisher refinement over existing segment publishing.

NFR Requirements: skip. This is deterministic string construction with no new dependencies, secrets, or external services.

## Dependencies

- u57 and u74 must remain complete; u99 reads their approved shared macro and cause-map keys without changing eligibility.
- u97 should run before u99. When u99 is implemented before u97, it must include a local guard that prevents watchlist-only or low-confidence evidence from producing a strong thesis.
- u100 must run with or immediately after u99 because u99 inserts new first-viewport text.

## Fixed Contracts

### Data Model

Add these fields to `src/investo/models/bundle_context.py`:

```python
class DailyThesisSignal(BaseModel):
    segment: str
    key: str
    tier: str
    evidence_label: str
    source_ids: tuple[str, ...] = ()

class DailyThesisDecision(BaseModel):
    mode: Literal["strong", "data_limited", "omit"]
    line: str | None = None
    macro_keys: tuple[str, ...] = ()
    supporting_segments: tuple[str, ...] = ()
    reason: str
```

Extend `BundleContext` with:

```python
daily_thesis_signals: tuple[DailyThesisSignal, ...] = ()
daily_thesis_decision: DailyThesisDecision = DailyThesisDecision(mode="omit", reason="not_evaluated")
```

Older payloads load with empty signals and `omit`.

### Ownership

`src/investo/orchestrator/bundle_context.py` owns thesis evaluation and returns the final `DailyThesisDecision`. `src/investo/publisher/daily_thesis.py` only renders and idempotently injects the already-decided line.

### Decision Table

| Inputs | Decision |
|--------|----------|
| 0-1 successful segments | `mode="omit"`, `line=None`, `reason="insufficient_successful_segments"` |
| At least 2 successful segments but no shared u57/u74-approved or u97-core signal | `mode="data_limited"`, neutral status line, `reason="no_shared_core_signal"` |
| At least 2 successful segments, shared approved signal, no forbidden cause-map type | `mode="strong"`, thesis line, `reason="shared_core_signal"` |
| Any candidate key suppressed by u74 forbidden-type logic | `mode` cannot be `strong` for that key; the key is omitted from thesis inputs |

The data-limited line must be neutral status, not a causal thesis.

### Thesis Shape

Strong thesis lines must use this shape:

```text
> **오늘의 큰 그림:** {driver}가 {supporting_segments}에 동시에 걸리며, 오늘 독자는 {reader_implication}을 먼저 확인해야 합니다.
```

The line must include:
- one driver from u57/u74-approved keys or u97 `core` signal
- at least two supporting segment ids
- one reader implication phrase from a fixed set: `위험 선호의 방향`, `금리·달러 민감도`, `유동성 압력`, `방어적 순환매`

To keep provenance simple, the thesis line must contain no digits. Numeric facts remain in existing anchor/channel sections.

### Prompt Contract

Stage 2 must not author the thesis. `src/investo/briefing/prompts.py` may add only a negative instruction: do not emit a `> **오늘의 큰 그림:**` line because the publisher inserts it deterministically. Do not expose provisional thesis lines to Stage 2.

### Placement

`inject_daily_thesis_line(text, decision)` inserts after u57 shared macro block and summary/navigation material, before the first `## ①`. If `## ①` is absent, return `text` unchanged and log `daily_thesis.no_section_anchor`. If an existing thesis marker is present, replace the existing thesis block with the deterministic publisher line or remove it when mode is `omit`.

## Implementation Steps

1. Inspect `src/investo/models/bundle_context.py`.
   - Add `DailyThesisSignal`, `DailyThesisDecision`, `daily_thesis_signals`, and `daily_thesis_decision`.
   - Keep fields serializable and backward-compatible.
   - Use stable enum/string values rather than localized prose as internal keys.

2. Extend `src/investo/orchestrator/bundle_context.py`.
   - Compute shared signals from successful segments, u97 story tiers when available, market anchors, and existing shared macro metadata.
   - Require at least two successful segments for a strong shared thesis.
   - Return a data-limited or omitted thesis when evidence is insufficient.
   - Exclude any key not approved by u57/u74 when the line would imply causality.

3. Pass thesis context through `src/investo/orchestrator/pipeline.py`.
   - Ensure partial-publish behavior remains unchanged.
   - Ensure failed segments do not receive injected text.
   - Preserve deterministic segment ordering.

4. Add `src/investo/publisher/daily_thesis.py`.
   - Implement `render_daily_thesis_line(decision)` for `DailyThesisDecision`.
   - Implement `inject_daily_thesis_line(text, decision)` with idempotent insertion before the first `## ①` heading.
   - Bound the rendered line length and reject digits in the rendered thesis line.
   - Use conservative Korean phrasing:
     - prefix `> **오늘의 큰 그림:**`
     - observational wording
     - no advice or outcome prediction

5. Wire injection in `src/investo/publisher/segment_reader_format.py`.
   - Place after segment text is assembled and before final publish-boundary gates.
   - Preserve disclaimer/footer behavior.
   - Preserve u74 cause-map output and gating.

6. Update context rendering and prompts only as supporting work.
   - `src/investo/briefing/prompts.py` tells Stage 2 not to emit the deterministic thesis marker.
   - Do not expose a provisional thesis line to Stage 2.

7. Add tests.
   - Daily thesis evaluation with three successful segments.
   - Omission with one successful segment.
   - Downgraded data-limited line with insufficient shared signal.
   - Idempotent injection.
   - No advice/prediction wording.
   - u74 cause-map forbidden-type behavior unchanged.
   - Fixture names: `full_success_3_segments`, `partial_2_success_1_failed`, `one_success_only`, `two_success_no_shared_signal`, and `forbidden_cause_map_key`.

## Acceptance Criteria

- All successful segments in one bundle receive the same thesis line when enough shared signal exists.
- The thesis appears before §① and after first-viewport summary/navigation material.
- The thesis line is not duplicated when reader formatting runs twice.
- The thesis is omitted or downgraded when fewer than two successful segments support a shared view.
- The line contains no digits, advice, price targets, or outcome predictions.
- u74 cause-map gating and suppression behavior remains unchanged.
- Stage 2-authored thesis markers are removed or replaced by the deterministic publisher line.
- A forbidden u74 cause-map key cannot appear in the thesis line.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher tests/unit/orchestrator tests/unit/briefing -k "daily_thesis or bundle_context or cause_map or segment_reader"
uv run --extra dev pytest tests/unit/publisher/test_daily_thesis.py tests/unit/orchestrator/test_bundle_context_daily_thesis.py tests/unit/publisher/test_cross_market_cause_map.py
uv run --extra dev ruff check src/investo/models/bundle_context.py src/investo/orchestrator/bundle_context.py src/investo/orchestrator/pipeline.py src/investo/publisher src/investo/briefing tests/unit/publisher tests/unit/orchestrator tests/unit/briefing
uv run --extra dev mypy src
```

## Non-Goals

- No third LLM pass.
- No new market data source.
- No investment advice.
- No replacement of shared macro block.
- No replacement of cross-market cause map.
