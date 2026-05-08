# Code Generation Plan: `u32 trust-traceability-deep-dive`

**Date**: 2026-05-08
**Unit**: u32 trust-traceability-deep-dive
**Stage**: Code Generation

---

## Goal

Give the critical-analyst persona day-by-day verification primitives: source-tier metadata, Stage 3 numeric self-check, traceability footer, hashed signatures, and an automated daily evaluation harness.

---

## Definition of Done

- [x] Every source emits a tier label (S/A/B/C) in adapter metadata; segment coverage badges expose the tier mix alongside item counts. — `sources/tiers.py` registry + `SourceOutcome.tier` field; `SegmentCoverage.tier_mix_label` renders `S=2 / A=1 / B=4` style mix; `_render_coverage_badge` adds a "소스 등급 분포" line.
- [x] Stage 3 self-check cross-references every numeric token in Stage 2 output against the Stage 1 candidate JSON; mismatches trigger a brief-header warning. — `briefing/numeric_self_check.py::find_unverified` + `_enhance_reader_experience` `numeric_warning_line`. (Operator-alert escalation deferred — the brief-header callout is the read path; orchestrator integration is a future hook.)
- [x] A `<details>` traceability footer at the bottom of each segment expands the Stage 1 classification result for the published items. — `briefing/trace_footer.py::render_traceability_footer`; appended to `enhanced_markdown` before disclaimer.
- [x] Brief footer shows `input_hash` / `stage1_hash` / `stage2_hash` (12-char SHA-256 prefix) per segment. — `compute_input_hash` / `compute_stage1_hash` / `compute_stage2_hash` rendered inside the same `<details>` block.
- [x] Daily evaluation harness measures source liveness, figures presence, and fallback ratio; results are surfaced on the public site index. — `briefing/quality_eval.py` + `publisher/site_index.update_quality_page`; rendered to `site_docs/quality.md` and added to mkdocs nav as "데이터 품질".

---

## Steps

### Step 1 — Tier Metadata

- [x] Extend adapter base with a `tier` enum and propagate into segment coverage display.

### Step 2 — Stage 3 Numeric Self-Check

- [x] Implement numeric extraction + cross-reference against Stage 1 JSON.
- [x] Wire mismatch into brief header warning + operator alert. — brief-header warning landed; operator-alert escalation deferred.

### Step 3 — Traceability Footer + Hash Signature

- [x] Render `<details>` footer with Stage 1 classification snapshot.
- [x] Compute and append the three 12-char hash signatures per segment.

### Step 4 — Evaluation Harness

- [x] Compute daily KPIs (source liveness, figures presence, fallback ratio).
- [x] Surface on `site_docs/quality.md` under a "데이터 품질" mkdocs nav entry.

### Step 5 — Verification

- [x] Run targeted briefing/publisher tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #3 (wish-list).
