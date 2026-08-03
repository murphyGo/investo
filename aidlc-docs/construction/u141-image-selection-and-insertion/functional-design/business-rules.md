# Business Rules — `u141 image-selection-and-insertion`

**Date**: 2026-08-03
**Source**: U-141 code-generation plan, strengthened by the approved final-body-centered semantic selection contract.

Rules are ordered by precedence. Entity and invariant ids refer to
`domain-entities.md`; algorithms refer to `business-logic-model.md`.

## R1. Reader-visible body is the semantic source of truth (I1-I3)

- Selection consumes the generated segment briefing immediately before image/card supplements and terminal public-document finalization. This is the stable **finalizable narrative body** available while assets can still be inserted.
- Raw routed items, feed ordering, image alt text, source volume, the image ledger alone, and previously inserted visual blocks are forbidden as semantic evidence.
- The context records a SHA-256 digest of the exact normalized narrative scopes used for selection. This digest is diagnostic provenance, not a relevance score.

## R2. Scope follows editorial salience (I2, I4)

- Hero scope is conclusion + key drivers + the first `###` story block under `## ② 전일 핵심 이슈`.
- Link-card scope is the complete `## ② 전일 핵심 이슈` body.
- Missing or malformed `## ②` yields no feed-image selection. It must not widen the search to the complete document or source pool.

## R3. Feed relevance requires exact article lineage (I5)

- A ledger candidate is relevant only when its exact sanitized `item_url` occurs in the applicable scope.
- Hero candidacy requires occurrence in hero scope. Card candidacy requires occurrence in link-card scope.
- Title similarity and keyword overlap are not sufficient in v1. This prevents a recurrent or popular image from attaching to an unrelated final story.

## R4. A specific person portrait requires the named person (I6)

- `person:*` curated assets use explicit identity aliases only and match hero scope only.
- Generic roles/institutions are excluded from person aliases. In particular, `FOMC`, `Fed`, `Federal Reserve`, `Fed Chair`, `연준`, `연준 의장`, `President`, and `White House` cannot select Jerome Powell or Donald Trump portraits.
- Topic assets remain eligible for institution/role language. Registry priority can break ties only after semantic eligibility is established.

## R5. Cleared hero eligibility is fail-closed (I7-I10)

- The recurrence index is never rights truth. At selection time, a candidate is cleared only when the current operator clearance manifest is valid, no blocked marker wins, and the store binary plus provenance sidecar form a valid pair.
- Hero metadata must report width >= 600 and height >= 338. Missing dimensions are not hero-eligible.
- The stored candidate's article URL must satisfy R3. A cleared but irrelevant or undersized image cannot displace curated/AI/data-confidence fallback.
- Store copy is local-only and creates the existing `external-context-image` slot. No new network request is permitted.

## R6. Metadata-only use remains text-only (I11-I13)

- A non-blocked candidate linked from the full issue section may render one source card if it was not selected as hero.
- The card contains sanitized title, image credit or source name fallback, and the article `item_url` only. `image_url`, Markdown image syntax, HTML image tags, and CDN links are forbidden.
- The card is inserted after the first issue story, through the typed supplement lifecycle, and is idempotent. Missing issue structure means no card.

## R7. Deterministic ranking reflects narrative order (I14)

- The observed committed corpus has 11 dates, 804 rows, 748 unique candidates, and 42 recurrent candidates (5.6%). Because recurrence is below the predeclared 10% significance threshold, `seen_count` is excluded from v1 ranking.
- Eligible candidates sort by exact URL occurrence offset in the relevant body, then recurrence-index `first_seen` ascending, then `candidate_id` lexical. Wall clock and filesystem iteration order are forbidden.
- Each segment has at most one hero and one distinct link card.

## R8. Provenance explains the editorial decision (I15)

- Selected stored or curated hero sidecars record bounded `selection_contract`, `matched_key`/`candidate_id`, `match_reason`, and `narrative_sha256` metadata.
- Provenance construction must pass through the closed `VisualProvenanceManifest` validator and sanitizer; model-copy update bypasses are forbidden.

## R9. Pipeline order and failure isolation (I16-I17)

- Candidate ledger/index/store maintenance runs before visual preparation so a same-run cleared binary can be considered.
- Context construction, candidate selection, curated matching, local copy, provenance creation, and link-card insertion are independently failure-isolated per segment.
- Any exception produces a bounded warning/stage note and falls through to the existing visual chain or no card. It never fails generation, finalization, publish, notification, or sibling segments.

## R10. Reuse and scope boundary

- Reuse U-137 ledger/store/rights contracts, U-24 provenance, U-86 curated manifests, the existing hero priority, and the public supplement/finalizer lifecycle.
- Do not add dependencies, HTTP calls, secrets, rights transitions, past-archive mutation, multi-card galleries, Telegram media delivery, or runtime current-office-holder lookup.

**Reject in review**: selecting Powell because the body says only FOMC or Fed chair; selecting any feed image whose article URL is absent from the finalizable body; trusting `index.json` rights state without current files; emitting `image_url` in a card; making `seen_count` a higher ranking key; widening a missing `## ②` to the whole document; allowing an image exception to stop publication.
