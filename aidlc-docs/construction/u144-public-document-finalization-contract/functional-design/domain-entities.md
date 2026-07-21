# Domain Entities - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `aidlc-docs/construction/plans/u144-public-document-finalization-contract-code-generation-plan.md`

This document defines the in-process contracts between generated `Briefing`
objects and the exact public bytes written by the publisher. It introduces no
new persisted file format: archives remain Markdown. Entities are numbered
`E1`-`E8`; invariants are `I1`-`I34`.

---

## E1. PublicDocumentContext

Immutable, explicit bundle input supplied by the orchestrator to the publisher
finalizer.

| Attribute | Type | Notes |
|---|---|---|
| `target_date` | `date` | Must equal every input briefing target date. |
| `expected_segments` | `tuple[MarketSegment, ...]` | Production default is `SEGMENT_ORDER`; order is canonical. |
| `input_absences` | `Mapping[MarketSegment, SegmentInputAbsence]` | Known generation failures for expected segments that have no briefing; values contain bounded codes only. |
| `anchors_by_segment` | `Mapping[MarketSegment, tuple[MarketAnchor, ...]]` | Reconciled u70 payload only. |
| `items_by_segment` | `Mapping[MarketSegment, tuple[NormalizedItem, ...]]` | Already-routed items; finalizer does no routing or collection. |
| `coverage_by_segment` | `Mapping[MarketSegment, SegmentCoverage]` | Existing typed coverage state used to derive E4 reasons; no Korean-copy parsing. |
| `source_outcomes` | `tuple[SourceOutcome, ...]` | Existing typed outcomes for limitation/evidence decisions. |
| `bundle_context` | `BundleContext | None` | Existing u57 shared macro/cause/thesis input. |
| `fact_bundle` | `VerifiedFactBundle` | Existing u101 entity-fact gate input. |
| `entity_observed_at_utc` | `datetime` | Existing timezone-aware run observation instant passed to `scan_entity_fact_claims`; finalizer never reads the clock. |
| `supplements_by_segment` | `Mapping[MarketSegment, tuple[PublicDocumentSupplement, ...]]` | Pre-rendered visual/chart/carryover Markdown in stable insertion order; defaults to an empty tuple per segment. |
| `staged_artifacts_by_segment` | `Mapping[MarketSegment, tuple[StagedArtifact, ...]]` | Typed temporary-file descriptors referenced by supplements; no file is opened by the finalizer. |

`PublicDocumentSupplement` is a publisher-boundary value, not an asset loader:

```python
PublicSupplementKind = Literal["visual", "chart", "carryover"]
SegmentInputAbsence = Literal["generation_failed"]

@dataclass(frozen=True, slots=True)
class StagedArtifact:
    artifact_id: str
    segment: MarketSegment
    kind: PublicSupplementKind
    relative_public_path: PurePosixPath
    staged_path: Path
    sha256: str

@dataclass(frozen=True, slots=True)
class PublicDocumentSupplement:
    supplement_id: str
    kind: PublicSupplementKind
    markdown: str
    stable_order: int
    artifact_ids: tuple[str, ...] = ()
```

The orchestrator adapts already-computed producer output into this value after
any asset/sidecar I/O. Placement remains owned by the existing kind-specific
publisher helper; the finalizer neither opens an asset nor guesses placement
from Markdown text.

**Invariants**

- I1. The context is frozen/slotted and contains inputs only.
- I2. Construction performs no I/O, environment read, clock read, routing, or
  source fetch.
- I3. `expected_segments` contains no duplicate and follows `SEGMENT_ORDER`.
- I4. A briefing key outside `expected_segments` is rejected as a programmer
  error. Every missing expected briefing must have exactly one `input_absences`
  entry; an unexplained missing key or an absence entry with a briefing is a
  programmer error.
- I5. The finalizer accepts this context, never an orchestrator
  `PipelineContext`.
- I5a. Supplement tuples are sorted by `(stable_order, kind, supplement_id)`
  and contain no duplicate `supplement_id` or `(stable_order, kind)` pair.
  `supplement_id` uses the same bounded lexical pattern as `artifact_id`.
  Empty/whitespace-only supplement Markdown is rejected rather than encoded as
  a conditional no-op. Supplement Markdown is not yet public authority and
  must pass projection, repair, and terminal validation.
