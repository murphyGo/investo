# Session Log: 2026-08-03 - u141 Curated Approval Supply Follow-up

## Outcome

- Increased the selectable, license-cleared curated library from 13 to 15 filed assets.
- Added current Federal Reserve Chair Kevin Warsh and U.S. Treasury Secretary
  Scott Bessent as explicit-name-only person assets.
- Preserved the u137 feed-candidate boundary: 748 indexed news images remain
  `metadata-only`; no rights state was inferred from host, RSS presence, credit,
  recurrence, or public accessibility.

## Root Cause

The approval bottleneck is not candidate volume. It is the missing evidence edge
between a candidate binary and a file-specific, reviewable rights assertion.

```text
feed observation (804 / 748 unique)
  -> image candidate metadata
  -X-> file-specific license evidence
  -X-> operator clearance
  -X-> stored binary
  -X-> u141 stored hero

reviewed PD/CC0/government work
  -> source + file metadata + embedded restriction check
  -> operator decision
  -> curated manifest + committed binary
  -> semantic registry
  -> u141 final-body selection
```

The production fetch opt-in is already enabled. Creating more generic `og:image`
candidates would therefore increase the left side of the graph without creating
the missing rights-evidence edge.

## Target Approval Graph

```text
Publisher -> OfficialAccount -> AssetRecord -> BinaryVariant
                                   |                |
                                   |                +-> MIME / dimensions / SHA-256
                                   +-> DepictedEntityOrTopic
                                   +-> RightsAssertion -> TermsSnapshot
                                                        -> EmbeddedMetadata
                                                        -> OriginatingSource

RightsAssertion + no contradiction -> OperatorDecision -> CuratedAsset
FinalNarrative -> named entity/topic -> CuratedAsset -> rendered image
```

Approval requires all positive edges and no negative edge. In particular,
`extmetadata=public-domain` is insufficient when embedded metadata says
copyrighted, personal-use-only, editorial-only, or permission-required.

Recommended blocker codes for an offline review workbench are:

- `NO_LICENSE_EVIDENCE`
- `SOURCE_POLICY_METADATA_ONLY`
- `MISSING_DIMENSIONS`
- `TOO_SMALL`
- `LICENSE_CONTRADICTION`
- `READY_FOR_REVIEW`
- `CLEARED_NOT_STORED`

Discovery and draft generation must never write a final clearance. Only an
explicit operator action may perform `pending -> cleared`; CI remains offline
and validates committed evidence and bytes.

## Source Decisions

| Source | Decision | Boundary |
|---|---|---|
| Wikimedia Commons exact-file API | Ship now, operator-reviewed | PD/CC0 only; pin file title/revision SHA-1, binary SHA-256, source page, author, license and embedded restriction summary |
| Federal Reserve, Treasury and SEC official portraits | Ship now, operator-reviewed | File-level government-work evidence only; exclude seals, logos, art and third-party photos |
| WordPress Photo Directory | Ship next | Directory-wide moderated CC0 policy; retain work page, author, direct media, dimensions and tags, and still review for subject relevance |
| Library of Congress Free to Use and Reuse | Ship next | Exact Free-to-Use membership plus item rights and no restriction signal |
| Openverse | Discovery only | Openverse does not verify the accuracy of each work's license |
| Smithsonian Open Access | Defer | Strong record-level CC0 evidence, but requires a new optional API-key contract |
| KOGL Type 1 | Defer | Commercial reuse is possible, but public TASL-style attribution and a structured source contract are not implemented |
| CC BY / CC BY-SA | Defer | Current public provenance does not yet render author, license URL and modification status |
| Unsplash / Pexels API | Defer | API keys and provider-specific attribution/hotlink/download-tracking contracts are not implemented |
| Reuters, AP, Yahoo/The Block feed images, generic `og:image` expansion | Reject for auto-clear | Publisher/CDN accessibility is not republication permission |

Primary policy references used for the decisions:

- MediaWiki `imageinfo`: <https://www.mediawiki.org/wiki/API:Imageinfo>
- Wikimedia reuse guidance: <https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en>
- Federal Reserve disclaimer: <https://www.federalreserve.gov/disclaimer.htm>
- U.S. government copyright caveats: <https://www.usa.gov/government-copyright>
- WordPress Photo Directory guidelines: <https://wordpress.org/photos/guidelines/>
- Library of Congress APIs: <https://www.loc.gov/apis/json-and-yaml/>
- Library of Congress Free to Use: <https://www.loc.gov/free-to-use/>
- Openverse API warning: <https://docs.openverse.org/api/reference/made_with_ov.html>
- KOGL Type 1 guidance: <https://www.kogl.or.kr/info/licenseType1.do>

## Filed Assets

| Asset | Evidence | Filed binary |
|---|---|---|
| `person:kevin-warsh` | Official Federal Reserve portrait, 17 U.S.C. 105; Commons page `194061530`, image timestamp `2026-06-18T02:24:01Z`, original SHA-1 `710583b982101211209f4c429001e3d73639e727`; embedded `Copyrighted=False`, no restriction signal | JPEG 960x1242, 148,755 bytes, SHA-256 `eb338312c7a4edd75e06fc449ba49cd1d7d27e14ec3146e64f2a96d1291a0648` |
| `person:scott-bessent` | Official U.S. Treasury portrait, 17 U.S.C. 105; Commons page `161642723`, image timestamp `2025-03-10T15:00:43Z`, original SHA-1 `a9386b030bfa91505cfaef40ed5ea496f39092af`; Commons copyright false and no restriction signal. Editorial context only; do not imply Treasury endorsement, and retain seal/flag caution | JPEG 960x1344, 332,712 bytes, SHA-256 `7400c8be6433a2875fcd006eb9ec6d964ec3dcfda0762e04a950d3322ee0be77` |

Registry aliases contain names only. `Fed Chair`, `FOMC`, `Treasury Secretary`,
and similar roles cannot select either portrait. A generic FOMC story continues
to select a Federal Reserve topic image; a portrait is eligible only when the
final narrative explicitly names the person.

## Validation

- `uv run pytest tests/unit/visuals/test_curated.py -q`: 46 passed.
- `uv run pytest -q`: 4,162 passed.
- `uv run python scripts/check_curated_assets.py`: 15 filed, 0 deferred.
- Ruff check and format check passed.
- `git diff --check` passed.

## Next Scalable Slice

Implement an offline `discover -> evidence -> review -> file` workbench. Phase 1
accepts exact-title Commons PD/CC0 and LOC Free-to-Use records only, stores an
immutable evidence snapshot, detects embedded-metadata contradictions, and emits
a deterministic pending queue. Phase 2 may add CC BY/KOGL only after the public
provenance surface can render complete author/license/source attribution.
