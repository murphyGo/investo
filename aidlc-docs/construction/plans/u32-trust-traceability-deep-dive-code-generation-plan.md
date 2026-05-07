# Code Generation Plan: `u32 trust-traceability-deep-dive`

**Date**: 2026-05-08
**Unit**: u32 trust-traceability-deep-dive
**Stage**: Code Generation

---

## Goal

Give the critical-analyst persona day-by-day verification primitives: source-tier metadata, Stage 3 numeric self-check, traceability footer, hashed signatures, and an automated daily evaluation harness.

---

## Definition of Done

- [ ] Every source emits a tier label (S/A/B/C) in adapter metadata; segment coverage badges expose the tier mix alongside item counts.
- [ ] Stage 3 self-check cross-references every numeric token in Stage 2 output against the Stage 1 candidate JSON; mismatches trigger a brief-header warning and an operator alert.
- [ ] A `<details>` traceability footer at the bottom of each segment expands the Stage 1 classification result for the published items.
- [ ] Brief footer shows `input_hash` / `stage1_hash` / `stage2_hash` (12-char SHA-256 prefix) per segment.
- [ ] Daily evaluation harness measures URL 200 OK ratio, EPS/figures presence, and fallback ratio; results are surfaced on the public site index.

---

## Steps

### Step 1 — Tier Metadata

- [ ] Extend adapter base with a `tier` enum and propagate into segment coverage display.

### Step 2 — Stage 3 Numeric Self-Check

- [ ] Implement numeric extraction + cross-reference against Stage 1 JSON.
- [ ] Wire mismatch into brief header warning + operator alert.

### Step 3 — Traceability Footer + Hash Signature

- [ ] Render `<details>` footer with Stage 1 classification snapshot.
- [ ] Compute and append the three 12-char hash signatures per segment.

### Step 4 — Evaluation Harness

- [ ] Compute daily KPIs (URL liveness, figures presence, fallback ratio).
- [ ] Surface on `docs/index.md` (or `docs/quality/index.md`) under a "데이터 품질" block.

### Step 5 — Verification

- [ ] Run targeted briefing/publisher tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #3 (wish-list).
