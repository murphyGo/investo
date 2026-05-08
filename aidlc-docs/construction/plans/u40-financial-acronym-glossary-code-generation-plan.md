# Code Generation Plan: `u40 financial-acronym-glossary`

**Date**: 2026-05-09
**Unit**: u40 financial-acronym-glossary
**Stage**: Code Generation
**Status**: ✅ Complete
**Source**: 10-persona evaluation 2026-05-09 — persona #1 (초보 직장인) + persona #5 (국내 페르소나)
**Estimated Effort**: ~1 h
**Dependencies**:
- Builds on `u2 briefing` (`briefing/prompts.py::STAGE2_SYSTEM` is the prompt chokepoint).
- Coexists with `u32 trust-traceability-deep-dive` (`briefing/numeric_self_check.py`) — this unit adds a parallel post-render check for unexplained acronyms.
- No model / source change.

---

## Goal

Make the briefing readable for the 95% of readers who do not know what `EIA` / `DXY` / `ESM26` / `프로그램매매` / `숏커버링` mean on first read. Add a Stage 2 prompt rule that requires every financial acronym, ticker code, or market jargon to carry a 1-3-word Korean parenthetical gloss on first appearance per segment, and add a deterministic post-render glossary check that flags first-appearance acronyms missing a gloss.

---

## Persona evidence

> Persona #1 (초보 직장인, P0): "EIA 주간 재고 — 이게 뭔지 처음 보는 사람은 모름. DXY 도. ESM26 도 시황 첫 줄에 그냥 던져놓으면 읽다가 멈춘다."

> Persona #5 (국내, P0): "프로그램매매, 숏커버링 같은 한국 시장 jargon 도 똑같이 풀어줘야 한다. '한국 사람이라 다 알 거다' 가정 금물 — 직장인 초보가 더 많다."

Both personas converge on one rule: **on first appearance per segment, every acronym / ticker / market jargon must carry a 1-3-word Korean gloss in parentheses.** Subsequent appearances do not need a re-gloss (avoids reading-noise inflation).

---

## Definition of Done

- [x] `briefing/prompts.py::STAGE2_SYSTEM` carries an explicit "약자 풀어쓰기 룰" rule block: every financial acronym (`EIA`, `DXY`, `CPI`, `FOMC`, etc.), every futures contract code (`ESM26`, `NQU25`, etc.), and every market jargon term (`프로그램매매`, `숏커버링`, `옵션만기`, `배당락`, etc.) must carry a 1-3-word Korean gloss in parentheses on its first appearance per segment.
- [x] A curated baseline glossary lives at `src/investo/briefing/glossary.py::BASELINE_GLOSSARY: dict[str, str]` (term → 1-3-word Korean gloss). At least 30 entries covering the persona-cited terms (EIA, DXY, CPI, FOMC, ESM*, NQU*, 프로그램매매, 숏커버링, 옵션만기, 배당락, etc.).
- [x] `briefing/glossary.py::audit_glossary_compliance(rendered_markdown, *, segment) -> list[GlossaryGap]` deterministically scans the rendered Stage 2 output and reports first-appearance terms (per segment) that match a baseline glossary key but do not have a gloss in parentheses immediately after on first appearance.
- [x] Compliance gaps render a brief-header soft-callout `> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — EIA(에너지정보청), DXY(달러지수)` (capped at 5 terms; "외 N건" suffix beyond cap). The callout is informational, not blocking — the briefing still publishes; the LLM has another chance the next day.
- [x] Anti-regression: a regression test that takes a known briefing body containing `EIA 주간 재고는 ...` (no gloss) and asserts the rendered output adds the `> 용어 가이드` callout with `EIA(에너지정보청)`.
- [x] Anti-regression: a regression test that takes a briefing body containing `EIA(에너지정보청) 주간 재고는 ... 다음 EIA 발표는 ...` (gloss present on first, absent on second) and asserts the callout is not rendered (subsequent appearances do not need re-gloss).
- [x] Anti-regression: per-segment isolation — `EIA(에너지정보청)` glossed in the US-equity segment must not satisfy the first-appearance requirement in the domestic-equity or crypto segment (each segment is its own gloss scope).
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Baseline Glossary Module

- [x] Create `src/investo/briefing/glossary.py` exporting:
  - `BASELINE_GLOSSARY: dict[str, str]` — at least 30 entries, terms in canonical case, glosses 1-3 Korean words each.
  - Categories covered: macro releases (CPI, PPI, PCE, NFP, EIA, DXY, ISM, JOLTS), Fed-related (FOMC, FRB, FFR, QT, QE), futures codes (ESM*, NQU*, CLM*, GCM*), options jargon (옵션만기, 콜옵션, 풋옵션, 변동성지수, VIX), Korean market (프로그램매매, 숏커버링, 배당락, 자사주매입, 공매도, 시간외거래), crypto (스테이킹, 토큰언락, 시가총액, 거래대금).
- [x] Files affected:
  - `src/investo/briefing/glossary.py` (new)
