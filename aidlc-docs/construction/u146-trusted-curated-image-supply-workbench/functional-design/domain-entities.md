# Domain Entities - u146 Trusted Curated Image Supply Workbench

## E1 `CuratedRightsEvidence`

Frozen, extra-forbidden evidence produced from one stored Commons API snapshot and one local binary. It records asset/category, exact file page/revision/image identity, selected variant URL/path/hash/MIME/dimensions, PD/CC0 mapping, author, restriction signals, snapshot path/hash, and either `READY_FOR_REVIEW` with no blocker or `BLOCKED` with at least one closed-set blocker.

## E2 `CuratedOperatorDecision`

Frozen approved-only record authored after review. It links the exact evidence, binary, manifest, registry key, reviewed date/reviewer, and explicit confirmations for file identity, license scope, subject relevance, non-copyright restrictions, and endorsement risk. Pending/rejected queue records are not filing decisions.

## E3 `LegacyCuratedSeal`

One immutable list of exactly the 15 pre-u146 assets. Each entry fixes asset/category, binary relative path/hash, and manifest relative path/hash. An asset whose bytes change must migrate to E1/E2; the legacy list cannot grow.

## E4 `CuratedReviewPacket`

The workbench output directory containing copied snapshot bytes, one pending evidence JSON, and a completion seal. It is not a filing and must live outside protected repository roots.

## E5 `CuratedFilingGraph`

The verifier's read-only view of snapshot -> evidence -> approved decision -> binary/manifest -> registry. Every non-legacy filed asset must have one complete graph; every rights directory must resolve to one filed asset.
