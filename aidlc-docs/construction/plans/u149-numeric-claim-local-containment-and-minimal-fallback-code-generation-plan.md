# Code Generation Plan: `u149 numeric-claim-local-containment-and-minimal-fallback`

**Date**: 2026-08-05
**Unit**: u149 numeric-claim-local-containment-and-minimal-fallback
**Stage**: Code Generation
**Status**: Design-gated backlog — Functional Design and NFR Requirements required before implementation
**Source**: 2026-08-04 domestic-segment finalization failure; GitHub Actions run `30958850155`; u148 incident/ingress analysis
**Estimated Effort**: ~18-26 h across eight bounded steps
**Dependencies**:
- u148 domestic-price-public-trust-projection (Backlog; must complete first) — rejected domestic price rows cannot be repair inputs.
- u130 domestic-anchor-level-claim-quarantine-v2 (Complete) — sole domestic level/move claim detector and symbol-consistency owner.
- u144 public-document-finalization-contract (Complete) — sole lifecycle, region ownership, terminal gates, seal, staged artifacts, notifier DTO, survivor fixed point, and partial-publication contract.
- u63/u94 partial publication (Complete) — true generation absence and non-degradable trust blocks remain partial/exit 2.

Planned design artifacts:

- `aidlc-docs/construction/u149-numeric-claim-local-containment-and-minimal-fallback/functional-design/`
- `aidlc-docs/construction/u149-numeric-claim-local-containment-and-minimal-fallback/nfr-requirements/`

---

## Problem Statement

u130 correctly detects a precise domestic core-symbol claim when the corresponding canonical anchor is absent. Its prose path can rewrite an isolated sentence, but structural Markdown (`#`, table rows, HTML, fenced blocks) is scan-only and remains a blocking finding.

u144 currently converts that one local finding into whole-segment absence at two points:

1. `segment_reader_format.apply_reader_format_to_segments()` raises `NumericAnchorReconciliationError` before `PublicDocumentLayout.reindex()` can assign the claim to an owned region. `_assemble_phase_one_reader_draft()` immediately maps the exception to `_SegmentTrustBlockedError(issue_codes=("numeric.anchor_assertion",))`.
2. `_validate_repaired_draft()` runs the read-only numeric scan first and removes the segment if any finding survives.

For the 2026-08-04 run this behavior discarded the complete domestic six-section briefing while the US and crypto segments were sealed and published. The pipeline correctly reported partial and exited 2, but the blast radius was larger than the defect: one unsupported local numeric assertion made the whole domestic segment unavailable.

This is not a request to weaken the numeric trust gate. Unsupported exact claims must still never ship. The missing capability is deterministic containment: locate the finding after layout ownership exists, remove or replace the smallest safe public unit, and fall back once to a no-LLM minimal domestic document if local containment cannot prove safety.

There is an additional masking risk. The current terminal validator short-circuits on numeric findings before entity, compliance, disclaimer, summary, and structure checks. A naive minimal fallback could replace the original draft and hide a simultaneous P0 compliance or entity contradiction. Eligibility therefore requires collecting every original hard-gate result first; numeric fallback is permitted only when numeric assertion is the sole hard defect family.

## Goal

Keep the numeric assertion gate fail-closed for public bytes while changing its domestic failure radius from whole segment to the smallest deterministically owned claim, row, subtree, or region. If and only if the original repaired layout has no non-numeric hard defect and local containment leaves numeric residue, run one no-LLM minimal-segment attempt through the same generated-to-sealed lifecycle.

A safely sealed degraded segment remains a published document. Three expected documents in `finalized` or `finalized_degraded` state mean content-complete, pipeline exit 0, Telegram delivery, and Pages dispatch. `generation_absent`, a non-numeric hard defect, or exhaustion of the one minimal attempt preserves the existing partial/exit-2 behavior.

## Existing Coverage / Deduplication

