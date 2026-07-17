# NFR Requirements — `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-18
**Source**: u137-image-candidate-registry-and-licensed-store-code-generation-plan.md (NFR REQUIRED-focused, Stage Decision items a-d)

This document fixes measurable, testable acceptance criteria for the NFR
surfaces u137 introduces — committed-binary **storage budget** and a
blocking **license-compliance CI gate** — plus R13 secret hygiene across
the new persisted artifacts. It does **not** duplicate the FD rules
(`R1`-`R10`); it adds the testable AC layer and CI-gate contract on top.
Anything not listed is OUT of scope for u137.

ACs: `AC-1.1`-`AC-1.3` (unit-local numbering, u86 convention — distinct
from the plan's unit-level `AC-137.1`-`AC-137.6`). FD references:
`R1`-`R10`, `E1`-`E5`, `I1`-`I17`. Stage Decision item (d) — no new
dependency — is recorded as `TS-1`/`TS-3` in
`tech-stack-decisions.md`, not as an AC.

---

## NFR-Storage: Repository / Pages binary size budget

Cleared binaries grow the public git repo and the GitHub Pages deploy.
u137 caps them at both fetch time and CI time.

### Acceptance criteria

- **AC-1.1** — Storage budget, blocking at fetch + CI:
  - Per-file cap: ≤ **2,000,000 bytes** — the **existing**
    `visuals/external_image._MAX_IMAGE_BYTES` cap, reused, not
    re-declared (I11). The 100-byte minimum also carries over.
  - Store total: ≤ **50,000,000 bytes** across everything under
    `assets/images/` (binaries; sidecar JSON counts toward the total).
  - Format restricted to the existing signature-parser output set
    (`.png` / `.jpg`); any unrecognized extension in the store fails the
    gate (I12 / AC-1.2).
  - Enforced twice: the fetch path refuses to write an over-cap binary
    (I11, WARN, nothing stored); `scripts/check_image_store.py` fails
    CI on any per-file or total-budget breach.
  - Pinned by tests that (a) reject an over-cap fetch body, and
    (b) inject an over-budget store fixture and assert the gate exits
    non-zero with a byte-budget message.

## NFR-License: License-compliance blocking CI gate

A blocking gate, mirroring `scripts/check_curated_assets.py`, asserting
the store contains **only** operator-cleared, fully documented binaries.

### Acceptance criteria

- **AC-1.2** — A CI-runnable check (`scripts/check_image_store.py`,
  stdlib-only, wired into the GHA quality workflow) **exits non-zero**
  on any of:
  - a store binary with no valid `…{ext}.provenance.json` sidecar, or a
    sidecar missing `content_sha256` (I12);
  - a store binary with no corresponding clearance manifest
    `clearances/{candidate_id}.manifest.json` (R7);
  - an invalid / unparseable / hash-mismatched clearance manifest —
    including manifests whose `sha256(normalize(source_url))` differs
    from the `{candidate_id}` filename (I8 / I9, fail-closed; RED even
    when no binary was stored for it);
  - an orphan sidecar (sidecar with no binary) or an unrecognized store
    extension (I12);
  - a per-file / store-total budget breach (AC-1.1);
  - an R13 secret-pattern hit (AC-1.3).
  - **Green states (binding)**: an empty store passes; a
    metadata-only-everything state (ledgers + index present, zero
    binaries, zero clearances) passes; a `blocked` marker with no binary
    passes. The gate polices the **store**, not the operator's clearance
    backlog.
  - Pinned by fixtures: (a) clean paired store → exit 0; (b) injected
    orphan binary → RED; (c) injected binary-without-clearance → RED;
    (d) injected hash-mismatched clearance → RED; (e) empty store →
    exit 0 — each failure with a distinct, clear message.

## NFR-Secret: R13 hygiene across the new persisted artifacts

- **AC-1.3** — No secret value appears in any ledger row, index entry,
  clearance-derived provenance sidecar, or this unit's log lines
  (project rule R13). All persisted string fields route through the
  project-wide u27 redaction chokepoint via `sanitize_provenance_text`
  (R4), exactly as `visuals/provenance.py` already does. The CI gate
  (AC-1.2) additionally scans ledgers / index / manifests for the
  redaction patterns. Pinned by a test injecting a Telegram-token-shaped
  value into a candidate `item_title` and asserting the persisted row is
  redacted, plus a gate-level test asserting a secret-bearing manifest
  fixture goes RED.

---

## NFR AC ↔ Step coverage map

| AC | Concern | Covered by step |
|----|---------|-----------------|
| AC-1.1 | Storage budget (2,000,000 B/file reuse + 50,000,000 B store total) | Step 3, Step 5 |
| AC-1.2 | License-compliance blocking CI gate (pairing + clearance + fail-closed manifests) | Step 3, Step 5 |
| AC-1.3 | R13 secret hygiene in ledger / index / manifests / logs | Step 1, Step 3, Step 5 |
