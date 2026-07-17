# Domain Entities — `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-18
**Source**: u137-image-candidate-registry-and-licensed-store-code-generation-plan.md (Fixed Contracts #1-#4)

This unit introduces new **persisted artifacts** — a date-keyed image
candidate ledger, a recurrence index, an operator clearance directory, and
a license-gated content-addressed binary store — fed exclusively by the
u136 `image_*` raw_metadata keys. It reuses, and does not duplicate, the
`visuals/policy.py` manifest type (`ExternalAssetManifest`), the
`visuals/external_image.py` fetch machinery, and the
`visuals/provenance.py` sidecar system. `E1`-`E5`, invariants `I1`-`I17`.
`R13` below always means the **project-wide** secret-hygiene rule, not a
u137-local rule number.

---

## E1. ImageCandidateRecord (one ledger row)

One harvested image reference, persisted as one JSONL line in the date
ledger (Contract #1). pydantic v2, `frozen=True`, `extra="forbid"`.

| Attribute | Type | Notes |
|-----------|------|-------|
| `candidate_id` | str | 64-char lowercase sha256 hex of the **normalized** `image_url` (I1). Addresses the ledger row, the clearance files, and the store binary. |
| `image_url` | str | As harvested by u136 (http(s)-only, ≤ 1000 chars). Stored **un**-normalized; normalization exists only for hashing (I1). |
| `source_name` | str | Emitting adapter (`yonhap-market` / `yahoo-finance-news` / `theblock-crypto` / future adapters). |
| `segment` | str | Routed `MarketSegment` value of the carrying item. |
| `item_url` | str | The carrying `NormalizedItem`'s article URL. |
| `item_title` | str | Sanitized + capped at **160 chars** (I2, R4). |
| `image_width` | int \| None | u136 `image_width` verbatim; absent key → `None`. |
| `image_height` | int \| None | u136 `image_height` verbatim; absent key → `None`. |
| `image_mime` | str \| None | u136 `image_mime` verbatim; absent key → `None`. |
| `image_credit` | str \| None | u136 `image_credit` verbatim (already 240-char capped); re-sanitized (I2). |
| `collected_on` | date | The run's **target date** (I3). Never wall clock. |

**Invariants**

- I1 (candidate identity). `candidate_id = sha256(normalize(image_url))`
  hex, where `normalize` = lowercase scheme + lowercase host + fragment
  stripped; path / query / port preserved byte-exact. No further
  canonicalization (no query reordering, no trailing-slash trimming) —
  v1 identity is URL-hash equality only (perceptual dedup deferred, R2).
- I2 (closed, sanitized shape). `frozen=True`, `extra="forbid"`; every
  string field passes `sanitize_provenance_text` (u27 chokepoint — R13);
  `item_title` ≤ 160 chars post-sanitization; `image_credit` carries the
  u136 240-char cap (R4).
- I3 (target-date provenance). `collected_on` equals the pipeline target
  date. No code path in this unit reads the wall clock for persisted
  values (R3).
- I4 (ledger determinism + idempotency). Ledger serialization uses a
  fixed key order (model field order) and candidate_id-lexical row order;
  at most one row per `candidate_id` per date file; re-running the same
  target date over the same inputs yields a **byte-equal** file
  (merge-rewrite, existing-row-wins — R3).

---

## E2. RecurrenceIndexEntry (one entry in `index.json`)

The single committed index `archive/_meta/image_candidates/index.json`
maps `candidate_id` → entry (Contract #2). `seen_count` is the v1
"자주 쓰이는 이미지" signal (AC-137.6).

| Attribute | Type | Notes |
|-----------|------|-------|
| `first_seen` | date (ISO str) | Earliest ledger date containing the candidate. |
| `last_seen` | date (ISO str) | Latest ledger date containing the candidate. |
| `seen_count` | int ≥ 1 | Number of **distinct ledger dates** carrying the candidate (multi-day recurrence, not per-run row count). |
| `sources` | list[str] | Sorted unique `source_name`s across all appearances. |
| `rights_state` | str | `metadata-only` / `cleared` / `blocked` — a mirror of clearance-directory file existence only (E5, I7). |

**Invariants**

- I5 (atomic rewrite). The index is always fully rewritten via the
  existing `_internal/_io.write_atomic`; no in-place mutation; readers
  never observe a partial file (R5).
- I6 (derived-only, deterministic rebuild). The index is fully
  rebuildable by scanning all date ledgers + the clearances directory,
  and the rebuild is deterministic (sorted `candidate_id` keys, fixed
  entry key order, stable separators). The index carries no state that is
  not derivable from those inputs.
- I7 (rights mirror, blocked precedence). `rights_state` reflects **only**
  file existence at index-write time: `{candidate_id}.blocked` present →
  `blocked`; else `clearances/{candidate_id}.manifest.json` present and
  valid → `cleared`; else `metadata-only`. When both files exist,
  **`blocked` wins** (fail-safe precedence — decision 2026-07-18). The
  index is never a source of truth for rights (I14).

---

## E3. ClearanceManifest (alias — not a new type)

Not a new class (Contract #3). The per-candidate clearance file at
`archive/_meta/image_candidates/clearances/{candidate_id}.manifest.json`
is a complete, **operator-authored** `ExternalAssetManifest` (u19,
frozen, `extra="forbid"`) with `kind="explicit-license"`. Its fields
(`source_url`, `license`, `attribution`, `author`, `fetched_on`,
`allowed_use`) are themselves the clearance evidence.

**Invariants**

- I8 (no parallel schema; fail-closed parse). The full field set is
  required. A missing / invalid / unparseable clearance file means the
  candidate is **not** cleared — runtime treats it as `metadata-only` and
  logs one WARN; the CI gate fails on any unparseable or schema-invalid
  clearance file (R7, AC-1.2).
- I9 (URL identity). `sha256(normalize(manifest.source_url))` must equal
  the `{candidate_id}` filename stem. A clearance authored for URL A can
  never authorize fetching URL B. Mismatch → not cleared at runtime
  (WARN); CI gate RED (R7, AC-1.2).

---

## E4. StoredImageAsset (binary + provenance sidecar pair)

A cleared, fetched, validated binary plus its u24 provenance sidecar
(Contract #4).

| Attribute | Value | Notes |
|-----------|-------|-------|
| binary path | `assets/images/{candidate_id[:2]}/{candidate_id}{ext}` | Content-addressed by `candidate_id`; `ext ∈ {.png, .jpg}` — the existing `_extension_for_image` output set (I11). |
| sidecar path | `assets/images/{candidate_id[:2]}/{candidate_id}{ext}.provenance.json` | u24 `VisualProvenanceManifest` via `build_external_provenance` + `write_manifest` (R8, TS-2). |

**Invariants**

- I10 (content-addressed idempotency). The store address is the
  `candidate_id` (URL hash). When the binary already exists, the fetch is
  **skipped entirely** and the sidecar is left untouched — re-runs are
  no-ops with zero git churn (R8).
- I11 (binary integrity). Stored bytes passed the **existing**
  `visuals/external_image._extension_for_image` gate — PNG/JPEG signature
  + 100 B–2,000,000 B byte cap (AC-1.1). Validation failure → nothing
  written + one WARN (R8). No new image parser; pillow is NOT introduced
  (TS-1).
- I12 (pairing + content hash). Every store binary has exactly one
  sidecar and vice versa. The sidecar's `additional_metadata` records
  `content_sha256` — the sha256 of the stored **bytes**, distinct from
  the URL-hash `candidate_id`. Orphan binaries, orphan sidecars, or
  unrecognized extensions are CI gate RED (AC-1.2).

---

## E5. ImageRightsState (the rights state machine)

The per-candidate rights lifecycle (Contract #3). The clearances
directory encodes the state; code only reads it.

| State | Meaning | Clearance-dir file | Binary fetch/store | CI gate |
|-------|---------|--------------------|--------------------|---------|
| `metadata-only` | Default. Ledger + index presence only; republication forbidden (news wire photos / publisher thumbnails / memes live here permanently unless the operator acts). | none | **forbidden** (I13) | green |
| `cleared` | Operator verified a republication basis and authored the full manifest (E3). | `{candidate_id}.manifest.json` (valid per I8/I9) | permitted **iff** the full quadruple gate holds (I13) | green iff the manifest is valid |
| `blocked` | Operator explicit exclusion; permanent (I15). | `{candidate_id}.blocked` marker (empty file OK; wins over a coexisting manifest, I7) | **forbidden forever** | green |

**Transitions**

```
(candidate appears in a ledger) ──> metadata-only               # default: no file
metadata-only ──(operator writes clearances/{id}.manifest.json)──> cleared
metadata-only ──(operator writes clearances/{id}.blocked)──────> blocked
cleared ──(operator removes the manifest)──────────────────────> metadata-only
cleared ──(operator adds {id}.blocked)─────────────────────────> blocked   # I7 precedence
blocked ──(no code-driven exit; only operator marker removal)──> metadata-only
```

**Invariants**

- I13 (quadruple fetch gate). A binary fetch occurs only when **all
  four** hold: (1) `rights_state == cleared` with a valid manifest
  (I8/I9); (2) `external_image_scraping_enabled()` env opt-in
  (`INVESTO_EXTERNAL_IMAGE_ASSETS=1`); (3) `assert_external_asset_allowed`
  passes for the clearance manifest (invoked with the env-derived
  scraping flag — the module-level `EXTERNAL_IMAGE_SCRAPING_ENABLED`
  default stays `False` and is unchanged); (4)
  `assert_external_image_host_allowed` passes (public host + optional
  `INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS` allowlist). `metadata-only` and
  `blocked` candidates produce **zero** fetch attempts under every
  combination of the other three conditions — pinned by regression tests
  (AC-137.2).
- I14 (operator-only transitions). Clearance-directory files are
  authored and removed exclusively by the operator. No code path
  creates, modifies, or deletes files under `clearances/`; code never
  auto-promotes a rights state. The index only mirrors existence (I7).
- I15 (blocked permanence). A `blocked` candidate is permanently
  excluded from fetch candidacy. Re-appearance on later dates still
  updates the ledger and `seen_count` (metadata-everything, I17) but
  never re-candidates it for fetch while the marker exists.
- I16 (failure isolation — cross-cutting). No exception raised anywhere
  in the image-candidate stage (extraction, ledger, index, fetch, store,
  sidecar) ever fails briefing generation / publish / notify. Failures
  degrade to WARN + one coverage diagnostic line (R9, AC-137.4).
- I17 (posture — cross-cutting). **Metadata-everything,
  binaries-only-with-clearance**: every image-bearing routed item lands
  in the ledger regardless of rights; the store contains a binary only
  for candidates that satisfied I13 at fetch time. A default run (no
  clearance files, no env opt-in) stores exactly **zero** binaries
  (R1, AC-137.2).