- **u130 owns detection.** Extend `AnchorAssertionFinding` with deterministic location/kind metadata, but reuse its aliases, magnitude rules, level/move distinction, symbol sweep, and idempotent prose callout. No second scanner.
- **u144 owns finalization.** Reuse `finalize_public_bundle()`, `PublicDocumentLayout`, exhaustive `RegionSpec`/`PublicRegionExpectation`, region dispositions, public projection, terminal validators, SHA-256 seal, staged-artifact transaction, notification DTO, and survivor fixed point. Do not create a second finalizer or mutate post-seal bytes.
- **u100/u108/u112 own surface detection/projection/repair.** Numeric containment may use the same owned-region execution framework but must not add numeric codes to the surface scanner or duplicate public-language policy.
- **u109/u148 own input trust.** The finalizer receives only projected public items. It never reclassifies raw domestic values or uses a quarantined value as a correction candidate. u149 preserves u109 AC-1.3 (a safe degraded segment may publish) and amends AC-1.4 only from segment-level rejection to unsafe-claim rejection; the public exact claim still fails closed.
- **u63/u94 own true partial publication.** This unit narrows only a domestic numeric-only defect; generation absence and all other non-degradable trust failures retain their current semantics.

## Scope Boundary

In scope:

- Location-aware numeric findings and exact E3 region ownership.
- Numeric-only pre-seal hard-gate aggregation without changing terminal gate truth.
- Deterministic claim/row/H3/region containment before terminal validation.
- A single no-LLM six-section minimal-segment attempt through the same u144 lifecycle.
- `finalized_degraded` segment outcome, completeness/exit/Pages/Telegram integration, and bounded operator/quality diagnostics.
- Incident regressions and exact-date production closeout for 2026-08-03 and 2026-08-04.

Out of scope:

- Relaxing numeric truth, u109 bands, u130 detection, or canonical-anchor availability.
- Hiding or degrading entity, compliance, disclaimer, target-date, required-structure, security, or notification-summary failures.
- Arbitrary token substitution, LLM rewrite/retry, network lookup, or inference of a missing price.
- A general CommonMark AST, generic validator registry rewrite, or US/crypto trust-policy change.
- Historical archive backfill.

## Stage Decision

### Functional Design — REQUIRED

u149 changes binding u109 AC-1.4 and u144 behavior: numeric-only structural claims currently become `trust_blocked`; the new contract introduces local action ownership, one minimal-attempt state, `finalized_degraded`, and complete-vs-partial delivery semantics. The design must explicitly amend u109 AC-1.4 plus the numeric-only portions of u144 R9/AC-144.7 while preserving every other hard-gate and lifecycle invariant.

### NFR Requirements — REQUIRED

The unit must pin determinism, idempotence, bounded one-attempt runtime, no I/O/LLM/env/clock in finalization, exact-byte isolation outside the target, redacted diagnostics, no post-seal mutation, artifact non-promotion, and workflow visibility. These are new measurable reliability/security requirements.

### NFR Design — SKIP candidate, decide in Step 0

Prefer SKIP if the design proves the implementation is entirely inside the existing u144 phase/region/seal architecture and introduces no new infrastructure. If Step 0 requires a new lifecycle phase, external store, or async boundary, stop and register NFR Design instead of silently extending scope.

### Code Generation — GATED

Do not implement until u148 is complete and the Functional Design/NFR Requirements above are authored and independently reviewed.

## Fixed Contracts

### C1. Preserve the u144 lifecycle and terminal-read-only boundary

1. The sole path remains `finalize_public_bundle()` with `generated -> assembled -> projected -> repaired -> validated -> sealed`.
2. Assembly must stop converting numeric findings to a trust-block before layout. Numeric scanning/containment happens only after `PublicDocumentLayout.reindex()` provides exhaustive ownership.
3. Numeric transformations occur inside the existing pre-validation repair phase. `_validate_repaired_draft()` remains read-only and must reject any residual finding.
4. Each target/region receives at most one bounded action, public projection is rerun after replacement, and no Markdown changes after validation/seal.
5. The new containment/minimal policy is enabled only for `segment == DOMESTIC_EQUITY`. US/crypto findings retain their pre-u149 behavior and state/output bytes.

### C2. Location-aware finding contract

Extend the existing `AnchorAssertionFinding` rather than create a second detector. In addition to segment/symbol/label/sentence/isolation it carries deterministic location metadata sufficient to map the finding to exactly one region:

- `start: int` and `end: int` — half-open offsets in the exact scanned Markdown.
- `line_kind: Literal["prose_sentence", "list_or_callout", "table_row", "h3_subtree", "structural_region"]`.
- An optional stable line/claim digest may be derived, but raw Markdown is not copied into diagnostics.

`public_document` maps `[start, end)` to one `PublicDocumentRegion`. Overlap, no owner, multiple owners, or offsets that change before action are deterministic containment failures and advance to C5, never arbitrary text search.