- [x] Unit tests at `tests/unit/briefing/test_glossary.py`:
  - `BASELINE_GLOSSARY` has ≥ 30 entries.
  - Each gloss is 1-3 Korean words (1-12 Hangul characters; whitespace allowed).
  - No duplicate keys; no empty values.

### Step 2 — Compliance Auditor

- [x] Implement `audit_glossary_compliance(markdown: str, *, segment: str) -> list[GlossaryGap]` in `briefing/glossary.py`. Returns one `GlossaryGap` per first-appearance term that has no parenthetical gloss within the next 8 characters.
- [x] Detection rule: scan the markdown linearly per segment, track which terms have already appeared, on first appearance check the immediate next 8 characters for `(...)` containing a Korean gloss substring.
- [x] Files affected:
  - `src/investo/briefing/glossary.py`
- [x] Unit tests:
  - `EIA 주간 재고` (no gloss) → 1 gap reported.
  - `EIA(에너지정보청) 주간 재고는 ... 다음 EIA 발표` → 0 gaps (gloss on first appearance suffices).
  - `EIA(EIA, 에너지정보청)` (gloss with English alias inside parens) → 0 gaps (Korean substring satisfies).
  - empty input → 0 gaps.
  - segment isolation — same `audit_glossary_compliance` call on a domestic-equity body produces independent results from a US-equity body call.

### Step 3 — Stage 2 Prompt Rule

- [x] Extend `briefing/prompts.py::STAGE2_SYSTEM` with the "약자 풀어쓰기 룰" block (3-4 lines, Korean):
  - Rule: every financial acronym / futures code / market jargon term carries a 1-3-word Korean gloss in parentheses on its first appearance per segment.
  - Example: `EIA(에너지정보청) 주간 재고가 ...`
  - Example: `프로그램매매(기관 자동주문) 매수 우위로 ...`
  - Subsequent appearances do not need re-gloss.
- [x] Files affected:
  - `src/investo/briefing/prompts.py`
- [x] Anti-regression test:
  - `STAGE2_SYSTEM` contains the literal `약자 풀어쓰기 룰` heading and at least one example.
  - The rule block lives between the existing "주요 일정" rule (u35) and the "수치 자체검증" rule (u32) so the prompt's section ordering is stable.

### Step 4 — Brief-Header Callout Rendering

- [x] In `briefing/pipeline.py::_enhance_reader_experience` (or the equivalent post-render hook that already houses u32's numeric self-check callout), invoke `audit_glossary_compliance` and prepend `> **용어 가이드**: ...` callout when the gap list is non-empty.
- [x] Cap at 5 terms; render `외 N건` suffix when more.
- [x] Files affected:
  - `src/investo/briefing/pipeline.py`
- [x] Unit tests at `tests/unit/briefing/test_pipeline_glossary.py`:
  - briefing body with `EIA` (no gloss) and `DXY` (no gloss) → callout `> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — EIA(에너지정보청), DXY(달러지수)`.
  - briefing body with all terms glossed → no callout.
  - briefing body with 7 ungossed terms → callout caps at 5 terms + `외 2건` suffix.

### Step 5 — Verification

- [x] Run targeted glossary + pipeline tests + the full quality gate.
- [x] Manual archive re-render was not run locally; targeted pipeline tests verify callout firing and quiet paths.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable — the prompt rule extends the existing Stage 2 system prompt only.
- **Module boundary**: changes confined to `briefing/`; no new cross-module import.
- **R10 (record/replay fixtures, no fabrication)**: not applicable — no new external HTTP source.
- **R13 (secret hygiene)**: not applicable.
- **Disclaimer enforcement**: untouched.
- **No paid APIs**: glossary is a static module; no external lookup.
- **u25 numeric integrity rule**: harmonized — the Stage 2 prompt already forbids arithmetic over input figures (u25); this unit adds a parallel rule for terminology, not numbers.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (expect ~12-15 new tests)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **Auto-fix path** — when the auditor detects a gap, the briefing is **not** rewritten. The LLM gets the rule next run; the auditor's role is to surface the gap to the reader (via the callout) and to the operator (via Step Summary if escalated). Auto-fix would risk re-rendering numeric content and clashing with u25's "no arithmetic over input figures" guarantee.
- **Glossary expansion via LLM** — `BASELINE_GLOSSARY` is curated and committed. Auto-expansion via Claude is out of scope (would require record/replay fixtures and risks unstable content drift).
- **Per-reader glossary preferences** — every reader gets the same gloss style. Persona feedback on "더 자세한 설명을 보고 싶다" would belong to a separate hover-tooltip / sidebar unit, not this MVP-grade callout.
- **Detection beyond `BASELINE_GLOSSARY`** — terms not in the baseline glossary are silently ignored. Adding terms to the baseline is a 1-line change in `glossary.py`; no infrastructure work needed.
- **Cross-segment first-appearance dedup** — each segment is its own gloss scope. A reader who reads only the crypto segment must still get `BTC(비트코인)` even if the US-equity segment glossed it earlier in the same publish.

---

## Open questions

- **Initial glossary size**: 30 entries is the floor. The user may want to seed with a richer initial list (50-80 entries). The unit closeout will record which terms are in the baseline; new terms can be added in a follow-up PR without triggering a new unit.
