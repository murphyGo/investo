# Code Generation Plan: `u76 plain-language-reader-aids`

**Date**: 2026-05-24
**Unit**: u76 plain-language-reader-aids
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-05-24 beginner/non-expert Korean reader review of generated segmented briefings
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u40 financial-acronym-glossary
- u51 tldr-block-and-number-bold-inversion
- u56 compliance-language-and-observational-tags

**Overlap boundary**:
- u68 is not a hard prerequisite. u76 may proceed independently, but must not touch glossary/carryover mechanics owned by u68.

---

## Problem Statement

The briefing can be technically correct but still hard for a non-expert reader to use. Sections may list macro data, tickers, source names, and market jargon without a short explanation of why the fact matters. The user-facing question is often "그래서 의미는?".

Existing glossary work helps with terminology, but a glossary does not explain the market implication of a section. u76 adds a short plain-Korean meaning line per section while leaving glossary/carryover mechanics to u68.

---

## Goal

Add concise section-level meaning lines that answer "그래서 의미는?" for sections §②-§⑤ when enough evidence exists. The lines should:
- Use plain Korean.
- Be short and scannable.
- Explain relevance, not give advice.
- Include company/asset names where ticker-only prose would be confusing.
- Degrade to data-limited wording when evidence is weak.

Fixed meaning-line contract:
- Exact marker: `> **그래서 의미는?** `
- Placement: immediately after the first paragraph/table block of each eligible section §②-§⑤, before the next H3/H2.
- Limit: one meaning line per section, max 80 Korean-visible chars after the marker.
- Idempotency: rerun replaces an existing meaning line for the same section instead of appending another.
- Data-limited fallback: `> **그래서 의미는?** 현재 수집 근거가 부족해 방향보다 확인 필요 항목으로만 봅니다.`
- Evidence threshold: emit a specific meaning line only if the section has at least one source-backed/cited item or verified anchor and segment coverage is not `limited/failed`; otherwise use the data-limited fallback or omit the line for empty sections.

---

## Existing Coverage / Deduplication

This unit is not a glossary or carryover unit.

- u40 owns baseline financial glossary helpers.
- u51 owns TL;DR/layout and scanability.
- u56 owns compliance-safe wording.
- u68 owns reader-aid residuals around glossary/carryover, including any cross-day glossary suppression or inline glossary mechanics.

u76 excludes those mechanics and focuses only on **section-level meaning prose**.

---

## Scope Boundary

In scope:
- Prompt instruction for one optional meaning line per major section.
- Deterministic validation/repair for line length, placement, and compliance.
- Ticker-name clarity where names are available from existing metadata.
- Data-limited fallback when section evidence is weak.

Out of scope:
- New glossary state.
- Carryover event parsing.
- New data sources.
- Personalized advice or portfolio recommendations.
- Rewriting all section prose.

---

## Stage Decision

- **Functional Design — SKIP**. This is a reader-format and prompt contract refinement.
- **NFR Requirements — SKIP**. No new external service, dependency, secret, or runtime cost.

---

## Implementation Steps

### Step 1 — Define meaning-line contract `[ ]`
- [ ] Implement the exact marker `> **그래서 의미는?** `.
- [ ] Limit one meaning line per section §②-§⑤.
- [ ] Set maximum length to 80 Korean-visible chars after the marker.
- [ ] Use the data-limited fallback text above.
- [ ] Preserve idempotency by replacing existing meaning lines in the same section.
- **Acceptance**: contract tests pin marker, placement, and length.

### Step 2 — Update Stage 2 prompt `[ ]`
- [ ] Add instruction that meaning lines explain relevance in plain Korean.
- [ ] Forbid buy/sell/target-price language and quantified outcome predictions.
- [ ] Require ticker-heavy lines to include a company/asset name if available.
- **Acceptance**: prompt tests assert the instruction and compliance guard are present.

### Step 3 — Add reader-format validation/repair `[ ]`
- [ ] Detect missing/overlong meaning lines.
- [ ] Compliance precedence: scan whole markdown after meaning-line insertion; use deterministic repair only for length/duplication; if u56 P0 advice language remains, reject publish rather than silently paraphrasing.
- [ ] Avoid duplicating the TL;DR or glossary callout.
- **Acceptance**: malformed meaning-line fixtures are repaired or rejected deterministically.

### Step 4 — Ticker-name clarity `[ ]`
- [ ] Narrow source of known names to existing static aliases in `WatchlistConfig`/default aliases, configured watchlist terms, and existing anchor display labels. Do not add a new symbol-name registry in this unit.
- [ ] If `reader_format.py` remains string-only, implement ticker-name clarity as prompt guidance plus validation against known static aliases only; signature changes are optional and must be justified by tests.
- [ ] If a name is unavailable, avoid forcing a guessed name.
- [ ] Keep output concise; do not create a long mapping table.
- **Acceptance**: ticker-heavy fixture includes clear names for known tickers and does not hallucinate unknown names.

### Step 5 — Tests and gate `[ ]`
- [ ] Tests for jargon-heavy, ticker-heavy, and data-limited sections.
- [ ] Compliance tests for forbidden recommendation language.
- [ ] Run targeted briefing/publisher tests, ruff, and mypy if source signatures change.

---

## Acceptance Criteria

- **AC-76.1** — Sections §②-§⑤ can carry one short plain-Korean meaning line answering "그래서 의미는?".
- **AC-76.2** — Meaning lines are length-bounded and observational.
- **AC-76.3** — Ticker-heavy prose includes known company/asset names or avoids unexplained ticker-only lines.
- **AC-76.4** — u40/u68 glossary/carryover mechanics are untouched.
- **AC-76.5** — u56 compliance scanner blocks advice-like meaning lines.

---

## Tests / Validation

Expected test areas:
- `tests/unit/briefing/test_prompts.py`
- `tests/unit/publisher/test_reader_format*.py`
- `tests/unit/briefing/test_pipeline*.py`
- `tests/unit/publisher/test_compliance_language.py`

Minimum local gate:
- Targeted briefing/publisher pytest.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if signatures change.

---

## Non-Goals

- New glossary feature.
- New reader persona settings.
- Any investment recommendation.
- Historical archive rewrite.
