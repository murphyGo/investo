# Tech-Stack Decisions - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `aidlc-docs/construction/plans/u144-public-document-finalization-contract-code-generation-plan.md`

`TS-1`-`TS-9` are binding implementation decisions.

---

## TS-1. Publisher owns the lifecycle

- **Decision**: lifecycle types and `finalize_public_bundle` live under
  `src/investo/publisher/public_document.py` (or a same-name publisher
  subpackage if the implementation warrants separation).
- **Rationale**: the lifecycle is a publishing concern. Orchestrator may import
  publisher; placing the behavior in models would make the shared leaf own
  behavior and dependencies it should not know.
- **Constraint**: if a type must cross directly into notifier/another sibling,
  promote only that frozen DTO to models under u114 rules. Do not move finalizer
  behavior.

## TS-2. Typed lifecycle envelope, not a full Markdown AST

- **Decision**: use frozen/slotted lifecycle/context/outcome types plus bounded
  known block ownership. Keep block bodies as Markdown strings.
- **Rationale**: the root defect is uncontrolled ordering and string-encoded
  state. A full CommonMark AST would multiply migration risk and dependencies
  without being necessary to create a true terminal boundary.
- **Constraint**: do not perform arbitrary whole-document deletion when a block
  cannot be localized; fail closed. Implement the FD `RegionSpec` table and
  invisible supplement marker pairs exactly; do not add ad hoc `str.find`
  evidence heuristics. Optional supplement omission empties the body while
  preserving its marker shell and explicit E7 outcome.

## TS-3. Reuse existing specialized validators

- **Decision**: continue using u85's validation envelope where it already fits
  and the existing u100/u108/u112/u123/u127/numeric/entity/compliance APIs.
- **Rationale**: those policies have separate inputs and owners. u85 already
  documented that flattening every interleaved transform/gate into one generic
  registry is the wrong abstraction.
- **Constraint**: u144 owns phase/order/disposition, not validator internals.

## TS-4. SHA-256 seal with existing atomic writer

- **Decision**: seal UTF-8 Markdown with stdlib `hashlib.sha256`; writer
  recomputes before existing `write_atomic` execution.
- **Rationale**: a content digest is deterministic, dependency-free, and proves
  that validated bytes equal written bytes.
- **Constraint**: digest is integrity metadata, not a security signature. No
  key, HMAC, sidecar file, or archive schema change.

## TS-5. Typed partial bundle and atomic valid-subset transaction

- **Decision**: default segmented mode computes one terminal outcome per
  expected segment and constructs a non-empty E6 in memory before the existing
  publish transaction starts. One/two valid documents preserve u63/u94 partial
  publication and are committed atomically as the valid subset.
- **Rationale**: presentation fallback should keep its segment; a real
  truth/safety failure may use the intentional absence UX but must not look
  operationally green.
- **Constraint**: zero survivors fail before public writes. Reuse current
  filesystem snapshot/rollback for promotion/write/quality failures. Preserve
  current `PublisherGitError` recovery semantics after commit/push begins; do
  not claim or implement automatic git-history compensation in u144.

## TS-6. No long-lived feature flag

- **Decision**: characterize old behavior in tests, then switch production to
  the single finalizer path. Rollback is a commit revert.
- **Rationale**: two active post-processing paths would inevitably drift and
  recreate the defect.
- **Constraint**: temporary test-only comparison helpers are removed or kept
  non-production before closeout.

## TS-7. Prompt and public wording share the existing neutral owner

- **Decision**: briefing prompt/default code may import reader-safe constants
  from `_internal.public_quality_language`; publisher final projection uses the
  same owner.
- **Rationale**: publisher-specific types cannot be imported by briefing, while
  `_internal` is already the neutral u108 contract surface.
- **Constraint**: no duplicate Korean wording table in prompt, watchpoint, or
  finalizer modules.

## TS-8. Workflow preserves Pages while making content-partial red

- **Decision**: complete content is exit 0, content-partial is exit 2, and
  zero-document/E8 failure is exit 1. Notifier-only `PARTIAL` remains exit 0.
  `daily-briefing.yml` captures the rc/output, dispatches Pages only when
  `publication_committed=true`, then re-emits rc 1/2 in a final `always()` step.
- **Rationale**: u63/u94 intentionally publish valid sibling segments. The
  pipeline commit must still reach Pages, but content omission must alert as a
  red daily run.
- **Constraint**: no new job/workflow/service. Content-partial severity wins
  over notifier failure, and a hard failure with no commit never dispatches
  Pages.

## TS-9. Zero dependency/infrastructure delta

- **Decision**: use Python stdlib and existing project modules. No third-party
  parser, SDK, service, storage format, secret, environment variable, or paid
  API.
- **Rationale**: finalization is deterministic in-process composition and
  validation.

## TS-10. Run-owned artifact staging

- **Decision**: pre-finalization visual/chart/carryover writers target a
  `TemporaryDirectory` owned by the orchestrator and return relative public
  path, staged path, and SHA-256. Promotion happens inside the existing publish
  transaction only after E6.
- **Rationale**: current asset helpers write public files before finalization,
  contradicting zero-public-destination guarantees.
- **Constraint**: finalizer remains I/O-free. Staging is removed in `finally`;
  staged paths cannot escape the owned root; only survivor-referenced assets
  in the E6 promotion manifest are promoted. E1 supplement IDs, non-omitted E5
  survivor IDs, and E6 descriptors form one referential-integrity chain.

## TS-11. Neutral survivor-thesis owner and sealed notification DTO

- **Decision**: move the existing pure active-segment thesis redecision to
  `_internal.daily_thesis_decision`; orchestrator and publisher reuse it.
  Place `PublicNotificationSummary` in `models/public_notification.py`, while
  publisher owns derivation/validation and notifier owns rendering/delivery.
- **Rationale**: publisher cannot import orchestrator, and notifier cannot
  safely fall back to generated `Briefing.market_summary` after archive bytes
  have been finalized.
- **Constraint**: every fixed-point pass recomputes the active thesis. Default
  `BundleContext=None` stays `None`; otherwise active-thesis validation runs
  before assembly. Notification DTO derivation runs inside terminal validation
  so failure returns to the fixed point; seal only copies the validated DTO.
  Default
  segmented notifier accepts DTOs plus URLs and existing typed lookahead/price
  inputs only. DTO conclusion/watchlist derive from validated layout,
  coverage status/label derive from E1, and key/segment/date identity is
  checked. The legacy unsegmented fallback remains isolated and
  architecture-tested.

---

**Net third-party dependency delta**: none.
**Net external service/secret delta**: none.
**Net archive format delta**: none.
**Net workflow resource delta**: none; one existing workflow step sequence changes.
