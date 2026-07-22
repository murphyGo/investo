# Code Generation Plan: `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Unit**: u144 public-document-finalization-contract
**Stage**: Code Generation
**Status**: Complete through Step 8 (2026-07-22)
**Source**: 2026-07-20/21 daily-briefing incident diagnosis; GitHub Actions run `29707052598` (`target_date=2026-07-17`) and the earlier `summary.truncated_mid_token`, `quality.body_evidence_untracked`, and numeric-anchor incident family
**Estimated Effort**: ~28-36 h across eight bounded implementation steps
**Dependencies**:
- u81 reader-format-subpackage, u84 orchestrator-stage-abstraction, u85 unified-validator-gate-protocol — complete.
- u100/u108/u110/u112 surface/public-language/watchpoint gates — complete and reused; no parallel scanner.
- u114 shared-domain-contract-boundary and u117 typed-metadata rules — complete; no sibling-unit import regression.
- u118 generation request/result boundary, u123 evidence accounting, u127 summary reject predicate — complete and preserved.
- u63 partial-bundle-navigation and u94 bounded-segment-generation-concurrency — complete and preserved. u144 does not restore the superseded u7 all-three-or-fail rule.
- u141 image-selection-and-insertion is data-gated and u143 visual-theme-parity is planned/backlog. If either lands before/after u144, the later unit must rebase visual/link Markdown and files onto the staged pre-finalization supplement boundary; neither may leave a post-finalization mutation.
- Planned u130/u131/u133/u134/u135 retain ownership of their issue-specific numeric, bounding, routing, composition, and signal-generation rules. u144 owns only their common execution/finalization boundary.

Detailed design:
- `aidlc-docs/construction/u144-public-document-finalization-contract/functional-design/domain-entities.md`
- `aidlc-docs/construction/u144-public-document-finalization-contract/functional-design/business-rules.md`
- `aidlc-docs/construction/u144-public-document-finalization-contract/functional-design/business-logic-model.md`
- `aidlc-docs/construction/u144-public-document-finalization-contract/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/u144-public-document-finalization-contract/nfr-requirements/tech-stack-decisions.md`
- `aidlc-docs/construction/u144-public-document-finalization-contract/nfr-design/nfr-design.md`

---

## Problem Statement

The production pipeline has no true final public-document boundary. It repeatedly mutates `Briefing.rendered_markdown: str` through independent regex/string passes, and several producers run after an earlier public-language or surface-quality pass.

The 2026-07-20 scheduled run demonstrates the exact failure:

1. Crypto generation succeeded.
2. `apply_reader_format()` projected `데이터 부족` to reader-safe text.
3. `render_watchpoint_matrix()` ran later and reintroduced `상방 데이터 부족`, `하방 데이터 부족`, or `관심 영향 데이터 부족` from its defaults.
4. The terminal surface scan correctly raised `public_diagnostic.raw_label`.
5. The orchestrator caught the exception, removed only crypto, published domestic/US, and returned `status=partial` while GitHub Actions stayed green.

The same architectural shape caused earlier failures:

| Failure family | Producer/gate mismatch |
|---|---|
| `summary.truncated_mid_token` | first-viewport reflow emitted a string rejected by the later surface gate |
| `quality.body_evidence_untracked` | public projection removed raw `본문 사용` syntax before a later accounting gate parsed it |
| numeric-anchor reconciliation | protected/public text classification and canonical-anchor payload disagreed |
| `public_diagnostic.raw_label` | a downstream watchpoint producer recreated a phrase an upstream public projection had already removed |

The current surface gate in `publisher/segment_reader_format.py` is also not the real last mutation. `_stage_publish_segments()` subsequently rewrites segment navigation, emits/repairs disclaimers, repairs the first-viewport summary, and renders body-used counts before writing. A gate cannot guarantee final bytes while later code can still change those bytes.

## Goal

Create one publisher-owned, deterministic public-document finalization boundary that:

1. receives generated segment briefings plus all public supplement inputs;
2. performs every text-producing transform in one declared phase order;
3. converts typed limitation states to public wording only after the last producer;
4. repairs or replaces bounded presentation defects at block scope;
5. runs all blocking validators read-only at the true terminal boundary;
6. seals the exact bytes in `FinalizedPublicDocument`;
7. permits archive/index/notification consumers to read, but never mutate, the sealed document;
8. preserves intentional u63/u94 content-partial publication for generation or hard-trust failures, but makes that state typed and GitHub-red after publishing the valid subset.

The intended operational outcome is: a cosmetic/optional block defect becomes a safe fallback inside the same segment. A truth, compliance, structure, or disclaimer defect may block only that segment under the existing partial-bundle product contract; the valid subset is published with explicit u63 absence navigation, but the daily workflow ends red. If no segment survives, the run fails before public writes. This failure family must never again create a green two-of-three run.

## Existing Coverage / Deduplication

