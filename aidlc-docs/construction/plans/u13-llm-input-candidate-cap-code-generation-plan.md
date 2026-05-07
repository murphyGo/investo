# Code Generation Plan: `u13 llm-input-candidate-cap`

**Date**: 2026-05-07
**Unit**: u13 llm-input-candidate-cap
**Stage**: Code Generation

---

## Goal

Keep segmented briefing generation within the Claude retry budget when one source returns hundreds of low-signal rows.

---

## Definition of Done

- [x] Stage 1/2 LLM inputs are bounded before prompt serialization.
- [x] A single noisy source cannot consume the entire candidate set.
- [x] Later sources still survive when an earlier source returns many rows.
- [x] Existing zero-item/data-limited behavior remains unchanged.

---

## Steps

### Step 1 — Candidate Selection

- [x] Add a source-diversity cap before classification.
- [x] Cap the total LLM candidate set.
- [x] Feed the same selected candidates into section planning.

### Step 2 — Regression Tests

- [x] Assert a noisy single source is capped.
- [x] Assert later sources remain present after the cap.
- [x] Assert the total candidate set is bounded.
