# Code Generation Plan: `u68 reader-aids-residual`

**Date**: 2026-05-24
**Unit**: u68 reader-aids-residual
**Stage**: Code Generation
**Status**: ✅ Complete (3/3 steps — code/tests green; FD extension + summary + TECH-DEBT + state/audit closed by planner 2026-05-24)
**Source**: 2026-05-24 confirm-then-extend audit of review Gaps C/D (reader-facing review, Wave 12 P2/P3)
**Estimated Effort**: ~2-3 h
**Dependencies**:
- u40 financial-acronym-glossary (`briefing/glossary.py` — `audit_glossary_compliance` / `render_glossary_callout` / `BASELINE_GLOSSARY`)
- u52 prior-briefing-context-and-carryover (`briefing/carryover_parser.py` archive-walk pattern: `_is_weekday`, `_archive_markdown_path`, `_MAX_CALENDAR_DAYS`)

---

## Confirm-Then-Extend Audit (DoD #1 — done before any code)

The unit's first DoD item is "document which parts of C/D are already done before any code." Code-grounded findings:

| Residual candidate | Status | Code evidence | True residual? |
|---|---|---|---|
| **C — watchpoint actionability** | **Already complete (u64)** | Delivered by u64 watchlist-entity-matching-and-actionability. unit-of-work.md:854 explicitly excludes overlap. | No — out of scope, no work. |
| **D — glossary position (top-of-document callout)** | **Already complete (u40)** | `render_glossary_callout` (glossary.py:89) renders `> **용어 가이드**`; wired at `briefing/pipeline.py:1350-1361` into the header. | No — fully wired. |
| **D — inline first-use glossing variant (optional)** | **Not implemented; optional** | No inline (parenthetical-in-body) glosser exists; only the header callout. unit-of-work.md:854 marks this "(a) **optional** inline first-use glossing." | No — explicitly optional, not warranted for a 1-person tool. Deferred (see TECH-DEBT candidate). |
| **D — carryover §⑥→next-day §② resolved/unresolved echo** | **Already complete (u52)** | `load_carryover` (carryover_parser.py:160) walks ≤3 trading days, splits resolved/unresolved; `render_carryover_block` + `inject_carryover_block` (publisher/carryover.py) emit the deterministic `## Watchlist Carryover` block between §②/§③; prompt rules CARRY-1/CARRY-2 (prompts.py:415-422) drive the §② citation. Orchestrator wires all of it (orchestrator/pipeline.py:2026, 2110). | No — fully implemented and wired. |
| **D — glossary callout repeats the SAME terms every single day** | **REAL DEFECT** | `audit_glossary_compliance` builds its `seen` set fresh per call (glossary.py:71), scoped to one document. No cross-day state exists anywhere (grep confirms only per-document use). So ETF/EPS/VIX/etc. re-fire the "이번 시황에서 처음 등장한 용어" callout **every day** even though the reader saw the gloss yesterday. The callout text literally claims "처음 등장한" (first appearance) — which is false on day 2+. | **Yes — this is the only genuine u68 residual.** |

**Conclusion**: Gaps C/D are ~95% already delivered. The single real residual is the **cross-day repetition of the glossary callout** — a code-confirmed correctness defect in the callout's "처음 등장한 용어" claim, repeatedly cited in the continuous review as "ETF가 매일 처음 등장한 용어로 반복." u68 fixes exactly this and nothing else.

---

## Problem Statement

`render_glossary_callout` labels its terms "이번 시황에서 처음 등장한 용어." Because `audit_glossary_compliance` has no memory beyond the single `body_markdown` it receives, every baseline term that appears today is reported as "first appearance" — regardless of having been glossed in the same segment's briefing yesterday and the day before. For high-frequency terms (ETF, EPS, VIX, CPI), the reader sees an identical callout every day, which (a) makes the "처음 등장한" wording factually wrong and (b) defeats the reader-aid purpose (a once-learned term should not keep re-announcing itself).

---

## Goal

Make the glossary callout **carryover-aware**: a baseline term that was already glossed in the same segment's recent archived briefings is suppressed from today's "처음 등장한 용어" callout, so the callout shows only terms genuinely new to the reader within the recent window. Reuse the u52 archive-walk pattern; no new sources, no LLM, no schema change.

---

## Scope Boundary

