# Code Generation Plan: `u56 compliance-language-and-observational-tags`

**Date**: 2026-05-13
**Unit**: u56 compliance-language-and-observational-tags
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings, deduplicated against u51/u52/u53.
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u21 summary-quality-gate (publish-time first-viewport validation).
- u23 notification-actionability (Telegram summary surface).
- u25 summary-fidelity-and-content-trust (conservative wording).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u51: actionability/readability ratio for `§⑥` wording, non-blocking.
- u52: prior-day bridge and carryover.
- u53: data input expansion.

This unit owns **regulatory/compliance language risk**, not reader scanability.

---

## Goal

Prevent generated briefings and Telegram summaries from drifting into investment-advice wording. The footer disclaimer is necessary but not sufficient if the first viewport or prompt encourages action-instruction language.

Observed risks:
- Prompt examples allow `매수 검토`, `비중 축소`, `헤지 확대`, `손절 라인 설정`.
- `[강세]` and `[약세]` can read like an investment stance rather than market observation.
- Phrases such as `직접 반영된다`, `작용할 전망`, `추가 하방 시험` overstate certainty.
- Footer disclaimer appears only after the full article.

---

## Definition of Done

- [ ] Stage 2 prompt forbids direct trading-action instructions and uses observation/check language.
- [ ] Publish gate detects high-risk advisory, guarantee, and direct-action phrases.
- [ ] Action tags are renamed or rendered as observation labels in first viewport and Telegram.
- [ ] A short information-only disclaimer appears within the first viewport.
- [ ] Existing canonical footer disclaimer remains unchanged and verified.

---

## Steps

### Step 1 — Prompt language correction

- [ ] Replace action-instruction examples with `관찰`, `확인`, `리스크 점검`, `시나리오 비교`.
- [ ] Add a CARRY-safe rule: no personalized advice, no position sizing, no entry/exit/stop-loss wording.
- [ ] Add tests that prompt text does not contain banned examples.

### Step 2 — Compliance phrase gate

- [ ] Add `compliance_language.py` or extend `summary_quality.py` with high-risk phrase detection.
- [ ] Block P0 phrases: `매수 검토`, `비중 축소`, `손절`, `진입`, `청산`, `목표가`, `반드시`, `확실`.
- [ ] Warn/soften P1 phrases: `직접 반영된다`, `작용할 전망`, `불가피`, overconfident causal wording.

### Step 3 — Observational action tags

- [ ] Change first-viewport tag vocabulary from stance-like labels to observation labels such as `상승 관찰`, `하락 관찰`, `혼재`, `변동성 확대`.
- [ ] Preserve internal compatibility if existing `ActionTag` enum is used elsewhere.
- [ ] Update notifier summary formatting to avoid raw high-risk tags.

### Step 4 — First-viewport short disclaimer

- [ ] Add fixed short text near the first summary block: `정보 제공용 자동 시황이며 매매 권유가 아닙니다.`
- [ ] Gate that the short disclaimer appears within the first 30 rendered lines.
- [ ] Ensure the canonical footer disclaimer is still appended and verified.

### Step 5 — Tests and gates

- [ ] Unit tests for banned phrase detection and allowed observation wording.
- [ ] Publisher/orchestrator tests for first-viewport disclaimer.
- [ ] Notifier tests for Telegram-safe tag rendering.
- [ ] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src/`, `uv run pytest -q`, `uv run mkdocs build --strict`.

---

## Out of Scope

- Making `§⑥` more actionable for readers (u51).
- Numeric/factual verification (u55).
- Segment routing/time reconciliation (u57).

