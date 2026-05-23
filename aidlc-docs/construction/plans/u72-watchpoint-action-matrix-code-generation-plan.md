# Code Generation Plan: `u72 watchpoint-action-matrix`

**Date**: 2026-05-24
**Unit**: u72 watchpoint-action-matrix
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-05-24 ten-subagent user-quality review of generated segmented briefings
**Estimated Effort**: ~5-7 h
**Dependencies**:
- u52 prior-briefing-context-and-carryover
- u55 numeric-freshness-and-market-fact-gates
- u56 compliance-language-and-observational-tags
- u64 watchlist-entity-matching-and-actionability

---

## Problem Statement

Section §⑥ "오늘의 관전 포인트" is often more specific than before u64, but it can still read like a list of generic monitoring verbs: `관찰`, `확인`, `점검`, `비교`. A user wants to know:
- Which signal matters?
- What is the current observed state?
- What would make the signal bullish or bearish?
- How confident is the system in the evidence?
- What does this imply for the watchlist/portfolio context, without becoming investment advice?

The output should be a structured monitoring matrix, not a recommendation engine.

---

## Goal

Render watchpoints as a bounded observational matrix with these fields:
- Signal
- Current
- Bullish trigger
- Bearish trigger
- Confidence
- Portfolio implication

The matrix must stay compliance-safe, source-backed where possible, and concise enough for daily reading. Telegram should receive only a compact summary, not the full table.

Field naming is internal/English in this plan; reader-facing Korean labels should be observational:
- Bullish trigger → `상방 확인 조건`
- Bearish trigger → `하방 확인 조건`
- Portfolio implication → `섹션 내 관심 영향`

The last field is section-local context only. Direct/Related/Uncertain/Rejected watchlist workflow grouping belongs to u73.

---

## Existing Coverage / Deduplication

This unit is not a watchlist matcher rewrite.

- u64 already fixed strict entity matching, match confidence, evidence reasons, and basic watchpoint actionability.
- u52 already provides prior watchpoint/carryover context.
- u55 already owns numeric anchor verification.
- u56 already owns observational language and forbidden investment-advice phrasing.

u72 converts existing evidence into a **standard watchpoint matrix** and validates that generic watchpoints are either structured or explicitly data-limited.

u72 must consume u64 actionability outputs/diagnostics and may delegate generic-watchpoint rejection/repair to the existing u64 validator. It must not create a second source/trigger/threshold/implication validation contract.

---

## Scope Boundary

In scope:
- Prompt contract for matrix-shaped watchpoints.
- Deterministic renderer/validator for the matrix.
- Data-limited fallback when triggers cannot be source-backed.
- Compact Telegram summary behavior.

Out of scope:
- Buy/sell signals, position sizing, target prices, or portfolio optimization.
- New user accounts or brokerage integrations.
- Replacing u64 entity matching.
- New numeric data sources.

---

## Stage Decision

- **Functional Design — SKIP**. No new domain model is required unless implementation chooses a thin internal dataclass for rendering. The business rule is a presentation/validation rule.
- **NFR Requirements — SKIP**. No new external service, dependency, secret, or runtime budget.

---

## Implementation Steps

### Step 1 — Define matrix schema and allowed degradation `[ ]`
- [ ] Define required columns/fields and max visible rows.
- [ ] Define allowed confidence labels using the table below.
- [ ] Define when `데이터부족` may replace triggers.
- **Acceptance**: schema and degradation rules are pinned in tests.

Confidence labels:

| Label | Required evidence |
|-------|-------------------|
| 높음 | verified u55 anchor or u64 source-backed watchpoint plus non-limited segment coverage |
| 보통 | u64 evidence reason exists, but no verified numeric threshold or segment coverage is partial |
| 낮음 | only carryover/topic evidence exists, no fresh numeric/source anchor |
| 데이터부족 | segment coverage is limited/failed or required source/anchor is missing |

