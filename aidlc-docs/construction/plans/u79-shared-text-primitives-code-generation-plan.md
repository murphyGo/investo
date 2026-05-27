# Code Generation Plan: `u79 shared-text-primitives`

**Date**: 2026-05-28
**Unit**: u79 shared-text-primitives
**Stage**: Code Generation (refactor)
**Status**: Complete — 3/3 steps
**Source**: 2026-05-28 abstraction review — `notifier/` + `briefing/` + `_internal/`
**Estimated Effort**: ~2-3 h
**Dependencies**: none (but **u80 depends on this** — UTF-16 helpers move here first)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit.

---

## Problem Statement

Two reusable text primitives live in the wrong place or in triplicate:

1. **UTF-16 unit counting + truncation is buried in `notifier/summary.py`** (`_utf16_units` ~L121-148, `_utf16_truncate` ~L484-495). These are pure text utilities (Telegram counts UTF-16 code units), not summary logic. They belong in `_internal/text.py` (which today holds only `truncate_stderr`) so they can be reused without importing the notifier. `operator_alerter.py` also needs UTF-16 truncation and currently reaches into summary internals.
2. **Ticker / markdown regex patterns are defined 3× inside `briefing/`** — `_KOREAN_EXCHANGE_TICKER` / `_US_TICKER` / crypto-term patterns appear in `briefing/pipeline.py` (~L173-199), `briefing/segments.py` (~L263-287), and `briefing/citation_cardinality.py` (~L42-44). They agree by inspection today but a change to one would silently diverge.

> **Already resolved — do NOT touch:** DEBT-035 (redaction regex, now single-sourced in `_internal/redaction.py`) and DEBT-060 (conclusion-prefix, now single-sourced via `briefing/extract.py` + `briefing/summary_quality.py` exports). Those are done; this unit must not reopen them.

---

## Goal

- Move UTF-16 helpers to `_internal/text.py` as public functions; `notifier/summary.py` and `notifier/operator_alerter.py` import them. (This is a prerequisite for u80's notifier split.)
- Centralize the briefing ticker/markdown regex patterns in one `briefing/_text/patterns.py` (briefing-internal); the three sites import from it.

No change to any truncated string, summary byte, or citation-warning output.

---

## Existing Coverage / Deduplication

- `_internal/text.py` already exists with `truncate_stderr` — extend it; do not create a parallel text module.
- All three regex consumers are inside `briefing/`, so the shared pattern module stays briefing-internal (no boundary concern).
- **Open TECH-DEBT to check, not assume:** there is an open entry about duplicated summary-reject regexes between `briefing/pipeline.py::_is_unsafe_summary_candidate` and `briefing/summary_quality.py` (the producer/gate mirror). `grep DEBT- docs/TECH-DEBT.md` for the live ID. If folding that dedup in is clean (single reject-pattern set imported by both), do it in Step 2 and reference the DEBT ID in closeout. If it risks changing gate behavior, leave it and note as out-of-scope.

---

## Scope Boundary

In scope:
- UTF-16 helpers → `_internal/text.py`; migrate the two notifier consumers.
- Briefing regex patterns → `briefing/_text/patterns.py`; migrate the three consumers.
- Optionally (only if behavior-safe) the summary-reject-set dedup noted above.

Out of scope:
- The full `notifier/summary.py` extractor/formatter split (that is **u80**).
- The `briefing/pipeline.py` decomposition (that is **u83**).
- DEBT-035 / DEBT-060 (resolved).

---

## Stage Decision

- **Functional Design — SKIP.** No new entity; relocating/centralizing pure text utilities.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. R13 (no secret in output) is unaffected (redaction untouched).

---

## Implementation Steps

### Step 1 — UTF-16 helpers to `_internal/text.py` `[x]`
- [x] Add public `utf16_units(text) -> int`, `utf16_truncate(text, max_units) -> str`, and a `truncate_with_suffix(text, max_units, suffix) -> str` if a call site needs the "…"-append pattern. Match `summary.py`'s exact current semantics (boundary handling, suffix behavior).
- [x] Update `notifier/summary.py` and `notifier/operator_alerter.py` to import from `_internal/text.py`; remove the local copies.
- **Acceptance**: every pre-existing `notifier/` test (`test_summary.py`, `test_telegram.py`, operator-alerter tests) passes unchanged; new `_internal` tests pin code-unit counting for BMP + surrogate-pair (emoji) strings and the truncation boundary.

### Step 2 — briefing regex patterns to `briefing/_text/patterns.py` `[x]`
- [x] Create `briefing/_text/patterns.py` holding the canonical `KOREAN_EXCHANGE_TICKER`, `US_TICKER`, crypto-term patterns (and the markdown-cleaning patterns if they are identical across sites).
- [x] Update `briefing/pipeline.py`, `briefing/segments.py`, `briefing/citation_cardinality.py` to import them; delete the local `re.compile` literals. (Also migrated `summary_quality.py`'s identical `_MEANINGFUL_TEXT_RE`.)
- [x] (Conditional) Reviewed DEBT-047 — left out-of-scope (see closeout note); it requires restructuring the gate's prefix-specific exception messages, which is gate-behavior-touching, not a clean shared-pattern-set swap.
- **Acceptance**: existing `briefing/` tests (`test_segments_exclusivity.py`, citation/cardinality tests, `test_pipeline_unit.py`) pass unchanged; a grep guard test asserts no site redeclares the moved patterns.

### Step 3 — full gate `[x]`
- [x] ruff / ruff-format / mypy --strict / pytest / mkdocs build --strict.
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-79.1** — UTF-16 helpers live only in `_internal/text.py`; both notifier consumers delegate; truncated Telegram bytes are identical to pre-refactor.
- **AC-79.2** — Briefing ticker/markdown regexes have one home; the three sites import them; citation/segment outputs unchanged.
- **AC-79.3** — Every pre-existing notifier + briefing test passes without modification.
- **AC-79.4** — DEBT-035 / DEBT-060 untouched; mypy --strict clean; module boundary intact.

---

## Tests / Validation

- `tests/unit/notifier/test_summary.py`, `test_telegram.py`; `tests/unit/briefing/test_segments_exclusivity.py`, citation-cardinality tests — stay green unchanged.
- New: `tests/unit/_internal/test_text.py` (UTF-16 units/truncate incl. emoji surrogate pairs) and a briefing pattern grep-guard test.
- Gate: targeted notifier + briefing pytest; full gate before closeout.

---

## Non-Goals

- notifier/summary.py extractor/formatter split (u80).
- briefing/pipeline.py decomposition (u83).
- Reopening DEBT-035 / DEBT-060.
- **A `Ticker` value object** (review 2026-05-28, guide §6). Centralizing the ticker *regexes* here is correct and behavior-preserving; introducing a `Ticker` value object to kill the primitive obsession is the genuine DDD cure the codebase still wants, BUT it ripples into the `Briefing` model and many call sites (behavior-touching) — out of scope for this wave. Record it as a future TECH-DEBT/unit so the trail is not lost.