### C3. Original hard-gate eligibility must be exhaustive

Recovery eligibility is restricted to `segment == DOMESTIC_EQUITY` and a valid indexed layout. US/crypto numeric findings retain the u144 `trust_blocked` behavior. A pre-layout/non-indexable failure or any non-numeric assembly failure keeps its existing immediate block/error path because there is no safe common layout on which to aggregate or edit.

Before any domestic numeric-only fallback can replace original content, run all existing read-only hard gates over the same repaired original layout and collect sorted bounded codes rather than short-circuiting:

- numeric anchor assertions;
- entity/fact contradictions;
- P0 compliance/public-language violations;
- required surface/summary/target-date/section structure;
- canonical and first-viewport disclaimer checks;
- notification-summary derivation and any existing security/leak guard.

Local numeric containment or minimal fallback is eligible only when `segment == DOMESTIC_EQUITY` and the original hard-code set is exactly `{numeric.anchor_assertion}`. If any other hard code coexists, keep the existing `trust_blocked` result and preserve all codes in bounded diagnostics. A minimal document must never mask a defect from the original document.

The aggregator reuses the exact terminal scanner functions; it must not define parallel truth rules. Terminal validation still reruns every gate on the repaired/fallback candidate.

### C4. Fixed local recovery ladder

For an eligible domestic numeric-only original, first group every finding by its owner `region_id`. Build one immutable edit plan from each region's original bytes and apply exactly one region replacement/omission. Never mutate a region sequentially, reuse shifted offsets, or rediscover a target through text search.

Within each region group, use this order and stop at the first safe region plan:

1. **Typed full-block correction** — allowed only when an existing registered renderer owns the entire claim/block and every numeric field comes from a trusted canonical anchor. Regenerate the whole typed claim/block. Replacing a number token inside generated prose is unreachable and forbidden.
2. **Claim exclusion/rewrite** — reuse the u130 canonical data-limited sentence for prose, bullets, and public callouts; remove only the offending table data row; remove an H3 from its heading through the next H2/H3/owned-region boundary.
3. **Owned-region action** — use existing u144 omission for optional `visual`, `chart`, `carryover`, or `cause_map`; use existing safe replacement for `shared_macro`, `crypto_indicators`, `channel_anchors`, `daily_thesis`, and `watchpoints`; replace only a required `section_body` body while preserving its canonical H2; replace first-viewport conclusion/caution with canonical data-limited copy.
4. **Minimal document request** — if a terminal-equivalent numeric rescan still finds residue, overlapping/unowned structure, a malformed remaining table, or an unsupported required block, request C5. Do not guess a larger arbitrary deletion.

If any finding in a region requires a region-level replace/omit, that one action dominates claim edits and is applied to the original region bytes. Otherwise sort non-overlapping claim/row/H3 edits by descending original offset, compose them in memory, and commit the composed bytes with one `replace_region_body()` call. Diagnostics retain per-target outcomes plus one region application witness; u144's one grouped disposition per region remains intact.

`header`, `navigation`, protected diagnostics, or disclaimer numeric ownership is never edited locally. It proceeds to C5 only when C3 confirms numeric is the sole hard family.

### C5. Exactly one no-LLM minimal-segment attempt

1. Extract the existing deterministic six-section data-limited content from `briefing._reader_enhance.enhancement` / `briefing.pipeline` into neutral owner `src/investo/_internal/data_limited_segment.py::build_data_limited_briefing(target_date, segment) -> Briefing` so publisher does not import sibling package `briefing`. The neutral builder owns the six section values, base six-H2 Markdown, canonical long disclaimer, and `Briefing` construction. Existing briefing helpers become compatibility delegators or enhance that neutral base through their current header/coverage path.
2. `finalize_public_bundle()` owns `minimal_source_by_segment: dict[MarketSegment, Briefing]` and `attempted_minimal_segments: set[MarketSegment]` outside its survivor fixed-point loop. On the first eligible request it builds/stores the minimal source and consumes the segment's one attempt. A later survivor pass re-finalizes the stored minimal source under the new active context; that is not a new fallback attempt and never calls the builder again.
3. A private typed finalizer request restarts the same segment at `generated` with that stored minimal `Briefing`; it is not a second finalizer and not recursion. If the stored minimal source fails under a later active context, the segment is blocked rather than rebuilt.
4. The fallback context retains target/segment identity, source outcomes, public coverage status, and the original frozen `entity_observed_at_utc`. It uses `VerifiedFactBundle(target_date=context.target_date)` and contains no items, anchors, supplements, staged artifacts, visual/chart/carryover inputs, or bundle semantic augmentations that could recreate the claim.
5. The neutral builder emits exactly six required H2 sections, deterministic data-limited watchpoint copy, and the canonical long disclaimer. The normal u144 assembly/finalization path—not the neutral builder—adds canonical navigation/status and the first-viewport short disclaimer, so both disclaimer forms are present before terminal validation. Neither layer performs an LLM/network/file/env/clock call for the fallback.
6. The bundle-scoped ledger enforces max one build/attempt per segment. The minimal draft traverses assembly, projection, repair, every terminal gate, notification DTO derivation, and seal exactly like a normal draft on every survivor pass.
7. If the minimal attempt/stored source fails any gate, return `trust_blocked` with `numeric.fallback_exhausted` plus the actual bounded terminal codes. Never build or attempt another fallback.