- I5b. `entity_observed_at_utc` is timezone-aware. Coverage, anchor, item, and
  supplement mappings contain entries only for generated segments unless an
  existing canonical default is explicitly documented.
- I5c. `artifact_id` is unique across E1 and matches `[a-z0-9][a-z0-9._-]{0,127}`;
  SHA-256 is lowercase hexadecimal. `relative_public_path` is relative, contains
  no `..`, and is unique. Every supplement artifact ID exists in the same
  segment tuple with compatible kind; unreferenced staged descriptors are
  rejected before finalization. These are lexical/referential checks only;
  staged-path ownership and file digest are verified by the staging/promotion
  boundary outside the pure finalizer.
- I5d. Assembly wraps every non-empty supplement in exactly one canonical pair
  `<!-- investo:block {kind}:{supplement_id} -->` /
  `<!-- /investo:block {kind}:{supplement_id} -->`. The wrapper is generated
  from typed fields, never accepted from producer Markdown. The original
  supplement body must contain no `investo:block` comment.

## E2. PublicDocumentDraft

Publisher-private immutable lifecycle envelope around one generated briefing.

| Attribute | Type | Notes |
|---|---|---|
| `segment` | `MarketSegment` | Segment identity. |
| `target_date` | `date` | Copied from the generated briefing and checked against E1. |
| `source_briefing` | `Briefing` | Original u2 output; never modified. |
| `layout` | `PublicDocumentLayout` | Current pre-seal bytes plus re-indexed owned regions. |
| `phase` | `PublicDocumentPhase` | `generated`, `assembled`, `projected`, `repaired`, or `validated`. |
| `limitation_reasons` | `tuple[PublicLimitationReason, ...]` | Unique ordered reasons derived from typed coverage plus producer results such as watchpoints. |
| `block_outcomes` | `tuple[PublicBlockOutcome, ...]` | Append-only logical audit of bounded changes. |
| `notification_summary` | `PublicNotificationSummary | None` | `None` until terminal validation derives it; non-`None` in phase `validated`. |

```python
PublicDocumentPhase = Literal[
    "generated",
    "assembled",
    "projected",
    "repaired",
    "validated",
]
```

**Invariants**

- I6. A phase transition returns a new draft; no draft is mutated in place.
- I7. `from_generated()` creates phase `generated`; allowed transitions are
  exactly `generated -> assembled -> projected -> repaired -> validated`.
- I8. A validated draft has zero blocking terminal findings and a non-`None`
  `notification_summary` derived during terminal validation. Earlier phases
  have `notification_summary is None`.
- I9. `source_briefing` remains available for immutable section metadata, but
  its original `rendered_markdown` is not publishable after E2 exists.
- I10. Draft types are publisher-private and are not accepted by writer APIs.

## E3. PublicDocumentLayout, PublicBlockKind, and PublicBlockOutcome

Typed ownership/containment metadata for known public-document regions. This is
not a full Markdown AST: block bodies remain Markdown strings, but placement,
criticality, and fallback disposition are explicit.

