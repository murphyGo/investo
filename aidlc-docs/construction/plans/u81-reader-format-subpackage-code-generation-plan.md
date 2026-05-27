# Code Generation Plan: `u81 reader-format-subpackage`

**Date**: 2026-05-28
**Unit**: u81 reader-format-subpackage
**Stage**: Code Generation (refactor)
**Status**: Planned — not started (0/4 steps)
**Source**: 2026-05-28 abstraction review — `publisher/reader_format.py`
**Estimated Effort**: ~3-4 h
**Dependencies**: **u78** (uses `write_atomic` if any pass writes; soft — primarily the package split)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit.

---

## Problem Statement

`publisher/reader_format.py` is 1208 lines containing ~8 independent transformation passes that share only some regex constants:

- `ensure_tldr_block` (~L96-147) — TL;DR synthesis
- `enforce_h3_subheadings` (~L185-237) — heading normalization
- `wrap_numbers_bold` (~L239-283) — number emphasis
- `check_action_bullet_ratio` (~L323-390) — watchpoint audit
- `dedupe_glossings` (~L431-583) — glossary cleanup
- `normalize_meaning_lines` (u76, ~L605-660) — section meaning-line repair
- `emit_first_viewport_disclaimer` (~L702-792) — short disclaimer injection
- `check_sentence_ending_diversity` (~L818+) — sentence-structure audit
- `reflow_first_viewport` (u71) and the `apply_reader_format` chain that orders all passes

The **order of passes in `apply_reader_format` is load-bearing** (u76 inserts at "step 4.5", disclaimer runs before footer rejoin, etc.). The file mixes all passes + the orchestration chain in one place, making any single pass hard to find, test, or change.

---

## Goal

Convert `reader_format.py` (module) into `reader_format/` (package), one module per pass, with the pass-ordering chain (`apply_reader_format`, `reflow_first_viewport`) living in `__init__.py`. **The public import path `from investo.publisher.reader_format import …` stays identical** because the package `__init__.py` re-exports every public name. No pass changes behavior; the chain order is preserved exactly.

---

## Existing Coverage / Deduplication

- Shared regex/markers (`MEANING_MARKER`, `MEANING_FALLBACK`, glossary markers, disclaimer constants) go into `reader_format/_constants.py`, imported by the passes — single source.
- If any pass writes files, it uses u78's `write_atomic`. (Most passes are pure `str → str`; verify.)
- `apply_reader_format`'s exact step sequence (including the u76 "step 4.5 after dedupe_glossings, before footer rejoin" and u71 reflow position) is the contract — copy it verbatim into `__init__.py`. Do not reorder.

---

## Scope Boundary

In scope:
- Module → package conversion; one file per pass; `_constants.py`; `__init__.py` orchestration + full re-export.

Out of scope:
- Changing any pass's transformation logic, regex, or the chain order.
- Merging passes or "improving" the TL;DR / meaning-line / disclaimer behavior.
- The unified-gate protocol (that is **u85**; reader-format passes are candidates for it later but not here).

---

## Stage Decision

- **Functional Design — SKIP.** Pure structural split of an existing reader-format module; no new entity.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. Disclaimer-injection and compliance behavior preserved (face of NFR), not changed.

---

## Implementation Steps

### Step 1 — create the package skeleton `[ ]`
- [ ] Create `publisher/reader_format/` with `_constants.py` (all shared markers/regex) and one module per pass: `tldr.py`, `headings.py`, `emphasis.py`, `watchpoint_audit.py`, `glossary.py`, `meaning.py`, `disclaimer.py`, `sentence_audit.py`, `reflow.py`.
- [ ] Move each pass's functions + its private helpers into the matching module, importing shared markers from `_constants.py`.
- **Acceptance**: each pass module imports cleanly; no logic edits (diff is move-only per pass).

### Step 2 — orchestration in `__init__.py` `[ ]`
- [ ] Put `apply_reader_format` and `reflow_first_viewport` in `reader_format/__init__.py`, calling the passes in the **exact** existing order.
- [ ] Re-export every name currently importable from `reader_format` (functions + constants + `__all__`) so callers and tests are unchanged.
- **Acceptance**: `grep -rn "reader_format" src tests` shows no caller needs an import-path edit; `__all__` matches the old module's.

### Step 3 — behavior-preservation verification `[ ]`
- [ ] Run the full reader-format + pipeline + integration test set unchanged.
- [ ] Spot-check idempotency tests (u51/u71/u76 reruns must still be byte-stable).
- **Acceptance**: `tests/unit/publisher/test_reader_format*.py`, `test_reader_format_meaning_u76.py`, integration pipeline test — all green unchanged.

### Step 4 — full gate `[ ]`
- [ ] ruff / ruff-format / mypy --strict / pytest / mkdocs build --strict.
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-81.1** — `reader_format` is a package; one module per pass; chain in `__init__.py`.
- **AC-81.2** — Public import path and every public name are unchanged (full re-export); no caller edits.
- **AC-81.3** — `apply_reader_format` pass order is byte-for-byte identical to pre-refactor; idempotency preserved.
- **AC-81.4** — Every pre-existing reader-format / pipeline / integration test passes unchanged; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/publisher/test_reader_format*.py`, `test_reader_format_meaning_u76.py`, `tests/integration/test_pipeline.py` — stay green unchanged.
- New: optional per-pass focused tests are welcome but the unchanged suite is the proof.
- Gate: targeted publisher + integration pytest; full gate before closeout.

---

## Non-Goals

- Any change to a pass's output or the chain order.
- Folding passes into the u85 gate protocol.
