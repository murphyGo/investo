# NFR Requirements — `u86 curated-context-asset-library`

**Date**: 2026-05-28
**Source**: u86-curated-asset-library-code-generation-plan.md (NFR REQUIRED-focused)

This document fixes measurable, testable acceptance criteria for the two
new NFR surfaces u86 introduces — committed-binary **storage budget** and a
blocking **license-compliance CI gate** — plus R13 manifest secret hygiene.
It does **not** duplicate the FD rules (`R1`-`R9`); it adds the testable AC
layer and CI-gate contract on top of them. Anything not listed is OUT of
scope for u86.

ACs: `AC-1.1`-`AC-1.6`. FD references: `R1`-`R9`, `E1`-`E5`, `I1`-`I16`.

---

## NFR-Storage: Repository / Pages binary size budget

Committed binaries grow the git repo and the GitHub Pages deploy. u86 caps
them.

### Acceptance criteria

- **AC-1.1** — Storage budget, blocking at load + CI:
  - Per-asset binary ≤ **500 KB** (raster) / ≤ **64 KB** (SVG).
  - Total library binary footprint ≤ **20 MB** across all `filed` assets.
  - Image dimensions within the **existing** 100-2000 px gate
    (`visuals/assets.py`) — reused, not re-implemented (R4).
  - Format restricted to `png` / `jpg` / `jpeg` / `svg` (existing
    signature parsers). Any over-budget / out-of-bounds / unknown-format
    `filed` asset fails the gate (R4). **Deferred** assets carry no binary
    and are exempt from the byte/dim budget (R8 / I10), but the *count* of
    deferred keys is unbounded only because they cost zero committed bytes.
  - Guidance (non-blocking): prefer pre-compressed assets; the unit ships no
    compression pipeline (Non-Goal).
  - Pinned by a test that injects an over-budget fixture and asserts the
    gate rejects it with a byte-budget message.

## NFR-License: License-compliance blocking CI gate

A blocking gate, mirroring `scripts/check_no_paid_apis.py`, asserting every
`filed` library asset is republishable and every registered key is in a
sanctioned state.

### Acceptance criteria

- **AC-1.2** — A CI-runnable check (`scripts/check_curated_assets.py`,
  parallel to `check_no_paid_apis.py`, wired into the lint job) **exits
  non-zero** on any of:
  - a binary with no sibling manifest (R1);
  - a binary-absent registered key with **no** explicit `deferred` marker —
    a silent empty (R8 / I14);
  - a manifest carrying a disallowed / unrecognized license (R2, fail-closed);
  - a byte / dimension / format budget violation on a `filed` asset (AC-1.1);
  - an orphan manifest (manifest with neither binary nor deferral marker), or
    a registry id that resolves to no library entry (I8).
  - **Deferred-asset recognition (binding)**: an **explicitly** `deferred`
    key (deferral marker present, no binary) **passes** the gate (exit 0).
    The gate distinguishes `deferred` (green) from silent-empty (red) by the
    presence of the machine-checkable marker (I16) — this is the AC-level
    realization of the user's deferred-allowance policy.
  - **Auto-verification on fill**: when a deferred key's binary is later
    committed and the marker removed, the same gate re-classifies it as
    `filed` and applies R2/R3/R4 + AC-1.1 with no script edit (I15).
  - Pinned by: (a) gate passes on the seed library (filed seeds + deferred
    keys); (b) gate fails on an injected unmanifested fixture; (c) gate fails
    on an injected silent-empty (binary-absent, no marker); (d) gate passes
    on an injected explicit-deferred fixture.

- **AC-1.3** — Republishability + excluded-category enforcement (R2/R3):
  - Every `filed` asset's `license` / `allowed_use` clears republication to
    public Pages + public Telegram. Accepted bases enumerated in R2.
  - A news-photo / meme / corporate-trademark-logo / unofficial-real-person-
    portrait fixture is **rejected** by clearance (R3). Pinned by negative
    tests, one per excluded category.

- **AC-1.5** — No runtime fetch; scraping stays disabled (R4):
  - `EXTERNAL_IMAGE_SCRAPING_ENABLED` is asserted still `False`; the curated
    path performs **zero** external HTTP calls (pinned by a test that fails
    if any `httpx` / network call occurs on the curated selection +
    injection path). The `explicit-license` runtime-scraping path is
    unchanged (its tests stay green).

## NFR-Provenance: caption presence on every used asset

- **AC-1.4** — Every *selected* (filed) curated asset that renders as a hero
  emits a provenance caption (source / license / author) via the existing
  `provenance_caption`, and writes a provenance manifest via `write_manifest`
  (R9). The disclaimer is present and unchanged. Deferred assets never render
  and emit no caption (R8). Pinned by a test asserting caption + disclaimer
  presence on a matched-curated segment, and caption absence on a no-match
  segment.

## NFR-Secret: R13 manifest secret hygiene

- **AC-1.6** — No secret value appears in any manifest, registry entry, or
  provenance artifact (R7 / R13). Manifest + provenance text routes through
  the project-wide u27 redaction chokepoint
  (`investo._internal.redaction.redact_text`), exactly as
  `visuals/provenance.py` already does. The CI gate (AC-1.2) rejects any
  manifest matching the redaction patterns. Pinned by a test injecting a
  Telegram-token-shaped / OpenAI-key-shaped value into a manifest field and
  asserting the gate rejects it.

---

## NFR AC ↔ Step coverage map

| AC | Concern | Covered by step |
|----|---------|-----------------|
| AC-1.1 | Storage / Pages byte + dimension budget | Step 1, Step 2 |
| AC-1.2 | License-compliance blocking CI gate (incl. explicit-deferred recognition) | Step 2, Step 5 |
| AC-1.3 | Republishability + excluded-category rejection | Step 1, Step 2, Step 6 |
| AC-1.4 | Provenance caption on every used asset | Step 4 |
| AC-1.5 | No runtime fetch / scraping stays disabled | Step 4, Step 6 |
| AC-1.6 | Secret hygiene in manifests (R13) | Step 2 |
