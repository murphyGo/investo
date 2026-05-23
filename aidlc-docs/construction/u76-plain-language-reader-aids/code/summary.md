# u76 plain-language-reader-aids — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u76 plain-language-reader-aids
**Status**: Complete (5/5 steps)

## Goal

A briefing can be technically correct yet still hard for a non-expert Korean reader to use — sections list macro data, tickers, source names, and jargon without explaining *why* the fact matters ("그래서 의미는?"). A glossary explains terms but not the market implication of a section. u76 adds a short plain-Korean meaning line per eligible section §②-§⑤ that answers "그래서 의미는?" — a market-implication prose layer, **not** a glossary.

## Scope

In scope: a fixed meaning-line contract (marker / placement / length / idempotency / data-limited fallback); a Stage-2 prompt rule that produces the line content in plain Korean with ticker-name clarity; deterministic validation/repair for placement, length, and dedup; compliance precedence over the inserted line.
Out of scope: new glossary state; carryover event parsing; new data sources; personalized advice / portfolio recommendations; rewriting all section prose; historical archive rewrite.

## Stage Decision

- **Functional Design — SKIP** (per plan). Reader-format and prompt contract refinement over existing rendered markdown; no new shared domain model. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new external service, dependency, secret, or runtime cost. Pure `str → str` deterministic pass plus prompt text. Confirmed at closeout — no NFR file created.

## Hybrid Generation / Validation

u76 is a hybrid: **content = LLM**, **validation/repair = deterministic**.

- **Content (LLM)** — the `STAGE2_SYSTEM` prompt rule asks for one optional plain-Korean meaning line per major section, observational only, with company/asset names where ticker-only prose would confuse. The data-limited fallback is the LLM's contractual responsibility when evidence is weak.
- **Validation/repair (deterministic)** — `normalize_meaning_lines` operates on §②-§⑤ only: one line per section (dedup), and marker-trailing body truncated at 80 Korean-visible chars on a word boundary. **The deterministic pass never invents a meaning line** — if the LLM omits one, none is fabricated (the data-limited fallback stays a prompt-contract obligation, not a deterministic backfill).

## Deduplication / Non-Overlap (preserves u40/u68 — AC-76.4)

u76 adds **section-level meaning prose only**; glossary/carryover mechanics are untouched.

- **u40 glossary preserved**: the meaning marker `> **그래서 의미는?** ` is lexically disjoint from the u40 `> **용어 가이드**` callout.
- **u68 carryover preserved**: marker is also disjoint from u68 cross-day carryover vocabulary. `normalize_meaning_lines` regex-matches **only** the meaning marker, so glossary/carryover lines are never captured. glossary/carryover/prompts invariant re-confirmed by lead (71 passed).
- **u51 TL;DR preserved**: meaning lines are §②-§⑤-body-local and do not duplicate the TL;DR.

## Key Deliverables

- **Changed** `src/investo/publisher/reader_format.py`: u76 meaning-line section — constants `MEANING_MARKER` / `MEANING_FALLBACK` / `MEANING_MAX_CHARS`; helpers `_bound_meaning_body` / `normalize_meaning_lines` / `_repair_section_meaning`; `apply_reader_format` chain step 4.5 (runs **after** `dedupe_glossings`, immediately **before** the footer is rejoined); `__all__` updated.
- **Changed** `src/investo/briefing/prompts.py`: `STAGE2_SYSTEM` gains a meaning-line rule block (plain-Korean relevance, banned 매매권유/목표가/결과예측, observational-only, ticker-name clarity).
- **Tests**: new `tests/unit/publisher/test_reader_format_meaning_u76.py` (14) + `tests/unit/briefing/test_prompts.py` (+1). Net delta +15.

## Meaning-Line Contract (stable, idempotent)

- Marker: exactly `> **그래서 의미는?** `.
- Eligible sections: §②-§⑤ only.
- Placement: after the first paragraph/table block of each eligible section, before the next H3/H2.
- Limit: one line per section; marker-trailing body truncated at 80 Korean-visible chars on a word boundary.
- Idempotency: rerun replaces the existing meaning line for the same section instead of appending.
- Data-limited fallback (LLM-owned): `> **그래서 의미는?** 현재 수집 근거가 부족해 방향보다 확인 필요 항목으로만 봅니다.`

## Header-Preservation Bug Found and Fixed (during implementation)

The initial span reassembly dropped non-§②-§⑤ `##` header text (e.g. `## Watchlist Carryover`) when stitching sections back together. Fixed by re-inserting the `text[cursor:start]` header slice ahead of each section span during reassembly. Glossary/carryover tests pin the invariant.

## Compliance Precedence (AC-76.5)

- The meaning pass does **not** silently paraphrase u56 P0 advice vocabulary.
- After `apply_reader_format`, the orchestrator's existing `scan_compliance` scans the whole markdown; if P0 advice language survives in a meaning line, publish is **rejected** via `ComplianceLanguageError` rather than rewritten. Pinned by `test_advice_meaning_line_rejected_by_compliance` ("매수 검토" rejected).
- The Stage-2 prompt also forbids 매매권유 / 목표가 / 결과예측 and requires observational wording only.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-76.1 | §②-§⑤ can carry one short plain-Korean meaning line answering "그래서 의미는?" | MET | `normalize_meaning_lines` placement + `STAGE2_SYSTEM` rule; `test_reader_format_meaning_u76.py` placement tests |
| AC-76.2 | Meaning lines are length-bounded and observational | MET | `_bound_meaning_body` 80-char word-boundary truncation; observational prompt rule; length tests |
| AC-76.3 | Ticker-heavy prose includes known company/asset names or avoids unexplained ticker-only lines | MET | prompt ticker-name clarity rule (static aliases only, no new registry, no guessed names); ticker-heavy fixture test |
| AC-76.4 | u40/u68 glossary/carryover mechanics untouched | MET | marker lexically disjoint; `normalize_meaning_lines` matches only the meaning marker; header-preservation fix; glossary/carryover 71 passed |
| AC-76.5 | u56 compliance scanner blocks advice-like meaning lines | MET | post-format `scan_compliance` → `ComplianceLanguageError`; `test_advice_meaning_line_rejected_by_compliance` |

## FD Divergences Ratified

None. FD was SKIP (reader-format/prompt contract refinement over existing rendered markdown; no new entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

None (developer determination). No new dependency, no signature change — pure `str → str` plus prompt text.

## Potential Risks

- **Meaning-line content quality is LLM-dependent.** The deterministic pass enforces placement / length / dedup / compliance only; it does not assess whether the LLM's wording is *substantively* useful. If a future requirement demands deterministic evidence-threshold enforcement of the line content, that is a separate unit.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: 144 files clean
- pytest: 2641 passed
- mkdocs build --strict: pass

## Project Rules Upheld

무료 API only (no external call; deterministic `str → str` + prompt text), Anthropic SDK 금지 (untouched — content via Stage-2 Claude Code CLI prompt), 모듈 경계 (`reader_format` publisher-internal; prompt rule briefing-internal; orchestrator-only cross-unit import preserved), 면책조항 (footer untouched — meaning pass runs before footer rejoin) + 채널 분리 gates untouched, R13 no secret (no secret surface touched), `defusedxml` not invoked. No new data source / numeric-verification rule / dependency.
