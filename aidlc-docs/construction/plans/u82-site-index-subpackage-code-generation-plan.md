# Code Generation Plan: `u82 site-index-subpackage`

**Date**: 2026-05-28
**Unit**: u82 site-index-subpackage
**Stage**: Code Generation (refactor)
**Status**: Planned — not started (0/4 steps)
**Source**: 2026-05-28 abstraction review — `publisher/site_index.py`
**Estimated Effort**: ~2-3 h
**Dependencies**: **u78** (`_write_text_atomic` should delegate to `write_atomic`)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit.

---

## Problem Statement

`publisher/site_index.py` (681 lines) builds four unrelated public surfaces in one module:

- **Hero block** for the home page — quote cards (~L298-397)
- **Archive sections** — latest / legacy indices (~L504-572)
- **Per-segment archive listings** (~L336-353)
- **Quality / Accuracy dashboard** KPI page (~L181-271)

plus shared block-replacement helpers (`_replace_section`, `_replace_marker_block`, `_write_text_atomic` ~L657-660) and inline-escape helpers (~L651-653). The four surfaces are independent but co-located, so changing one means reading all four.

---

## Goal

Convert `site_index.py` into a `site_index/` package: one module per surface, shared block-replacement/escape helpers in a private module, and the public entry point (`update_latest_index_pages` and any other exported names) preserved in `__init__.py` via full re-export. No produced HTML/markdown byte changes.

---

## Existing Coverage / Deduplication

- `_write_text_atomic` must now delegate to u78's `write_atomic` (not its own `os.replace`). If u78 is not yet landed, this unit is blocked on it.
- `_replace_section` / `_replace_marker_block` are reused by multiple surfaces — they go into `site_index/_blocks.py`, imported by each surface module.
- The inline-escape helper (`_escape_inline`) goes into `_blocks.py` (or `publisher/_escape.py` if shared with `render.py` — but cross-module escape sharing is optional and NOT required here; keep it local unless trivially shared).

---

## Scope Boundary

In scope:
- Module → package; `hero.py`, `archive_sections.py`, `segment_archives.py`, `quality_dashboard.py`, `_blocks.py`; `__init__.py` public API + re-export.

Out of scope:
- Changing any rendered page content, marker, or ordering.
- The quality-consistency gate logic (lives in `quality_consistency.py` — untouched).
- Markdown-builder abstraction (the review's optional `MarkdownBuilder` is deferred — do not introduce it here; keep diffs move-only).

---

## Stage Decision

- **Functional Design — SKIP.** Structural split of an existing publisher module; no new entity.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost.

---

## Implementation Steps

### Step 1 — create the package + shared helpers `[ ]`
- [ ] Create `publisher/site_index/` with `_blocks.py` holding `_replace_section`, `_replace_marker_block`, `_escape_inline`, and `_write_text_atomic` (delegating to u78 `write_atomic`).
- [ ] Create `hero.py`, `archive_sections.py`, `segment_archives.py`, `quality_dashboard.py`; move each surface's renderers + private helpers in, importing from `_blocks.py`.
- **Acceptance**: each surface module imports cleanly; per-module diffs are move-only.

### Step 2 — orchestration + re-export in `__init__.py` `[ ]`
- [ ] Put `update_latest_index_pages` (the public driver) in `__init__.py`, calling the surface modules in the existing order.
- [ ] Re-export every name currently importable from `site_index` (match `__all__`).
- **Acceptance**: `grep -rn "site_index" src tests` shows no caller needs an import edit.

### Step 3 — behavior-preservation verification `[ ]`
- [ ] Run the site-index / index-page / quality-dashboard tests unchanged; confirm `mkdocs build --strict` produces the same pages.
- **Acceptance**: existing tests green unchanged; mkdocs strict pass.

### Step 4 — full gate `[ ]`
- [ ] ruff / ruff-format / mypy --strict / pytest / mkdocs build --strict.
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-82.1** — `site_index` is a package; one module per surface; shared helpers in `_blocks.py`.
- **AC-82.2** — Public import path and names unchanged (full re-export); no caller edits.
- **AC-82.3** — `_write_text_atomic` delegates to u78 `write_atomic`; no second atomic-write implementation remains here.
- **AC-82.4** — Every pre-existing test passes unchanged; mkdocs --strict produces identical pages; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/publisher/` site-index / index / quality tests — stay green unchanged.
- Gate: targeted publisher pytest + mkdocs build --strict; full gate before closeout.

---

## Non-Goals

- Any rendered-page content change.
- Introducing a `MarkdownBuilder` abstraction (deferred).
- Touching `quality_consistency.py`.
