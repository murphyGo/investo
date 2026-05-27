# Wave 14 — Internal Abstraction & Clean-Code Refactor (Overview)

**Date**: 2026-05-28
**Stage**: Code Generation (refactor wave)
**Units**: u77 – u85 (9 units)
**Status**: Planned — none started
**Source**: 2026-05-28 whole-codebase abstraction review (4-module fan-out: sources / briefing / publisher+visuals / orchestrator+notifier+models). The review found two god-modules and several cross-module duplication patterns. See the per-unit plans for evidence.

> **Read this overview first.** It defines the shared **Refactor Contract** that every Wave 14 unit (u77–u85) inherits. Each per-unit plan is self-contained but does NOT repeat these invariants — they apply to all of them. A context-free agent picking up any u77–u85 plan MUST read this file before touching code.

---

## Why this wave exists

The codebase is functionally healthy (2641+ tests green, mypy --strict clean) but has accumulated structural debt as 76 feature units landed:

- **Two god-modules**: `orchestrator/pipeline.py` (2775 lines, 41 functions, imports 34 submodules) and `briefing/pipeline.py` (1918 lines, 88 functions). Both tangle 5+ responsibilities, making them hard to test in isolation and risky to change.
- **Large single-file modules**: `publisher/reader_format.py` (1208), `notifier/summary.py` (755), `publisher/site_index.py` (681).
- **Cross-module duplication** of low-level primitives: atomic file-write (6 modules), JSON-decode boilerplate (17 source adapters), UTF-16 truncation, datetime→UTC parsing, numeric-parse helpers.
- **No unifying protocol** for the ~11 briefing checks and ~5 publisher gates — each is an ad-hoc function with a different shape.

This wave does **not** add product behavior. It pays down structural debt so the next feature waves are cheaper and safer.

---

## The Refactor Contract (applies to ALL units u77–u85)

1. **Behavior-preserving is the prime directive.** No change to: generated briefing markdown bytes, Telegram message bytes, archive file layout, public site HTML, or any observable output. If a refactor would change output, it is out of scope — stop and record it as TECH-DEBT instead.
2. **Existing tests stay green WITHOUT modification** — except mechanical import-path updates when a symbol moves. The unchanged existing suite is the primary proof of behavior preservation. If an existing assertion must change to pass, that is a behavior change → reject.
3. **Prefer "extract + delegate" over "move + rewrite."** Old call sites should call the new helper/class; keep diffs small and reviewable. When splitting a module into a package, the package `__init__.py` MUST re-export every public name so no external caller changes its import path.
   > **Qualifier (review 2026-05-28, guide §9.3):** "extract + delegate / move-only" guarantees *safety* but does NOT by itself achieve SLAP at the function level — a move-only split of a god-module can leave the orchestrator function (e.g. `generate_briefing`) at mixed abstraction levels. Where a unit's stated goal is a "thin orchestrator" (u83, u84), ONE explicitly-scoped re-leveling step (a behavior-preserving *logic edit*, verified by the replay harness / unchanged suite) is permitted and expected. Such a step must be called out explicitly in the unit plan.
   > **Full re-export is a migration tactic, not the final interface (guide §9.2/§9.4):** re-exporting every public name preserves callers but freezes today's whole surface as the API. After the wave, a follow-up should narrow each package `__all__` to the genuine entry points. Record the wide surface as deferred TECH-DEBT.
4. **Project rules are non-negotiable and re-verified per unit** (CLAUDE.md "Critical Project Rules"):
   - No Anthropic SDK — LLM calls only via Claude Code CLI subprocess.
   - **Module boundary** — only `orchestrator` imports `sources/briefing/publisher/notifier`. Those 4 units share only `models/` and `_internal/` (both are legitimate shared layers). A refactor must NOT introduce a new cross-unit import.
   - Free APIs only; disclaimer gate intact; Telegram channel separation (public channel ID ≠ operator chat ID) intact; `defusedxml` only; R13 secret hygiene (no secret in logs/errors/raw_metadata/fixtures).
