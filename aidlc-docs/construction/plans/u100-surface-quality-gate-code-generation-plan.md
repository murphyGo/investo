# Code Generation Plan: `u100 surface-quality-gate`

Date: 2026-06-10
Last Updated: 2026-06-11
Status: Complete
Source: 2026-06-10 ten-subagent reader review and stage-specific design discussion of the 2026-06-09 generated bundle

## Problem Statement

The 2026-06-09 review found first-viewport surface defects that damage trust even when underlying market facts are usable. Examples include `불강한성`, dangling `...`, broken markdown/link fragments, and repeated template phrases. Existing compliance checks catch advice and disclosure issues, but they do not repair or block these reader-facing language artifacts.

## Goal

Add a deterministic repair-and-gate pass for known bad tokens and first-viewport broken artifacts. The pass repairs safe known cases, blocks unrepaired first-viewport defects, and reports repeated template phrases as warnings.

## Existing Coverage / Deduplication

- u56 owns compliance language gates.
- u61 owns first-viewport structural validation.
- u71 owns first-viewport reflow.
- u76 owns section-level meaning-line normalization.
- This unit adds surface-quality repair/block behavior; it does not add a full Korean spellchecker or semantic rewrite.
- u100 consumes fixed surface issue codes only; it does not add new summary-heading, truncation, or fallback categories owned by u61/u71.

## Scope Boundary

In scope:
- Repair known bad token `불강한성` to `불확실성`.
- Repair or block first-viewport dangling `...`.
- Repair or block broken markdown links and trace/link fragments.
- Warn on repeated template phrases.
- Skip code blocks, markdown tables, disclaimers, and diagnostic details.

Out of scope:
- Global grammar correction.
- Full Korean spellchecking.
- LLM-based paraphrasing.
- Blocking every ellipsis in the body.
- Changing compliance/advice policy.

## Stage Decision

Functional Design: skip. This is a validator/formatter refinement over existing reader-format and summary-quality surfaces.

NFR Requirements: skip. This is deterministic text processing with no new dependencies, secrets, or external services.

## Dependencies

- u100 should run with u99 or immediately after u99 so the deterministic thesis line is also checked.
- u96 remains higher priority when public status contradicts segment status.

## Fixed Contracts

### Shared Owner

Create `src/investo/_internal/surface_quality.py` as the neutral owner for detection types and regexes. `briefing` and `publisher` callers both import from this module. Do not make `briefing` import from `publisher`.

Required exports:

```python
SurfaceIssueSeverity = Literal["warn", "block"]

@dataclass(frozen=True, slots=True)
class SurfaceQualityIssue:
    code: str
    severity: SurfaceIssueSeverity
    evidence: str
    region: Literal["first_viewport", "body", "protected"]
```

Publisher error:

```python
class SurfaceQualityError(Exception):
    segment: str
    issues: tuple[SurfaceQualityIssue, ...]
```

### First-Viewport Boundary

The first viewport is the substring from the start of markdown through the first line that starts with `## ①`. If `## ①` is missing, the first viewport is the text before the first other `## ` heading; if no H2 exists, it is the first 1600 characters. Protected regions are fenced code blocks, markdown tables, disclaimer/footer text, and collapsed `<details><summary>수집/품질 진단</summary>` diagnostics.

### Issue Matrix

| Code | Severity | Region | Behavior |
|------|----------|--------|----------|
| `bad_token.bulganghanseong` | `warn` after repair | any unprotected prose | replace `불강한성` with `불확실성`; block only if still present after repair |
| `markdown.unmatched_link` | `block` | first viewport prose | block unmatched `[`/`](` or truncated markdown link residue |
| `trace.fragment` | `block` | first viewport prose before diagnostics | block raw `input_hash`, `stage1_hash`, or `stage2_hash` outside diagnostics |
| `ellipsis.dangling_line` | `warn` after repair | first viewport prose | repair lines that are only `...` or end with ` ...`; allow bounded snippets ending with `...` from u71 |
| `template.repeated_phrase` | `warn` | first viewport prose | warn when an exact phrase from the fixture list appears 3 or more times; never rewrite or block |