- **u81** owns the reader-format package and individual pass implementations. u144 moves ordering ownership; it does not merge those modules back together.
- **u85** owns the generic `ValidationResult`/`ValidationRegistry` envelope. Its deliberate descope found that interleaved transforms are not a flat validator registry. u144 does not force unlike validators into one payload; it introduces lifecycle phases around the existing specialized APIs.
- **u100/u112** own surface issue detection and deterministic Markdown repairs. u144 reuses `find_surface_quality_issues()` and `repair_surface_artifacts()`.
- **u108** owns forbidden public phrases and reader-safe projection. u144 moves that projection to the terminal projection phase and requires every producer to be covered.
- **u110/u135** own watchpoint content quality. u144 owns only public-safe defaults and block-failure containment; it does not synthesize market signals.
- **u118** owns generation input/result. `Briefing` remains the generated artifact; u144 adds a distinct publisher-finalized artifact rather than changing the LLM contract.
- **u123** owns body-evidence counting. u144 moves `render_body_used_count()` before terminal projection/validation but does not change counting semantics.
- **u127** owns the canonical summary reject predicate. u144 reuses it through existing summary repair/validator APIs.
- **u63/u94** own intentional missing-segment navigation and generation-failure isolation. u144 preserves them, adds typed finalization outcomes, and changes only operational visibility: content-partial exits 2 after a valid subset is committed; notifier-only partial remains exit 0.
- **u130/u131/u133/u134/u135** remain issue-specific planned units. Their producers must appear in the documented assembly call graph before the terminal projection phase and may not add a new after-gate mutation.

## Scope Boundary

In scope:

- A publisher-local typed lifecycle for draft, block outcome, finalization report, and sealed final document.
- One `finalize_public_bundle(...)` API as the only production path from generated `Briefing` objects to publishable segment documents.
- Migration of every current post-generation `rendered_markdown` mutation into the declared pre-seal phase order, including the late publish-stage nav/disclaimer/summary/body-used rewrites.
- Moving public-quality projection after every text producer, including watchpoint rendering.
- Reader-safe prompt/default constants so raw operator labels are not deliberately produced on public paths.
- Bounded block fallback/omission for optional presentation blocks.
- Typed per-segment outcomes for generation absence and non-degradable trust blocks; zero surviving segments fail before writes.
- Run-scoped staging for file-producing supplements (current visual/chart assets and any future file-backed carryover) so finalization failure cannot leak public-destination artifacts. Current text-only carryover remains an in-memory supplement.
- A sealed writer API and architecture tests that reject post-finalization mutation.
- Regression, composition, idempotence, and property-based tests over real incident fixtures.
- Pipeline/CLI/workflow behavior that distinguishes content-partial exit 2 from notifier-only partial exit 0 and still triggers Pages for a committed valid subset.

Out of scope:

- A general CommonMark AST or replacement Markdown parser.
- New LLM calls, paraphrasing calls, retry loops, data sources, secrets, dependencies, or network I/O.
- Changing numeric-anchor truth policy, entity facts, compliance phrases, source coverage, watchlist matching, or evidence-count semantics.
- Historical archive backfill.
- Changing Telegram delivery failure semantics: publish-success + public-channel notification failure remains `PARTIAL`/exit 0 under the existing u5 contract.
- Replacing the quality-consistency transaction/rollback logic for index/history pages.
- Changing git commit/push compensation semantics or rewriting local history after `PublisherGitError`.

## Stage Decision

### Functional Design — EXECUTE / authored

Required because u144 introduces a new document lifecycle, typed state, ownership boundary, failure-containment policy, and explicit partial-bundle finalization contract. These are behavioral/architectural decisions, not a mechanical refactor.

### NFR Requirements — EXECUTE / authored

Required because the finalizer must guarantee determinism, idempotence, bounded runtime, zero I/O, no post-seal mutation, safe diagnostics, fault containment, and exact operational visibility.

### NFR Design — EXECUTE / authored

Required for the run-scoped artifact staging/promote/rollback boundary, finalizer fixed-point bound, seal verification, and content-partial exit/Pages sequencing. See `nfr-design/nfr-design.md`.

### Infrastructure Design — EXECUTE / workflow-only

No new job, secret, service, storage engine, or deployment resource is added, but `daily-briefing.yml` must capture the pipeline exit, dispatch Pages for committed exit-0/exit-2 results, and then re-emit exit 2 so content-partial runs are red. The exact sequence is fixed in NFR Design.

## Fixed Contracts

### Contract 1 — Canonical owner and public API

Canonical lifecycle owner: `src/investo/publisher/public_document.py`.

```python
def finalize_public_bundle(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    context: PublicDocumentContext,
) -> FinalizedPublicBundle:
    ...
```

Rules:

- The API is pure with respect to network, filesystem, environment, wall clock, and subprocesses.
- `PublicDocumentContext` contains explicit already-computed inputs only: target date, expected segment order, known generation absences, reconciled anchors, routed items, typed segment coverage, source outcomes, optional bundle context, verified fact bundle, timezone-aware entity observation instant, ordered pre-rendered visual/chart/carryover supplements, and typed staged-artifact descriptors. Supplements reference artifact IDs; the finalizer performs no asset I/O. E4 limitation reasons are derived by the exhaustive FD mapping and typed producer results, never by parsing Korean prose.
- It must not accept `PipelineContext` or read orchestrator globals.
- Among **new u144 symbols**, `publisher.__init__` re-exports only `finalize_public_bundle`, `FinalizedPublicDocument`, `FinalizedPublicBundle`, and the writer API. Existing public exports remain backward compatible; draft/layout internals remain publisher-private.

### Contract 2 — Typed lifecycle and outcomes

Implement frozen/slotted publisher-local types matching the detailed FD:

```python
PublicDocumentPhase = Literal["generated", "assembled", "projected", "repaired", "validated"]
PublicBlockDisposition = Literal["kept", "repaired", "replaced", "omitted"]

@dataclass(frozen=True, slots=True)
class PublicBlockOutcome:
    region_id: str
    block: PublicBlockKind
    disposition: PublicBlockDisposition
    issue_codes: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class FinalizedPublicDocument:
    segment: MarketSegment
    target_date: date
    briefing: Briefing
    markdown_sha256: str
    staged_artifact_ids: tuple[str, ...]
    notification_summary: PublicNotificationSummary
    block_outcomes: tuple[PublicBlockOutcome, ...]
    warnings: tuple[str, ...] = ()
```