### C6. Segment outcome and content completeness

Change the shared model to:

```text
SegmentFinalizationState =
  finalized | finalized_degraded | generation_absent | trust_blocked
```

- `finalized`: sealed document, no containment action, empty `issue_codes`.
- `finalized_degraded`: sealed document, at least one numeric containment/minimal action, non-empty `issue_codes` including `numeric.anchor_assertion`.
- `generation_absent` and `trust_blocked`: current semantics unchanged.

The new `SegmentFinalizationOutcome.numeric_containment_outcomes` field defaults to `()`. Construction rejects `finalized` with a non-empty tuple and rejects `finalized_degraded` with an empty tuple; legacy three-state constructors/serialized fixtures therefore retain their current defaults.

`FinalizedPublicBundle.documents` includes both finalized states. Content is `complete` when every expected segment is one of those two states, `partial` when at least one document exists and at least one segment is absent/blocked, and `none` when no document survives. Three published documents therefore commit, notify, dispatch Pages, and exit 0 even when one is `finalized_degraded`. Source-health warnings and quality degradation remain independently visible.

### C7. Typed degradation witness, closed actions, and diagnostics

Canonical shared owner: `src/investo/models/public_document_outcome.py::NumericContainmentOutcome`, a frozen/slotted DTO with exactly `target_date`, `segment`, `symbol`, `region_id`, `line_kind`, `action`, sorted `issue_codes`, and `claim_digest`. The same neutral module owns the closed `NumericClaimLineKind` and `NumericContainmentAction` literals so publisher and orchestrator do not import each other. `PublicDocumentDraft.numeric_containment_outcomes` accumulates the tuple pre-seal; `FinalizedPublicDocument.numeric_containment_outcomes` carries it with the sealed document; `SegmentFinalizationOutcome.numeric_containment_outcomes` copies the exact tuple. `finalized_degraded` and its bounded issue-code union derive only from that non-empty tuple. Logs, GitHub summary, and quality history are projections of this typed witness, never the source of state; they do not re-derive a publisher-owned block kind after seal.

Use a closed action set with a one-to-one mapping to C4:

```text
corrected | rewritten | excluded | replaced | omitted | minimal_fallback
```

- `corrected`: C4.1 typed full-block rendering.
- `rewritten`: C4.2 prose/list/callout data-limited replacement.
- `excluded`: C4.2 table-row or H3-subtree removal.
- `replaced`: C4.3 required/replaceable region fallback.
- `omitted`: C4.3 optional region omission.
- `minimal_fallback`: C5 one-attempt document replacement.

The typed DTO stores `claim_digest` as exactly 64 lowercase hexadecimal SHA-256 characters. A bounded log/event projection contains target date, segment, canonical symbol, region ID, line kind, action, sorted issue codes, and only the first 16 digest characters. It deliberately omits publisher-owned `PublicBlockKind`; region ID plus line kind are the complete cross-boundary location metadata. Logs/GitHub summary/quality history must not include the original sentence, full Markdown, raw payload, source URL, env, or secret. A minimal fallback increments the existing data-limited quality count and a dedicated bounded degraded-segment/action count; it does not rewrite source-health to success. Step 0 must pin DTO field/default serialization and compatibility for old three-state outcome readers.

### C8. Preserved hard failures and artifacts

