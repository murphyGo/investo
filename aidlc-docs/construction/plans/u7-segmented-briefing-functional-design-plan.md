# Functional Design Plan: `u7 segmented briefing`

**Date**: 2026-05-07
**Unit**: u7 segmented briefing — Domestic / US / Crypto briefing split
**Stage**: Functional Design
**Trigger**: Production briefing over-focused on one market when surviving sources were skewed. User requested three separate briefings: domestic equities, US equities, and crypto.

---

## Unit Context

### Product Goal

Generate three independent daily market briefings in one pipeline run:

1. `domestic-equity` — 국내 증시
2. `us-equity` — 미국 증시
3. `crypto` — 크립토

The goal is not merely cosmetic sectioning. Each segment must have its own input boundary and quality behavior so a strong Korea-only news day, a Yahoo outage, or a crypto-heavy day cannot dominate unrelated market coverage.

### Existing Units Reused

- u1 sources: raw `NormalizedItem` collection remains unchanged for v1 of this unit.
- u2 briefing: Claude Code CLI, retry/budget, disclaimer, leak guard, parsing primitives are reused.
- u3 publisher: markdown write + git commit/push remains the persistence mechanism.
- u4 notifier: Telegram channel remains the delivery channel.
- u5 orchestrator: still owns the run lifecycle and failure routing.
- u6 infra/CI: no schedule change required.

### Stage Decisions

| Stage | Decision | Rationale |
|-------|----------|-----------|
| Functional Design | Execute | New business contract: segmentation, fallback, paths, notification shape. |
| NFR Requirements | Skip | Existing u2/u5 NFRs still apply; no new dependency or external SLA. |
| Code Generation | Execute | Requires code changes across briefing/orchestrator/publisher/notifier tests. |

---

## Execution Checklist

### Part 1 — Planning

- [x] Define segment IDs and user-facing labels.
- [x] Define input routing rules for source/category/title/ticker provenance.
- [x] Define insufficient-data behavior.
- [x] Define archive path and public URL shape.
- [x] Define Telegram message shape.
- [x] Define orchestration success/failure policy.

### Part 2 — Generation

- [x] `aidlc-docs/construction/u7-segmented-briefing/functional-design/domain-entities.md`
- [x] `aidlc-docs/construction/u7-segmented-briefing/functional-design/business-rules.md`
- [x] `aidlc-docs/construction/u7-segmented-briefing/functional-design/business-logic-model.md`
- [x] `aidlc-docs/construction/plans/u7-segmented-briefing-code-generation-plan.md`
- [x] `aidlc-docs/aidlc-state.md` updated
- [x] `docs/requirements.md` updated with FR-008

---

## Key Questions Resolved

### Q1. Output shape

Decision: three separate markdown briefings, not one long page with three headings.

Reasoning: Independent URLs and archive files make Telegram links clear, preserve history per market, and let later retries/regeneration target one segment.

### Q2. Archive path

Decision:

```text
archive/{segment}/YYYY/MM/YYYY-MM-DD.md
```

Public URL:

```text
{SITE_URL_BASE}/archive/{segment}/YYYY/MM/YYYY-MM-DD/
```

### Q3. Input fallback

Decision: do not substitute another market's news to fill a segment. If a segment has too little signal, generate a data-limited briefing with an explicit "데이터 부족" note.

### Q4. LLM calls

Decision: v1 allows three independent u2 generation calls. This is slower but maximally isolates quality. If runtime pressure appears, optimize later with shared classification or a multi-output prompt.

### Q5. Notification

Decision: one Telegram message per run containing a short summary and three links. Avoid three channel messages per day unless later requested.