Evidence precedence for row population:
1. u55 verified anchor/core fact → `Current` and numeric trigger text.
2. u64 watchpoint evidence/reason → Signal and source-backed rationale.
3. u52 carryover item → prior context only; cannot create a new trigger by itself.
4. Otherwise render one `데이터부족` row and omit invented triggers.

### Step 2 — Update prompt contract `[ ]`
- [ ] Add Stage 2 instruction for §⑥ to produce matrix-compatible content.
- [ ] Include examples that are observational, not advisory.
- [ ] Require source-backed thresholds when present; prohibit invented thresholds.
- [ ] Allowed templates: `{지표}가 {조건}을 확인하면 상방 압력 관찰`, `{지표}가 {조건}을 이탈하면 방어적 해석`, `관심 영향: 변동성 확대 여부를 점검`.
- [ ] Banned examples: `매수`, `매도`, `비중 확대`, `목표가`, `손절`, `진입`, `청산`, and any guaranteed outcome wording.
- **Acceptance**: prompt tests assert matrix fields and compliance wording are present.

### Step 3 — Add deterministic renderer/validator `[ ]`
- [ ] Parse or normalize generated watchpoints into the matrix shape where feasible.
- [ ] Delegate generic-watchpoint rejection/repair to u64's existing watchpoint actionability validator; u72 only formats successful output into a matrix.
- [ ] Keep table compact and Markdown-safe.
- **Acceptance**: generic `확인/점검` fixture becomes data-limited or fails validation deterministically.

### Step 4 — Connect evidence inputs `[ ]`
- [ ] Integration points: consume u55 `CoreFact`/verified anchor results already passed through orchestrator, u52 `BriefingCarryover` rows from `models/carryover.py`, and u64 `WatchlistImpact` / evidence reason strings from `briefing/watchlist.py`.
- [ ] Allow verified anchors from u55 to populate `Current` or trigger references.
- [ ] Allow u52 carryover items to populate prior-signal context.
- [ ] Allow u64 watchlist evidence to populate only section-local `관심 영향`; no Direct/Related/Uncertain/Rejected grouping.
- [ ] If no evidence exists, produce an explicit data-limited note instead of a fake matrix row.
- **Acceptance**: at least one test row uses each evidence type without cross-segment leakage.

### Step 5 — Notification behavior `[ ]`
- [ ] Telegram summary includes at most one compact watchpoint line or link cue.
- [ ] Full matrix stays on the static site/markdown briefing.
- [ ] Compliance scanner runs on both full and compact text.
- **Acceptance**: notifier tests show no large table in Telegram payload.

### Step 6 — Tests and gate `[ ]`
- [ ] Unit tests for schema, validation, degradation, compliance, and notification compactness.
- [ ] Replay fixture for generic watchpoints found in the review.
- [ ] Run targeted publisher/briefing/notifier tests, ruff, and mypy if source signatures change.

---

## Acceptance Criteria

- **AC-72.1** — §⑥ renders a bounded matrix/list with Signal, Current, Bullish trigger, Bearish trigger, Confidence, and Portfolio implication.
- **AC-72.2** — Missing triggers require explicit `데이터부족` evidence; generic monitor verbs alone are not enough.
- **AC-72.3** — Matrix rows can consume verified anchors, carryover items, and watchlist evidence without inventing facts.
- **AC-72.4** — Compliance scanner blocks investment-advice wording.
- **AC-72.5** — Telegram remains concise and does not embed the full matrix.

---

## Tests / Validation

Expected test areas:
- `tests/unit/briefing/test_prompts*.py`
- `tests/unit/publisher/test_reader_format*.py`
- `tests/unit/notifier/test_summary.py`
- `tests/unit/publisher/test_briefing_replay.py`

Minimum local gate:
- Targeted pytest for changed areas.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if typing contracts change.

---

## Non-Goals

- Trading recommendations.
- Auto-generated orders or alerts.
- New portfolio accounting.
- A charting change.
