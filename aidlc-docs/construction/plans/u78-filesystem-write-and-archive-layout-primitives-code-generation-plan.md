# Code Generation Plan: `u78 filesystem-write-and-archive-layout-primitives`

**Date**: 2026-05-28
**Unit**: u78 filesystem-write-and-archive-layout-primitives
**Stage**: Code Generation (refactor)
**Status**: Planned — not started (0/4 steps)
**Source**: 2026-05-28 abstraction review — `publisher/` + `visuals/`
**Estimated Effort**: ~2-3 h
**Dependencies**: none
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit.

---

## Problem Statement

Two filesystem primitives are duplicated across the publish/visual layers:

1. **Atomic write (tmp-sibling + `os.replace`) — reimplemented in 8 call sites across 6 files** (count CORRECTED after review 2026-05-28): `publisher/writer.py:73`, `publisher/site_index.py:660` (`_write_text_atomic`), `publisher/weekly_digest.py:239`, `publisher/chart_sidecar.py:221`, `visuals/assets.py:651` and `:665`, and **`visuals/og_card.py:141` and `:142`** (two `os.replace` — SVG + PNG; originally omitted). Each does `mkdir(parents=True)` → write tmp → `os.replace`. A SIGINT-safety or encoding fix would have to land in all of them and could drift.
2. **Archive path layout coupling** — `visuals/paths.py::visual_asset_dir` is derived from `publisher/paths.py::archive_path` by reconstructing the `archive/{segment}/YYYY/MM/YYYY-MM-DD` shape. The directory convention lives implicitly in two files; a layout change breaks both.

---

## Goal

- One `write_atomic` implementation (str + bytes), consumed by all six sites — identical on-disk result and atomicity guarantee.
- One `ArchiveLayout` source of truth for the briefing path and its derived asset directory; `publisher/paths.py` and `visuals/paths.py` both delegate.

No change to any produced file path, byte content, or commit set.

---

## Existing Coverage / Deduplication

- `chart_sidecar.py` writes **bytes**; the others write **str (utf-8)**. The new helper must support both (e.g. `write_atomic(path, text: str)` + `write_atomic_bytes(path, data: bytes)`, or a single function accepting `str | bytes`). Match each call site's current encoding exactly.
- The atomic helper belongs in `publisher/` (e.g. `publisher/_io.py`) because publisher is its primary owner and the existing import direction `visuals → publisher` (already present via `visual_asset_dir`) is preserved. Do NOT create a `visuals → publisher` import where one does not already exist for the bytes path; if `visuals/assets.py` cannot import publisher without a new boundary edge, place the IO helper in `_internal/` instead (shared layer). **Decision point — resolve at Step 1 and record which home you chose and why.**

## Module-boundary note

`publisher`, `visuals`, `notifier`, `briefing`, `sources` may share only `models/` and `_internal/`. `visuals/paths.py:11` and `visuals/assets.py:23` already import `publisher.paths.archive_path` today — a sibling adapter→adapter edge.