```python
PublicBlockKind = Literal[
    "header",
    "navigation",
    "first_viewport",
    "visual",
    "anchor_table",
    "shared_macro",
    "crypto_indicators",
    "channel_anchors",
    "cause_map",
    "daily_thesis",
    "carryover",
    "chart",
    "section_body",
    "watchpoints",
    "diagnostics",
    "disclaimer",
]

PublicBlockDisposition = Literal[
    "kept",
    "repaired",
    "replaced",
    "omitted",
]

@dataclass(frozen=True, slots=True)
class PublicDocumentRegion:
    region_id: str
    block: PublicBlockKind
    required: bool
    projection_policy: Literal[
        "reader_visible",
        "protected_diagnostics",
        "exact_disclaimer",
    ]
    start: int
    end: int
    content_start: int
    content_end: int

@dataclass(frozen=True, slots=True)
class PublicRegionExpectation:
    target_date: date
    segment: MarketSegment
    segmented_mode: bool
    supplement_ids: tuple[str, ...]
    shared_macro_required: bool
    crypto_indicators_required: bool
    channel_anchors_required: bool
    daily_thesis_required: bool
    anchor_table_required: bool

@dataclass(frozen=True, slots=True)
class PublicDocumentLayout:
    markdown: str
    regions: tuple[PublicDocumentRegion, ...]
    expectation: PublicRegionExpectation

    def replace_region_body(
        self,
        region_id: str,
        replacement_body: str,
    ) -> "PublicDocumentLayout": ...

    def omit_optional_region(self, region_id: str) -> "PublicDocumentLayout": ...

    @classmethod
    def reindex(
        cls,
        markdown: str,
        *,
        expectation: PublicRegionExpectation,
    ) -> "PublicDocumentLayout": ...

@dataclass(frozen=True, slots=True)
class RegionSpec:
    id_pattern: str
    block: PublicBlockKind
    start_rule: str
    end_rule: str
    requirement: Literal["always", "conditional", "optional"]
    projection_policy: Literal[
        "reader_visible",
        "protected_diagnostics",
        "exact_disclaimer",
    ]
    repeatable: bool = False

@dataclass(frozen=True, slots=True)
class PublicBlockOutcome:
    region_id: str
    block: PublicBlockKind
    disposition: PublicBlockDisposition
    issue_codes: tuple[str, ...] = ()
```

**Invariants**

- I10a. Regions are discovered only from canonical headings/markers already
  owned by publisher helpers. They are unique, ordered, non-overlapping Python
  string-offset spans and are re-indexed after every whole-document producer.
  This is a bounded section index, not a general Markdown parser.
- I10b. Existing surface scanning runs once per owned region to create
  `(region_id, SurfaceQualityIssue)` findings, plus once over the fully rendered
  document for cross-region defects. A blocking finding that cannot be mapped
  to exactly one region fails closed; it is never repaired by an unbounded
  whole-document deletion.
- I10c. Projection and leakage traversal use `projection_policy`, never heading
  substring guesses at the terminal phase. Reader-visible tables remain
  `reader_visible`; only collapsed diagnostics are `protected_diagnostics` and
  canonical/short disclaimer regions are `exact_disclaimer`.
- I10d. `PublicRegionExpectation` is derived once per active-survivor pass from
  E1 plus that pass's recomputed bundle decision. Its booleans are the outputs
  of the existing pure producer-eligibility decisions, and assembly receives
  those same decisions; eligibility is not recomputed independently.
  `reindex()` uses it to decide conditional presence and exact
  title/disclaimer rules; it never guesses whether a missing conditional block
  was expected from Markdown. `BundleContext=None` makes macro/thesis flags
  false. A replacement retains the same expectation.
- I10e. `content_start/content_end` exclude the canonical wrapper or required
  heading/prefix owned by the region. `replace_region_body()` changes only that
  body and preserves the exact marker/heading/ID. For marker-backed optional
  supplements, `omit_optional_region()` leaves the paired empty marker shell in
  place and records E7 `omitted`; for non-marker optional single-line regions
  it removes the whole span. Required regions cannot be omitted.

### Canonical region specification

Specific marker spans are indexed first in the priority shown below. Remaining
unclaimed text is then assigned to the fallback first-viewport/section-body
regions, so regions form a non-overlapping partition of the whole string.