Repeated-template phrase list for this unit:
- `본문을 참고하세요`
- `데이터가 제한적입니다`
- `추가 확인이 필요합니다`

### Ordering

1. Apply u71 `reflow_first_viewport()`.
2. Repair safe surface artifacts.
3. Run blocking surface-quality scan.
4. Run final compliance, disclaimer, and public consistency gates.
5. Raise `SurfaceQualityError` before archive/index/quality writes for the affected segment.
6. Preserve existing partial-publish behavior for sibling segments.

## Implementation Steps

1. Add a focused surface-quality module.
   - Create `src/investo/_internal/surface_quality.py`.
   - Export `repair_surface_artifacts(text: str) -> str`.
   - Export `find_surface_quality_issues(text: str) -> tuple[SurfaceQualityIssue, ...]`.
   - Export `extract_first_viewport(text: str) -> str`.
   - Keep the module pure and deterministic.

2. Implement scoped repair.
   - Replace `불강한성` with `불확실성`.
   - Remove or close dangling first-viewport `...` when it is an artifact at paragraph end or broken list text.
   - Remove raw trace fragments and broken markdown link fragments in first-viewport prose.
   - Do not edit fenced code blocks, markdown tables, disclaimer/footer text, or collapsed diagnostic details.

3. Add blocking behavior.
   - Add `SurfaceQualityError` in `src/investo/publisher/errors.py`.
   - Route the error through `src/investo/orchestrator/pipeline.py` so unrepaired first-viewport defects fail the affected segment at the publish boundary.
   - Keep repeated template phrases as warning findings only.

4. Integrate with reader-format ordering.
   - Call the repair pass after u71 reflow in `src/investo/publisher/segment_reader_format.py`.
   - Run the blocking scan in `src/investo/publisher/segment_reader_format.py` before final compliance/disclaimer/public consistency gates.
   - Confirm the pass is idempotent.

5. Harden summary extraction.
   - Update `src/investo/briefing/summary_quality.py` to report first-viewport surface defects.
   - Update `src/investo/briefing/_assembly/summary_extraction.py` so broken artifacts are not selected as summary/conclusion lines.
   - Summary extraction may reject candidates using shared issue codes only; it must not repair or normalize prose.

6. Add tests.
   - Repair `불강한성`.
   - Warn after repairing first-viewport dangling `...`.
   - Block broken markdown link fragments in first viewport.
   - Preserve code blocks, tables, disclaimers, and diagnostic details.
   - Warn but do not block repeated template phrases.
   - Confirm idempotence.
   - Confirm orchestrator routes `SurfaceQualityError` as a segment publish failure without changing unrelated segment success behavior.
   - Confirm u99 thesis text is checked by the same pass.

## Acceptance Criteria

- Final published markdown cannot contain `불강한성`.
- First-viewport dangling `...` artifacts are repaired and reported as warnings.
- Broken markdown/link fragments in first viewport are blocked with `SurfaceQualityError`.
- Code blocks, tables, disclaimers, and diagnostics are not rewritten.
- Repeated template phrases generate warnings only.
- The pass is idempotent.
- Final compliance and disclaimer gates still run after this pass.
- Broken artifacts cannot be selected as summary/conclusion lines.
- `SurfaceQualityError` is raised before archive/index/quality writes for the affected segment.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher tests/unit/briefing tests/unit/orchestrator -k "surface or summary_quality or segment_reader or first_viewport"
uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py tests/unit/orchestrator/test_surface_quality_publish_routing.py
uv run --extra dev ruff check src/investo/publisher src/investo/briefing tests/unit/publisher tests/unit/briefing tests/unit/orchestrator
uv run --extra dev mypy src
```

## Non-Goals

- No full Korean spellchecker.
- No semantic LLM rewrite.
- No global ellipsis ban.
- No source adapter changes.
- No investment-advice policy changes.
