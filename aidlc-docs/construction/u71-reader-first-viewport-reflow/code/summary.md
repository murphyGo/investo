# u71 reader-first-viewport-reflow — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u71 reader-first-viewport-reflow
**Status**: Complete (5/5 steps)

## Goal

Reflow the generated segment header / first viewport into a stable, idempotent reader-first order so the first screen answers "무엇이 일어났고, 얼마나 신뢰할 수 있고, 무엇을 지켜봐야 하나" before any operations-log diagnostics. u71 is **not** a new summary-quality gate: it only controls ordering, compactness, and diagnostic collapse over already-validated values (plan Goal / Scope Boundary).

## Scope

In scope: header/first-viewport assembly order; length bounding for caution/watchpoint snippets; diagnostic block placement + collapse; static-site-compatible presentation; Telegram alignment only if it reuses the same first-viewport lines.
Out of scope: new LLM summary algorithm; new severity/KPI semantics; chart redesign; historical archive rewrite; concealing source limitations (prioritization, not concealment).

## Stage Decision

- **Functional Design — SKIP** (per plan). Presentation contract over existing summary/status values; no new entity. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new dependency, source, secret, or material runtime cost; output stays static-site (MkDocs Material) compatible with no new CSS asset. Confirmed at closeout — no NFR file created.

## Deduplication / Non-Overlap

u71 runs **after** the existing first-viewport chain and only reorders/truncates its already-validated output:

- **u51** owns TL;DR (`## 한눈에 보기`), H3 conversion, number bolding, dedupe, reader layout foundations — retained, consumed as-is.
- **u61** owns malformed first-viewport summary validation/repair — retained; u71 delegates any malformed summary/caution value back to the existing u61 API/fallback and adds **no parallel validator** (AC-71.5).
- **u54/u62** own status values and public quality truth — the compact chip reads those canonical values (`본문 사용 {n|미집계}` is the u62 reconciliation, not re-derived).

u71 introduces only reflow + bounded truncation; no second summary validator is created.

## Key Deliverables

- **Changed** `src/investo/publisher/reader_format.py`: new `reflow_first_viewport` + helpers `bound_summary_snippet` / `_compact_status_chip` / `_extract_badge_lines` / `_bound_caution_line` / `_insert_after_summary_callouts`; new constants `DIAGNOSTICS_SUMMARY_LABEL` / `SNIPPET_MAX_CHARS`; all public names added to `__all__`.
- **Changed** `src/investo/orchestrator/pipeline.py`: `reflow_first_viewport` wired into the per-segment post-format chain immediately after `emit_first_viewport_disclaimer`.
- **Tests**: new `tests/unit/publisher/test_reader_format_reflow_u71.py` (15 tests) covering ordering, long-diagnostics collapse, malformed/long caution fallback, status chip fields, idempotency, and disclaimer preservation.

## First-Viewport Reflow Order (stable, idempotent)

1. Segment title + watermark (기준 시각) + nav.
2. `## 한눈에 보기` TL;DR block (u51).
3. Summary callouts: `오늘의 결론` / `핵심 동인` / `주의할 점` (caution bounded <=90 chars, word-boundary truncation).
4. Compact one-line status chip:
   `> **데이터 상태**: {label} · 본문 사용 {n|미집계} · 실패 {n} · 0건 {n}`
5. Collapsed diagnostics: `<details><summary>수집/품질 진단</summary>...raw badge body...</details>` (source counts / grade distribution / detail reasons / per-source status — the former raw badge body).
6. `## ①` and the rest of the body.

Contract details:
- Default-expanded (`<details open>`) **only** when segment status is `실패` (failed) or u61 could not produce a usable summary.
- **Idempotency guard** = presence of the `수집/품질 진단` summary; a second reflow pass is a no-op.
- Disclaimer footer is **fixed** — reflow touches only the header region (pinned by `test_disclaimer_preserved`).
- Compact status chip is **not** treated as raw diagnostics (per plan Step 2); only source-outcome tables / API error detail / zero-item per-source rows / KPI explanations collapse.

## Snippet Bounding (Step 3)

- First-viewport caution/watchpoint lines: max 3, max 90 Korean-visible chars each.
- Too-long but valid snippets get `...` only after a word boundary; if no boundary exists before 90 chars the snippet is omitted (no mid-token truncation, no malformed date concatenation).
- Smart-quote boundary glyphs (RUF001 set) are excluded from the truncation boundary set.
- Malformed values are not repaired here — delegated to u61.

## Module Boundary

`reader_format.reflow_first_viewport` is publisher-internal and operates on prepared segment markdown; the orchestrator wires it into the post-format chain. Orchestrator-only cross-unit import rule upheld; no briefing/notifier import added.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-71.1 | Reader summary appears before diagnostics/source errors for non-failed segments | MET | reflow order 1-5 before body; `test_reader_format_reflow_u71.py` ordering tests |
| AC-71.2 | Diagnostics still available but visually/structurally secondary | MET | raw badge body moved into collapsed `<details>수집/품질 진단</details>` |
| AC-71.3 | First-viewport caution/watchpoint snippets bounded, not truncated mid-token | MET | `bound_summary_snippet` word-boundary `...`/omit; long/broken caution fixture tests |
| AC-71.4 | Mobile layout keeps first useful summary visible without chart/diagnostic overlap | MET (structural) | single-column document-order + native Material `<details>`; no CSS added — see Risk |
| AC-71.5 | u61 summary validation + u56 compliance remain single source of truth | MET | malformed values delegated to u61; no parallel validator added |

## FD Divergences Ratified

None. FD was SKIP (no entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

None. The one open risk (mobile manual render spot-check) is anticipated by plan Step 4 and is structurally non-overlapping with no CSS change; tracked as a risk note below rather than a debt item.

## Potential Risks

- **Mobile render verification gap**: the plan Step 4 390x844 / 1280x720 visual render check was **not** executed — no Browser/Playwright in the environment. Mitigation: no CSS was added; the layout is single-column document-order plus Material-native `<details>`, so overlap is structurally impossible. A manual mobile spot-check on the next generated briefing is recommended.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: clean
- pytest: 2544 passed (15 new u71 tests)
- mkdocs build --strict: pass
