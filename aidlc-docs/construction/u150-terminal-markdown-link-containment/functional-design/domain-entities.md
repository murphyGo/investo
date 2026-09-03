# Domain Entities - `u150 terminal-markdown-link-containment`

**Date**: 2026-09-03
**Status**: Approved for Code Generation on 2026-09-03
**Source**: approved answers `A / B / A / A / A`; u150 business logic model and business rules; u112 surface-quality types; u144 public-document entities; u149 numeric-containment boundary

u150 introduces no public or persisted domain entity. It adds one closed internal value type, amends two internal scanner/validation records, and reuses the u144 finalization entities. The purpose is to carry only the minimum information needed to select one safe owned-region action while keeping target text and evidence outside outcomes, errors, logs, and artifacts.

## 1. Entity decision summary

| Concept | Decision | Public or persisted | Reason |
| --- | --- | --- | --- |
| `SurfaceLinkShape` | Add closed internal value type | No | Policy must distinguish recoverable links, reference definitions, and residual malformed fragments without receiving target text. |
| `SurfaceQualityIssue.link_shape` | Add optional field with default `None` | No | The canonical scanner, not the finalizer, owns syntax classification. The default preserves existing four-argument construction. |
| `_OwnedSurfaceQualityFinding` | Reuse unchanged | No | It already binds one canonical issue to exactly one owned region and block. |
| `_RegionDispositionDecision` | Reuse its redacted fields; amend semantic validation | No | Shape-aware selection consumes full findings, but the one-action plan needs only region, block, canonical codes, and selected disposition. |
| `PublicDocumentRegion` / `PublicDocumentLayout` | Reuse unchanged | No new schema | Existing ownership, span, heading, and projection invariants define the only mutation boundary. |
| `PublicBlockOutcome` | Reuse unchanged | Existing typed output only | It already records one redacted action per region without evidence or target data. |
| `_TerminalHardGateSnapshot` | Add canonical residual-actionable link codes | No | The final error builder must add `document.fallback_exhausted` only when a permitted action failed to close a link finding. |
| Final document, segment, and bundle entities | Reuse unchanged | Existing contract | Link containment changes presentation bytes, not segment-state or delivery semantics. |

## 2. E1 - `SurfaceLinkShape`

`investo._internal.surface_quality` owns this closed value type:

```python
SurfaceLinkShape = Literal[
    "inline_link",
    "image",
    "autolink",
    "reference_definition",
    "incomplete_inline",
    "unmatched_residual",
]
```

This is an internal classification value, not a new business aggregate, public DTO, serialized enum, or persistence key.

### Invariants

- The set is exhaustive for the two u150 link codes and has no `unknown` or free-text member.
- A scanner finding receives exactly one shape or fails closed before policy selection.
- Shape assignment is deterministic from the canonical scanner's already-matched syntax.
- The value contains no label, alt text, target, reference identifier, line content, offset, hash, or evidence-derived length.
- Policy compares literal shape values only; it never reruns regexes or parses Markdown.
- The declaration order is not a business precedence. Disposition precedence remains the existing u144 order.

## 3. E2 - amended `SurfaceQualityIssue`

The existing immutable scanner record gains one backward-compatible field:

```python
@dataclass(frozen=True, slots=True)
class SurfaceQualityIssue:
    code: str
    severity: SurfaceIssueSeverity
    evidence: str
    region: SurfaceIssueRegion
    link_shape: SurfaceLinkShape | None = None
```

### Code-to-shape relation

| Issue code | Permitted `link_shape` values |
| --- | --- |
| `markdown.href_ellipsis` | `inline_link`, `image`, `autolink`, `reference_definition` |
| `markdown.unmatched_link` | `incomplete_inline`, `unmatched_residual` |
| Every other registered surface code | `None` only |

### Finding cardinality