> **CORRECTED default after review (2026-05-28, guide §10 #4 dependency-arrows-toward-stability, §9.2 Parnas): home `ArchiveLayout` in `_internal/archive_layout.py`, not `publisher/`.** `ArchiveLayout` is the most *stable* thing both consumers share (the `archive/{segment}/YYYY/MM/...` convention). Homing it in `_internal/` makes both `publisher` and `visuals` depend *inward* on the stable shared layer and **dissolves the sibling `visuals → publisher` edge entirely** — strictly better than the status quo. It is pure path derivation (no IO), so the move is low-risk. Likewise home `write_atomic` in `_internal/_io.py` (cross-cutting IO primitive, no publisher-domain content). Treat removing the sibling edge as the goal, not a contingency.

---

## Scope Boundary

In scope:
- `write_atomic` / `write_atomic_bytes` extraction + migrating all six sites.
- `ArchiveLayout` extraction + delegating both `paths.py` modules.

Out of scope:
- Changing any path string, filename, or directory structure.
- Touching git staging logic (that stays in `git_ops.py`).
- The `_write_text_atomic` callers inside `site_index.py` beyond swapping the implementation (the larger `site_index.py` split is **u82**).

---

## Stage Decision

- **Functional Design — SKIP.** Internal IO/path helper extraction; no new entity.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. Atomicity (an existing NFR property) is preserved, not introduced.

---

## Implementation Steps

### Step 1 — `write_atomic` helper `[x]`
> **Use a SPLIT API, not a `str | bytes` union (review 2026-05-28, guide §9.4 minimize-leak-surface / §3 ISP).** A single `write_atomic(path, str | bytes)` leaks encoding ambiguity (caller must hold the unstated "str ⇒ utf-8, bytes ⇒ verbatim" contract) and widens the union at every call site under mypy --strict. Provide two honest signatures instead.
- [x] Create `write_atomic(path, text: str)` (utf-8) and `write_atomic_bytes(path, data: bytes)`. **Home: `_internal/_io.py`** (cross-cutting IO primitive, no publisher-domain content). Behavior: `path.parent.mkdir(parents=True, exist_ok=True)`, write to `path` + `.tmp` sibling, `os.replace(tmp, path)`. Docstring states the leak boundaries: atomic only within a single filesystem (cross-device `os.replace` raises `OSError`); no `fsync` durability guarantee.
- [x] Migrated all 8 sites: `writer.py`, `site_index.py::_write_text_atomic`, `weekly_digest.py`, `chart_sidecar.py` (bytes), `visuals/assets.py:651`+`:665`, and `visuals/og_card.py:141`+`:142`. `_write_text_atomic` kept as thin delegates in site_index/weekly_digest; og_card's misnamed direct-write helper removed (now uses `write_atomic` + `write_atomic_bytes`; PNG rendered to a `.render.tmp` then published via `write_atomic_bytes`). The one mechanical test edit: `test_writer.py` `os.replace` patch target moved `investo.publisher.writer.os.replace` → `investo._internal._io.os.replace` (symbol moved).
- **Acceptance**: existing publisher/visuals tests pass unchanged; new `tests/unit/_internal/test_io.py` pins atomicity (tmp removed, final present, failed-replace keeps prior) for both str and bytes; zero executable `os.replace` write patterns remain in the 6 files (only docstring mentions).

### Step 2 — `ArchiveLayout` source of truth `[x]`
- [x] Extracted the `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` derivation into `ArchiveLayout` (`briefing_path(target_date, segment)`, `asset_dir(target_date, segment)`) in `_internal/archive_layout.py`. Root is **injected** (the class owns the *shape*, not the mutable seam).
- [x] `publisher/paths.py::archive_path` delegates via `ArchiveLayout(ARCHIVE_ROOT)`; `visuals/paths.py::visual_asset_dir` and `visuals/assets.py` delegate to `ArchiveLayout(...)`. segment=None (combined) and per-segment cases covered.
- **Home decision (recorded):** `ArchiveLayout` is homed in `_internal/` per the corrected default — this dissolved the **top-level `visuals → publisher` import edge** (visuals no longer `from investo.publisher.paths import archive_path`). The *mutable* `ARCHIVE_ROOT` root binding **stays in `publisher.paths`** because the orchestrator god-module reads it via call-time `from investo.publisher.paths import ARCHIVE_ROOT` and ~30 tests monkeypatch `investo.publisher.paths.ARCHIVE_ROOT`. Relocating that seam to `_internal` would force a rewrite of every orchestrator call-time read (u84's domain) and change those tests' patch targets en masse — out of u78's low-risk envelope. visuals therefore reads the live root via a lazy in-function `import investo.publisher.paths` (NOT a top-level edge), preserving the monkeypatch contract. Fully relocating the seam is recorded as deferred Wave-14 TECH-DEBT (depends on u84).
- **Acceptance**: existing path tests pass unchanged; new `tests/unit/_internal/test_archive_layout.py` asserts byte-identical paths to pre-refactor for segment=None and each segment, plus publisher/visuals delegation parity and monkeypatch flow-through.

### Step 3 — boundary test + idempotency verification `[x]`
- [x] **Added an enforced module-boundary test** `tests/unit/_internal/test_module_boundary.py`: walks each adapter package's AST and asserts the **`publisher ⇄ visuals` pair has zero top-level import edges in either direction** — the `visuals → publisher` edge u78 dissolved stays gone. Honest scope note in the test: a *full* "zero sibling edges" invariant is not yet achievable because `publisher`/`notifier`/`sources`/`visuals` all statically import `briefing` (shared domain vocabulary: segments/market_anchor/extract/watchlist); collapsing those is out of u78's scope (deferred Wave-14 TECH-DEBT). The test enforces what u78 actually guarantees.
- [x] Confirmed chart_sidecar byte-determinism (u75 contract) holds — `test_chart_sidecar.py` green after migrating to `write_atomic_bytes`.
- **Acceptance**: boundary test present and green; publisher⇄visuals pair has zero top-level sibling edges; u75 sidecar determinism tests green.

### Step 4 — full gate `[x]`
- [x] ruff (clean) / ruff-format (u78 files clean; 2 pre-existing unrelated violations in `summary_quality.py` + `test_assets.py` present at HEAD, left untouched) / mypy --strict (clean, 151 files) / pytest (2720 passed, +24 vs 2696 baseline) / mkdocs build --strict (ok).
- **Acceptance**: full gate green for u78 scope.

---

## Acceptance Criteria

- **AC-78.1** — Exactly one atomic-write implementation; all six sites delegate.
- **AC-78.2** — Exactly one archive-layout source; both `paths.py` modules delegate; all produced paths byte-identical to pre-refactor.
- **AC-78.3** — Every pre-existing publisher/visuals test passes without modification.
- **AC-78.4** — No new cross-unit import edge; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/publisher/test_git_ops.py`, `test_reader_format.py`, and any `test_paths`/`test_site_index`/`test_chart_sidecar`/`test_chart_assets` — stay green unchanged.
- New: `tests/unit/publisher/test_io.py` (atomic write) and `test_archive_layout.py` (path parity).
- Gate: targeted publisher/visuals pytest; full gate before closeout.

---

## Non-Goals

- The `site_index.py` decomposition (that is **u82**).
- Any change to archive directory structure, filenames, or git staging.
