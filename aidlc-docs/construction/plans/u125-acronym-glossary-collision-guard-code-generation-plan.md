# Code Generation Plan: `u125 acronym-glossary-collision-guard`

**Date**: 2026-06-25
**Unit**: u125 acronym-glossary-collision-guard
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing review, focused on the crypto glossary line `ESMA(미니S&P선물)`.
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u40 financial-acronym-glossary is complete; reuse `BASELINE_GLOSSARY`.
- u51 tldr-block-and-number-bold-inversion is complete; preserve glossary dedupe and first-use behavior.
- u68 reader-aids-residual is complete; keep prior-briefing suppression behavior.
- u112 reader-markdown-polish-gate-v2 is complete; add only bounded wrong-expansion blockers.

---

## Problem Statement

The 2026-06-23 crypto briefing renders:

`> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — ESMA(미니S&P선물)`

The body later uses ESMA in the regulatory context of the European Securities and Markets Authority. Rendering it as E-mini S&P futures is a false reader aid. The root class is acronym collision: a shorter or related market term can match inside a longer all-caps acronym, then the glossary attaches the wrong expansion.

## Goal

Make glossary and inline reader aids identity-safe: an acronym expands only when the exact canonical token and context match the glossary entry. Known wrong acronym-expansion pairs must be blocked before archive write.

## Existing Coverage / Deduplication

- u40 owns baseline glossary terms and first-appearance audit.
- u51 owns first-use dedupe and reader-format integration.
- u68 owns residual suppression across recent archives.
- u112 owns bounded public markdown/polish blockers.

This unit adds identity and collision guards to those existing paths. It does not add a broad in-body auto-glosser, new data source, or LLM-based glossary reviewer.

## Scope Boundary

In scope:
- Enforce exact acronym token boundaries for all-caps glossary keys.
- Add canonical ids for ambiguous terms where plain text is not enough.
- Block known wrong expansion pairs in public glossary callouts and inline parentheticals.
- Add prompt guardrails against composing acronym meanings from substrings.

Out of scope:
- No complete financial dictionary.
- No machine-translation service.
- No broad spelling or grammar checker.
- No archive backfill.
- No user-configurable glossary editor.

## Stage Decision

Functional Design: skip. This is a deterministic validation extension over the existing glossary contract.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Canonical Acronym Entries

Extend glossary metadata for ambiguous acronyms with this shape while preserving the public `BASELINE_GLOSSARY` view:

```python
@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term: str
    gloss: str
    canonical_id: str
    aliases: tuple[str, ...] = ()
    forbidden_context_terms: tuple[str, ...] = ()
```

Initial required entries:

| canonical_id | term | gloss | Collision Guard |
|---|---|---|---|
| `regulator.esma` | `ESMA` | `유럽증권시장청` | must not use `미니S&P선물` |
| `futures.emini_sp500` | `E-mini S&P 500` | `미니 S&P 500 선물` | must not match inside `ESMA` |

### Boundary Rules

- All-caps acronym keys match only as full tokens bounded by non-letter/digit characters.
- Hyphenated futures terms match as full phrase tokens.
- Korean parenthetical expansions must match the canonical id's gloss, not another entry's gloss.
- The public glossary line is blocked when a forbidden pair appears, for example `ESMA(미니S&P선물)`.

## Implementation Steps

- [ ] Inspect `src/investo/briefing/glossary.py` functions `audit_glossary_compliance`, `render_glossary_callout`, `_term_regex`, and `BASELINE_GLOSSARY`.
- [ ] Inspect `src/investo/publisher/reader_format/glossary.py` to preserve existing dedupe semantics.
- [ ] Add an internal `GLOSSARY_ENTRIES` map and derive the existing `BASELINE_GLOSSARY` dict from it for compatibility.
- [ ] Replace acronym regex construction with exact token-boundary rules for all-caps keys and phrase-boundary rules for hyphenated futures terms.
- [ ] Add a pure validator `find_glossary_collision_issues(markdown) -> tuple[GlossaryCollisionIssue, ...]` in `briefing/glossary.py` or `_internal/surface_quality.py`.
- [ ] Wire the validator into the existing surface-quality gate before archive writes.
- [ ] Update `src/investo/briefing/prompts.py` glossary instruction so Stage 2 must not infer acronym expansions from substrings.
- [ ] Add tests for `ESMA`, `E-mini S&P 500`, `ESU26`, `S&P 500`, and Korean parenthetical callouts.
- [ ] Write `aidlc-docs/construction/u125-acronym-glossary-collision-guard/code/summary.md`.

## Acceptance Criteria

1. `ESMA` in a regulation paragraph renders as `ESMA(유럽증권시장청)` or appears in the glossary as `ESMA(유럽증권시장청)`.
2. `ESMA(미니S&P선물)` is blocked by the surface-quality gate.
3. `E-mini S&P 500` and `ESU26` futures contexts can still receive valid futures glosses.
4. `E-mini`/`ES` matching never fires inside the longer token `ESMA`.
5. Existing u51 glossary dedupe still suppresses repeat explanations after the first valid appearance.
6. Prior-briefing suppression from u68 still ignores terms already explained in the recent archive window.
7. Tests cover all-caps boundaries, hyphenated futures names, Korean parenthetical expansions, glossary callout rendering, and idempotent reruns.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py tests/unit/publisher/test_reader_format.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_prompts.py
uv run --extra dev ruff check src/investo/briefing/glossary.py src/investo/publisher/reader_format/glossary.py src/investo/_internal/surface_quality.py src/investo/briefing/prompts.py tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py
uv run --extra dev ruff format --check src/investo/briefing/glossary.py src/investo/publisher/reader_format/glossary.py src/investo/_internal/surface_quality.py src/investo/briefing/prompts.py tests/unit/briefing/test_glossary.py tests/unit/briefing/test_pipeline_glossary.py
uv run --extra dev mypy src
```

## Non-Goals

- No broad glossary rewrite.
- No in-body auto-glossing expansion beyond existing behavior.
- No external dictionary or translation service.
- No archive backfill.
- No source collection change.