| Priority / deterministic ID | Block | Start rule | End rule | Requirement | Policy / repeatability |
|---|---|---|---|---|---|
| 1 `disclaimer:canonical` | `disclaimer` | line exactly `## ⑦ 면책조항` | EOF | always | `exact_disclaimer`, once |
| 2 `diagnostics:quality` | `diagnostics` | `<details><summary>수집/품질 진단</summary>` | matching `</details>` inclusive | always | `protected_diagnostics`, once; no nested `<details>` |
| 3 `chart:{supplement_id}` | `chart` | `<!-- investo:block chart:{supplement_id} -->` | exact `<!-- /investo:block chart:{supplement_id} -->` inclusive | conditional on that non-empty E1 supplement | reader-visible, repeatable |
| 4 `visual:{supplement_id}` | `visual` | `<!-- investo:block visual:{supplement_id} -->` | exact `<!-- /investo:block visual:{supplement_id} -->` inclusive | conditional on that non-empty E1 supplement | reader-visible, repeatable |
| 5 `carryover:{supplement_id}` | `carryover` | `<!-- investo:block carryover:{supplement_id} -->` | exact `<!-- /investo:block carryover:{supplement_id} -->` inclusive | conditional on that non-empty E1 supplement; body contains one exact `## Watchlist Carryover` | reader-visible, repeatable |
| 6 `macro:shared` | `shared_macro` | line exactly `## ⓪ 오늘의 매크로` | next H2 or EOF | conditional on shared macro | reader-visible, once |
| 7 `indicator:crypto` | `crypto_indicators` | line exactly `## ⓪-A 크립토 지표 (UTC 24h 스냅샷)` | next H2 or EOF | conditional on crypto indicator input; forbidden on siblings | reader-visible, once |
| 8 `anchor:channel` | `channel_anchors` | line exactly `## ⓪-B 채널 기준선` | next H2 or EOF | conditional on channel contract | reader-visible, once |
| 9 `cause:cross_market` | `cause_map` | line prefix `> **크로스마켓 연결 고리**:` | newline | optional | reader-visible, once |
| 10 `thesis:daily` | `daily_thesis` | line prefix `> **오늘의 큰 그림:**` | newline | conditional on active-bundle decision | reader-visible, once |
| 11 `navigation:segments` | `navigation` | line prefix `**세그먼트**:` | newline | always in segmented mode | reader-visible, once |
| 12 `disclaimer:short` | `disclaimer` | equity: exact `> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.`; crypto: exact `> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. 가상자산은 가격 변동성이 매우 큽니다.` | newline | always | `exact_disclaimer`, once |
| 13 `anchor:market` | `anchor_table` | equity/domestic line exactly `| 종목 | 종가 | 변동 | 비고 |`; crypto line exactly `| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |` | first non-table line; next line exactly `|------|------|------|------|` | conditional on non-empty reconciled anchors (`anchor_table_required`) | reader-visible, once |
| 14 `watchpoints:section` | `watchpoints` | line exactly `## ⑥ 오늘의 관전 포인트` | diagnostics start or `## ⑦` | always | reader-visible, once |
| 15 `section:{n}` | `section_body` | exact one of `## ① 요약`, `## ② 전일 핵심 이슈`, `## ③ 섹터/수급 동향`, `## ④ 지표·이벤트`, `## ⑤ 주요 종목` | next numbered H2/special owned H2 | all five required in that order | reader-visible, five unique IDs |
| 16 `header:title` | `header` | first line exactly `# {target_date.isoformat()} {SEGMENT_LABELS[segment]} 시황` | newline | always | reader-visible, once |
| 17 `first_viewport:{ordinal}` | `first_viewport` | each remaining non-empty unclaimed span before `## ①` | next claimed span or `## ①` | conditional residual | reader-visible, repeatable in source order |

Supplement assembly adds the invisible paired comments in rows 3-5; it never
discovers supplement regions from image URL/evidence text. A duplicated
non-repeatable ID, unmatched marker pair, nested/overlapping span, missing
required region, unexpected numbered H2, or unclaimed bytes after partition is
a required-structure hard block.

`replace_region_body()` splices by the current content offsets, preserves the
canonical wrapper/heading, then calls
`reindex(..., expectation=self.expectation)` on the entire result. A
replacement for a marker-backed always/conditional region must reproduce the
same canonical marker/ID; a first-viewport residual keeps its ordinal between
the same neighboring claimed regions. `omit_optional_region()` follows I10e;
it does not delete a conditionally expected supplement marker pair. After
reindex, unaffected region IDs and order must remain stable. A second
replacement/omission of the same ID in one call is forbidden by E7.
- I11. `issue_codes` are unique and sorted for deterministic logs/tests.
- I11a. `region_id` exists in the final layout (including an omitted
  marker-shell region) and is unique in `block_outcomes`; E5 artifact exclusion
  joins on this exact ID, never on block kind alone.