- `Briefing` remains the u2 generated artifact and must no longer be documented as the exact final archive bytes.
- `FinalizedPublicDocument` is created only by the module-private sealing factory after zero blocking terminal findings.
- `briefing` is the final compatibility view whose `rendered_markdown` is the sealed archive byte source; the original generated briefing is not embedded.
- `markdown_sha256` is lowercase SHA-256 of `briefing.rendered_markdown` UTF-8 bytes. Writer rechecks it before I/O.
- Internal typed limitation reasons must not be recovered by parsing public Korean prose.
- `PublicDocumentDraft` owns a bounded `PublicDocumentLayout(markdown, regions, expectation)` index over canonical publisher headings/markers. `PublicRegionExpectation` carries target date/segment, segmented mode, expected supplement IDs, and anchor/macro/crypto/channel/thesis conditional-presence booleans derived from E1 plus the active survivor decision. One typed producer plan supplies both eligibility flags and assembly payloads. Regions are re-indexed after every whole-document producer; repair/fallback targets a unique region ID. Conditional absence is checked against the typed expectation, never guessed from Markdown. This is not a general Markdown AST.
- Each existing surface scan runs per owned region and once on the fully rendered document. A blocking finding that cannot map to exactly one region is a hard segment block; it is never repaired by guessing from duplicated evidence text.
- FD fixes the exhaustive `RegionSpec` table, supplement marker comments, priority, required/conditional/optional rules, duplicate/overlap behavior, and replace-then-reindex semantics. Implementers may not invent marker heuristics.
- E1 `PublicDocumentSupplement(supplement_id, kind, markdown, stable_order, artifact_ids)` values are wrapped in canonical `investo:block` marker pairs; their `StagedArtifact` IDs are referentially checked. Omission empties only the marker body and records an E7 outcome, so typed conditional structure remains valid. E5 excludes artifact IDs for explicitly omitted regions and E6 `promotion_manifest` equals the ordered union of the remainder. URLs are never parsed to discover assets.

### Contract 3 — One declared phase order

`finalize_public_bundle` owns this exact top-level order:

1. **Assemble**: recompute the active-survivor daily-thesis decision through the neutral shared owner; ingest marker-wrapped visual/chart/carryover supplements; anchor-table/anchor-assertion processing; reader-format structural passes; shared macro; crypto indicators; channel anchors; cause map; daily thesis; pre-watchpoint compliance scan; typed watchpoint rendering; post-watchpoint compliance scan; canonical segment navigation; canonical/short disclaimer; first-viewport reflow; summary repair; body-used rendering.
2. **Project**: call the canonical newline-preserving `project_public_markdown(...)` API across every reader-visible region after all text producers have run. Raw diagnostics remain only in explicitly protected collapsed/structured regions.
3. **Repair**: run deterministic compliance/surface repairs and bounded presentation fallbacks. Re-run projection on any replacement block before reassembly.
4. **Validate**: run specialized read-only gates in a declared order: required structure, numeric anchors, entity facts, compliance, owned public-language leakage (including reader-visible tables), canonical/short disclaimer, summary quality, surface quality, then derive/validate `PublicNotificationSummary`. Missing/unsafe notification conclusion returns a typed hard block inside the current survivor attempt. No validator may mutate.
5. **Seal**: compute digest and construct `FinalizedPublicDocument`.

No text-producing call is allowed after step 4 begins. No code may change `markdown` after step 5.

### Contract 4 — Public limitation state

Add publisher-local typed reasons (exact names fixed in FD):

```python
PublicLimitationReason = Literal[
    "limited_coverage",
    "core_price_missing",
    "source_count_unavailable",
    "watchpoint_unavailable",
]
```

- Prompt context and producer inputs carry typed conditions; `CoverageReasonCode` values map to E4 exactly as specified in FD, and public copy is rendered at Contract 3 phase 2.
- `SEGMENT_DATA_LIMITED_NOTE` must no longer instruct the LLM to emit `데이터 부족`, `[데이터부족]`, or another phrase forbidden by u108.
- Watchpoint defaults must be reader-safe by construction. Raw phrases remain legal only in protected diagnostics/structured metadata.
- `public_quality_language.py` stays the single wording-map owner; do not copy strings into watchpoint, prompt, notifier, or finalizer modules.
- Production watchpoint rendering returns `WatchpointRenderResult(markdown, state, usable_card_count, limitation_reasons)`. A limited result contributes `watchpoint_unavailable` to the E2 typed reasons; the finalizer never parses watchpoint Korean copy to recover state.

Canonical terminal API:

```python
def project_public_markdown(
    layout: PublicDocumentLayout,
    *,
    limitation_reasons: tuple[PublicLimitationReason, ...],
) -> PublicDocumentLayout:
    ...
```

It lives in `publisher/reader_format/public_projection.py`, processes reader-visible lines/regions with `splitlines(keepends=True)`, preserves newline bytes and canonical disclaimer bytes, and protects only fenced code, collapsed `수집/품질 진단`, and structured metadata. It must **not** protect every Markdown table: reader-visible watchpoint tables are projected. It calls `_internal.public_quality_language.project_public_quality_language()` only on visible fragments. The existing `normalize_data_limited_reader_copy()` becomes a compatibility wrapper around this API or is removed after production call sites reach zero. Repeat application is byte-idempotent.

### Contract 5 — Degradable vs blocking failures