5. **Full local gate green per unit**: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy --strict`, `uv run pytest`, `uv run mkdocs build --strict`. A unit is not Complete until all five pass on the full repo (or the documented targeted scope, matching prior-unit precedent).
6. **Stage Decision: FD = SKIP, NFR = SKIP for every unit** — these are internal refactors. No new domain entity, no new external service/dependency/secret/runtime cost. (Re-state this in each unit's closeout.)
7. **New helper modules get focused unit tests**, but those tests supplement — never replace — the unchanged existing suite.
8. **One unit = one reviewable, independently shippable change** with its own green gate. Do not bundle two units into one commit.

---

## Units, sequencing, and dependencies

| Unit | Title | Domain | Risk | Depends on |
|------|-------|--------|------|------------|
| **u77** | source-adapter shared helpers | `sources/` | Low | — |
| **u78** | filesystem write & archive-layout primitives | `publisher/` + `visuals/` | Low | — |
| **u79** | shared text primitives (UTF-16 + briefing regex) | `_internal/` + `briefing/` | Low | — |
| **u80** | notifier decomposition + TelegramDispatcher base | `notifier/` | Medium | u79 |
| **u81** | reader_format → `_reader_format/` subpackage | `publisher/` | Medium | u78 |
| **u82** | site_index → subpackage | `publisher/` | Medium | u78 |
| **u83** | briefing/pipeline.py decomposition | `briefing/` | High | u79 (soft) |
| **u84** | orchestrator/pipeline.py Stage abstraction | `orchestrator/` | High | u81 (soft) |
| **u85** | unified Validator/Gate protocol + registry | `briefing/` + `publisher/` | Medium | **u84 (HARD)**, u83 (soft) |

> **Review-driven amendments (2026-05-28).** A 10-lens conformance review against the architecture guide was run; all findings verified against source. Material corrections folded into the unit plans: **u77** parse-helpers are NOT one semantic (3 distinct `_parse_float` contracts — do not force-unify; AC relaxed); **u78** atomic-write is 8 sites incl. `og_card.py` (split str/bytes API; `ArchiveLayout`/`write_atomic` home in `_internal/` to dissolve the `visuals→publisher` edge; add an enforced boundary test); **u83** context-block rendering single-homed + a SLAP re-leveling Step 4b added; **u84** `PipelineContext` frozen/inputs-only, exception map as declarative dict, composition-root injection, path-norm DEBT in its own commit; **u85** drop `downgrade`/`is_blocking` unless real, `ValidationResult` is a gating envelope only, **u85→u84 is now HARD**; **u80** dispatch via composition (not an LSP base), `parse_mode` owned; pre-flight test-brittleness audit added to u83/u84.

**Recommended execution order** (three phases):

1. **Foundation (parallelizable, low-risk):** u77, u78, u79. Mechanical extractions that unblock the bigger splits.
2. **Mid-tier module splits:** u80, u81, u82. Each is a single-domain decomposition.
3. **God-module splits + capstone:** u83 → u84 → u85. Largest blast radius; do last, one at a time, gate-green between each.

A unit may start before its soft dependency lands, but the hard dependencies in the table must be Complete first.

---

## Out of scope for the whole wave

- Any product/behavior change, new feature, new data source, or prompt-content change.
- Rewriting test logic (only import-path edits allowed).
- Resolved TECH-DEBT (DEBT-035 redaction-regex and DEBT-060 conclusion-prefix are **already resolved** — do not re-touch `_internal/redaction.py` or `briefing/extract.py` chokepoints for those reasons).
- Performance optimization beyond what falls out of cleaner structure.

---

## Relationship to existing TECH-DEBT

- **Already resolved (do not reopen):** DEBT-035, DEBT-060.
- **May be closed by this wave (verify the entry, then reference it in closeout):** the open entries about (a) `_stage_publish_segments` absolute-vs-relative path normalization → fold into **u84**; (b) duplicated summary-reject regexes between `briefing/pipeline.py::_is_unsafe_summary_candidate` and `briefing/summary_quality.py` → fold into **u79** or note as out-of-scope. The implementer MUST `grep DEBT- docs/TECH-DEBT.md` for the live IDs (numbers drift) before claiming a close.

---

## Closeout discipline (per unit, per AIDLC)

On completing each unit: write `aidlc-docs/construction/uNN-<slug>/code/summary.md`, flip the plan Status → Complete with all Steps `[x]`, update the `aidlc-state.md` unit row + Code-Generation / Build-and-Test lines, prepend a newest-first `audit.md` entry, and write a per-step session log under `docs/sessions/`. FD = SKIP and NFR = SKIP confirmed at closeout.