- I11b. E7 `record_warning` serializes as E3 disposition `kept`; the issue code
  remains in that region's outcome without changing layout bytes.
- I12. Outcomes contain no original Markdown, raw source payload, full URL, or
  secret-shaped value.
- I13. `section_body`, `watchpoints`, `navigation`, and `disclaimer` cannot be
  omitted. A broken watchpoint region is replaced with its required safe body.
- I14. `visual`, `chart`, `carryover`, `cause_map`, and equivalent augmentation
  blocks may be omitted only through the policy in `business-rules.md`.
- I15. A replacement block is passed through public projection and terminal
  validation just like generated prose.

## E4. PublicLimitationReason

Typed private reason for generating bounded reader-facing limitation copy.

```python
PublicLimitationReason = Literal[
    "limited_coverage",
    "core_price_missing",
    "source_count_unavailable",
    "watchpoint_unavailable",
]
```

| Reason | Typed source | Public effect |
|---|---|---|
| `limited_coverage` | segment coverage/data-limited input | reader-safe limitation sentence |
| `core_price_missing` | source/coverage outcome | precise price prose reduced/withheld |
| `source_count_unavailable` | evidence/coverage accounting | diagnostics pointer sentence |
| `watchpoint_unavailable` | watchpoint row/card outcome | safe bounded watchpoint note |

E4 is a projection category, not a replacement coverage state. The finalizer
derives it from the existing `SegmentCoverage` contract using this exhaustive
mapping:

| Existing typed condition | Derived E4 reason |
|---|---|
| `coverage.status != "normal"`; `ZERO_ITEMS`, `BELOW_THRESHOLD`, `MISSING_NEWS`, `MISSING_MACRO`, `MISSING_CALENDAR`, `MISSING_EARNINGS`, `SOURCE_FAILED`, `SOURCE_ZERO`, `LOOKAHEAD_DATA_MISSING`, `ALL_FAILED`, `MACRO_ACTUAL_MISSING`, `MACRO_ACTUAL_ZERO`, `MACRO_ACTUAL_FAILED`, `MACRO_ACTUAL_STALE`, `MACRO_REQUIRED_OMITTED`, or `MACRO_FORECAST_UNVERIFIED` | `limited_coverage` |
| `MISSING_PRICE`, `CORE_FAILED`, `CORE_ZERO`, or `CORE_STALE` | `core_price_missing` (and `limited_coverage` when status is not normal) |
| `coverage.source_count == 0` or the existing evidence counter cannot produce a count | `source_count_unavailable` |
| typed watchpoint renderer outcome says no usable card | `watchpoint_unavailable` |
| `DOMESTIC_DISCLOSURE_QUIET` alone | no E4 reason; this is a truthful quiet-session state, not degraded coverage |

Unknown future `CoverageReasonCode` values fail an exhaustiveness test until
the mapping is classified. One condition may derive multiple unique, ordered
E4 reasons.

Watchpoint absence is produced by this exact publisher contract:

```python
WatchpointRenderState = Literal["rendered", "limited"]

@dataclass(frozen=True, slots=True)
class WatchpointRenderResult:
    markdown: str
    state: WatchpointRenderState
    usable_card_count: int
    limitation_reasons: tuple[PublicLimitationReason, ...] = ()
```

Add `render_watchpoint_matrix_result(...) -> WatchpointRenderResult` as the
production API. State `limited` requires `usable_card_count == 0` and exactly
`("watchpoint_unavailable",)`; state `rendered` requires a positive count and
no watchpoint limitation. The legacy string-only renderer may delegate to
`.markdown` for tests, but has zero default segmented call sites. E2 accumulates
the result reasons before phase 2 projection.

**Invariants**

- I16. These values are private state and never render verbatim.
- I17. State is not inferred by parsing public Korean copy when a typed source
  exists.
- I18. Public strings are owned only by
  `_internal.public_quality_language`; producer modules do not duplicate them.
- I19. `데이터 부족`, `[데이터부족]`, `확인 소스 미상`, and equivalent raw
  operator labels are not legal serialized public defaults.

## E5. FinalizedPublicDocument

Frozen sealed representation of the exact segment document consumed by all
public write/read surfaces.

