# Code Generation Plan: `u85 unified-validator-gate-protocol`

**Date**: 2026-05-28
**Unit**: u85 unified-validator-gate-protocol
**Stage**: Code Generation (refactor)
**Status**: In progress — 5/5 steps done; descoped per wrong-abstraction stop (see Step 3/4 notes)
**Source**: 2026-05-28 abstraction review — briefing checks + publisher gates
**Estimated Effort**: ~5-6 h
**Dependencies**: **u84 — HARD** (both rewrite the orchestrator's blocking-gate call sites; if u85 swaps call sites against the old inline cascade and u84 then rewrites that cascade, they conflict — u85 MUST land strictly after u84 closes; review 2026-05-28). **u83 — soft.**
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit. This is the **capstone**: additive, wrapping existing checks without changing their logic.

---

## Problem Statement

The codebase has ~11 briefing checks and ~5 publisher gates, each an ad-hoc function with a different shape and no common contract:

- **briefing** — `accuracy.compute_accuracy`, `citation_cardinality.detect_cardinality_warnings`, `date_corruption.find_corrupt_date_tokens`, `leak_guard.scan`, `numeric_verify.verify_core_facts`, `summary_quality.validate_first_viewport_summary`, … Outputs vary: aggregate report / tuple of warnings / single hit-or-None / comparison report / pass-or-raise.
- **publisher** — `compliance_language.scan_compliance`, `cross_segment_lint.lint_*`, `anchor_assertion_gate.gate_body_assertions`, `cross_market_cause_map.evaluate_cause_map`, `quality_consistency` (publish-boundary gate).

They are called ad-hoc in sequence in the orchestrator/briefing pipeline with no registry, no uniform severity, and no composition. Adding/reordering a check means editing call sites; there is no single place that says "these are the gates, in this order, with these block/warn semantics."

---

## Goal

Define one **`Validator` protocol** + a **`ValidationResult`** (uniform severity: `pass` / `warn` / `downgrade` / `block`) + a **registry** that runs validators in a declared order and aggregates results. Wrap each existing check as a **thin adapter** that calls the unchanged underlying function and maps its output to `ValidationResult`. The orchestrator/briefing pipeline calls the registry instead of the ad-hoc sequence.

**Additive and behavior-preserving:** keep every existing check function; the adapter layer only standardizes invocation and result shape. The same gates fire in the same order with the same block/warn outcomes.

---

## Existing Coverage / Deduplication

- Do NOT rewrite any check's internal logic. The adapter calls the existing function and translates the result. (A future unit may then simplify a check now that it has a uniform contract — out of scope here.)
- The publish-boundary blocking gates (compliance P0 → `ComplianceLanguageError`, quality-consistency → `QualityConsistencyError`, disclaimer verify) must keep raising/blocking exactly as today. The registry's `block` level maps to the existing raise; do not soften a blocking gate to a warning.
- Where briefing checks and publisher gates live in different units, the protocol type itself goes in the **shared layer** (`models/` or `_internal/`) so both sides can implement it without a cross-unit import. The registry instances live on each side (orchestrator owns the publish-boundary registry; briefing owns its in-pipeline checks) — do not create a briefing→publisher or publisher→briefing import.

---

## Scope Boundary

In scope:
- `ValidationResult` + `Validator` protocol in the shared layer.
- Thin adapters wrapping the existing briefing checks and publisher gates.
- A registry that runs them in the current order; orchestrator/briefing call the registry.

Out of scope:
- Changing any check's detection logic, thresholds, or messages.
- Changing which gates block vs warn.
- Merging/deleting checks (a follow-up unit may, once the contract exists).

---

## Stage Decision

- **Functional Design — SKIP.** Introduces an internal protocol over existing checks; no new domain entity (a `ValidationResult` value type is an internal contract, not a persisted/domain entity).
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. R5 channel separation, disclaimer gate, R13, and compliance blocking are preserved.

---

## Implementation Steps

### Step 1 — define the contract `[x]`
> **Scope `ValidationResult` as a thin GATING ENVELOPE, not a payload-unifier (review 2026-05-28, guide §9.4/§9.5).** The ~16 checks have genuinely divergent inputs (markdown vs `NormalizedItem`s vs `log_path`+`price_lookup` vs `BundleContext`), outputs, and side-effect profiles (`compute_accuracy` does file I/O; `leak_guard.scan` is pure). Unifying their *payloads* would be the wrong abstraction. The protocol unifies ONLY the *gating role* (severity + ordering). Consumers needing structured detail keep calling the underlying check directly — **never reconstruct per-check structured data out of the generic `findings` tuple** (that is the wrong-abstraction trap maturing; if adapters start accreting special-cases, re-inline per guide §9.5).
- [x] Add `ValidationResult` (`findings: tuple[...]`, `message: str`, severity) and a `Validator` protocol in the shared layer. Home: `src/investo/_internal/validation.py` (recorded in module docstring — behavioural contract, not domain entity).
- [x] **Severity = `pass`/`warn`/`block` only.** `downgrade` DROPPED — no existing Investo gate produces a distinct downgrade outcome.
- [x] **`is_blocking` DROPPED from the protocol.** Registry derives blocking from the `block` severity; no static flag kept (no fail-fast-before-running need exists).
- **Acceptance**: types compile under mypy --strict; severity is 3-valued unless a real downgrade case is documented; no `is_blocking` on the protocol (or justified); no call site changed yet.

### Step 2 — wrap briefing checks `[x]`
- [x] Added `briefing/validators.py` with `LeakGuardValidator` + `build_post_validation_registry`. **DESCOPED to the genuinely in-pipeline gate (leak_guard only):** of the listed briefing checks, ONLY `leak_guard.scan` is actually invoked inside `briefing/pipeline.py` (`_finalize_briefing`). citation_cardinality / date_corruption / numeric_verify / summary_quality / accuracy are NOT called in the briefing pipeline — they run at the orchestrator publish boundary or in publisher site-index rendering, with divergent inputs. Wrapping functions the briefing pipeline does not call would add dead surface (guide §1 YAGNI). `summary_quality` IS wrapped — on the orchestrator side, where it actually fires (Step 3).
- **Acceptance**: adapter result equals `leak_guard.scan` for clean/leaky fixtures; briefing tests green unchanged.

### Step 3 — wrap publisher gates `[x]` (descoped to the genuinely-alike boundary trio)
- [x] Added `orchestrator/validators.py` with `FirstViewportSummaryValidator` (raise-through `SummaryQualityError`), `DisclaimerFooterValidator`, `ShortDisclaimerValidator` + `build_publish_boundary_registry`. These are the three gates that run as a **flat, ordered, per-segment sequence at the actual orchestrator publish boundary** (`_stage_publish_segments`).
- [x] **STOPPED on compliance_language / cross_segment_lint / anchor_assertion_gate / cross_market_cause_map (wrong-abstraction signal, plan's descope permission + guide §9.5).** These gates do NOT run as a separable orchestrator-level sequence — they are interleaved BETWEEN the str→str markdown transforms deep inside `publisher/segment_reader_format.py`, with load-bearing ordering (`scan_compliance` runs once before and once after `render_watchpoint_matrix`). Lifting them into a flat registry would require reordering that mutation pipeline = a behaviour change Wave 14 forbids. They stay where they are. `quality_consistency` (`_enforce_quality_consistency_gate`) is a single standalone gate already at its own clean boundary point with bespoke rollback semantics; wrapping a 1-element registry around it adds indirection with no ordering benefit, so it is left as-is.
- **Acceptance**: blocking gates still raise the same exceptions on the same inputs; publisher + orchestrator tests green unchanged.

### Step 4 — registry + call-site swap `[x]`
- [x] Registry (`ValidationRegistry` in `_internal/validation.py`) holds validators in the **current execution order**, runs them, short-circuits on the first `block`, and lets a raise-through adapter's exception propagate unchanged.
- [x] Swapped two call sites: (1) `briefing/pipeline.py::_finalize_briefing` → `build_post_validation_registry` (same `BriefingGenerationError`, same message); (2) `orchestrator/pipeline.py::_stage_publish_segments` per-segment trio → `build_publish_boundary_registry` (same order, same `SummaryQualityError` / `PublisherDisclaimerError`, same log text). One mechanical test fix: `test_run_pipeline.py` now patches `verify_disclaimer` on `orchestrator.validators` (its new resolution site).
- **Acceptance**: full pipeline + integration tests green unchanged; order and blocking behaviour identical.

### Step 5 — full gate `[x]`
- [x] ruff check ✓ / ruff format --check ✓ / mypy --strict src ✓ (193 files) / pytest ✓ (2844) / mkdocs build --strict ✓.

---

## Acceptance Criteria

- **AC-85.1** — One `Validator` protocol + `ValidationResult` in the shared layer; both briefing and publisher implement it without a cross-unit import.
- **AC-85.2** — Every existing check is wrapped by a thin adapter; no check's internal logic, threshold, or message changed.
- **AC-85.3** — The same gates fire in the same order with identical block/warn/raise outcomes for all inputs (proven by unchanged tests).
- **AC-85.4** — Publish-boundary blocking gates (compliance P0, quality-consistency, disclaimer) still raise their existing exceptions; mypy --strict clean.

---

## Tests / Validation

- All existing briefing + publisher + orchestrator + integration tests — stay green **unchanged**.
- New: `tests/unit/.../test_validation_registry.py` (severity mapping, ordering, block-raises) and per-adapter equivalence tests.
- Gate: full `pytest` mandatory; mkdocs build --strict.

---

## Non-Goals

- Changing detection logic, thresholds, messages, or block/warn classification.
- Merging or deleting checks (a possible follow-up once the contract exists).
- Cross-unit imports between briefing and publisher.
