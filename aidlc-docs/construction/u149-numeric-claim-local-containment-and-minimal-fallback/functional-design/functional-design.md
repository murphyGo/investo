# u149 Functional Design — Numeric Claim Local Containment

**Date**: 2026-08-05
**Status**: Approved for construction by the user's instruction to continue development without approval pauses
**Supersedes**: u109 AC-1.4 and u144 numeric-only segment-blocking behavior only

## Purpose and boundary

The public numeric gate remains fail-closed: an unsupported exact domestic anchor claim may never reach sealed bytes. u149 changes only the failure radius. A domestic numeric-only defect is assigned to its indexed u144 region and receives one deterministic action. Entity, compliance, disclaimer, summary, required-structure, target-date, notification-summary, and security failures remain segment-blocking.

The sole lifecycle remains:

`generated -> assembled -> projected -> repaired -> validated -> sealed`

There is no second finalizer, recursive finalization, post-seal mutation, LLM repair, external lookup, or guessed number.

## Supersession matrix

| Existing contract | u149 amendment | Preserved invariant |
|---|---|---|
| u109 AC-1.4 blocks a segment for an unsupported structural domestic claim | block the unsafe owned claim/row/subtree/region; use one minimal attempt only when local containment cannot prove safety | unsupported exact value never publishes |
| u144 R9/AC-144.7 maps residual numeric findings to `trust_blocked` | domestic numeric-only findings first traverse the closed local action ladder | US/crypto and all non-numeric failures retain prior behavior |
| `finalized` is the only document-bearing outcome | `finalized_degraded` is also document-bearing and derives from sealed typed witnesses | seal, notifier DTO, artifact transaction, and exact-byte writers are unchanged |

## Domain contracts

### Location-aware finding

`AnchorAssertionFinding` retains segment/symbol/label/sentence/isolation and adds half-open `start`/`end` offsets into the exact scanned Markdown plus a closed `line_kind`:

- `prose_sentence`
- `list_or_callout`
- `table_row`
- `h3_subtree`
- `structural_region`

Offsets must satisfy `0 <= start < end <= len(markdown)`, and the indexed slice must match the scanner-owned sentence or complete structural line. Legacy zero-length defaults are stale. Offsets must map wholly to exactly one `PublicDocumentRegion`. Zero owners, multiple owners, overlap, or stale offsets request the minimal path; no text search is allowed.

### Exhaustive original hard-gate collection

After ordinary u144 surface repair and reindexing, the original candidate runs every existing read-only terminal gate. Codes are canonicalized and collected without short-circuiting. Local containment is eligible only when:

1. segment is `domestic-equity`;
2. layout is indexed;
3. the complete code set is exactly `{numeric.anchor_assertion}`.

Any coexisting code on an indexable layout returns `trust_blocked` with the complete bounded set. A pre-layout/non-indexable structure failure remains an immediate structure block and is only required to prove that fallback was not invoked; numeric co-codes are not fabricated without safe ownership. A replacement document cannot hide an original defect.

### Closed local action ladder

Findings are grouped by original `region_id`; one immutable plan is made per region and one region operation is applied.

| Input kind / owner | Action | Result |
|---|---|---|
| registered typed whole block | `corrected` | re-render whole trusted block; token substitution is forbidden |
| prose, bullet, callout | `rewritten` | canonical data-limited claim sentence |
| table data row | `excluded` | remove only the complete row |
| H3 | `excluded` | remove heading through next H3/H2/region boundary |
| optional visual/chart/carryover/cause-map | `omitted` | existing u144 omission, no artifact promotion |
| replaceable/required owned region | `replaced` | existing safe region fallback while retaining required H2 |
| protected, unowned, overlapping, malformed, or residual | request minimal | no arbitrary broader deletion |

Multiple edits inside one region are composed from original bytes in descending offset order and committed through one `replace_region_body()` call.

### One minimal attempt

The neutral `_internal.data_limited_segment.build_data_limited_briefing()` owns deterministic first-viewport conclusion/driver/caution copy, six-section base Markdown, a bounded diagnostics shell, section fields, canonical long disclaimer, and `Briefing` construction. The normal assembly still adds the title, navigation, and short disclaimer; typed coverage remains in the retained context for terminal notification metadata. The builder performs no I/O, LLM, env, file, clock, or network operation.

`finalize_public_bundle()` owns bundle-scoped `minimal_source_by_segment` and `attempted_minimal_segments` ledgers outside the survivor loop. The builder is called at most once per segment. A stored minimal source may be re-finalized after a sibling changes the survivor set; that does not consume another attempt.

The minimal segment receives a stripped finalizer context: no items, anchors, supplements, staged artifacts, bundle augmentation, or original fact claims; it retains target/segment, coverage/source outcomes, and the frozen entity observation time. It traverses the same assembly, projection, repair, terminal gates, notifier summary derivation, and seal. Unowned/stale findings use sentinel `region_id="document:unowned"`; minimal fallback emits one witness per original finding in canonical finding order, and each digest is SHA-256 over the exact UTF-8 `finding.sentence` bytes.

### State and witnesses

`NumericContainmentOutcome` is the shared frozen witness with exactly:

- target date and segment;
- canonical symbol and region ID;
- line kind and closed action;
- sorted issue codes;
- 64-character lowercase SHA-256 claim digest.

The exact tuple flows `PublicDocumentDraft -> FinalizedPublicDocument -> SegmentFinalizationOutcome`. A non-empty tuple yields `finalized_degraded`; an empty tuple yields `finalized`. Logs expose only bounded fields and the first 16 digest characters.

Required `section_body` containment preserves its canonical H2 and replaces only the body with `검증된 수치 근거가 부족해 이 섹션의 정밀 판단을 보류합니다.`. `first_viewport` uses the neutral conclusion/driver/caution copy owned by the minimal builder. These are u149 canonical fallbacks; they do not depend on a pre-existing u144 section fallback.

## State transitions

| Original result | Recovery | Terminal result |
|---|---|---|
| no hard code | none | `finalized` |
| domestic numeric only; local action clears all gates | local action tuple | `finalized_degraded` |
| domestic numeric only; local action cannot prove safety; minimal seals | one minimal witness | `finalized_degraded` |
| minimal fails | no retry | `trust_blocked` + `numeric.fallback_exhausted` + actual codes |
| numeric plus any other hard code | ineligible | `trust_blocked` with all codes |
| US/crypto numeric | ineligible | existing `trust_blocked` behavior |

Both finalized states are documents. All expected segments in either finalized state means `content_completeness=complete`, normal publish/Telegram/Pages sequencing, and exit 0. True absence or a block remains partial/exit 2; zero survivors remains exit 1.

## Phase call graph

1. Assembly defers domestic anchor mutation but preserves US/crypto behavior.
2. Reindex assigns exhaustive region ownership.
3. Projection and ordinary u144 surface repair run unchanged.
4. Original hard gates are exhaustively collected.
5. Eligible domestic numeric findings are grouped and locally contained.
6. Projection/reindex and every terminal gate rerun read-only.
7. Residual/unsafe ownership requests the one stored minimal source.
8. Validated draft derives notification DTO and is sealed.

## Compatibility

- Legacy `SegmentFinalizationOutcome` constructors keep empty witness defaults.
- Clean domestic, US, and crypto bytes are unchanged.
- Legacy direct reader-format callers retain immediate numeric enforcement; only the u144 typed finalizer defers domestic findings to indexed containment.
- Existing artifact selection and rollback use the sealed document's survivor IDs and require no new storage or infrastructure.
