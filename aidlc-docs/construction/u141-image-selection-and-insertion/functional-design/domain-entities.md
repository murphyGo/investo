# Domain Entities — `u141 image-selection-and-insertion`

**Date**: 2026-08-03

This unit adds ephemeral selection values only. U-137 remains the owner of persisted candidates, rights files, and stored binaries; U-24 remains the owner of persisted visual provenance.

## E1. ImageNarrativeContext

A frozen value derived only from one segment's finalizable reader-facing Markdown.

| Attribute | Type | Meaning |
| --- | --- | --- |
| `segment` | `MarketSegment` | Segment whose body was parsed. |
| `hero_markdown` | `str` | Conclusion, key drivers, and first issue story. |
| `issue_markdown` | `str` | Complete `## ② 전일 핵심 이슈` body. |
| `narrative_sha256` | `str` | Digest of the canonical scope tuple. |

**Invariants**

- I1: No raw item, feed metadata, prior supplement, or image metadata contributes to these strings.
- I2: Scope extraction is deterministic and wall-clock-free.
- I3: The digest is lowercase SHA-256 over a fixed serialization of segment, hero scope, and issue scope.
- I4: If the issue section or first issue story is absent, the applicable scope is empty; callers do not broaden it.

## E2. ImageUsageSelection

A frozen, ephemeral decision for one segment.

| Attribute | Type | Meaning |
| --- | --- | --- |
| `hero_candidate` | `ImageCandidateRecord | None` | Cleared, stored, sufficiently large candidate linked from hero scope. |
| `card_candidate` | `ImageCandidateRecord | None` | Non-blocked, non-hero candidate linked from issue scope. |
| `narrative_sha256` | `str` | E1 digest used for both decisions. |
| `reason` | `str` | Bounded diagnostic summary. |

**Invariants**

- I5: Every selected candidate's `item_url` occurs exactly in its allowed scope.
- I7: A hero is backed by current clearance truth and a valid binary/sidecar pair.
- I8: A blocked marker excludes the candidate even if a manifest/store binary also exists.
- I9: Hero dimensions are known and at least 600x338.
- I10: Hero and card candidate ids differ; each field has cardinality zero or one.
- I11: A card carries metadata only and never authorizes binary use.
- I14: Equal inputs produce an equal selection; rank is occurrence offset, first_seen, candidate_id.

## E3. CuratedSemanticMatch

The existing curated selection enriched with selection evidence.

| Attribute | Type | Meaning |
| --- | --- | --- |
| `asset` | `CuratedAsset` | Existing validated curated manifest. |
| `matched_key` | `str` | Semantic registry key. |
| `match_reason` | `str` | Bounded alias/scope explanation. |
| `narrative_sha256` | `str` | E1 digest. |

**Invariants**

- I6: A `person:*` match requires a named-person alias in hero scope. Role-only aliases are invalid.
- Registry priority resolves multiple already-eligible keys; it cannot create eligibility.

## E4. ImageSourceCardSupplement

A typed `PublicDocumentSupplement(kind="visual")` whose fragment contains one metadata-only source card and no artifact ids.

**Invariants**

- I12: The fragment contains title, credit/source, and `item_url` only; `image_url` is absent.
- I13: Placement is after the first issue story, idempotent, and omitted when the owned section is unavailable.

## E5. SelectionProvenanceMetadata

Sanitized `additional_metadata` attached to the existing `VisualProvenanceManifest`.

Required keys are `selection_contract=final-body-semantic-v1`, `match_reason`, and `narrative_sha256`; stored images also carry `candidate_id`, while curated images carry `matched_key` and `asset_id`.

**Invariants**

- I15: Values are bounded and validated by the normal provenance constructor; no secret-bearing body text, full URL, or raw Markdown is stored.
- I16: Selection/provenance failures degrade to fallback and do not escape the segment visual boundary.
- I17: A failure in one segment does not alter sibling selection or publication.
