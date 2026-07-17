# Tech-Stack Decisions — `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-18
**Source**: u137-image-candidate-registry-and-licensed-store-code-generation-plan.md (Stage Decision item d + Existing Coverage list)

`TS-1`-`TS-4`. These record the binding library/dependency choices for u137.

---

## TS-1. No new dependency — reuse existing fetch, signature, and dimension machinery

- **Decision**: u137 adds **no** new third-party dependency. In
  particular, **pillow is NOT introduced.**
- **Rationale**: `visuals/external_image.py` already implements the
  licensed fetch (`_fetch_manifest_image`), the PNG/JPEG signature check
  and byte cap (`_extension_for_image`, 100 B-2,000,000 B), and
  `visuals/assets.py` already reads image dimensions for provenance.
  u137 exposes the **minimum** of that machinery needed by
  `visuals/image_library.py` (minimal publicization — R8) and forbids
  private re-implementation. HTTP stays on the existing `httpx` client
  path; hashing uses stdlib `hashlib`.

## TS-2. Reuse the existing manifest + provenance types — no parallel schema

- **Decision**: the operator clearance file is the **existing**
  `ExternalAssetManifest` with `kind="explicit-license"` (E3 — no new
  manifest class, no new `kind` literal). Store sidecars are the
  **existing** u24 `VisualProvenanceManifest` via
  `build_external_provenance` + `write_manifest`. Two minimal,
  additive accommodations are permitted: (a) recording
  `content_sha256` in `additional_metadata`, and (b) writing the sidecar
  at the Contract #4 path `{candidate_id}{ext}.provenance.json` (the u24
  default sidecar convention is `<asset>.json`; the `.provenance.json`
  name is pinned by the plan's Fixed Contract #4 so the CI gate can
  address sidecars unambiguously). No schema fork.
- **Rationale**: a parallel manifest type would fork the R13 redaction
  chokepoint (u27) and the clearance semantics; u86's TS-2 precedent
  applies unchanged.

## TS-3. CI gate as a stdlib script mirroring `check_curated_assets.py`

- **Decision**: the license-compliance gate (AC-1.2) ships as
  `scripts/check_image_store.py`, a stdlib-only Python script (no new
  dependency) wired into the GHA quality workflow alongside the existing
  gates. JSON parsing uses stdlib `json`; hashing stdlib `hashlib`;
  secret screening reuses the u27 redaction patterns already in-tree.
- **Rationale**: matches the established `check_curated_assets.py` /
  `check_no_paid_apis.py` blocking-gate pattern with zero dependency
  delta.

## TS-4. Persistence is JSONL + JSON on git — no database

- **Decision**: the candidate ledger is date-keyed JSONL and the
  recurrence index is a single JSON file, both written with the existing
  `_internal/_io.write_atomic` primitives and committed to the repo
  (`archive/_meta/` precedent). No sqlite / tinydb / parquet.
- **Rationale**: the storage backend of this project is the git repo
  (CLAUDE.md tech stack); volumes are tiny (tens of rows/day), the
  merge-rewrite discipline (R3) gives deterministic diffs, and any
  database file would be opaque to review and to the CI gates.

---

**Net dependency delta for u137: none.**
