# Code Generation Plan: `u150 terminal-markdown-link-containment`

**Date**: 2026-09-02
**Unit**: u150 terminal-markdown-link-containment
**Stage**: Code Generation
**Status**: Design-gated backlog — Functional Design required before implementation
**Source**: Scheduled daily-briefing runs `32784998097`, `33035060796`, `33146560495`, `33238048642`, `33344214754`, and successful comparison run `33457514796`; target dates 2026-08-24/26/27/28/31; `archive/_meta/quality_history.jsonl`
**Estimated Effort**: ~12-18 h across seven bounded steps plus production closeout
**Dependencies**:
- u100 surface-quality-gate and u112 reader-markdown-polish-gate-v2 — complete; retain their canonical `SurfaceQualityIssue` detection and issue codes.
- u144 public-document-finalization-contract — complete; retain `PublicDocumentLayout`, owned regions, grouped one-disposition containment, survivor fixed point, typed outcomes, seal, staged artifacts, and partial exit 2.
- u98/u110 watchpoint render/fallback — complete; reuse `PUBLIC_WATCHPOINT_LIMITED_TEXT`.
- u149 numeric-claim-local-containment-and-minimal-fallback — complete through production Step 7b on 2026-09-02; daily runs `33543213131` and `33547421276` clear this prerequisite.

---

## Problem Statement

The current finalizer detects unsafe Markdown targets correctly but still turns a presentation-only link defect into whole-segment absence.

Production evidence from the last ten scheduled runs ending on 2026-09-01:

| Run | Target date | Segment outcome relevant to this unit |
| --- | --- | --- |
| `32784998097` | 2026-08-24 | US `trust_blocked`: `document.fallback_exhausted` |
| `33035060796` | 2026-08-26 | US `document.fallback_exhausted`; crypto `markdown.href_ellipsis` |
| `33146560495` | 2026-08-27 | crypto `markdown.href_ellipsis` |
| `33238048642` | 2026-08-28 | domestic `markdown.unmatched_link` |
| `33344214754` | 2026-08-28 | crypto `markdown.href_ellipsis` |
| `33457514796` | 2026-08-31 | all three finalized; domestic numeric degradation contained normally |

Every failed run still published its valid subset, sent Telegram, dispatched Pages, and exited 2. The u63/u94/u144 partial contract therefore worked, but four runs lost an otherwise generated segment to a Markdown presentation defect. The final successful run shows that generation is intermittent; it does not close the repeated failure mode.

The implementation gap is concrete:

1. `_internal.surface_quality` detects `markdown.href_ellipsis` in closed inline/image/reference/autolink targets and `markdown.unmatched_link` in malformed fragments.
2. `repair_surface_artifacts()` unwraps only a recoverable unmatched fragment in the document first viewport. It has no target-specific rewrite for a closed URL containing `...` or `…`, and does not repair required section-body link fragments.
3. u144's policy maps both link codes in required section bodies and watchpoints to `block_segment`.
4. When a policy says `repair` but the transform leaves residue, `_repair_projected_draft()` collapses the reason to `document.fallback_exhausted`, so the log cannot identify the residual surface code.

## Goal

Make link-target presentation defects obey u144's owned-region containment contract:

1. never publish, guess, complete, fetch, or log an invalid link target;
2. preserve only proven reader-visible label/alt text when the link shape is recoverable;
3. replace an unrecoverable required reader region with existing canonical limitation text rather than removing the segment;
4. preserve every numeric, entity, compliance, disclaimer, required-structure, security, and notification-summary hard gate;
5. expose bounded residual issue codes without evidence text so future production failures are diagnosable.

## Existing Coverage / Deduplication

- **u100/u112 own detection.** Keep `_INLINE_LINK_RE`, `_REFERENCE_LINK_RE`, `_AUTOLINK_RE`, `_RECOVERABLE_LINK_FRAGMENT_RE`, `_href_ellipsis_evidence()`, and `_looks_like_unmatched_link()` with the canonical scanner. Do not add a second scan or another Markdown issue family.
- **u144 owns finalization.** Extend `_public_document_policy.py` and the existing `_repair_projected_draft()` region loop. Do not add a pre-finalizer rewrite, a second finalizer, post-seal mutation, or another survivor loop.
- **u98/u110 own watchpoints.** Reuse the typed watchpoint region and existing limitation copy. Do not edit watchpoint signal synthesis or matrix parsing.
- **u149 owns numeric containment.** The u150 eligibility set is surface-link codes only. Its transform cannot run as a fallback for `numeric.anchor_assertion`, entity, compliance, disclaimer, summary, required-structure, or notification-summary findings.
- **u63/u94 own content-partial publishing.** True hard blocks still publish valid siblings and exit 2 after Pages; u150 changes only link-only presentation outcomes.

## Scope Boundary

In scope:

- Pure, target-specific transforms for existing link shapes outside protected regions.
- A fixed two-code/owned-region disposition amendment in the existing u144 table.
- Canonical first-viewport, section-body, and watchpoint replacement for unrecoverable fragments.
- Residual issue-code propagation beside `document.fallback_exhausted` with R13-bounded fields.
- Real-run metadata fixtures, synthetic private Markdown fixtures, finalizer composition tests, PBT, and exact-date production qualification.

Out of scope:

- A general CommonMark parser, HTML sanitizer, URL resolver, network validation, or URL completion.
- Logging or archiving the blocked generated Markdown, raw link target, evidence string, or source URL.
- Changing valid-link rendering, citation counts, source attribution, visual supplement links, Telegram URL construction, or Pages routing.
- Relaxing numeric/entity/compliance/disclaimer/summary/structure/security gates.
- LLM rewrite/retry, prompt changes, new dependencies, sources, secrets, environment flags, or historical archive backfill.

## Stage Decision

### Functional Design — REQUIRED

u150 amends u144 R8's fixed required-region disposition and changes a public failure outcome from whole-segment `trust_blocked` to bounded region repair/replacement. Functional Design must freeze the link-shape action table, owned-region matrix, one-action semantics, simultaneous-hard-defect precedence, and residual diagnostic contract before code changes.

### NFR Requirements — SKIP

The unit reuses NFR-003 reliability, NFR-005 maintainability, NFR-006 testing, and NFR-007/R13 diagnostics. It adds no dependency, source, network call, secret, cost, retry, timeout, storage family, or public operator surface.

### PBT Partial Extension

PBT-03/PBT-07/PBT-08/PBT-09 apply to the pure transform: generated valid Markdown link lines remain byte-identical; transformed output contains no scanner-owned invalid target; repeated transformation is byte-idempotent; strategies generate domain-valid inline/image/autolink/reference/incomplete-link shapes and retain shrinking/reproducibility. PBT-02 round-trip is N/A because invalid-target removal is intentionally lossy. Stateful PBT is outside the project's partial opt-in.

## Fixed Contracts

### Contract 1 — Canonical detection and closed rewrite shapes

`investo._internal.surface_quality` remains the sole scanner/repair owner. Add one pure helper consumed by `repair_surface_artifacts()` with these exact outputs when the target contains `...` or `…`:

| Input shape | Output |
| --- | --- |
| `[label](invalid-target)` | `label` |
| `![alt](invalid-target)` | escaped plain `alt` text |
| `<invalid-target>` | empty string |
| `[reference-id]: invalid-target` | empty line |
| `[label](https://incomplete` matched by the existing recoverable-fragment regex | `label` |

Valid targets, code spans, fenced code, tables, diagnostics details, and disclaimer/footer regions remain byte-identical. The helper never returns or records an invalid target.

### Contract 2 — Owned-region disposition amendment

The u144 table retains one disposition per `(issue_code, PublicBlockKind)`:

| Issue | First viewport | Section body | Watchpoints | Optional augmentation | Header/navigation/diagnostics/disclaimer |
| --- | --- | --- | --- | --- | --- |
| `markdown.href_ellipsis` | `repair` | `repair` | `replace_block` | existing closed lookup | `block_segment` |
| `markdown.unmatched_link` residual | `replace_block` | `replace_block` | `replace_block` | existing closed lookup | `block_segment` |

Section replacement preserves the required H2 marker through the current region-body replacement API. Watchpoint replacement preserves `## ⑥` and uses `PUBLIC_WATCHPOINT_LIMITED_TEXT`. No new fallback string is introduced.

### Contract 3 — One action and terminal closure

Each owned region receives one grouped action and one `PublicBlockOutcome`. Repairs use original region bytes, reindex once, and must close every link finding covered by the action. Replacement is recorded as replacement, not repair. Any residual actionable issue after the one pass remains fail-closed; no second string search or post-seal edit occurs.

### Contract 4 — Bounded residual diagnostics

When residual actionable surface findings remain, `_SegmentTrustBlockedError.issue_codes` contains sorted unique `document.fallback_exhausted` plus the residual scanner codes. Logs, workflow summary, and typed finalization outcomes may expose only target date, segment, phase, and these codes. Evidence strings, line contents, URLs, Markdown, source payloads, and secrets are forbidden.

### Contract 5 — Hard-gate precedence

Link containment is a presentation phase action, not a general fallback. A document that also fails numeric, entity, compliance, disclaimer, summary, required-structure, seal, or notification-summary validation retains the existing hard-block outcome. Domestic numeric handling remains exclusively u149; US/crypto numeric behavior remains unchanged.

## Implementation Steps