| Finding class | Required behavior |
|---|---|
| known public-label/Markdown artifact with deterministic repair | repair, record `repaired`, re-project, revalidate |
| invalid required watchpoint section | replace its body with the fixed public-safe watchpoint limitation block, preserve `## ⑥`, record outcome, revalidate full document |
| invalid visual/chart/carryover/cause-map/indicator optional block | use `omit_optional_block` for visual/chart/carryover/cause-map and `replace_block` for indicator-class blocks exactly as the FD table fixes; record outcome and revalidate |
| invalid first-viewport summary presentation | use existing deterministic summary fallback, record `replaced`, revalidate |
| unsupported precise numeric claim | block segment; never invent/drop the number silently |
| entity fact contradiction | block segment |
| residual P0 compliance/advice phrase | block segment |
| missing canonical or short disclaimer after deterministic insertion | block segment |
| missing/duplicate required segment section or unparseable required structure | block segment |
| residual blocking issue after one bounded fallback pass | block segment |

Fallback is bounded to one replacement/omission per affected region. Findings are grouped by region, issue codes are sorted, and disposition precedence is exactly `block_segment > omit_optional_block > replace_block > repair > record_warning`. The FD block table resolves every optional/conditional block to one disposition; there is no replace-or-omit choice. Marker-backed omission preserves an empty canonical wrapper. There is no unbounded repair loop and no LLM retry.

### Contract 6 — Partial bundle, atomic valid-subset publish, and status

- Production segmented mode expects `SEGMENT_ORDER` (domestic, US, crypto).
- A known missing generated input enters E1 as `generation_failed`; a non-degradable terminal finding becomes `trust_blocked`. Both are explicit E6 outcomes, never implicit dict omission.
- Presentation/surface findings covered by Contract 5 may not create a missing segment.
- The pure finalizer computes the surviving set and u63 absence navigation by a bounded fixed point: restart from original generated drafts after a new hard block, at most `len(SEGMENT_ORDER)` passes. Zero survivors before writes raises E8.
- A non-empty valid subset is sealed completely before reader-facing archive/index/quality writes or their git staging and then committed in one existing transaction. Pre-existing private operational state such as macro-carryover/forecast logs is outside the public-document seal and retains its current best-effort lifecycle; it cannot enter E5/E6 or be presented as a public artifact. One/two documents => `PipelineStatus.PARTIAL`, `content_completeness=partial`, process exit 2, operator alert, and red workflow after Pages dispatch.
- Three documents plus notification failure => existing delivery-only `PARTIAL`, `content_completeness=complete`, exit 0. Optional visual failure may publish text-only and does not imply a missing segment.
- Zero documents or bundle/programmer invariant failure => `FAILED`, exit 1, no public commit.

### Contract 7 — Sealed writer boundary

Add `write_finalized_document(document: FinalizedPublicDocument) -> Path` to `publisher/writer.py`.

- It verifies the digest, target date/segment archive path, and disclaimer before atomic write.
- The segmented production path calls only this API.
- Keep `write_briefing()` as a documented legacy/unsegmented compatibility wrapper during u144; it is forbidden in the default segmented publish path by an architecture test.
- Site index, OG/visual summaries, quality accounting, and notifier extraction receive read-only finalized bytes or a read-only compatibility view. They may not return an updated final document.
- File-producing supplements first write to a run-owned temporary staging root and return `StagedArtifact(artifact_id, segment, kind, relative_public_path, staged_path, sha256)`. This covers current visual/chart assets and any future file-backed carryover; current text-only carryover performs no file I/O. Supplements reference IDs, E5 freezes non-omitted IDs, and E6 carries the exact promotion manifest. After E6 exists, the existing pre-git publish transaction verifies ownership/digests and promotes only that manifest with sealed Markdown/index artifacts; promotion/write/quality failure rolls back public destinations and staging is always removed. Existing `PublisherGitError` semantics remain after commit/push begins; u144 does not promise git-history compensation or byte rollback of a possibly created local commit.
- Add shared `models.public_notification.PublicNotificationSummary(segment, target_date, conclusion, coverage_status, coverage_label, watchlist)`. Conclusion/watchlist are extracted and public-language/summary validated during terminal validation, before the survivor attempt is accepted; coverage fields come from E1 typed coverage. The validated E2 draft stores the DTO and seal only copies it. Canonical prefix extraction stays in `_internal.briefing_extract`, shared cleanup moves from notifier to `_internal.public_summary_extract`, and missing/unsafe conclusion hard-blocks without alternate prose. Default segmented notifier accepts only this DTO plus URLs/existing typed lookahead/price inputs; `Briefing` and `Briefing.market_summary` fallback are forbidden on that path by a call-contract/AST test.

### Contract 8 — Compatibility and extension points

- Existing renderer/gate implementations remain canonical; u144 centralizes their invocation rather than cloning algorithms.
- Pre-finalization supplements are explicit and ordered. u143 and future producers must appear in the documented assembly call graph before phase 2.
- Existing public functions may remain thin compatibility wrappers for tests, but the production call graph must contain one path to the finalizer and one path from sealed document to writer.
- No new sibling imports that violate the u114 boundary.
- Architecture coverage is deliberately bounded: an AST/rg test allowlists production `rendered_markdown` construction/mutation sites and the one seal factory. It does not claim to detect arbitrary semantic string transforms hidden inside any helper.

### Contract 9 — Diagnostics

Each replacement/omission emits one bounded structured log:

```text
public_document.block_degraded segment=<segment> block=<block> disposition=<...> codes=<sorted-codes>
```

