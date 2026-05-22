# Code Generation Plan: `u65 generated-briefing-quality-replay-harness`

**Date**: 2026-05-23
**Unit**: u65 generated-briefing-quality-replay-harness
**Stage**: Code Generation
**Status**: Complete (7/7)
**Source**: 2026-05-23 review follow-up across latest generated artifacts
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u21 summary quality gate
- u42 quality KPI history
- u54 source-status severity and quality KPI
- u56 compliance language and observational tags
- u57 segment narrative scope and time reconciliation
- u60 shared macro evidence hardening

---

## Problem Statement

Several defects were visible only after reviewing full generated artifacts together: summary breakage, status mismatch, partial navigation, watchlist mismatch, and macro/source attribution problems. Unit tests exist for many individual components, but there is no compact replay harness that evaluates a generated bundle as a user-facing artifact.

---

## Goal

Add an offline quality replay harness that can run against generated archive markdown and metadata, producing deterministic failures or warnings for the exact classes of defects found in the review.

---

## Scope Boundary

In scope:
- A local script or test helper that reads archive markdown plus quality metadata.
- Deterministic checks for first viewport, status consistency, navigation completeness, watchlist/entity sanity, and compliance wording.
- Fixture-based tests using small synthetic archive bundles.

Out of scope:
- Calling external APIs.
- Calling Claude or regenerating briefings.
- Automatically rewriting archive files.

---

## Implementation Steps

### Step 1 - Define replay input contract

- [x] Read one target date and optional segment list from local archive paths.
- [x] Load matching `archive/_meta/quality_history.jsonl` when present.
- [x] Treat missing metadata as a warning, not a crash.

### Step 2 - Add first-viewport checks

- [x] Detect heading leakage, broken emphasis, dangling tokens, and truncation.
- [x] Reuse u61 validator if already available.
- [x] Produce segment/date/field diagnostics.

### Step 3 - Add status consistency checks

- [x] Compare segment status lines with quality history and index status.
- [x] Detect `본문 사용 0` contradictions when body source traces exist.
- [x] Reuse u62 canonical snapshot helper if already available.

### Step 4 - Add navigation completeness checks

- [x] Verify expected segment nav entries for domestic, US, and crypto.
- [x] Detect silent missing segments in partial bundles.
- [x] Reuse u63 absence-state helper if already available.

### Step 5 - Add watchlist and compliance checks

- [x] Detect exact known watchlist false-positive patterns such as `BTC` -> `BTM`.
- [x] Run compliance scanner over body and watchpoints.
- [x] Warn on generic watchpoints without trigger/source.

### Step 6 - CLI/test integration

- [x] Expose the replay as either a `scripts/` command or a pytest helper.
- [x] Add fixture tests for passing and failing bundles.
- [x] Ensure diagnostics are stable and concise for CI logs.

### Step 7 - Documentation and gate

- [x] Document how to run replay against a date-stamped archive bundle.
- [x] Add the replay to the targeted validation checklist for briefing quality work.
- [x] Run targeted replay tests and `uv run mkdocs build --strict` if docs are touched.

---

## Definition of Done

- [x] A local offline command or test helper can review a generated bundle without network or LLM calls.
- [x] The review findings from 2026-05-23 are represented as deterministic checks or documented warnings.
- [x] The harness is reusable for future `서브에이전트 N개` briefing reviews.
- [x] No archive mutation or automatic backfill occurs.
