# Business Rules — `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-18
**Source**: u137-image-candidate-registry-and-licensed-store-code-generation-plan.md (Problem Statement legal posture + Fixed Contracts #1-#6).

Rules are listed in order of precedence. `R1`-`R10`. Entity ids (`E1`-`E5`)
and invariants (`I1`-`I17`) reference `domain-entities.md`. NFR ACs
(`AC-1.1`-`AC-1.3`) reference `nfr-requirements/nfr-requirements.md`;
`AC-137.x` are the plan's unit-level acceptance criteria. `R13` always
means the **project-wide** secret-hygiene rule.

---

## R1. Metadata-everything, binaries-only-with-clearance (binding legal posture) (I17, AC-137.2)

- This repo is public and its outputs go to public Pages + a public
  Telegram channel. Yonhap feed images are Reuters/AP wire photos;
  Yahoo / The Block thumbnails are publisher copyright. Therefore the
  default rights state of **every** candidate is `metadata-only`:
  ledger + index presence, republication forbidden.
- A binary may exist in the store only for a candidate the operator
  individually cleared (R6/R7). Code never infers, relaxes, or assumes
  a license.
- u86's curation exclusion of news photos / memes stays intact. The u137
  store holds only "그 날의 실제 기사 이미지" cleared per-item; when the
  operator instead sources a license-clean substitute, it belongs in the
  u86 curated library, not here.

## R2. Candidate identity is the normalized-URL hash (I1)

- `candidate_id = sha256(normalize(image_url))` lowercase hex, where
  normalization is exactly: lowercase scheme, lowercase host, strip
  fragment; path / query / port preserved byte-exact.
- No other canonicalization in v1 (no query reordering, no
  trailing-slash trimming, no tracking-param stripping). Similar-image
  (perceptual) dedup is explicitly deferred (plan Deferred Candidates).

## R3. Date ledger: path + write discipline (I3, I4, AC-137.1)

- Path: `archive/_meta/image_candidates/{YYYY}/{YYYY-MM-DD}.jsonl`
  (reuses the `archive/_meta/` layout precedent from run_traces). One
  line = one `ImageCandidateRecord` (E1) JSON object.
- Input: only routed items carrying the u136 `image_url` raw_metadata
  key. Items without it are skipped; the ledger never invents
  candidates. Same-run dedup: the first item carrying a `candidate_id`
  wins.
- Write mode is **merge-rewrite**: read the existing date file (if any),
  merge with the run's rows by `candidate_id` with **existing-row-wins**,
  sort rows candidate_id-lexical, serialize with fixed key order, and
  atomically rewrite the whole file. Re-runs are byte-idempotent; a
  later run on the same date can add new candidates but never mutates or
  drops earlier rows.
- `collected_on` = the run's target date. Reading the wall clock for any
  persisted ledger/index value is forbidden.

## R4. String hygiene + caps (I2; project rule R13; AC-1.3)

- Every string field of every persisted artifact (ledger rows, index
  entries, provenance sidecars) passes `sanitize_provenance_text` — the
  u27 redaction chokepoint. No secret value can land in the ledger,
  index, manifests, or this unit's log lines.
- `item_title` is capped at 160 chars after sanitization. `image_credit`
  carries u136's 240-char cap. Other u136 `image_*` values are carried
  verbatim (absent key → `None`, never empty string).

## R5. Recurrence index (I5-I7, AC-137.6)

- `archive/_meta/image_candidates/index.json`, atomically rewritten via
  the existing `_internal/_io.write_atomic` on every stage run.
- Entry shape per E2: `first_seen` / `last_seen` / `seen_count` /
  `sources` / `rights_state`. `seen_count` counts **distinct ledger
  dates** — the v1 definition of the "자주 쓰이는 이미지" signal.
- The index is derived-only: deterministically rebuildable from the
  ledgers + the clearances directory, and never a source of truth for
  rights (I7).

## R6. Rights states + operator file contract (E5, I13-I15)

- `metadata-only` is the default (no file). `cleared` exists iff
  `archive/_meta/image_candidates/clearances/{candidate_id}.manifest.json`
  exists and is valid (R7). `blocked` exists iff
  `archive/_meta/image_candidates/clearances/{candidate_id}.blocked`
  exists (empty marker file is sufficient).
- `blocked` takes precedence when both files exist (I7).
- State transitions happen **only** by operator file placement/removal.
  No code path creates, edits, or deletes clearance-directory files;
  code never auto-promotes (I14). `blocked` is permanent exclusion from
  fetch candidacy — re-appearance never re-candidates it (I15).

## R7. Clearance manifest contract (I8, I9; TS-2)

- The clearance file is a complete `ExternalAssetManifest` with
  `kind="explicit-license"` — **no new manifest class** is introduced.
  The manifest fields are the clearance evidence: `license` /
  `attribution` / `author` / `allowed_use` document the operator's
  verified republication basis; `fetched_on` is the operator's
  verification date.
- `source_url` must be the candidate's image URL: hash-verified
  `sha256(normalize(source_url)) == candidate_id` (I9).
- Missing / invalid / unparseable / hash-mismatched manifest =
  **not cleared** — runtime degrades to `metadata-only` + WARN
  (fail-closed); the CI gate goes RED (AC-1.2).

## R8. Quadruple-gated fetch + content-addressed store (I10-I12, AC-137.2, AC-137.3)

- Fetch happens only when all four I13 conditions hold: `cleared` AND
  `external_image_scraping_enabled()` env opt-in AND
  `assert_external_asset_allowed` AND host-allowlist pass.
  `metadata-only` / `blocked` fetch count is zero in every combination —
  regression-pinned.
- The fetch reuses the `visuals/external_image.py` machinery
  (`_fetch_manifest_image` / `_extension_for_image`) via **minimal
  publicization** — no private re-implementation (TS-1).
- Store at `assets/images/{candidate_id[:2]}/{candidate_id}{ext}`,
  `ext ∈ {.png, .jpg}`; sidecar at
  `assets/images/{candidate_id[:2]}/{candidate_id}{ext}.provenance.json`
  via `build_external_provenance` + `write_manifest`, with
  `content_sha256` (bytes hash) recorded in `additional_metadata` (I12).
- Already-stored binary → skip fetch entirely, sidecar untouched (I10).
  Signature/byte-cap validation failure → nothing written + one WARN
  (I11, AC-1.1).

## R9. Pipeline stage: post-routing, failure-isolated (I16, AC-137.1, AC-137.4)

- `orchestrator/pipeline.py` gains one stage after segment routing:
  routed items → candidate extraction → ledger merge-rewrite (R3) →
  index update (R5) → cleared fetch (R8).
- Any exception anywhere in the stage → WARN + one coverage diagnostic
  line; briefing generation / publish / notify continue unaffected. The
  stage's result is recorded in the run trace.
- Files produced by the stage (ledger, index, binaries, sidecars) join
  the existing publish staging (`git add` target list).

## R10. CI gate + reuse boundary (AC-1.1, AC-1.2, AC-1.3; TS-1..TS-4)

- New `scripts/check_image_store.py` — stdlib-only, mirrors
  `check_curated_assets.py` — exits non-zero on: missing binary↔sidecar
  pairing or missing clearance manifest for a store binary (I12);
  invalid / hash-mismatched clearance manifest (I8/I9); unrecognized
  store extension; per-file > 2,000,000 B or store total > 50,000,000 B
  (AC-1.1); R13 secret-pattern hit in ledger / index / manifests
  (AC-1.3). Wired into the GHA quality workflow (investo-ops surface).
- Module boundary: all new logic lives in `visuals/image_library.py`;
  only `orchestrator` calls it. No imports to/from
  `sources` / `briefing` / `publisher` / `notifier`.
- `EXTERNAL_IMAGE_SCRAPING_ENABLED` module default stays `False`
  (unchanged); the u86 curated library remains a separate channel with
  its own gate.

---

**Violation examples (reject in review)**: a binary stored for a
candidate with no clearance manifest, or under env default-off (R1/R8);
code writing/deleting anything under `clearances/` or auto-promoting a
rights state (R6/I14); a fetch attempt for a `blocked` or
`metadata-only` candidate in any gate combination (R8/I13); a new
manifest class or a private copy of the fetch machinery (R7/R8/TS-2);
`collected_on` from the wall clock, or a non-idempotent ledger rewrite
(R3); an image-stage exception propagating into publish (R9/I16); a
secret value in a ledger row / manifest / log line (R4); a store binary
whose sidecar lacks `content_sha256` or whose clearance `source_url`
hash mismatches the filename (R7/R8/I9/I12).