Final failure logs include target date, segment, phase, sorted issue codes, and bounded evidence length/preview after existing redaction. Never log full generated Markdown, raw source payloads, URLs with secrets, or environment values.

The GitHub step summary/output must show expected/finalized/published counts, content completeness, and bounded outcome codes. Content-partial is red through exit 2 after Pages dispatch; zero-document/bundle failure is red through exit 1.

## Implementation Steps

### Step 0 — Freeze the current mutation graph and incident corpus

- [x] Enumerate every production `rendered_markdown` mutation and its call order. The baseline list must include `visuals/assets.py`, chart/carryover injection, `segment_reader_format.py`, `_rewrite_segment_nav_for_published_segments`, canonical/short disclaimer, summary repair, and body-used rendering. Baseline: `aidlc-docs/construction/u144-public-document-finalization-contract/code/mutation-graph-baseline.md`.
- [x] Add redacted fixtures for run `29707052598` (`데이터 부족` reintroduction), the first-viewport truncation family, and the body-evidence projection mismatch. Fixtures: `tests/fixtures/u144/`.
- [x] Pin the pre-u144 failure behavior in characterization tests before changing it. Tests: `tests/unit/publisher/test_public_document_incident_characterization_u144.py`.
- [x] Freeze the existing u63/u94 content-partial behavior and notifier-only partial behavior as separate fixtures before changing exit signaling. Fixtures: `tests/fixtures/u144/legacy-content-partial-u63-u94.json`, `tests/fixtures/u144/legacy-notifier-only-partial.json`.
- [x] Enumerate every current `SurfaceQualityIssue.code` and land the exhaustive issue-code × owned-block disposition table from FD; a newly added code must fail the exhaustiveness test. Policy: `src/investo/publisher/_public_document_policy.py`; baseline: `aidlc-docs/construction/u144-public-document-finalization-contract/code/surface-issue-disposition-baseline.md`.
- [x] Record the exact list of planned u130/u131/u133/u134/u135 hooks that need rebasing if they land concurrently. Baseline: `aidlc-docs/construction/u144-public-document-finalization-contract/code/planned-hook-rebase-baseline.md`.

### Step 1 — Add lifecycle types and pure finalizer skeleton

- [x] Add `publisher/public_document.py` with `generated -> assembled -> projected -> repaired -> validated`, E1 coverage/absence/entity-clock/supplement/staged-artifact inputs, bounded layout regions, E5 artifact/notification outputs, E6 segment outcomes/promotion manifest, errors, and seal factory. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-lifecycle-types.md`.
- [x] Add pure bundle/segment finalization skeletons with phase assertions. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-finalizer-skeleton.md`.
- [x] Implement the FD `RegionSpec` table and `PublicRegionExpectation` exactly, including typed `supplement_id` marker-wrapped blocks, active-pass conditional presence, exact anchor headers/empty-anchor absence, five section titles/short disclaimers/H1, priority partition, duplicate/overlap/missing rules, body-only replacement/marker-shell omission, and full reindex; prove duplicated evidence in two blocks maps by region ID rather than `str.find`. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-region-index.md`. Fresh-eyes implementation review exposed an unrepresentable original combination (contiguous unique section/watchpoint spans versus current H2-scoped markers); FD rows 14-15 now minimally define deterministic continuation IDs while preserving producer placement and non-overlap.
- [x] Add `models.public_notification.PublicNotificationSummary` with segment/date, typed coverage status/label, sealed conclusion, and optional sealed watchlist; add the typed `WatchpointRenderResult` contract without switching production yet. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-notification-watchpoint-contracts.md`.
- [x] Add writer digest verification and the new sealed writer API without switching production yet. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-sealed-writer.md`.
- [x] Add unit tests for invalid phase transition, digest mismatch, segment/date mismatch, and external construction/production-use guard. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-1-lifecycle-architecture-guards.md`.

### Step 2 — Move all mutations before the terminal boundary

- [x] Move nav, canonical/short disclaimer, summary repair, and body-used rendering out of `_stage_publish_segments` into phase 1. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-phase-one-publish-mutations.md`.
- [x] Make `segment_reader_format` an internal assembly collaborator; remove its premature terminal surface gate. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-segment-reader-internal-collaborator.md`.
- [x] Route visual/chart/carryover Markdown through explicit pre-finalization supplements or a single pre-finalizer adapter. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-pre-finalization-supplements.md`.
- [x] Change current visual/chart file writers (and the common contract for any future file-backed carryover) to accept a run staging root and return full typed `StagedArtifact` descriptors; text-only carryover stays in memory. Typed supplement IDs/marker regions must resolve, omitted supplements contribute no E5 IDs, E5 survivor IDs must form the E6 promotion manifest without parsing Markdown URLs, promotion occurs only inside the post-E6 publish transaction, and staging cleans on all exits. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-staged-artifact-chain.md`.
- [x] Remove every production `Briefing.model_copy(update={"rendered_markdown": ...})` that occurs after finalization. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-post-finalization-mutation-audit.md`.
- [x] Add an AST architecture test with an explicit compatibility allowlist. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-2-rendered-markdown-architecture-guard.md`.

### Step 3 — Align producers and terminal public projection

