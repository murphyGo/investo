# Functional Design Plan: `u150 terminal-markdown-link-containment`

**Date**: 2026-09-02
**Unit**: u150 terminal-markdown-link-containment
**Stage**: Functional Design
**Status**: Approved 2026-09-03; all 7 steps complete and Code Generation Step 0 gate satisfied
**Source**: production incidents `33035060796`, `33146560495`, `33238048642`, and `33344214754`; u112 surface scanner; u144 public-document finalization contract; approved u150 Code Generation plan

## Objective

Freeze the technology-agnostic business rules that turn a broken Markdown link target into one bounded owned-region action without publishing the target or dropping an otherwise usable market segment. The design must preserve u144's generated-to-sealed lifecycle and every non-presentation hard gate.

## Context loaded

- Unit definition and story mapping for US-002, US-003, US-005, US-007, FR-002, FR-003, FR-008, and FR-009.
- NFR-003 reliability, NFR-005 maintainability, NFR-006 testing, and NFR-007/R13 diagnostic secrecy.
- u112's canonical `markdown.href_ellipsis` and `markdown.unmatched_link` detection/repair ownership.
- u144 R8-R12, `PublicDocumentLayout`, owned-region index, one-disposition precedence, bounded fallback, active-survivor fixed point, terminal validation, and sealed consumer contract.
- u98/u110 canonical watchpoint limitation copy and u149's exclusive numeric-containment boundary.
- Current implementation of `_internal.surface_quality`, `_public_document_policy`, and the finalizer region-action loop.

## Fixed boundaries inherited from the approved unit

- No new scanner family, CommonMark parser, URL completion, URL fetch, redirect lookup, or LLM retry.
- Invalid targets, generated Markdown evidence, source payloads, and secrets never enter logs, typed outcomes, fixtures, or public artifacts.
- Header, navigation, diagnostics, disclaimer, required structure, numeric, entity, compliance, seal, and notification-summary defects remain fail-closed.
- Each owned region receives at most one grouped action and one recorded outcome before terminal revalidation.
- Existing canonical limitation text is reused; u150 introduces no new reader-facing fallback copy.

## Plan

- [x] Step 1 — Analyze the unit definition, requirements, u112 scanner contract, u144 functional design, current finalizer behavior, production incident metadata, and the pre-authored Code Generation plan.
- [x] Step 2 — Create this Functional Design plan and record the remaining decisions as explicit questions.
- [x] Step 3 — Collect every answer, validate it for ambiguity or contradiction, and update the Code Generation fixed contracts if an answer changes the current draft.
- [x] Step 4 — Create `business-logic-model.md` with the link-shape action flow, owned-region call graph, one-action lifecycle, and terminal revalidation sequence.
- [x] Step 5 — Create `business-rules.md` with the closed shape/region disposition matrices, protected-region rules, hard-gate precedence, residual diagnostic policy, and production qualification rules.
- [x] Step 6 — Create `domain-entities.md` describing reused and amended typed concepts, invariants, deterministic ordering, redacted outcomes, and no-new-entity decisions.
- [x] Step 7 — Validate the three artifacts against u112/u144/u149, the u150 Code Generation plan, partial PBT opt-in, and strict Markdown; present them for explicit approval before Code Generation.

## Functional Design Questions

Complete every `[Answer]:` tag with one letter. The recommended choices preserve the already-approved u150 scope unless a newly identified ambiguity requires a safer boundary.

### Question 1 — Closed invalid-target action table

How should recoverable closed link shapes be transformed outside protected regions?

A) Adopt the current fixed table: inline link keeps plain label, invalid image keeps escaped plain alt text, autolink disappears, and an incomplete inline fragment keeps its label. The target is never retained or recovered. (Recommended)
B) Replace the entire owned region for every invalid target, even when its visible label is independently recoverable.
C) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

### Question 2 — Invalid reference-style definitions

An invalid definition such as `[ref]: https://broken...` may have `[label][ref]` uses elsewhere. What is the bounded behavior?

A) Delete only the invalid definition line as the current Code Generation table states; unresolved uses remain byte-identical because their target text is no longer present.
B) Treat an invalid reference definition as unrecoverable for its owned region and replace that region with canonical limitation text; do not add cross-region reference lookup. (Recommended)
C) Add a bounded same-region reference lookup that unwraps proven labels, but replace the region when any use is outside that region.
D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B

### Question 3 — Residual unmatched-link fragments

