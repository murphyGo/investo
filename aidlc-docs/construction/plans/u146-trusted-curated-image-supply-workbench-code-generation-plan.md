# Code Generation Plan: `u146 trusted-curated-image-supply-workbench`

**Date**: 2026-08-03
**Status**: Complete (2026-08-03)
**Source**: User request to increase approved images and use graph engineering when needed

## Stage Decision

- Functional Design: Required
- NFR Requirements: Required
- Reason: exact-file external evidence, operator approval, path confinement, immutable digests, and CI filing policy form a new compliance trust boundary.
- Source of requirements: FR-002, FR-003, FR-008, NFR-002, NFR-003, NFR-006, NFR-007/R13, NFR-008; u86/u137 no-auto-clear contracts; 2026-08-03 independent approval-graph review.

## Fixed Contracts

1. `CuratedRightsEvidence` and `CuratedOperatorDecision` remain separate from the existing seven-field `ExternalAssetManifest`.
2. The Phase-1 provider is exactly `wikimedia-commons-exact-file`; only file-specific PD/CC0 can become `READY_FOR_REVIEW`.
3. The workbench is offline and writes only a pending review directory outside repository asset/store/clearance roots. It never writes a manifest, registry row, approved decision, u137 clearance, or binary into the library.
4. Every digest verifies exact stored bytes. A new filing is valid only when snapshot, evidence, approved decision, binary, manifest, and registry entry form one matching chain.
5. The current 15 assets are allowed only through `legacy-v0.json`, which fixes binary/manifest relative paths and SHA-256. Later assets cannot be added to legacy-v0.
6. Filed orphan assets, orphan rights artifacts, incomplete chains, duplicate JSON keys, path traversal, secret-shaped values, and hash/metadata mismatches fail CI.

## Steps

### Step 1 - Design and registration `[x]`
- [x] Register u146/u147 in the unit map, story map, and AIDLC state.
- [x] Write u146 functional/NFR contracts and this plan with no unresolved decision placeholders.

### Step 2 - Evidence models and offline workbench `[x]`
- [x] Implement frozen evidence/decision models, strict JSON loader, Commons exact-file assessment, binary verification, deterministic packet writer, and path confinement.
- [x] Add blocked/ready, duplicate-key, protected-output, deterministic-output, and no-auto-clear tests.

### Step 3 - Legacy seal and full filing gate `[x]`
- [x] Create the exact 15-entry legacy-v0 seal and integrate exact-byte graph validation into `check_curated_assets.py`.
- [x] Cover legacy tamper and current complete-graph regression; the gate itself rejects incomplete chains, orphan rights artifacts, digest mismatches, and unreachable filings.

### Step 4 - File reviewed Commons assets `[x]`
- [x] Preserve exact source snapshots and evidence for data center, gold, Bitcoin mining, and renewable-grid subjects. Reject the otherwise-valid semiconductor candidate because its exact Commons binary URL triggers the unchanged R13 secret-shape gate; reject the dated KOSPI thumbnail because its selected PNG response provides no provider checksum and the 2055px original exceeds the unchanged binary-dimension gate.
- [x] Add separately authored approved decisions, manifests, binaries, and registry references after subject/restriction/endorsement review.
- [x] Verify the gate reports 19 filed, zero deferred, zero orphan assets.

### Step 5 - Quality gate and independent review `[x]`
- [x] Run focused tests, Ruff/format, mypy, no-paid, curated gate, strict docs build when applicable, and `git diff --check`.
- [x] Obtain fresh-eyes review and resolve every Critical/High/Medium finding.
- [x] Write code summary/session/audit evidence and update AIDLC state.

## Non-goals

- No daily/runtime network call, source adapter, secret, automatic search, automatic approval, u137 clearance mutation, or Telegram delivery.
- No CC BY/SA, WordPress Photo Directory filing, Openverse, Unsplash/Pexels, government-photo inference, or feed-image rights promotion in Phase 1.