- Entity, compliance, disclaimer, target-date, required structure, notification-summary, security/leak, unknown/unowned non-numeric failures remain immediate `trust_blocked`.
- A local omission cannot promote its staged artifact. Minimal fallback promotes no segment supplement artifact.
- E1 descriptor -> non-omitted E5 selected ID -> E6 promotion manifest, rollback, `PublisherGitError`, seal verification, and exact-byte writer contracts remain unchanged.
- Sealed `PublicNotificationSummary` remains the notifier's only content input.

## Implementation Steps

- [x] Step 0 — Author and independently review the Functional Design and NFR Requirements. Include the explicit u109 AC-1.4/u144 numeric-only supersession matrix, C3 masking guard, phase call graph, state transitions, action table, attempt witness, and benchmark/security ACs. Stop if NFR Design becomes required.
- [x] Step 1 — Add incident and masking characterization fixtures before changing behavior: structural table/H3 numeric-only cases, numeric+entity, numeric+P0 compliance, numeric+disclaimer, and numeric+required-structure cases.
- [x] Step 2 — Extend `publisher/anchor_assertion_gate.py` findings with stable offsets/kinds while reusing u130 detection. Add pure claim/row/H3 transforms and prove scanner/transforms are deterministic and idempotent.
- [x] Step 3 — Refactor `segment_reader_format.py` / assembly so numeric findings survive to indexed layout without early trust-block. Add the exhaustive original hard-gate collector using existing terminal scanners.
- [x] Step 4 — Add the domestic numeric-only action policy and original-byte, region-grouped edit planning inside new pure helper `publisher.numeric_containment`, `publisher.public_document`, and `_public_document_policy.py`. Apply one composed operation per region; preserve region expectations, reprojection, and read-only terminal validation.
- [x] Step 5 — Extract the no-LLM builder to `investo._internal.data_limited_segment`, keep compatibility owners explicit, and add the bundle-scoped `minimal_source_by_segment` / `attempted_minimal_segments` ledgers outside the fixed-point loop with stripped fallback context/artifacts.
- [x] Step 6 — Add canonical shared `models.public_document_outcome.NumericContainmentOutcome`/literals and thread the exact tuple `PublicDocumentDraft -> FinalizedPublicDocument -> SegmentFinalizationOutcome`; add `finalized_degraded` to the same model, bundle/result/completeness/CLI/workflow summary, quality metrics, and notifier/Pages sequencing. Update exhaustive state tests and serialization compatibility.
- [x] Step 7a — Run unit/composition/property/full local gates; update `docs/DESIGN.md`, component methods, u144 supersession notes, and code summary.
- [ ] Step 7b — Complete exact-date production replays for 2026-08-03 and 2026-08-04, followed by Pages/live URL closeout. This remains a separate production closeout action and was not invoked by local construction.

## Acceptance Criteria

