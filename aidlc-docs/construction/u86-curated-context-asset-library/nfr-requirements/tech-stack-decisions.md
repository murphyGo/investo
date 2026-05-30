# Tech-Stack Decisions — `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Source**: u86-curated-asset-library-code-generation-plan.md

`TS-1`-`TS-3`. These record the binding library/dependency choices for u86.

---

## TS-1. No new dependency — reuse existing binary signature + dimension parsing

- **Decision**: u86 adds **no** new third-party dependency. In particular,
  **pillow is NOT introduced.**
- **Rationale**: `visuals/assets.py` already parses PNG / JPEG / SVG
  signatures and extracts dimensions for the existing validation gate. The
  curated-asset binary checks (signature, dimensions, format restriction —
  AC-1.1 / R4) reuse that code verbatim. A heavyweight imaging dependency
  for read-only signature/dimension inspection is unjustified and would
  enlarge the dependency surface against the project's free/lean posture.

## TS-2. Reuse the existing manifest + provenance types — no parallel schema

- **Decision**: extend the **existing** `visuals/policy.py`
  `AllowedExternalAssetKind` literal with `"curated-licensed"` and reuse
  `ExternalAssetManifest` (frozen pydantic v2). Reuse `visuals/provenance.py`
  (`build_external_provenance` / `provenance_caption` / `write_manifest`);
  add a thin `build_curated_provenance` only if the existing builder cannot
  represent `curated-licensed`.
- **Rationale**: a second manifest/caption type would fork the secret-hygiene
  chokepoint (R7 / AC-1.6) and the provenance contract. Reuse keeps the R13
  redaction path single-sourced (u27).

## TS-3. CI gate as a stdlib script mirroring `check_no_paid_apis.py`

- **Decision**: the license-compliance gate (AC-1.2) ships as
  `scripts/check_curated_assets.py`, a stdlib-only Python script (no new
  dependency) wired into the existing lint job alongside
  `check_no_paid_apis.py`. JSON manifest parsing uses stdlib `json`; the
  deferral marker (I16) is a filesystem check; secret screening reuses the
  u27 redaction chokepoint already in-tree.
- **Rationale**: matches the established no-paid-apis gate pattern, keeps the
  blocking-gate ergonomics consistent, and adds zero dependency.

---

**Net dependency delta for u86: none.**