- [x] Implement exact `project_public_markdown(layout, *, limitation_reasons) -> PublicDocumentLayout` semantics from Contract 4 and move production u108 projection to phase 2 after watchpoint and all other text producers. Region projection policy, not blanket table protection, controls visibility. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-terminal-public-projection.md`.
- [x] Change prompt/default producer copy to use the shared public-language map; eliminate raw public defaults from `watchpoint_matrix.py`. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-public-safe-producer-defaults.md`.
- [x] Make `render_watchpoint_matrix_result()` the production API, accumulate its typed limitation reason in E2, and reduce the legacy string renderer to a zero-production-call compatibility facade. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-typed-watchpoint-result.md`.
- [x] Preserve raw diagnostic labels inside collapsed diagnostics and structured metadata only. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-protected-diagnostic-metadata-boundary.md`.
- [x] Add the read-only owned-region leakage traversal over the existing u108 evidence predicate so reader-visible tables are terminally checked without cloning phrase policy. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-owned-region-leakage-traversal.md`.
- [x] Add the exhaustive `CoverageReasonCode -> PublicLimitationReason` mapping test and pass timezone-aware `entity_observed_at_utc` into the existing entity guard. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-coverage-reason-entity-clock.md`.
- [x] Add whole-chain regression proving the run-29707052598 watchpoint shape finalizes with zero `public_diagnostic.raw_label` issues. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-3-whole-chain-incident-regression.md`.

### Step 4 — Add block-scoped containment and remove duplicate gates

- [x] Add region-owned outcome recording and implement the exhaustive single-disposition table from FD. Group every region's findings, apply the fixed precedence once, and test multiple simultaneous cosmetic findings without a second-attempt segment drop. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-grouped-region-dispositions.md`.
- [x] Prove a malformed required watchpoint section is safely replaced without losing `## ⑥`, and malformed optional chart/visual blocks do not drop the segment. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-required-optional-containment.md`.
- [x] Remove both current entity-drop paths from `GenerateStage` and `_stage_publish_segments`; run `scan_entity_fact_claims(..., entity_observed_at_utc)` once in terminal validation. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-terminal-entity-fact-gate.md`.
- [x] Move the existing pure daily-thesis survivor decision from `orchestrator.bundle_context` to `_internal.daily_thesis_decision`; each fixed-point pass branches `None -> None`, otherwise recomputes and validates the active context before assembly. Publisher must not import orchestrator. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-active-daily-thesis-fixed-point.md`.
- [x] Use existing `gate_body_assertions()` in assembly for deterministic repair and add exact read-only `scan_anchor_assertions(markdown, *, segment, available_symbols) -> tuple[AnchorAssertionFinding, ...]` for terminal validation. Keep `enforce_anchor_assertions()` only as a compatibility wrapper with zero default segmented call sites. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-terminal-numeric-anchor-scan.md`.
- [x] Keep `repair_compliance_language()` in assembly and `scan_compliance()` read-only at the terminal gate; remove duplicate/interleaved reader-format ownership after characterization. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-compliance-repair-terminal-scan.md`.
- [x] Register `PublicDocumentFinalizationError` in `_PUBLISH_FAILURES` and `EXCEPTION_ROUTING` with publish-stage alert/status semantics. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-finalization-error-routing.md`.
- [x] Replace the orchestrator's surface catch/drop retry with one `finalize_public_bundle` call; hard-block fixed-point and outcome creation live inside the pure finalizer. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-production-finalizer-switch.md`.
- [x] Preserve rollback for failures that occur later during actual I/O. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-4-staged-promotion-rollback.md`.

### Step 5 — Preserve partial publication and switch to sealed documents

- [x] Switch segmented writer to `write_finalized_document`. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-sealed-writer-switch.md`.
- [x] Pass finalized bytes to index, OG, evidence accounting, quality snapshot, replay, and notifier summary consumers without mutation. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-sealed-consumer-view.md`.
- [x] Add canonical `extract_watchlist_impact()` beside `extract_conclusion()`, move notifier text cleanup to neutral `_internal.public_summary_extract`, and derive `PublicNotificationSummary` inside terminal validation from final layout bytes plus typed coverage. Store it on validated E2; seal only copies it. Missing/unsafe conclusion is a survivor-attempt trust block. Default segmented `build_segmented_summary(summaries, ...)` accepts DTOs/URLs/existing typed lookahead and price inputs only, checks key/segment/date identity, and cannot read a `Briefing` or fall back to generated `market_summary`. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-notifier-dto-boundary.md`.
- [x] Extend `PipelineResult` with backward-compatible typed `content_completeness` and per-segment outcomes. Preserve u63 absence navigation for one/two-document E6. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-content-completeness-result.md`.
- [x] Map complete success to exit 0, content-partial to exit 2, zero-document/bundle failure to exit 1, and complete-content notifier-only partial to exit 0. Content-partial severity wins if notification also fails. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-content-aware-exit-codes.md`.
- [x] Update `daily-briefing.yml`: wrapper captures the pipeline rc and `$GITHUB_OUTPUT`; Pages runs when `publication_committed=true`; a final `if: always()` step re-emits rc 1/2 after Pages. Add workflow contract tests. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-workflow-pages-sequencing.md`.
- [x] Extend GitHub step summary with expected/finalized/published counts, content completeness, and bounded finalization codes. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-github-summary-diagnostics.md`.
- [x] Update the `daily-briefing.yml` contract header, `aidlc-docs/inception/application-design/component-methods.md`, and `docs/DESIGN.md` so the finalizer, sealed consumer, notifier DTO, and exit/Pages sequence are the documented production owners. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-5-production-owner-documentation.md`.

### Step 6 — Composition/property tests and full validation

- [x] Add idempotence tests: finalizing already-finalized equivalent input is byte-stable or rejected as an explicit phase misuse; no duplicate block/disclaimer/nav. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-idempotence-phase-misuse.md`.
- [x] Add transform-closure tests: every producer in the documented assembly call graph followed by terminal projection/repair yields zero public-label leaks on generated token matrices. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-transform-closure.md`.
- [x] Add partial fixed-point tests: initial generation absence, `bundle_context=None`, one hard-trust block, notification-summary hard block, two sequential hard blocks, zero survivors, canonical u63 nav, and a strict maximum of three passes. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-partial-fixed-point.md`.
- [x] Add active-survivor thesis tests proving a removed segment is absent from support/wording on the next pass without a publisher→orchestrator import. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-active-survivor-thesis.md`.
- [x] Add watchpoint result tests for rendered/limited count/reason invariants and notifier tests for DTO key/segment/date mismatch, typed failed-coverage collapse, sealed watchlist decoration, missing conclusion hard block, and unsafe generated `market_summary` being unreachable when sealed Markdown is safe. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-watchpoint-notifier-invariants.md`.
- [x] Add region-table contract tests for every spec, empty/non-empty anchor inputs, supplement marker pairing, explicit marker-shell omission with no E5 artifact, duplicate/overlap/missing markers, residual partition coverage, stable IDs after replacement, and reader-visible tables. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-region-table-contracts.md`.
- [x] Add staging tests proving E8 leaves every public destination byte-identical and removes the temporary root; promotion failure exercises existing rollback. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-staging-rollback.md`.
- [x] Add Hypothesis tests for forbidden-label combinations, delimiter balance, block fallback determinism, and stable issue ordering. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-hypothesis-properties.md`.
- [x] Run focused, full, static, import-boundary, no-paid, and strict MkDocs gates. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-6-full-quality-gates.md`.