```python
@dataclass(frozen=True, slots=True)
class PublicNotificationSummary:
    segment: MarketSegment
    target_date: date
    conclusion: str
    coverage_status: CoverageStatus
    coverage_label: str
    watchlist: str | None = None

PublicNotificationSummaryIssueCode = Literal[
    "summary.missing_conclusion",
    "summary.invalid_conclusion",
    "summary.invalid_coverage_label",
    "summary.invalid_watchlist",
]

class PublicNotificationSummaryError(ValueError):
    issue_code: PublicNotificationSummaryIssueCode
```

`PublicNotificationSummary` lives in `models/public_notification.py` as the
minimal u114 shared DTO; no finalizer behavior lives there. The error remains
publisher-private, contains no rejected prose, and is converted to a segment
hard block. The publisher derives the DTO as the final terminal-validation
step, stores it on validated E2, and follows this exact non-fallback path:

1. `_internal.briefing_extract.extract_conclusion(layout.markdown)` reads the
   canonical `> **오늘의 결론**:` line. Missing/empty output is
   `summary.missing_conclusion` and hard-blocks the segment; generated
   `Briefing.market_summary` is never consulted.
2. Add `WATCHLIST_IMPACT_PREFIX` and `extract_watchlist_impact()` to the same
   canonical prefix owner. Move the Markdown-token cleanup currently in
   `notifier._summary_extract.clean_summary_text()` to
   `_internal.public_summary_extract.clean_public_summary_text()`; publisher
   and the legacy notifier adapter reuse it instead of importing one another.
3. `conclusion` must remain non-empty after cleanup and pass the existing
   `is_unsafe_summary_value()` plus owned public-leak predicate. Failure is
   `summary.invalid_conclusion`, with no alternate text source.
4. `coverage_status` and `coverage_label` are copied from the E1
   `SegmentCoverage.status`/`.status_label`, not parsed from Korean Markdown.
5. `watchlist` is the cleaned final-layout value or `None`. The shared helper
   preserves the current notifier exclusions for `관심 목록 미설정` and
   `데이터 수집 부족으로 매칭 판단 보류`; it never reads the generated
   briefing. A non-empty value passes the public-leak predicate before seal.

The default `build_segmented_summary()` signature changes from a mapping of
`Briefing` to `Mapping[MarketSegment, PublicNotificationSummary]`; the existing
URL, lookahead-item, and price-item arguments remain separate typed inputs.
It verifies mapping key/DTO segment identity and one target date, uses
`coverage_status` for the failed-segment compact form, and decorates only the
DTO `watchlist`. The current UTF-16 whole-message budget remains notifier
formatting behavior; it cannot select substitute prose. Legacy unsegmented
`build_summary(Briefing, ...)` remains outside the default segmented path.

```python
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

The embedded `briefing` is a final compatibility view: its
`rendered_markdown` contains the sealed bytes. The original draft briefing is
never embedded.

**Invariants**

- I20. `briefing.target_date == target_date`.
- I21. `markdown_sha256 == sha256(briefing.rendered_markdown.encode("utf-8"))`.
- I22. The exact disclaimer is present and passes existing publisher
  verification for `segment`.
- I23. No blocking surface, summary, compliance, numeric, entity, structure, or
  disclaimer finding remains at construction.
- I24. Only the module-private seal factory constructs production instances;
  an AST/import regression test restricts construction sites.
- I25. A consumer can read `briefing` or `rendered_markdown` but cannot return a
  changed E5 instance to the production publish path.
- I25a. `staged_artifact_ids` are unique, stable, and exactly the artifact IDs
  referenced by marker-backed supplement regions whose E7 outcome is not
  `omitted`. Sealing joins region IDs to E1 `supplement_id`, excludes explicit
  omission outcomes, then takes the remaining ordered `artifact_ids`; the
  empty marker shell of an omitted supplement contributes none. It never
  discovers assets from Markdown URLs. `notification_summary` is copied from
  the validated E2 draft and passes the same
  public-language/summary bounds; it is never copied from the generated
  `Briefing.market_summary` field.
- I25b. `notification_summary.segment/target_date` equal E5, its coverage fields
  equal the segment's E1 coverage, and its optional watchlist is derived only
  from the validated layout. A default segmented notifier accepts no
  `Briefing` or free-form summary fallback.

## E6. FinalizedPublicBundle

Frozen ordered collection created after every generated candidate reaches a
terminal outcome. It preserves the intentional u63/u94 partial-publish product
contract while making incompleteness typed and operationally non-green.

| Attribute | Type | Notes |
|---|---|---|
| `target_date` | `date` | Shared report date. |
| `documents` | `tuple[FinalizedPublicDocument, ...]` | Non-empty finalized subset in canonical expected-segment order. |
| `expected_segments` | `tuple[MarketSegment, ...]` | Equal to E1 input. |
| `segment_outcomes` | `tuple[SegmentFinalizationOutcome, ...]` | Exactly one outcome for every expected segment. |
| `promotion_manifest` | `tuple[StagedArtifact, ...]` | Canonical expected-segment/artifact-order descriptors for surviving E5 references only. |

```python
SegmentFinalizationState = Literal[
    "finalized",
    "generation_absent",
    "trust_blocked",
]

