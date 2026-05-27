# Code Generation Plan: `u85 unified-validator-gate-protocol`

**Date**: 2026-05-28
**Unit**: u85 unified-validator-gate-protocol
**Stage**: Code Generation (refactor)
**Status**: Planned — not started (0/5 steps)
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

### Step 1 — define the contract `[ ]`
> **Scope `ValidationResult` as a thin GATING ENVELOPE, not a payload-unifier (review 2026-05-28, guide §9.4/§9.5).** The ~16 checks have genuinely divergent inputs (markdown vs `NormalizedItem`s vs `log_path`+`price_lookup` vs `BundleContext`), outputs, and side-effect profiles (`compute_accuracy` does file I/O; `leak_guard.scan` is pure). Unifying their *payloads* would be the wrong abstraction. The protocol unifies ONLY the *gating role* (severity + ordering). Consumers needing structured detail keep calling the underlying check directly — **never reconstruct per-check structured data out of the generic `findings` tuple** (that is the wrong-abstraction trap maturing; if adapters start accreting special-cases, re-inline per guide §9.5).
- [ ] Add `ValidationResult` (`findings: tuple[...]`, `message: str`, severity) and a `Validator` protocol in the shared layer. Default home `_internal/` (a behavioral contract, not a persisted/domain entity — the plan's own Stage Decision); record the choice.
- [ ] **Severity = `pass`/`warn`/`block` only.** DROP `downgrade` unless a concrete existing check produces it (review 2026-05-28, guide §1 YAGNI / §9.6 Rule-of-Three — a 4th level with zero real cases is speculative surface). If a real downgrade case exists, define what consumes it and pin it in AC-85.3.
- [ ] **DROP `is_blocking` from the protocol** (review 2026-05-28, guide §3 ISP / §1 DRY): it duplicates the `block` severity already in `ValidationResult` and forces every warn-only adapter to declare policy it doesn't own. Let the registry derive blocking from severity + ordering. Keep a static flag only if fail-fast-before-running is truly needed, and document why both exist.
- **Acceptance**: types compile under mypy --strict; severity is 3-valued unless a real downgrade case is documented; no `is_blocking` on the protocol (or justified); no call site changed yet.

### Step 2 — wrap briefing checks `[ ]`
- [ ] Add adapters for the briefing checks (citation_cardinality, date_corruption, leak_guard, numeric_verify, summary_quality, accuracy where invoked in-pipeline), each calling the unchanged function and mapping its result to `ValidationResult`.
- **Acceptance**: adapters' results equal the underlying checks for fixtures; briefing tests green unchanged.

### Step 3 — wrap publisher gates `[ ]`
- [ ] Add adapters for compliance_language, cross_segment_lint, anchor_assertion_gate, cross_market_cause_map, quality_consistency. `block`-level adapters preserve the existing raise/`*Error` at the publish boundary.
- **Acceptance**: blocking gates still raise the same exceptions on the same inputs; publisher tests green unchanged.

### Step 4 — registry + call-site swap `[ ]`
- [ ] Add a registry that holds validators in the **current execution order** and runs them, aggregating results (and raising on the first `block` exactly where the pipeline raises today).
- [ ] Swap the orchestrator/briefing ad-hoc sequence to call the registry. Preserve order and the exact point where blocking occurs.
- **Acceptance**: full pipeline + integration tests green unchanged; the order and blocking behavior are identical.

### Step 5 — full gate `[ ]`
- [ ] ruff / ruff-format / mypy --strict / pytest (full) / mkdocs build --strict.
- **Acceptance**: full gate green.

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