### Step 7 — Production closeout

- [x] Write the unit code summary and update DESIGN.md with the finalization/seal boundary. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/summary.md`.
- [x] Commit/push the implementation as one bounded unit or one commit per completed step according to the active user instruction. The per-step wave, runtime repairs through `39381dc`, and production bot commit `e3c8b2f` are synchronized on `origin/main`.
- [x] Rerun the exact failed `target_date=2026-07-17` and one current normal date. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-7-production-closeout.md`.
- [x] Verify `ok=3 failed=0`, all three archive paths, commit/push, notifier result, internal `status=success`, daily workflow conclusion, and separate Pages success. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-7-production-closeout.md`.

### Step 8 — Close post-implementation review gaps

This corrective slice reuses the approved FD/NFR contracts; it does not add a
new product workflow, external dependency, persisted schema, or infrastructure
resource. Functional Design and NFR Requirements therefore remain complete.
The user approved this complete five-item corrective sequence on 2026-07-22
with: "위 개선 안건들을 u144에 반영하고 작업 진행하자".

- [x] Wire the existing owned-region public-label traversal and the canonical full-document surface scan into terminal validation. Reader-visible tables must be checked, and any residual/unowned blocker must fail closed before notifier DTO derivation.
- [x] Remove silent whole-document surface repair from the production assembly/repair path. Every repair/replacement/omission must start from an owned finding and append one `PublicBlockOutcome`; residual blocking findings still fail closed after the single bounded attempt.
- [x] Carry typed `SegmentFinalizationOutcome` values into the segmented notifier, render generation absence and trust-blocked absence with distinct public copy, and emit a bounded publish-stage operator alert for each committed trust-blocked outcome.
- [x] Make pre-git rollback failures observable as `PublisherIOError`, restore prior bytes atomically, continue best-effort restoration of the remaining snapshot set, and preserve the existing no-rollback claim after git begins.
- [x] Introduce one typed per-segment producer plan for each active-survivor pass and reuse its payload/eligibility decisions for both assembly and `PublicRegionExpectation`; add focused regressions and run the full U-144 quality gate. Evidence: `aidlc-docs/construction/u144-public-document-finalization-contract/code/step-8-review-corrections.md`.

## Acceptance Criteria

1. **AC-144.1**: Default segmented production has exactly one `finalize_public_bundle` call and no reader-facing archive/index/quality write or git staging before it succeeds. Existing private operational state files are explicitly outside E5/E6.
2. **AC-144.2**: No production code mutates finalized Markdown or calls `Briefing.model_copy(update={"rendered_markdown": ...})` after sealing.
3. **AC-144.3**: The run-29707052598 crypto fixture publishes reader-safe watchpoint copy with zero `public_diagnostic.raw_label` findings.
4. **AC-144.4**: Public projection runs after the documented assembly call graph. An AST/rg allowlist test fails when production adds a direct `rendered_markdown` mutation/construction outside the finalizer/legacy compatibility allowlist; it does not claim arbitrary semantic helper detection.
5. **AC-144.5**: Raw diagnostic labels remain available in protected diagnostics/structured metadata and do not appear in reader-visible regions.
6. **AC-144.6**: Optional presentation block defects are replaced/omitted deterministically and do not remove the segment.
7. **AC-144.7**: Numeric-anchor, entity-fact, residual compliance, required-structure, and disclaimer failures create a typed `trust_blocked` segment outcome; they are never downgraded to presentation fallback.
8. **AC-144.8**: A known generation absence or trust block may produce the intentional u63 one/two-segment commit, but it is typed content-partial, emits operator diagnostics, exits 2, triggers Pages for the committed subset, and leaves the daily workflow red. Zero survivors exit 1 with no public commit.
9. **AC-144.9**: Notifier-only failure remains PARTIAL/exit 0 and does not alter the already-published finalized bytes.
10. **AC-144.10**: `write_finalized_document` rejects checksum/date/segment/disclaimer mismatch before touching the destination.
11. **AC-144.11**: Finalization is deterministic, idempotent at the supported boundary, and performs no I/O/network/env/clock/subprocess access.
12. **AC-144.12**: Existing u100/u108/u112/u123/u127 specialized contracts remain single-owned; u144 adds no duplicate scanner, wording table, evidence parser, or summary predicate.
13. **AC-144.13**: u114 import-boundary tests, full mypy, Ruff, pytest, no-paid guard, and MkDocs strict build pass.
14. **AC-144.14**: Exact-date production replay publishes all three segments and the chained Pages workflow succeeds before the unit is marked complete.
15. **AC-144.15**: Every current surface issue code has one exhaustive block-aware disposition. Multiple findings in one region are grouped and resolved once by fixed precedence; duplicated evidence is contained by region ID, and an unowned blocker fails the affected segment closed.
16. **AC-144.16**: Finalization reads the existing typed coverage and explicit timezone-aware entity observation instant; it reads no wall clock and no limitation state from Korean prose.
17. **AC-144.17**: Pre-finalization assets exist only in a run-owned staging root. Finalization failure changes no public destination; successful promotion participates in existing rollback.
18. **AC-144.18**: E1 supplement artifact IDs are referentially valid; marker-shell omission remains structurally valid but contributes no E5 ID; every non-omitted surviving E5 freezes its exact IDs; E6 promotion manifest equals their ordered union; absent/blocked/omitted artifacts are never promoted.
19. **AC-144.19**: Each survivor pass recomputes daily thesis for the active tuple through the shared neutral owner; removed segments cannot remain in support, wording, or distinctness validation.
20. **AC-144.20**: Watchpoint availability reaches projection only through `WatchpointRenderResult`; the limited state yields the typed reason and no raw sentinel default.
21. **AC-144.21**: Default segmented notification is built only from E5 `PublicNotificationSummary` plus URLs and existing typed lookahead/price inputs. DTO identity/date is checked; conclusion/watchlist come only from validated layout, coverage fields come from E1, missing/unsafe conclusion hard-blocks inside terminal validation and participates in survivor fixed-point/nav/thesis recomputation, and generated `Briefing.market_summary` cannot reach Telegram after finalization.
22. **AC-144.22**: Every canonical region has a fixed `RegionSpec` and every active pass has a typed `PublicRegionExpectation`; duplicate/overlap/missing/unclaimed layouts and missing expected conditional regions fail deterministically, while replacement preserves the expectation and performs a full stable reindex.
23. **AC-144.23**: Terminal validation invokes the canonical reader-visible leakage traversal and the canonical full-document surface scan exactly as read-only gates; a reader-visible table leak or unowned/cross-region blocking surface finding cannot seal.
24. **AC-144.24**: A deterministic surface repair that changes final Markdown always has one matching redacted `PublicBlockOutcome`; production assembly performs no unrecorded surface repair and the bounded repair phase performs no unowned whole-document rewrite.
25. **AC-144.25**: A committed content-partial bundle emits bounded operator diagnostics for every `trust_blocked` outcome, while public Telegram copy distinguishes `generation_absent` from `trust_blocked` without exposing issue codes or rejected prose.
26. **AC-144.26**: Pre-git rollback restores existing bytes with the shared atomic byte writer, reports unlink/restore failure as `PublisherIOError`, and still attempts the remaining snapshot entries; rollback failure is never silently suppressed.
27. **AC-144.27**: Each active survivor pass constructs one typed producer plan whose rendered payloads and eligibility booleans feed both assembly and `PublicRegionExpectation`; the production path does not independently recompute conditional-region eligibility.

## Tests / Validation

```bash
uv run --extra dev pytest \
  tests/unit/publisher/test_public_document.py \
  tests/unit/publisher/test_public_document_staging.py \
  tests/unit/publisher/test_segment_reader_surface_quality.py \
  tests/unit/publisher/test_watchpoint_matrix.py \
  tests/unit/publisher/test_writer.py \
  tests/unit/orchestrator/test_run_pipeline.py \
  tests/unit/orchestrator/test_main.py \
  tests/unit/orchestrator/test_daily_workflow_contract.py \
  tests/integration/test_briefing_reader_format.py \
  tests/integration/test_bundle_reconciliation.py \
  tests/integration/test_pipeline.py