- [ ] Step 0 — Author and independently review Functional Design. Freeze the link-shape action table, region matrix, simultaneous-hard-defect precedence, residual diagnostics, call graph, and PBT properties. Stop before code generation until the design is approved.
- [ ] Step 1 — Add bounded incident characterization: run metadata for `32784998097`, `33035060796`, `33146560495`, `33238048642`, `33344214754`, and `33457514796`; private synthetic Markdown fixtures for each link shape; current-policy tests proving the pre-u150 segment-block/fallback outcomes.
- [ ] Step 2 — Implement the canonical target-specific pure transform in `_internal.surface_quality`, integrate it into `repair_surface_artifacts()`, and add example plus Hypothesis tests for valid-link stability, invalid-target absence, idempotence, protected-region byte stability, Unicode labels, and scanner/repair closure.
- [ ] Step 3 — Amend `_public_document_policy.py` and `public_document.py` to apply the fixed region matrix, reuse existing safe fallbacks, preserve one outcome per region, and prove required H2/sibling-region/supplement/seal stability.
- [ ] Step 4 — Propagate bounded residual codes beside `document.fallback_exhausted`; add R13 negative tests proving evidence, URLs, Markdown, payloads, and secrets never reach logs, workflow summary, or typed outcomes.
- [ ] Step 5 — Add finalizer/orchestrator/integration regressions for link-only 3/3 success, simultaneous hard-gate blocking, US/crypto numeric non-regression, partial exit-2 preservation for genuine blocks, Telegram summary inputs, and Pages sequencing.
- [ ] Step 6 — Run scoped and full quality gates; update u144 supersession notes, DESIGN/component methods, state/audit/code summary, and cross-check. After local approval, replay 2026-08-27 and 2026-08-28, verify three archive URLs, Telegram, pipeline exit 0, chained Pages success, live HTTP 200, invalid-target absence, and record workflow/commit/Page IDs.

## Acceptance Criteria

1. AC-150.1: The canonical scanner remains the sole detector; no second link regex family or Markdown parser is added outside `_internal.surface_quality`.
2. AC-150.2: Every closed invalid-target shape in Contract 1 produces the exact fixed output and exposes no target substring.
3. AC-150.3: Valid links and every protected region are byte-identical after repair.
4. AC-150.4: The transform is deterministic and byte-idempotent for arbitrary domain-valid generated link lines.
5. AC-150.5: `markdown.href_ellipsis` in first viewport or section body seals after region repair; visible label/alt text is preserved and the invalid target is absent.
6. AC-150.6: Residual `markdown.unmatched_link` replaces only the owned first-viewport, section-body, or watchpoint body; required headings and siblings remain.
7. AC-150.7: Optional augmentation behavior remains the exact u144 lookup; omitted assets are not promoted and marker-shell contracts remain intact.
8. AC-150.8: Header/navigation/diagnostics/disclaimer link corruption still blocks the segment as an invariant/trust failure.
9. AC-150.9: Link-only findings cannot produce `trust_blocked`; simultaneous non-presentation hard defects retain their original block codes and no link repair masks them.
10. AC-150.10: Residual failure contains `document.fallback_exhausted` plus exact sorted surface codes and no evidence text, line, URL, Markdown, payload, or secret.
11. AC-150.11: u149 domestic numeric containment and US/crypto numeric fail-close behavior remain unchanged.
12. AC-150.12: Three sealed documents produce complete status, Telegram, Pages dispatch, and exit 0; genuine one-segment hard block still commits valid siblings, dispatches Pages, and exits 2.
13. AC-150.13: Example and partial-mode PBT run in normal pytest/CI with shrinking and reproducible failure output.
14. AC-150.14: Exact-date production replays for 2026-08-27 and 2026-08-28 complete 3/3, send Telegram, finish Pages, return live HTTP 200, and publish no invalid targets.

## Tests / Validation

Expected test owners:

- `tests/unit/internal/test_surface_quality.py`
- `tests/unit/internal/test_surface_quality_properties.py`
- `tests/unit/publisher/test_public_document_policy_u144.py`
- `tests/unit/publisher/test_public_document_containment_u144.py`
- `tests/unit/publisher/test_public_document_finalization_u144.py`
- `tests/unit/publisher/test_public_document_terminal_validation_u144.py`
- `tests/unit/orchestrator/test_run_pipeline.py`
- `tests/integration/test_pipeline.py`

Local gate:

```bash
uv lock --check
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest -q
uv run python scripts/check_no_anthropic_sdk.py
uv run python scripts/check_no_paid_apis.py
uv run --extra docs mkdocs build --strict
git diff --check
```

Production closeout occurs only after the now-complete u149 Step 7b evidence remains documented and the u150 implementation is approved.

## Non-Goals

- No URL recovery, network validation, redirect following, guessed completion, or source lookup.
- No general Markdown AST/parser dependency.
- No LLM rewrite, retry, prompt change, or new generated-content loop.
- No new public fallback wording or operator channel.
- No change to numeric/entity/compliance/disclaimer/summary/structure/security thresholds.
- No historical archive rewrite outside the explicitly approved exact-date production replays.