- Each non-overlapping closed invalid-target occurrence produces one `markdown.href_ellipsis` issue in stable line order and left-to-right span order. A later reference definition or autolink on the same line may not be hidden by an earlier inline link.
- `markdown.unmatched_link` remains a line-level structural issue. It is `incomplete_inline` only when every unmatched construct on that line is accepted by the canonical recoverable-fragment owner and a read-only trial of the pure transform closes the unmatched-link predicate without changing unrelated bytes.
- A mixed, overlapping, partially covered, or still-unmatched line is one `unmatched_residual` issue and selects the region's unrecoverable disposition before mutation.
- Scanner emission may contain repeated issue codes. Deduplication occurs only in the redacted region decision and terminal code tuples, never before every shape has contributed to policy selection.

### Invariants

- `link_shape=None` is valid for non-link findings and preserves existing constructors and call sites.
- A u150 link finding may not leave the canonical scanner with `link_shape=None`.
- A shape that is incompatible with its issue code is an invariant failure, never a best-effort repair.
- Closed-match classification order and line-level unmatched classification are fixed; regex registration or mapping iteration order cannot change the emitted shapes.
- `evidence` remains transient scanner-private data required by existing detection and exact-span transformation. It is not copied to policy inputs, outcomes, terminal snapshots, exceptions, logs, workflow summaries, fixtures derived from production, or public artifacts.
- `link_shape` authorizes no mutation by itself. Ownership and the exhaustive block/shape policy must also succeed.
- Equality remains value equality. Equal input bytes and scanner configuration produce equal issue sequences including shapes.

## 4. E3 - reused `_OwnedSurfaceQualityFinding`

The existing record remains structurally unchanged:

```python
@dataclass(frozen=True, slots=True)
class _OwnedSurfaceQualityFinding:
    region_id: str
    block: PublicBlockKind
    issue: SurfaceQualityIssue
```

### Invariants

- `region_id` is non-empty and identifies exactly one region in the same `PublicDocumentLayout` snapshot.
- `block` equals the identified region's block kind.
- The finding is created from the pre-mutation projected bytes; it is never reacquired by searching for its evidence.
- Every closed invalid-target occurrence contributes its own finding, while one unmatched line contributes its one whole-line recoverability class.
- An unowned, multiply owned, stale, or block-mismatched finding raises the existing finalization invariant path.
- The record may temporarily carry scanner evidence through `issue`, but no downstream redacted entity copies that evidence.
- Findings are consumed in canonical layout-region order. Input mapping or scanner emission order cannot affect the selected action.

## 5. E4 - shape-aware policy input and region decision

`FinalizationIssueDisposition` and its precedence remain unchanged:

`block_segment > omit_optional_block > replace_block > repair > record_warning`

Policy resolution is amended from a lossy `(issue_code, block)` lookup to a finding-aware lookup:

- non-link findings use the existing `(issue_code, block)` table;
- u150 link findings use `(issue_code, block, link_shape)`;
- a missing or unregistered combination returns `block_segment` and fails the exhaustiveness test;
- policy receives no `evidence` value and performs no syntax inspection.

The existing redacted decision remains:

```python
@dataclass(frozen=True, slots=True)
class _RegionDispositionDecision:
    region_id: str
    block: PublicBlockKind
    issue_codes: tuple[str, ...]
    disposition: FinalizationIssueDisposition
```

### Amended construction rule

The private resolver is the sole semantic factory. It validates ownership, evaluates every full finding through the shape-aware policy, selects the strongest requested disposition, canonicalizes the issue codes, and only then discards evidence and shape detail when constructing the decision.

The decision's `__post_init__` continues to validate the identifier, block, non-empty canonical code tuple, and supported disposition. It no longer recomputes the disposition from only `(issue_codes, block)`, because that redacted pair intentionally cannot distinguish `incomplete_inline` from `unmatched_residual`. The resolver and exhaustive policy tests own that semantic invariant.

### Decision invariants

- Exactly one decision exists per affected `region_id`.
- `issue_codes` is sorted, unique, non-empty, and machine-readable.
- `disposition` equals the strongest result from every finding in the group.
- The decision retains no shape collection, evidence, target, Markdown, source payload, line number, or content-derived fingerprint.
- All actions read the original region body. A stronger replacement or omission prevents a weaker repair from running first.
- Duplicate action attempts for a region remain `document.fallback_repeat`.

## 6. E5 - reused layout and action outcome entities

`PublicDocumentRegion`, `PublicDocumentLayout`, and `PublicBlockOutcome` are reused without field changes. Their existing relationship is:

```text
PublicDocumentLayout
  -> ordered PublicDocumentRegion
       -> zero or more pre-mutation owned findings
       -> exactly zero or one region decision
       -> exactly zero or one successful PublicBlockOutcome
```

`PublicBlockOutcome` remains:

```python
@dataclass(frozen=True, slots=True)
class PublicBlockOutcome:
    region_id: str
    block: PublicBlockKind
    disposition: PublicBlockDisposition
    issue_codes: tuple[str, ...] = ()
```

### Outcome invariants

- `region_id` and `block` identify the acted-on canonical region.
- `issue_codes` is sorted and unique through the existing canonicalizer.
- One region contributes at most one outcome.
- `repair`, `replace_block`, `omit_optional_block`, and `record_warning` map respectively to the existing `repaired`, `replaced`, `omitted`, and `kept` values.
- A blocked or failed action does not fabricate a successful outcome.
- Replacement of a reference definition or residual fragment is recorded as `replaced`, never `repaired`.
- The outcome contains no `link_shape`, evidence, target, label, alt text, Markdown, source payload, secret, or failure-only location detail.
- Outcome ordering follows canonical layout order and is independent of finding order.

The existing region boundaries remain authoritative. A section-body replacement preserves its H2, a watchpoint replacement preserves `## ⑥`, optional omission preserves its marker shell and artifact-selection contract, and clean sibling regions remain byte-identical.

## 7. E6 - amended `_TerminalHardGateSnapshot`

The read-only terminal snapshot gains a bounded subset that distinguishes action exhaustion from an ordinary protected link failure:

```python
@dataclass(frozen=True, slots=True)
class _TerminalHardGateSnapshot:
    issue_codes: tuple[str, ...]
    residual_actionable_link_codes: tuple[str, ...]
    notification_summary: PublicNotificationSummary | None
```

### Invariants

- Both code tuples are sorted, unique, and machine-readable.
- `residual_actionable_link_codes` is a subset of `issue_codes`.
- Its members are limited to `markdown.href_ellipsis` and `markdown.unmatched_link`.
- A member is included only when the post-action canonical finding maps to `repair`, `replace_block`, or `omit_optional_block` under the exhaustive shape-aware policy. A protected or unknown combination that maps directly to `block_segment` is not action exhaustion.
- The snapshot contains no scanner finding, evidence, region identifier, shape, URL, Markdown, source payload, exception text, or secret.
- Terminal collection remains exhaustive and read-only; notification-summary derivation does not short-circuit another hard gate.

The final failure-code builder computes:

```text
issue_codes
+ {document.fallback_exhausted if residual_actionable_link_codes is non-empty}
```

and canonicalizes the union once. If containment cleared every actionable link finding, the generic marker is absent even when another hard gate fails. If residue and another hard defect coexist, both code families survive.

## 8. E7 - reused finalization and bundle entities

The following existing entities and errors receive no field or state change:

- `_SegmentTrustBlockedError`;
- `PublicDocumentFinalizationError`;
- `FinalizedPublicDocument`;
- `SegmentFinalizationOutcome`;
- `FinalizedPublicBundle`.

`FinalizedPublicDocument.block_outcomes` already carries the successful presentation actions. No parallel link-containment outcome is added.

### State invariants

- A link-only repair, replacement, or omission that clears every terminal gate seals through the existing `validated -> FinalizedPublicDocument` boundary.
- Its segment state remains `finalized`.
- `finalized_degraded` remains exclusive to u149's non-empty `numeric_containment_outcomes`; link containment alone can never select it.
- No `finalized_link_degraded`, `link_repaired`, or other segment state is introduced.
- Protected, unowned, policy-unavailable, residual, or simultaneously hard-defective documents use the existing `trust_blocked` path.
- Bundle survivor count, exit status, Pages dispatch, Telegram behavior, and publication rules remain unchanged.
- Sealed Markdown, digest, staged artifact IDs, notification summary, block outcomes, and numeric outcomes remain the only existing final-document contract.

## 9. Lifecycle and relationship constraints