@dataclass(frozen=True, slots=True)
class SegmentFinalizationOutcome:
    segment: MarketSegment
    state: SegmentFinalizationState
    issue_codes: tuple[str, ...] = ()
```

**Invariants**

- I26. Segment keys in `documents` exactly equal the E6 outcomes whose state is
  `finalized`, in `expected_segments` order. `generation_absent` corresponds
  exactly to E1 `input_absences`; `trust_blocked` is produced only by a
  non-degradable terminal finding.
- I27. Duplicate, extra, unexplained-missing, cross-date, or zero-document
  bundles are rejected. Zero finalized documents raise E8.
- I28. An E6 value is returned before any reader-facing
  archive/index/quality write or git staging. Existing private operational
  state files are not E5/E6 public artifacts and remain outside this lifecycle.
- I29. A partial E6 is legal and must use the existing u63 explicit
  absence/navigation surface. Presentation-only findings may not create a
  `trust_blocked` outcome; they must use E7 repair/replacement/omission.
- I29a. Promotion-manifest IDs equal the ordered union of E5
  `staged_artifact_ids`; blocked/absent segment artifacts never appear. The
  staging owner rechecks each manifest path/digest before promotion.

## E7. FinalizationIssueDisposition

Closed disposition assigned to a specialized validator finding without
replacing the finding's canonical owner.

```python
FinalizationIssueDisposition = Literal[
    "record_warning",
    "repair",
    "replace_block",
    "omit_optional_block",
    "block_segment",
]
```

The mapping key is `(issue_code, block_kind)` when block context matters. The
existing `SurfaceQualityIssue`, compliance report, numeric/entity violations,
and disclaimer/summary exceptions remain their canonical evidence types.

**Invariants**

- I30. Every reachable blocking surface issue code has exactly one mapped
  disposition or fails closed as unmapped for that segment. Reachable
  non-blocking codes map to `record_warning` explicitly.
- I31. The mapping contains policy only; it does not duplicate scanner regexes
  or validator algorithms.
- I32. One block may be repaired/replaced/omitted at most once per finalization
  call.

## E8. PublicDocumentFinalizationError

Publisher error raised before write when no segment can be finalized, input
contracts are inconsistent, or a bundle-wide invariant cannot be represented
as a segment outcome.

| Attribute | Type | Notes |
|---|---|---|
| `target_date` | `date` | Report date. |
| `segment` | `MarketSegment | None` | Specific segment or bundle-level absence. |
| `phase` | `str` | Bounded lifecycle phase. |
| `issue_codes` | `tuple[str, ...]` | Unique/sorted, no raw evidence. |
| `cause` | `Exception | None` | Existing typed cause retained for routing, never rendered raw publicly. |

**Invariants**

- I33. E8 routes through publish failure, operator alert, `FAILED`, and exit 1.
  A one- or two-document E6 is not E8; it is typed content-partial output.
- I34. E8 construction/logging is R13-safe: no full Markdown, raw payload,
  secret, or unredacted environment value.