What should happen when `markdown.unmatched_link` remains after the one canonical repair pass in a first-viewport, required section-body, or watchpoint region?

A) Replace only that owned region body with its existing canonical limitation text while preserving the required heading and sibling regions. (Recommended)
B) Run a broader delimiter-stripping pass over the region before considering replacement.
C) Keep the existing whole-segment `trust_blocked` outcome.
D) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

### Question 4 — Simultaneous hard-defect precedence

How should a document containing both a link presentation defect and a numeric/entity/compliance/disclaimer/structure/notification-summary defect be evaluated?

A) Perform the single bounded presentation action in the existing containment phase, then run the unchanged read-only terminal validators; any non-presentation defect still blocks with its original code, and the link action cannot mask it. (Recommended)
B) Add an earlier hard-gate pre-scan and skip all link containment whenever that scan finds a non-presentation defect.
C) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

### Question 5 — Residual diagnostic contract

If actionable surface issues remain after the one allowed region action, which codes may leave the finalizer?

A) Sorted unique `document.fallback_exhausted` plus the exact residual scanner codes, with no evidence text, URL, Markdown, payload, or secret. (Recommended)
B) Exact residual scanner codes only, without the generic fallback marker.
C) `document.fallback_exhausted` only, preserving the current opaque behavior.
D) Other (please describe after the `[Answer]:` tag below)

[Answer]: A

## Validated Answer Record

The user approved the recommended set `A / B / A / A / A` on 2026-09-02. Every answer is valid, mutually consistent, and within the approved u150 boundary.

- Q1 freezes the exact label/alt/autolink/incomplete-fragment outputs and forbids target recovery.
- Q2 supersedes the draft Code Generation behavior that rewrote an invalid reference definition to an empty line. A reference definition is an unrecoverable closed shape: the canonical scanner identifies that already-matched shape before mutation, and policy selects one safe action for its owning region. There is no cross-region definition/use lookup and no repair-then-replace sequence.
- Q3 replaces only the affected owned first-viewport, section-body, or watchpoint body for residual unmatched fragments; required headings and sibling regions survive.
- Q4 retains the current presentation-action phase followed by unchanged terminal hard gates, so containment cannot mask a non-presentation defect.
- Q5 emits sorted unique `document.fallback_exhausted` plus exact residual scanner codes and no evidence-bearing field.

For the Q2 override, ordinary first-viewport and required section-body regions use their existing canonical limitation replacement; watchpoints use their existing limitation replacement; optional augmentation retains its existing closed lookup; and header, navigation, anchor-table, diagnostics, and disclaimer regions remain fail-closed. This is a bounded shape-aware selection inside the canonical scanner/policy path, not a new scanner family or Markdown parser.

## Planned Functional Design Artifacts

- `aidlc-docs/construction/u150-terminal-markdown-link-containment/functional-design/business-logic-model.md`
- `aidlc-docs/construction/u150-terminal-markdown-link-containment/functional-design/business-rules.md`
- `aidlc-docs/construction/u150-terminal-markdown-link-containment/functional-design/domain-entities.md`

No frontend/UI artifact applies. The unit changes deterministic publisher behavior only.

## Step 7 Validation Record

Completed 2026-09-03 with no unresolved blocking contradiction.

- The approved `A / B / A / A / A` answers trace to all three artifacts: exact visible transformations, unrecoverable reference-region action, direct residual replacement, unchanged simultaneous hard gates, and bounded residual codes.
- The u144 extension is exhaustive across all 16 `PublicBlockKind` values and all four policy columns: recoverable closed, recoverable incomplete, reference definition, and unmatched residual.
- The earlier coarse “single reference override” wording was removed. Both link codes now resolve from the complete `(issue_code, block_kind, link_shape)` input, while non-link policy remains unchanged.
- Scanner cardinality is explicit: closed invalid targets emit per occurrence; unmatched syntax remains line-level and is recoverable only when every unmatched construct is canonically covered and a read-only trial closes the predicate.
- u149 remains exclusive owner of domestic numeric containment and `finalized_degraded`; successful link containment remains ordinary `finalized`.
- The Partial PBT opt-in is satisfied by pure transform properties only. Lossy invalid-target removal has no round-trip requirement and no stateful PBT is added.
- Security Baseline remains declined, while the existing NFR-007/R13 no-target/no-evidence disclosure boundary is preserved as a normal project requirement.
- No new dependency, source, secret, network call, persistence schema, public DTO, reader-facing fallback copy, segment state, or infrastructure component is introduced.