1. AC-149.1: Numeric findings reach an indexed owned layout; assembly never removes a segment solely because a structural numeric finding exists.
2. AC-149.2: The original repaired layout's hard gates are exhaustively collected before fallback. Numeric+entity/compliance/disclaimer/required-structure cases remain `trust_blocked`; fallback cannot mask them.
3. AC-149.3: A trusted typed renderer may correct an entire block, but arbitrary numeric-token substitution is unreachable.
4. AC-149.4: Prose/list/callout repair changes only the target claim; a table finding removes only its data row; an H3 finding removes only its owned subtree. Surrounding bytes and unrelated regions remain unchanged.
5. AC-149.5: Optional visual/chart/carryover/cause-map findings omit only that block and promote no artifact; replaceable owned regions use the existing safe fallback; required section H2 headings remain present.
6. AC-149.6: Every locally repaired candidate is reprojected/reindexed and passes the unchanged read-only terminal numeric scanner with zero findings before seal.
7. AC-149.7: Residual, overlapping, unowned, or malformed numeric-only content requests exactly one no-LLM minimal attempt.
8. AC-149.8: The minimal document has canonical navigation/status, six required sections, watchpoint limited copy, two disclaimers, no items/anchors/supplements/staged artifacts/LLM call, and passes every normal terminal gate plus notification-summary derivation.
9. AC-149.9: A failed minimal attempt is the only numeric-only path to `trust_blocked`, with `numeric.fallback_exhausted`; no second attempt occurs.
10. AC-149.10: A sealed locally repaired or minimal document is `finalized_degraded` with non-empty bounded issue/action diagnostics; a clean document remains `finalized` with byte-identical Markdown.
11. AC-149.11: Domestic `finalized_degraded` plus finalized US/crypto yields three published archives, `content_completeness=complete`, pipeline exit 0, Telegram delivery, and Pages dispatch. True absence/non-numeric block remains partial/exit 2; zero survivors remains exit 1.
12. AC-149.12: Minimal fallback increments data-limited/degraded quality metrics without erasing original source-health failures or withheld reasons.
13. AC-149.13: Logs and GitHub summary expose only bounded symbol/region/action/code/hash metadata, never original claim/Markdown/raw payload/URL/secret.
14. AC-149.14: Repeated finalization produces equal Markdown, outcomes, actions, and digests; max one action per target/region and one minimal attempt per segment.
15. AC-149.15: US/crypto and normal domestic fixtures remain byte-compatible; u144 seal, notifier DTO, staged-artifact, rollback, survivor fixed-point, and import-boundary tests remain green.
16. AC-149.16: 2026-08-03 and 2026-08-04 incident fixtures seal a domestic document with rejected/wrong values absent and both sibling segments unchanged.
17. AC-149.17: Exact-date production replays publish all three archive URLs, log domestic `finalized_degraded` or `finalized`, exit 0, send Telegram, and complete the chained Pages run; live domestic URLs return 200 and contain none of the rejected values.
18. AC-149.18: A US/crypto structural numeric finding remains `trust_blocked` with pre-u149 state/output behavior; domestic containment/minimal code is unreachable for those segments.
19. AC-149.19: When a sibling trust block forces a second survivor fixed-point pass after domestic minimal success, the minimal builder is called once, the stored source is re-finalized, and the domestic document can still seal without consuming a second attempt.
20. AC-149.20: Multiple numeric findings in one region are planned from the original region bytes and committed through one grouped operation; no shifted-offset reuse or sequential text search occurs.
21. AC-149.21: `finalized_degraded` is derived only from non-empty sealed `NumericContainmentOutcome` data, whose exact fields/actions/digest are preserved from draft to document to segment outcome; deleting log output cannot change state.
22. AC-149.22: Pre-layout/non-indexable and non-numeric assembly failures preserve their existing immediate block/error paths and never enter hard-gate aggregation or fallback.

## Tests / Validation

Focused tests:

```bash
uv run --extra dev pytest \
  tests/unit/publisher/test_anchor_assertion_gate.py \
  tests/unit/publisher/test_numeric_degradation_containment_u149.py \
  tests/unit/publisher/test_public_document_types_u144.py \
  tests/unit/publisher/test_public_document_assembly_u144.py \
  tests/unit/publisher/test_public_document_containment_u144.py \
  tests/unit/publisher/test_public_document_policy_u144.py \
  tests/unit/publisher/test_public_document_incident_chain_u144.py \
  tests/unit/orchestrator/test_run_pipeline.py \
  tests/unit/orchestrator/test_main.py \
  tests/unit/orchestrator/test_daily_workflow_contract_u144.py \
  tests/integration/test_bundle_reconciliation.py
```

Required property/architecture coverage:

- offsets always map to zero or one region; zero/multiple ownership never performs an arbitrary edit;
- action ordering and issue-code ordering are stable under repeated execution;
- unsupported token/delimiter combinations cannot corrupt a table or section boundary;
- publisher does not import `investo.briefing`; both use the neutral data-limited builder;
- terminal validation remains read-only and no public consumer mutates `FinalizedPublicDocument`.

Full gate:

```bash
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src
uv run --extra dev pytest
uv run python scripts/check_no_paid_apis.py
uv run --extra docs mkdocs build --strict
git diff --check
```

Production closeout:

1. Dispatch daily briefing for `target_date=2026-08-03`; verify three segment outcomes/documents, commit/push, Telegram, exit 0, Pages success, domestic HTTP 200, and rejected values absent.
2. Repeat for `target_date=2026-08-04` with the same checks.
3. Record workflow IDs, bot commit SHAs, Pages run IDs, archive/live URLs, outcome/action codes, and source-health/degradation distinction in the u149 code summary.

## Non-Goals

- No weakening or bypassing of terminal numeric validation.
- No fallback when the original document has any non-numeric hard defect.
- No second finalizer, new lifecycle phase, or post-seal mutation.
- No LLM repair, external lookup, or guessed numeric correction.
- No change to Telegram notifier-only failure semantics.
- No historical archive mutation.