In scope:
- A cross-day suppression set: terms already glossed (header callout OR immediate-paren gloss) in the same segment's prior ≤N trading-day archives are removed from today's callout.
- Reuse of the u52 trading-day archive-walk (`_is_weekday`, `_archive_markdown_path`, `_MAX_CALENDAR_DAYS`) — a pure, clock-injected, gracefully-degrading walk.
- Callout wording stays accurate: when the suppressed set empties the callout, the line is omitted (existing empty-gaps behavior).

Out of scope (explicitly):
- Inline (in-body parenthetical) glossing variant — optional per unit-of-work; deferred to TECH-DEBT.
- C / watchpoint actionability — owned by u64.
- Carryover echo mechanics — owned by u52 (verified complete above; no change).
- Any new source, schema field, prompt rule, or LLM call.
- Changing `BASELINE_GLOSSARY` contents.

---

## Stage Decision

Per CLAUDE.md / `/dev-investo`, Functional Design and NFR Requirements are **selective**.

- **Functional Design — REQUIRED (thin)**. The change adds one new deterministic algorithm (cross-day glossed-term suppression via archive walk) and tightens one rule (the callout's "처음 등장한" claim must be true within the recent window). Extend the u40 glossary FD with one logic-model step (`L-glossary.x`) and one business rule (next free `R*` in the u40 rule space). No new domain entity — operates on existing archive markdown + `GlossaryGap`. No sequence-diagram change beyond an added archive-read before callout render.
- **NFR Requirements — SKIP**. No new latency/cost/availability surface; the archive walk reuses u52's bounded `_MAX_CALENDAR_DAYS` cap and the existing graceful-skip contract. No new `tech-stack-decisions` (no new library — markdown + stdlib `re`/`pathlib`, no XML, no SDK, no paid API).

---

## Definition of Done

- [x] Confirm-then-extend audit recorded (done above; mirrored to audit.md at close).
- [x] Callout suppresses terms glossed in the same segment's prior ≤N trading-day archives.
- [x] When all of today's first-use terms were recently glossed, the callout line is omitted (no empty/false callout).
- [x] Archive walk is pure (clock-injected `today`), bounded (reuses `_MAX_CALENDAR_DAYS`), and degrades silently on missing/malformed archives (never raises in the pipeline).
- [x] Idempotent: same `(segment, date, archive state)` → byte-equal callout (FR-006).
- [x] No new source / schema / prompt rule / LLM call / library.
- [x] Quality gate green on changed scope: ruff, mypy --strict, targeted pytest. mkdocs --strict if any rendered output shape changes.
- [x] FD extended (u40 glossary): one `L-glossary.2` step + one business rule `R-glossary.4`. audit.md entry at close.

---

## Steps

### Step 1 — Cross-day glossed-term suppression in `briefing/glossary.py`  `[x]`
- [x] Add a pure helper that, given `archive_root`, `segment`, `today`, and a `lookback` (default mirrors u52's 3 trading days, bounded by a `_MAX_CALENDAR_DAYS`-style cap), returns the set of `BASELINE_GLOSSARY` canonical keys already glossed in that segment's prior archives. "Already glossed" = term appeared with an immediate Korean paren gloss (reuse `_has_immediate_korean_gloss`) OR appeared inside a prior `> **용어 가이드**` callout line.
- [x] Reuse the u52 walk shape (`_is_weekday`, per-day `archive_root/segment/YYYY/MM/YYYY-MM-DD.md`). Keep it pure (caller-injected `today`), bounded, and silently degrading on missing/malformed/OSError archives.
- [x] Extend `audit_glossary_compliance` (or add a thin wrapper) to accept an optional `already_glossed: set[str]` and drop those canonical keys from the returned gaps. Default empty set → existing behavior unchanged (back-compat for current callers/tests).
- **Acceptance**: AC-68.1 — a term glossed in any of the prior ≤N trading-day archives for the same segment is absent from today's `GlossaryGap` list. AC-68.2 — passing an empty/default suppression set reproduces today's existing output byte-for-byte.

### Step 2 — Wire the suppression into the header callout  `[x]`
- [x] In `briefing/pipeline.py` (`_enhance_reader_experience` / header build, around line 1350), compute the suppression set from the archive (reuse the same `archive_root` the orchestrator already passes for u52 carryover) and feed it to `audit_glossary_compliance` before `render_glossary_callout`.
- [x] When suppression empties the gap list, the existing `render_glossary_callout([]) == ""` path omits the line — verify no empty `> **용어 가이드**:` is ever emitted.
- [x] Keep the archive read off the hot path when `archive_root` is unavailable (data-limited / fresh-repo) — degrade to today-only behavior (current output).
- **Acceptance**: AC-68.3 — on a 2nd consecutive day for the same segment, a term glossed day-1 does not reappear in day-2's callout. AC-68.4 — fresh repo (no prior archive) renders the callout exactly as today (no regression). AC-68.5 — same `(segment, date, archive)` re-publish yields byte-equal callout (FR-006).

### Step 3 — Tests + FD + closeout  `[x]` (developer scope: tests; planner scope: FD/summary/state/audit pending)
- [x] Developer adds unit tests for the suppression helper (gloss-in-paren detected, gloss-in-prior-callout detected, missing/malformed archive degrades silently, bound respected) and a pipeline-level test for the 2-day no-repeat behavior + fresh-repo no-regression.
- [x] Planner extends u40 glossary FD: one `L-glossary.2` logic step (cross-day suppression) + one business rule `R-glossary.4` (callout "처음 등장한" claim is scoped to the recent ≤N trading-day window). Marked `(extension 2026-05-24)`. (u40 had no FD dir; new `functional-design/{business-logic-model,business-rules}.md` authored under the owning u40 unit — ratified in audit.md.)
- [x] Planner writes `aidlc-docs/construction/u68-reader-aids-residual/code/summary.md` with AC-68.1..AC-68.5 traceability, audit.md entry, aidlc-state.md row bump, and the inline-glossing-deferred TECH-DEBT entry (DEBT-070, Low).
- **Acceptance**: AC-68.1..AC-68.5 all MET; full changed-scope gate green.

---

## Step Dependency Graph

```
Step 1 (suppression helper)
   └─> Step 2 (wire into header callout)
            └─> Step 3 (tests + FD extension + closeout)
```

Step 1 is self-contained (pure helper + back-compat audit param). Step 2 depends on Step 1's signature. Step 3 depends on both.

---

## NFR AC Coverage Map

| AC | Covered by | NFR tie |
|----|-----------|---------|
| AC-68.1 cross-day term absent from gaps | Step 1 | FR-009 reader-facing format quality |
| AC-68.2 default suppression = byte-equal current output | Step 1 | FR-006 idempotency / no regression |
| AC-68.3 2-day no-repeat callout | Step 2 | FR-009 |
| AC-68.4 fresh-repo no regression | Step 2 | graceful degradation (u52 contract) |
| AC-68.5 re-publish byte-equal | Step 2 | FR-006 idempotency |

No new NFR ACs — reuses u52's bounded-walk + graceful-skip non-functional contract.

---

## Hard-Rule Compliance (restated)

- **No Anthropic SDK** — pure markdown/`re`/`pathlib`; no LLM call added.
- **No paid APIs / no new source** — reads only the local archive already produced.
- **Module boundary** — change lives in `briefing/glossary.py` + `briefing/pipeline.py`; orchestrator continues to own cross-unit wiring. No cross-unit import added.
- **Disclaimer enforcement** — untouched; callout sits in the header above the body, `verify_disclaimer` gate unaffected.
- **Telegram channel separation** — N/A (no notifier change).
- **No raw stdlib XML** — markdown only; no XML.
- **R13 secret hygiene** — no secrets in the archive walk or callout; nothing logged that carries a secret.

---

## TECH-DEBT Candidate (out of scope, register at close)

- **Inline first-use glossing variant** (in-body parenthetical auto-gloss beyond the header callout). Optional per unit-of-work; deferred. Register as a Low-priority TECH-DEBT item (next free id) with reasoning: "Header callout + cross-day suppression (u68) covers the reader-aid need for a 1-person tool; in-body auto-gloss risks distorting LLM prose and is unproven ROI."

---

## How to Approve

Reply with one of:
1. **Request Changes** — name the step / scope to adjust.
2. **Continue to Next Stage** — approve this plan; the developer implements Step 1 → Step 3 in order, and the planner closes the unit (summary, audit, state, TECH-DEBT) on completion.
