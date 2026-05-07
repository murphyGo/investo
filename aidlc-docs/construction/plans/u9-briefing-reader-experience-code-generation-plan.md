# Code Generation Plan: `u9 briefing-reader-experience`

**Date**: 2026-05-07
**Unit**: u9 briefing-reader-experience
**Stage**: Code Generation

---

## Goal

Improve the generated briefing as a reader-facing product after a five-reviewer user-perspective audit found that the output was too list-like, lacked first-screen context, repeated data-limited text, and did not expose source links.

---

## Definition of Done

- [x] Segment pages start with a proper H1, segment navigation, and a 3-line reader brief.
- [x] Zero-item segments generate a concise collection-status fallback without calling Claude.
- [x] Stage 2 prompt receives source URLs so the writer can cite important claims.
- [x] Stage 2 prompt asks for narrative newsletter structure, conservative wording, and grouped notable tickers/assets.
- [x] Targeted briefing tests pass.

---

## Steps

### Step 1 — Reader Header

- [x] Add segment markdown header: `# YYYY-MM-DD {segment label} 시황`.
- [x] Add segment navigation links between domestic-equity, us-equity, and crypto pages.
- [x] Add `오늘의 결론`, `핵심 동인`, and `주의할 점` from generated section bodies.

### Step 2 — Data-Limited Fallback

- [x] When a segment has zero routed items and is data-limited, avoid LLM calls.
- [x] Emit a concise six-section body that clearly says the regular briefing is deferred and avoids repeated generic "데이터 부족" prose.
- [x] Keep disclaimer and leak-guard validation.

### Step 3 — Source and Story Prompting

- [x] Include source URLs in Stage 2 grouped items and unassigned context.
- [x] Prompt for newsletter-style narrative rather than raw bullet dumps.
- [x] Prompt for source links, conservative wording, and grouped notable tickers/assets.

### Step 4 — Verification

- [x] Add prompt, pipeline helper, and zero-item fallback tests.
- [x] Run targeted briefing tests.