| Phase | Entity state | Allowed transition |
| --- | --- | --- |
| `projected` | Layout plus pre-mutation shaped findings | Group into one decision per owned region. |
| region decision | Redacted decision over original body | Apply exactly one action or fail closed. |
| `repaired` candidate | Updated layout plus ordered block outcomes | Reproject, re-index, and scan read-only. |
| terminal snapshot | Complete hard codes plus residual-actionable subset | Raise bounded failure or attach notification summary and validate. |
| `validated` | No hard code remains | Seal once using the existing factory. |
| sealed | Immutable final document | Existing bundle and delivery flow only; no mutation. |

Additional constraints:

- Transformed bytes never become the generated input to a new survivor iteration.
- No presentation action occurs after terminal collection begins.
- A replacement body is obtained only from an existing registered owner; missing ownership yields `document.fallback_unavailable`.
- Valid links and protected clean bytes never enter a u150 mutation result.
- Equal projected bytes, layout expectation, and context produce equal shapes, decisions, outcomes, terminal codes, Markdown, and seal digest.

## 10. No-new-entity decisions

| Rejected entity or field | Reason |
| --- | --- |
| `LinkRepairOutcome` | Duplicates `PublicBlockOutcome` and would split the existing presentation-action ledger. |
| `LinkTarget`, `RecoveredUrl`, or redirect result | Target completion, resolution, fetching, and retention are outside scope and violate the disclosure boundary. |
| Reference definition/use graph | Cross-region joining is explicitly rejected; each region is evaluated independently. |
| Evidence or Markdown DTO | Would allow blocked content to escape the canonical scanner boundary. |
| Shape list on `PublicBlockOutcome` | Public action consumers need codes and disposition only; shape is an ephemeral policy input. |
| New fallback-copy entity | Every replacement reuses an existing u144/u98/u110 owner. |
| New segment or delivery state | Existing `finalized`, `trust_blocked`, survivor, and delivery semantics already express every u150 result. |
| New persistence table, archive schema, event, secret, or environment flag | The change is deterministic in-process finalization behavior only. |

## 11. Ordering, privacy, and compatibility rules

- Region decisions and public outcomes use canonical `PublicDocumentLayout.regions` order.
- Issue-code tuples use `_canonical_issue_codes`: sorted, unique, non-empty where required, and machine-readable.
- Shape values are never sorted into or serialized with a public outcome; they disappear after private policy resolution.
- Repair spans are composed left to right from one original region body. This span order is transformation order, not outcome order.
- Failure surfaces may contain only target date, segment, phase, and bounded issue codes under the existing exception/logging contract.
- Existing four-positional-field `SurfaceQualityIssue` construction remains valid because `link_shape` defaults to `None`; link scanners must set it explicitly for the two u150 codes.
- Existing serialized/public structures require no migration because none gains a field.
- u112 remains canonical detector owner, u144 remains finalizer and block-outcome owner, and u149 remains numeric-degradation owner.

## 12. Validation and traceability

| Design rule | Entity proof |
| --- | --- |
| R1-R3 canonical ownership and closed shapes | E1, E2, and E3 prevent a finalizer-local parser or free-text classification. |
| R4 exact recoverable output | E2 carries scanner-owned shape; transformation still consumes transient exact-span evidence privately. |
| R5-R9 protected regions and one strongest action | E3, E4, and E5 bind findings to one owner, one decision, and one redacted outcome. |
| R10-R12 read-only closure and bounded residual codes | E6 records only canonical hard codes and the residual-actionable subset. |
| R13 determinism | Closed literals, canonical region order, canonical issue-code order, and immutable records remove input-order dependence. |
| R14 existing segment/bundle semantics | E7 adds no state and preserves u149's exclusive `finalized_degraded` condition. |
| R15 example/PBT contract | Generate domain-valid shape/body pairs; assert transform closure, idempotence, valid-link stability, ordering, and non-disclosure. |
| R16-R17 qualification and non-goals | No persistence, dependency, source, network, secret, prompt, or infrastructure entity is introduced. |

Property tests do not require round-trip serialization because every new or amended u150 field is internal and ephemeral. Serialization tests remain focused on proving that existing final outcomes, workflow summaries, logs, exceptions, archives, and public artifacts never acquire shape, evidence, target, or Markdown fields.