uv run --extra dev pytest
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src
uv run python scripts/check_no_paid_apis.py
uv run --extra docs mkdocs build --strict
git diff --check
```

Production closeout:

```bash
gh workflow run daily-briefing.yml --ref main -f target_date=2026-07-17
RUN_ID="$(gh run list --workflow daily-briefing.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --log
gh run list --workflow pages.yml --limit 3
```

## Rollout / Rollback

- Land steps in order; do not keep two production finalization paths behind a long-lived environment flag.
- The switch occurs only after characterization and sealed-writer tests are green.
- Rollback is a commit revert to the pre-switch call graph. Final document bytes and archive format remain Markdown-compatible; no data migration is required.
- Per-run destination snapshots cover promotion/write/quality failures before git. Once existing commit/push begins, `PublisherGitError` keeps its current recovery semantics; u144 adds no automatic history rewrite.
- If an issue-specific planned unit lands concurrently, rebase its producer into phase 1 rather than reintroducing an after-seal call.

## Non-Goals

- No new Markdown parser or full AST.
- No LLM copy-edit pass.
- No source/data-quality policy change.
- No weakening of compliance, numeric, entity, disclaimer, or surface blockers.
- No historical archive rewrite.
- No Telegram API or Pages architecture change.
- No generic replacement for specialized validators.
